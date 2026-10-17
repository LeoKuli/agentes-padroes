#!/usr/bin/env python3
"""Verificação de escopo de um PR contra a ficha (Issue) que ele cita.

Usado pelo workflow reutilizável `.github/workflows/escopo.yml`. Só biblioteca padrão.

Entradas (variáveis de ambiente; o corpo do PR é texto NÃO confiável e nunca passa por shell):
    PR_BODY          corpo do PR
    GH_REPO          dono/repositório do PR (ex.: LeoKuli/marketing)
    PR_NUMBER        número do PR
    GH_TOKEN         token usado pelo `gh`
    PROTEGIDOS       globs protegidos, um por linha (padrão: PROTEGIDOS_PADRAO)
    PROTEGIDOS_EXTRA globs protegidos adicionais, um por linha
    REGEX_TESTES     regex (re.search) dos caminhos que contam como teste
    AUTORES_FICHA    author_association aceitas para o autor da ficha (padrão: OWNER,MEMBER,COLLABORATOR)
    GITHUB_STEP_SUMMARY  (opcional) arquivo onde o resumo em Markdown é gravado

Saída: código 0 se o PR está no escopo; 1 se há violação, ficha inválida ou algo NÃO MEDIDO.
Regra da casa: falha de medição devolve "NÃO MEDIDO", nunca um resultado verde.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

PROTEGIDOS_PADRAO = [".github/**", "CODEOWNERS", "AGENTS.md", "**/constitution.md"]
REGEX_TESTES_PADRAO = r"(^|/)(test|tests|__tests__)/|_test\.|\.test\.|_spec\.|test_.*\.py$"
AUTORES_PADRAO = ("OWNER", "MEMBER", "COLLABORATOR")
LIMITE_API_ARQUIVOS = 3000  # a API de arquivos do PR não devolve mais que isso

_SEM_RESPOSTA = "_no response_"


class ErroFicha(Exception):
    """A ficha citada não existe, não é confiável ou está incompleta."""


class ErroNaoMedido(Exception):
    """Não foi possível medir (API fora, PR grande demais, regex inválida...)."""


# --------------------------------------------------------------------------------------
# Ficha citada no PR
# --------------------------------------------------------------------------------------

_RE_FICHA_NUM = re.compile(r"^Ficha:[ \t]*#(\d+)[ \t]*$", re.MULTILINE)
_RE_FICHA_ID = re.compile(r"^Ficha:[ \t]*[A-Z][A-Z0-9]*-\d+[ \t]*$", re.MULTILINE)
_RE_FECHA = re.compile(
    r"(?<![\w/#-])(?:closes?|closed|fix(?:es|ed)?|resolve[sd]?|fecha[mr]?|fechou|corrige|resolve)"
    r"[ \t]*:?[ \t]+#(\d+)\b",
    re.IGNORECASE,
)


def numero_da_ficha(corpo: str) -> int | None:
    """Número da Issue-ficha citada no corpo do PR, ou None.

    Aceita "Ficha: #123" (preferido) ou "Ficha: MKT-012" acompanhado de "Closes #123"/"Fecha #123".
    """
    corpo = (corpo or "").replace("\r\n", "\n").replace("\r", "\n")
    m = _RE_FICHA_NUM.search(corpo)
    if m:
        return int(m.group(1))
    if _RE_FICHA_ID.search(corpo):
        m = _RE_FECHA.search(corpo)
        if m:
            return int(m.group(1))
    return None


# --------------------------------------------------------------------------------------
# Corpo da Issue Form
# --------------------------------------------------------------------------------------


def secoes_da_issue(corpo: str) -> dict[str, str]:
    """Divide o corpo gerado por uma Issue Form em {título_da_seção_em_minúsculas: texto}.

    O GitHub renderiza cada campo como "### Rótulo" + linha em branco + valor.
    Vale a PRIMEIRA ocorrência de cada título.
    """
    corpo = (corpo or "").replace("\r\n", "\n").replace("\r", "\n")
    saida: dict[str, str] = {}
    atual: str | None = None
    buf: list[str] = []

    def fechar() -> None:
        if atual is not None:
            saida.setdefault(atual, "\n".join(buf).strip())

    for linha in corpo.split("\n"):
        if linha.startswith("### "):
            fechar()
            atual = linha[4:].strip().casefold()
            buf = []
        elif atual is not None:
            buf.append(linha)
    fechar()
    return saida


def _secao(secoes: dict[str, str], prefixo: str) -> str | None:
    prefixo = prefixo.casefold()
    for titulo, texto in secoes.items():
        if titulo.startswith(prefixo):
            return texto
    return None


def lista_de_globs(texto: str | None) -> list[str]:
    """Uma glob por linha; tolera bullets, crases e cercas de código; ignora '_No response_'."""
    if not texto:
        return []
    globs: list[str] = []
    for linha in texto.replace("\r", "").split("\n"):
        item = linha.strip()
        if not item or item.startswith("```") or item.casefold() == _SEM_RESPOSTA:
            continue
        item = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", item).strip()
        item = item.strip("`").strip()
        if item and item not in globs:
            globs.append(item)
    return globs


def tamanho_maximo(texto: str | None) -> int | None:
    if not texto or texto.strip().casefold() == _SEM_RESPOSTA:
        return None
    m = re.search(r"\d+", texto)
    return int(m.group(0)) if m else None


def validar_issue(issue: dict, numero: int, autores_aceitos: tuple[str, ...]) -> None:
    """Levanta ErroFicha se a Issue não puder valer como ficha."""
    if issue.get("pull_request"):
        raise ErroFicha(f"#{numero} é um pull request, não uma ficha (Issue).")
    rotulos = {(r.get("name") if isinstance(r, dict) else str(r)) for r in issue.get("labels", [])}
    if "ficha" not in rotulos:
        raise ErroFicha(f"A Issue #{numero} não tem o rótulo `ficha`; só fichas valem como escopo.")
    assoc = issue.get("author_association", "")
    if assoc not in autores_aceitos:
        raise ErroFicha(
            f"A ficha #{numero} foi aberta por alguém com vínculo `{assoc or '?'}`; "
            f"só valem fichas de: {', '.join(autores_aceitos)}."
        )


@dataclass
class Ficha:
    numero: int
    permitidos: list[str]
    max_diff: int


def ler_ficha(issue: dict, numero: int, autores_aceitos: tuple[str, ...] = AUTORES_PADRAO) -> Ficha:
    validar_issue(issue, numero, autores_aceitos)
    secoes = secoes_da_issue(issue.get("body") or "")
    permitidos = lista_de_globs(_secao(secoes, "Arquivos permitidos"))
    if not permitidos:
        raise ErroFicha(f"A ficha #{numero} não tem a seção 'Arquivos permitidos' preenchida.")
    max_diff = tamanho_maximo(_secao(secoes, "Tamanho máximo do diff"))
    if max_diff is None:
        raise ErroFicha(f"A ficha #{numero} não tem 'Tamanho máximo do diff' com um número.")
    return Ficha(numero=numero, permitidos=permitidos, max_diff=max_diff)


# --------------------------------------------------------------------------------------
# Globs
# --------------------------------------------------------------------------------------


def glob_para_regex(padrao: str, em_qualquer_nivel: bool = False) -> re.Pattern[str]:
    """Traduz uma glob estilo .gitignore para regex (usar com fullmatch).

    `*` e `?` não atravessam "/"; `**` atravessa; `**/` casa zero ou mais diretórios;
    barra final ("dir/") vira "dir/**". Com `em_qualquer_nivel`, um padrão sem "/" casa o
    nome do arquivo em qualquer pasta (usado nos protegidos: "CODEOWNERS" vale em .github/ e na raiz).
    """
    p = padrao.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if p.endswith("/"):
        p += "**"
    prefixo = "(?:.*/)?" if (em_qualquer_nivel and "/" not in p) else ""
    i, n, partes = 0, len(p), []
    while i < n:
        c = p[i]
        if c == "*":
            if p[i : i + 2] == "**":
                if p[i : i + 3] == "**/":
                    partes.append("(?:.*/)?")
                    i += 3
                else:
                    partes.append(".*")
                    i += 2
                continue
            partes.append("[^/]*")
        elif c == "?":
            partes.append("[^/]")
        elif c == "[":
            j = p.find("]", i + 2)
            if j == -1:
                partes.append(re.escape(c))
            else:
                corpo = p[i + 1 : j]
                if corpo.startswith("!"):
                    corpo = "^" + corpo[1:]
                partes.append("[" + corpo.replace("\\", "\\\\") + "]")
                i = j
        else:
            partes.append(re.escape(c))
        i += 1
    return re.compile(prefixo + "".join(partes))


def casa(caminho: str, globs: list[str], em_qualquer_nivel: bool = False) -> str | None:
    """Devolve a primeira glob que casa o caminho, ou None."""
    for g in globs:
        if glob_para_regex(g, em_qualquer_nivel).fullmatch(caminho):
            return g
    return None


# --------------------------------------------------------------------------------------
# Regras
# --------------------------------------------------------------------------------------


@dataclass
class ArquivoPR:
    caminho: str
    anterior: str | None
    status: str
    adicoes: int
    remocoes: int


@dataclass
class Resultado:
    violacoes: list[str] = field(default_factory=list)
    total_linhas: int = 0
    total_arquivos: int = 0


def verificar(
    arquivos: list[ArquivoPR],
    permitidos: list[str],
    max_diff: int,
    protegidos: list[str],
    regex_testes: str,
) -> Resultado:
    """Aplica as regras de escopo. Não faz I/O."""
    try:
        re_teste = re.compile(regex_testes)
    except re.error as e:
        raise ErroNaoMedido(f"regex de testes inválida: {e}") from e

    r = Resultado(total_arquivos=len(arquivos))
    r.total_linhas = sum(a.adicoes + a.remocoes for a in arquivos)

    for a in arquivos:
        # Renomear também toca o caminho antigo: ele precisa estar liberado como o novo.
        caminhos = [a.caminho] + ([a.anterior] if a.anterior and a.anterior != a.caminho else [])
        for c in caminhos:
            regra = casa(c, protegidos, em_qualquer_nivel=True)
            if regra:
                r.violacoes.append(f"`{_limpar(c)}` é um arquivo PROTEGIDO (regra `{_limpar(regra)}`); agente não altera.")
            elif not casa(c, permitidos):
                r.violacoes.append(f"`{_limpar(c)}` está FORA dos arquivos permitidos da ficha.")

    if r.total_linhas > max_diff:
        r.violacoes.append(
            f"O diff tem {r.total_linhas} linhas alteradas (adições + remoções); o máximo da ficha é {max_diff}."
        )

    if not any(a.status != "removed" and re_teste.search(a.caminho) for a in arquivos):
        r.violacoes.append("Nenhum arquivo de TESTE foi adicionado ou alterado (a ficha exige o teste que nasce com a mudança).")

    return r


def _limpar(s: str) -> str:
    """Tira controles e crases de um texto vindo do PR (nome de arquivo é não confiável)."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", s).replace("`", "'")


