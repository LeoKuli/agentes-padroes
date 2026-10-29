#!/usr/bin/env python3
"""Confere AUTOMATICAMENTE a "Mutação que tem de morrer" de uma ficha (Issue com rótulo `ficha`).

Usado pelo workflow reutilizável `.github/workflows/mutacao-ficha.yml`. Só biblioteca padrão.

Para cada mutação da ficha (arquivo, trecho `antes`, trecho `depois`):
  1. exige que `antes` apareça EXATAMENTE 1 vez no arquivo (0 ou >1 = "âncora não casa", nunca sucesso);
  2. aplica a troca e roda o comando de teste, que TEM DE REPROVAR;
  3. restaura o arquivo (sempre, mesmo se o comando explodir).
No fim roda o comando de novo na árvore restaurada, que TEM DE PASSAR (controle positivo).

Formatos aceitos na seção "### Mutação que tem de morrer" (cada mutação começa numa linha "Mutação ..."):

    - Mutação, em `pasta/arquivo.py`: trocar
    ```python
    antes
    ```
    por
    ```python
    depois
    ```

    - Mutação A: em `pasta/arquivo.ex`, `funcao/0`, trocar `antes` por `depois`.
    - Mutação B: trocar `antes` por `depois`.          (sem "em `arquivo`": vale o arquivo da anterior)

Entradas (variáveis de ambiente; o texto da ficha e do PR é NÃO confiável e nunca passa por shell):
    PR_BODY          corpo do PR (de onde sai `Ficha: #N`)
    GH_REPO          dono/repositório do PR
    GH_TOKEN         token usado pelo `gh` (NÃO é repassado ao comando de teste)
    COMANDO_TESTE    comando que roda os testes (vem do workflow chamador, é confiável)
    AUTORES_FICHA    author_association aceitas para o autor da ficha (padrão: as do escopo.py)
    TIMEOUT_SEGUNDOS tempo máximo de cada rodada do comando (padrão 900)
    GITHUB_STEP_SUMMARY  (opcional) arquivo onde o resumo em Markdown é gravado
Também por linha de comando: --repo, --ficha N, --comando, --raiz, --timeout.

No Windows o comando roda pelo cmd.exe: "./gradlew" não existe lá e o comando falha em TODA rodada, então toda
mutação aparece como "morreu" e só o controle positivo acusa. Use o caminho absoluto, por exemplo
--comando "C:/caminho/da/raiz/gradlew.bat -p C:/caminho/da/raiz :core:test" (lição de 29/10/2026, MYR-057).

Saída: código 0 só se TODA mutação morreu e o controle positivo passou; 1 em qualquer outro caso.
Ficha sem seção de mutação, formato não entendido, âncora que não casa, tempo esgotado: "NÃO MEDIDO",
nunca verde. Limite assumido: o script prova que o teste REPROVA com a troca; que ele reprova NA
asserção que a ficha indica é leitura do revisor (a cauda da saída vai no resumo). O único caso
detectado sozinho é o mutante que nem compila/importa, que "morre" sem asserção nenhuma.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import escopo  # noqa: E402  (uma casa por regra: leitor de seções e da Issue vêm de lá)
from escopo import ErroFicha, ErroNaoMedido  # noqa: E402

TIMEOUT_PADRAO = 900
LINHAS_DE_CAUDA = 30
# Variáveis que o comando de teste (código do PR) nunca recebe.
VARIAVEIS_RETIDAS = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "PADROES_TOKEN",
    "LLM_API_KEY",
    "ACTIONS_RUNTIME_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_URL",
)
# Se a saída do mutante tem isto, ele "morreu" sem asserção: a mutação quebrou o código, não a regra.
SINAIS_DE_QUEBRA = (
    "SyntaxError",
    "IndentationError",
    "TabError",
    "ModuleNotFoundError",
    "ImportError",
    "(CompileError)",
    "(TokenMissingError)",
)


# --------------------------------------------------------------------------------------
# Leitura da seção
# --------------------------------------------------------------------------------------


@dataclass
class Mutacao:
    rotulo: str
    arquivo: str
    antes: str
    depois: str

    def nome(self) -> str:
        return f"Mutação {self.rotulo}".strip()


_RE_MARCA = re.compile(
    r"(?m)^[ \t]*(?:[-*+][ \t]+)?(?:\*\*)?Mutação(?:[ \t]+(?P<rot>[A-Z]|\d+)(?=[\s:.,)*]))?"
)
_RE_ARQUIVO = re.compile(r"\bem[ \t]+`(?P<arq>[^`\n]+)`")
_RE_BLOCO = re.compile(
    r"\btrocar\b[ \t]*:?[ \t]*\n+[ \t]*(?P<c1>`{3,}|~{3,})[^\n]*\n(?P<antes>.*?)\n?[ \t]*(?P=c1)[ \t]*\n+"
    r"[ \t]*(?:\*\*)?por(?:\*\*)?[ \t]*:?[ \t]*\n+[ \t]*(?P<c2>`{3,}|~{3,})[^\n]*\n(?P<depois>.*?)\n?[ \t]*(?P=c2)",
    re.DOTALL,
)
_RE_INLINE = re.compile(r"\btrocar\b[ \t]+`(?P<antes>[^`\n]+)`[ \t]+por[ \t]+`(?P<depois>[^`\n]+)`")


def secao_da_mutacao(corpo_da_issue: str) -> str | None:
    """Texto da seção "Mutação que tem de morrer" da ficha, ou None se não existe/está vazia."""
    texto = escopo._secao(escopo.secoes_da_issue(corpo_da_issue), "Mutação")
    if texto is None or not texto.strip() or texto.strip().casefold() == escopo._SEM_RESPOSTA:
        return None
    return texto


def extrair_mutacoes(secao: str) -> list[Mutacao]:
    """Lê as mutações de uma seção. Levanta ErroNaoMedido se não achar nenhuma ou não entender uma."""
    secao = (secao or "").replace("\r\n", "\n").replace("\r", "\n")
    marcas = list(_RE_MARCA.finditer(secao))
    if not marcas:
        raise ErroNaoMedido('a seção de mutação não tem nenhuma linha começando com "Mutação ..., trocar ... por ...".')
    mutacoes: list[Mutacao] = []
    arquivo_anterior: str | None = None
    for i, marca in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(secao)
        trecho = secao[marca.start() : fim]
        rotulo = marca.group("rot") or (str(i + 1) if len(marcas) > 1 else "")
        nome = f"Mutação {rotulo}".strip()
        achados = [m for m in (_RE_BLOCO.search(trecho), _RE_INLINE.search(trecho)) if m]
        if not achados:
            raise ErroNaoMedido(f'não entendi a {nome}: falta o par "trocar ... por ..." (bloco de código ou `inline`).')
        achado = min(achados, key=lambda m: m.start())
        m_arq = _RE_ARQUIVO.search(trecho[: achado.start()])
        arquivo = m_arq.group("arq").strip() if m_arq else arquivo_anterior
        if not arquivo:
            raise ErroNaoMedido(f'a {nome} não diz o arquivo ("em `caminho`") e não há mutação anterior para herdar.')
        antes, depois = achado.group("antes"), achado.group("depois")
        if not antes.strip():
            raise ErroNaoMedido(f"a {nome} tem o trecho a trocar vazio.")
        arquivo_anterior = arquivo
        mutacoes.append(Mutacao(rotulo, arquivo, antes, depois))
    return mutacoes


# --------------------------------------------------------------------------------------
# Aplicar / restaurar
# --------------------------------------------------------------------------------------


def contar(texto: str, trecho: str) -> int:
    """Ocorrências de `trecho` em `texto`, contando sobreposições ("aa" em "aaa" são 2, não 1)."""
    if not trecho:
        return 0
    n, pos = 0, texto.find(trecho)
    while pos != -1:
        n += 1
        pos = texto.find(trecho, pos + 1)
    return n


def caminho_seguro(raiz: Path, relativo: str) -> Path:
    """Resolve `relativo` dentro de `raiz`; recusa absoluto, `..` e link que escapa."""
    if not relativo or Path(relativo).is_absolute() or re.match(r"^[A-Za-z]:", relativo):
        raise ErroNaoMedido(f"caminho inválido na ficha: `{escopo._limpar(relativo)}` (precisa ser relativo à raiz do repositório).")
    base = raiz.resolve()
    alvo = (base / relativo).resolve()
    if alvo != base and base not in alvo.parents:
        raise ErroNaoMedido(f"o caminho `{escopo._limpar(relativo)}` da ficha sai do repositório.")
    if not alvo.is_file():
        raise ErroNaoMedido(f"o arquivo `{escopo._limpar(relativo)}` da ficha não existe neste commit.")
    return alvo


class AncoraNaoCasa(Exception):
    """O trecho `antes` não aparece exatamente uma vez no arquivo."""


def montar_mutante(original: str, antes: str, depois: str) -> str:
    """Devolve o arquivo com a troca. Levanta AncoraNaoCasa se `antes` não casa exatamente 1 vez."""
    if "\r\n" in original:  # a ficha vem com LF; o arquivo pode estar em CRLF
        antes = antes.replace("\r\n", "\n").replace("\n", "\r\n")
        depois = depois.replace("\r\n", "\n").replace("\n", "\r\n")
    n = contar(original, antes)
    if n == 0 and antes.strip() != antes:  # indentação ou borda diferente da ficha: tenta o trecho aparado
        antes, depois = antes.strip(), depois.strip()
        n = contar(original, antes)
    if n == 0:
        raise AncoraNaoCasa("âncora não casa: o trecho a trocar NÃO aparece no arquivo")
    if n > 1:
        raise AncoraNaoCasa(f"âncora não casa: o trecho a trocar aparece {n} vezes no arquivo (tem de ser exatamente 1)")
    if antes == depois:
        raise AncoraNaoCasa("a troca é igual ao original: não muda nada")
    return original.replace(antes, depois, 1)


# --------------------------------------------------------------------------------------
# Rodar o comando
# --------------------------------------------------------------------------------------


def _matar(p: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            import signal

            os.killpg(p.pid, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)
    except (OSError, ProcessLookupError):
        pass
    try:
        p.kill()
    except OSError:
        pass


def rodar_comando(comando: str, cwd: Path, timeout: int) -> tuple[int, str]:
    """Roda `comando` no shell, em `cwd`, SEM os tokens do ambiente. Devolve (código, saída)."""
    env = {k: v for k, v in os.environ.items() if k not in VARIAVEIS_RETIDAS}
    extra = {"start_new_session": True} if os.name == "posix" else {}
    try:
        p = subprocess.Popen(
            comando,
            shell=True,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            **extra,
        )
    except OSError as e:
        raise ErroNaoMedido(f"não consegui rodar o comando de teste: {e}") from e
    try:
        saida, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as e:
        _matar(p)
        try:
            p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise ErroNaoMedido(f"o comando de teste passou de {timeout}s e foi morto.") from e
    return p.returncode, saida or ""


def cauda(saida: str, linhas: int = LINHAS_DE_CAUDA) -> str:
    return "\n".join((saida or "").replace("\r\n", "\n").splitlines()[-linhas:])


# --------------------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------------------


@dataclass
class Linha:
    n: int
    mutacao: Mutacao
    ok: bool
    veredito: str
    detalhe: str = ""
    saida: str = ""


@dataclass
class Controle:
    ok: bool
    veredito: str
    saida: str = ""


@dataclass
class Relatorio:
    linhas: list[Linha] = field(default_factory=list)
    controle: Controle | None = None

    @property
    def ok(self) -> bool:
        return bool(self.linhas) and all(l.ok for l in self.linhas) and bool(self.controle and self.controle.ok)


def testar_mutacao(n: int, m: Mutacao, raiz: Path, comando: str, rodar, timeout: int) -> Linha:
    """Aplica UMA mutação, roda o comando, restaura. O arquivo volta ao original em qualquer caminho."""
    try:
        alvo = caminho_seguro(raiz, m.arquivo)
        bruto = alvo.read_bytes()
        original = bruto.decode("utf-8")
    except UnicodeDecodeError:
        return Linha(n, m, False, "NÃO MEDIDO", "o arquivo não é UTF-8")
    except ErroNaoMedido as e:
        return Linha(n, m, False, "NÃO MEDIDO", str(e))
    try:
        mutante = montar_mutante(original, m.antes, m.depois)
    except AncoraNaoCasa as e:
        return Linha(n, m, False, "ÂNCORA NÃO CASA", str(e))
    try:
        alvo.write_bytes(mutante.encode("utf-8"))
        try:
            codigo, saida = rodar(comando, raiz, timeout)
        except ErroNaoMedido as e:
            return Linha(n, m, False, "NÃO MEDIDO", str(e))
    finally:
        alvo.write_bytes(bruto)  # sempre; se isto falhar o erro sobe e o job reprova
    if codigo == 0:
        return Linha(n, m, False, "SOBREVIVEU", "o comando de teste PASSOU com o mutante aplicado", cauda(saida))
    quebra = next((s for s in SINAIS_DE_QUEBRA if s in saida), None)
    if quebra:
        return Linha(
            n, m, False, "SUSPEITO",
            f"o mutante reprovou por `{quebra}` (o código quebrou), não por uma asserção; a trava que a ficha aponta não foi exercida",
            cauda(saida),
        )
    return Linha(n, m, True, "morreu", f"o comando de teste reprovou (código {codigo})", cauda(saida))


def executar(raiz: Path, mutacoes: list[Mutacao], comando: str, rodar=rodar_comando, timeout: int = TIMEOUT_PADRAO) -> Relatorio:
    rel = Relatorio()
    for i, m in enumerate(mutacoes, 1):
        rel.linhas.append(testar_mutacao(i, m, raiz, comando, rodar, timeout))
    try:
        codigo, saida = rodar(comando, raiz, timeout)
    except ErroNaoMedido as e:
        rel.controle = Controle(False, "NÃO MEDIDO", str(e))
        return rel
    if codigo == 0:
        rel.controle = Controle(True, "passou")
    else:
        rel.controle = Controle(False, "REPROVOU", cauda(saida))
    return rel


# --------------------------------------------------------------------------------------
# Saída
# --------------------------------------------------------------------------------------


def _nome(l: Linha) -> str:
    return l.mutacao.nome() or f"Mutação {l.n}"


def _celula(s: str, limite: int = 70) -> str:
    s = escopo._limpar(s).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= limite else s[: limite - 1] + "…"


def _neutro(s: str) -> str:
    """Texto vindo do comando de teste (código do PR): sem comandos de workflow nem cercas de código."""
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", s)
    return s.replace("::", ": :").replace("```", "'''")


def resumo(rel: Relatorio) -> str:
    sinal = "tudo morreu e o controle passou" if rel.ok else "REPROVADA"
    out = [f"## Mutação da ficha: {sinal}", ""]
    out += ["| # | Mutação | Arquivo | Troca | Resultado |", "|---|---|---|---|---|"]
    for l in rel.linhas:
        troca = f"`{_celula(l.mutacao.antes.strip(), 28).replace('`', chr(39))}` por `{_celula(l.mutacao.depois.strip(), 28).replace('`', chr(39))}`"
        out.append(f"| {l.n} | {_celula(l.mutacao.rotulo or '-')} | `{_celula(l.mutacao.arquivo, 40).replace('`', chr(39))}` | {troca} | **{l.veredito}** |")
    if rel.controle:
        out.append(f"| controle | árvore restaurada | | | **{rel.controle.veredito}** |")
    out.append("")
    for l in rel.linhas:
        if l.ok and not l.saida:
            continue
        out.append(f"- {_nome(l)}: **{l.veredito}**. {_neutro(l.detalhe)}")
    if rel.controle and not rel.controle.ok:
        out.append(f"- Controle positivo: **{rel.controle.veredito}**. A árvore sem mutação precisa passar o comando de teste.")
    out.append("")
    out.append("<details><summary>Cauda da saída de cada mutante (confira se reprovou na asserção que a ficha indica)</summary>")
    out.append("")
    for l in rel.linhas:
        if l.saida:
            out += [f"**{_nome(l)} — {l.veredito}**", "", "````", _neutro(l.saida), "````", ""]
    if rel.controle and rel.controle.saida:
        out += ["**Controle positivo**", "", "````", _neutro(rel.controle.saida), "````", ""]
    out.append("</details>")
    return "\n".join(out) + "\n"


def resumo_nao_medido(motivo: str, titulo: str = "NÃO MEDIDO") -> str:
    return f"## Mutação da ficha: {titulo}\n\n- {_neutro(escopo._limpar(motivo))}\n\nFalha de medição não é aprovação: corrija a ficha ou rode o job de novo.\n"


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None, env: dict | None = None, gh=escopo.gh_cli, rodar=rodar_comando) -> int:
    env = dict(os.environ if env is None else env)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo")
    ap.add_argument("--ficha", type=int)
    ap.add_argument("--comando")
    ap.add_argument("--raiz")
    ap.add_argument("--timeout", type=int)
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    destino = env.get("GITHUB_STEP_SUMMARY")

    def emitir(md: str) -> None:
        print(md)  # os trechos vindos do PR já passaram por _neutro ao montar o resumo
        if destino:
            with open(destino, "a", encoding="utf-8", newline="\n") as f:
                f.write(md)

    def anotar(msg: str) -> None:
        print(f"::error::{escopo._limpar(msg).replace('%', '%25')}")

    try:
        repo = args.repo or env.get("GH_REPO", "")
        if not escopo._RE_REPO.match(repo):
            raise ErroNaoMedido("GH_REPO ausente ou inválido.")
        comando = args.comando or env.get("COMANDO_TESTE", "")
        if not comando.strip():
            raise ErroNaoMedido("COMANDO_TESTE ausente: o workflow chamador precisa dizer como rodar os testes.")
        try:
            timeout = args.timeout or int(env.get("TIMEOUT_SEGUNDOS") or TIMEOUT_PADRAO)
        except ValueError as e:
            raise ErroNaoMedido("TIMEOUT_SEGUNDOS inválido.") from e
        numero = args.ficha or escopo.numero_da_ficha(env.get("PR_BODY", ""))
        if numero is None:
            raise ErroFicha("Não achei `Ficha: #<número da Issue>` na descrição do PR.")
        autores = tuple(a.strip() for a in (env.get("AUTORES_FICHA") or ",".join(escopo.AUTORES_PADRAO)).split(",") if a.strip())
        issue = escopo.buscar_issue(gh, repo, numero)
        escopo.validar_issue(issue, numero, autores)
        secao = secao_da_mutacao(issue.get("body") or "")
        if secao is None:
            raise ErroNaoMedido(f'a ficha #{numero} não tem a seção "Mutação que tem de morrer" preenchida.')
        mutacoes = extrair_mutacoes(secao)
        raiz = Path(args.raiz or env.get("RAIZ") or ".")
        rel = executar(raiz, mutacoes, comando, rodar=rodar, timeout=timeout)
    except ErroFicha as e:
        anotar(str(e))
        emitir(resumo_nao_medido(str(e), "ficha inválida"))
        return 1
    except ErroNaoMedido as e:
        anotar(f"NÃO MEDIDO: {e}")
        emitir(resumo_nao_medido(str(e)))
        return 1
    except Exception as e:  # noqa: BLE001 — qualquer surpresa é NÃO MEDIDO, nunca verde
        anotar(f"NÃO MEDIDO: erro inesperado ({type(e).__name__}): {e}")
        emitir(resumo_nao_medido(f"erro inesperado ({type(e).__name__}): {e}"))
        return 1

    emitir(resumo(rel))
    if not rel.ok:
        for l in rel.linhas:
            if not l.ok:
                anotar(f"{_nome(l)}: {l.veredito}. {l.detalhe}")
        if rel.controle and not rel.controle.ok:
            anotar(f"Controle positivo: {rel.controle.veredito}.")
        return 1
    return 0


if __name__ == "__main__":
    for _fluxo in (sys.stdout, sys.stderr):  # console do Windows (cp1252) não pode derrubar o relatório
        if hasattr(_fluxo, "reconfigure"):
            _fluxo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