# --------------------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------------------

_RE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def gh_cli(args: list[str]) -> str:
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    except OSError as e:
        raise ErroNaoMedido(f"não consegui rodar o gh: {e}") from e
    if p.returncode != 0:
        raise ErroNaoMedido(f"gh {' '.join(args[:2])} falhou: {p.stderr.strip()[:300]}")
    return p.stdout


def buscar_issue(gh, repo: str, numero: int) -> dict:
    try:
        return json.loads(gh(["api", f"repos/{repo}/issues/{numero}"]))
    except json.JSONDecodeError as e:
        raise ErroNaoMedido(f"resposta inválida da API ao ler a Issue #{numero}") from e


def buscar_arquivos(gh, repo: str, pr: int) -> list[ArquivoPR]:
    jq = ".[] | {filename, previous_filename, status, additions, deletions}"
    saida = gh(["api", "--paginate", f"repos/{repo}/pulls/{pr}/files?per_page=100", "--jq", jq])
    arquivos: list[ArquivoPR] = []
    for linha in saida.splitlines():
        if not linha.strip():
            continue
        try:
            d = json.loads(linha)
            arquivos.append(
                ArquivoPR(d["filename"], d.get("previous_filename"), d.get("status", ""), int(d["additions"]), int(d["deletions"]))
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ErroNaoMedido(f"resposta inválida da API ao listar os arquivos do PR: {e}") from e
    if not arquivos:
        raise ErroNaoMedido("a API devolveu zero arquivos para o PR; não dá para medir o escopo.")
    if len(arquivos) >= LIMITE_API_ARQUIVOS:
        raise ErroNaoMedido(f"o PR tem {LIMITE_API_ARQUIVOS}+ arquivos, acima do que a API lista; divida o PR.")
    return arquivos


# --------------------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------------------


def avaliar(corpo_pr: str, repo: str, pr: int, gh, config: dict) -> tuple[Ficha, Resultado]:
    numero = numero_da_ficha(corpo_pr)
    if numero is None:
        raise ErroFicha(
            "Não achei a ficha na descrição do PR. Use a linha `Ficha: #<número da Issue>` "
            "(ou `Ficha: <ID>` junto de `Closes #<número>`)."
        )
    ficha = ler_ficha(buscar_issue(gh, repo, numero), numero, config["autores"])
    arquivos = buscar_arquivos(gh, repo, pr)
    return ficha, verificar(arquivos, ficha.permitidos, ficha.max_diff, config["protegidos"], config["regex_testes"])


def _linhas(valor: str | None, padrao: list[str]) -> list[str]:
    if valor is None or not valor.strip():
        return list(padrao)
    return lista_de_globs(valor)


def resumo_md(titulo: str, linhas: list[str], rodape: str = "") -> str:
    partes = [f"## {titulo}", ""]
    partes += linhas
    if rodape:
        partes += ["", rodape]
    return "\n".join(partes) + "\n"


def main(env: dict | None = None, gh=gh_cli) -> int:
    env = dict(os.environ if env is None else env)
    destino = env.get("GITHUB_STEP_SUMMARY")

    def emitir(md: str) -> None:
        print(md)
        if destino:
            with open(destino, "a", encoding="utf-8", newline="\n") as f:
                f.write(md)

    def anotar(msg: str) -> None:
        msg = _limpar(msg).replace("%", "%25")
        print(f"::error::{msg}")

    try:
        repo = env.get("GH_REPO", "")
        if not _RE_REPO.match(repo):
            raise ErroNaoMedido("GH_REPO ausente ou inválido.")
        try:
            pr = int(env.get("PR_NUMBER", ""))
        except ValueError as e:
            raise ErroNaoMedido("PR_NUMBER ausente ou inválido.") from e
        extra = lista_de_globs(env.get("PROTEGIDOS_EXTRA"))
        config = {
            "protegidos": _linhas(env.get("PROTEGIDOS"), PROTEGIDOS_PADRAO) + extra,
            "regex_testes": env.get("REGEX_TESTES") or REGEX_TESTES_PADRAO,
            "autores": tuple(a.strip() for a in (env.get("AUTORES_FICHA") or ",".join(AUTORES_PADRAO)).split(",") if a.strip()),
        }
        ficha, res = avaliar(env.get("PR_BODY", ""), repo, pr, gh, config)
    except ErroFicha as e:
        anotar(str(e))
        emitir(resumo_md("Escopo do PR: ficha inválida", [f"- {e}"], "Corrija a descrição do PR ou a ficha e rode de novo."))
        return 1
    except ErroNaoMedido as e:
        anotar(f"NÃO MEDIDO: {e}")
        emitir(resumo_md("Escopo do PR: NÃO MEDIDO", [f"- {_limpar(str(e))}"], "Falha de medição não é aprovação: rode o job de novo ou chame o dono."))
        return 1

    cabecalho = [
        f"- Ficha: #{ficha.numero}",
        f"- Arquivos no PR: {res.total_arquivos}",
        f"- Linhas alteradas: {res.total_linhas} (máximo da ficha: {ficha.max_diff})",
        f"- Arquivos permitidos: {', '.join('`' + _limpar(g) + '`' for g in ficha.permitidos)}",
    ]
    if res.violacoes:
        for v in res.violacoes:
            anotar(v)
        emitir(
            resumo_md(
                f"Escopo do PR: {len(res.violacoes)} violação(ões)",
                cabecalho + ["", "### Violações", ""] + [f"- {v}" for v in res.violacoes],
                "Ajuste o PR à ficha. Se a ficha estiver errada, pergunte na Issue (rótulo `duvida`); não amplie o escopo por conta própria.",
            )
        )
        return 1
    emitir(resumo_md("Escopo do PR: dentro do escopo", cabecalho))
    return 0


if __name__ == "__main__":
    sys.exit(main())
