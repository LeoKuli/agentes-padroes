#!/usr/bin/env python3
"""Junta sozinho o PR do agente cuja ficha é SÓ DE TESTE e cujos checks estão todos verdes.

Usado pelo workflow reutilizável `.github/workflows/juntar-so-teste.yml`. Biblioteca padrão + `gh`.
A ficha, o regex de testes e as globs vêm de `escopo.py` (uma casa por regra: aqui só se importa).

Regra (TODAS obrigatórias; qualquer dúvida = NÃO junta):
 1. PR aberto por `kuligovski-portao[bot]` ou `github-actions[bot]`, título começando por `[agente:`,
    corpo com a linha `Ficha: #N`, aberto, não rascunho, vindo de branch do próprio repositório;
 2. a Issue N tem o rótulo `ficha`, foi aberta pelo OWNER e os "Arquivos permitidos" dela casam SÓ com
    caminhos de teste;
 3. todo arquivo do PR casa com o regex de testes E com os permitidos da ficha (nada protegido, nada
    removido, diff dentro do máximo da ficha);
 4. TODOS os checks do commit da cabeça concluídos com sucesso: nenhum pendente, nenhum falho; `skipped` só
    vale para `escopo`/`ficha` se existir um check de mesmo nome com sucesso; check com `mutacao`/`mutação`
    no nome tem de estar verde; e todo check OBRIGATÓRIO da proteção do branch-base tem de existir e passar;
 5. o PR é mergeable.

Falha de medição (API fora, proteção ilegível, mergeable indefinido) devolve NÃO MEDIDO e não junta:
nunca "verde por falta de dado".

Uso:
    GH_TOKEN=... python3 scripts/juntar_so_teste.py --repo LeoKuli/<repo> [--pr N] [--dry-run]
                                                     [--acao juntar|etiquetar] [--base main]

Sem `--pr` examina todos os PRs abertos que passam na regra 1. Com `--dry-run` só decide e imprime.
`--acao etiquetar` não junta: comenta "pronto para juntar" e põe o rótulo `estado:pode-juntar` (para quando a
proteção do branch não deixa o app passar por cima da revisão obrigatória). No modo `juntar`, se o GitHub recusar
a junção, o script cai sozinho para esse mesmo comentário + rótulo.

Código de saída: 0 se tudo foi medido (junte ou não); 1 se algo ficou NÃO MEDIDO ou a junção falhou.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import escopo  # noqa: E402 - irmão no mesmo diretório

AUTORES_PR = ("kuligovski-portao[bot]", "github-actions[bot]")
PREFIXO_TITULO = "[agente:"
AUTORES_FICHA = ("OWNER",)
ROTULO_PRONTO = "estado:pode-juntar"
# Estados de mergeabilidade aceitos. "blocked" entra porque é o estado da revisão obrigatória, que o app
# pode contornar; quem decide de verdade é a API de junção, e ela recusa o que a proteção não deixa.
ESTADOS_MERGEAVEIS = ("clean", "blocked", "has_hooks")
MOTIVO_ATRASADO = "a branch do PR está atrás da base (a proteção exige branch atualizada)"
MSG_JUNTADO = "Juntado automaticamente: ficha só de teste, todos os checks verdes"
MSG_PRONTO = "Pronto para juntar (só teste, tudo verde)."
TENTATIVAS_MERGEABLE = 4

_RE_CUSTO = re.compile(r"^Custo estimado pelo SDK:[ \t]*([^\n]{1,40})$", re.MULTILINE)


@dataclass
class Decisao:
    numero: int
    juntar: bool = False
    motivos: list[str] = field(default_factory=list)
    nao_medido: bool = False
    sha: str = ""
    ficha: int | None = None
    custo: str = ""
    ja_pronto: bool = False

    @property
    def so_atrasado(self) -> bool:
        """Tudo passou, menos a branch estar atrás da base: o conserto é atualizá-la (o CI roda de novo)."""
        return self.motivos == [MOTIVO_ATRASADO] and not self.nao_medido

    def resumo(self) -> str:
        if self.juntar:
            return f"PR #{self.numero}: JUNTAR (ficha #{self.ficha}, cabeça {self.sha[:7]})"
        marca = " [NÃO MEDIDO]" if self.nao_medido else ""
        return f"PR #{self.numero}: NÃO JUNTAR{marca}"


# --------------------------------------------------------------------------------------
# Regras puras (sem I/O)
# --------------------------------------------------------------------------------------


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return sem_acento.casefold()


def eh_check_de_mutacao(nome: str) -> bool:
    """`mutacao` ou `mutação` em qualquer parte do nome (a acentuação some na normalização)."""
    return "mutacao" in _normalizar(nome)


def eh_check_de_escopo_ou_ficha(nome: str) -> bool:
    return bool(set(re.findall(r"[a-z0-9]+", _normalizar(nome))) & {"escopo", "ficha"})


def glob_so_de_teste(glob: str, re_teste: re.Pattern[str]) -> bool:
    """A glob da ficha só pode alcançar caminhos de teste.

    Medida conservadora sobre o TEXTO da glob: ela mesma casa o regex de testes (o trecho que a torna "de teste"
    é literal), sem subir diretório ("..") e sem ser absoluta. O que protege de verdade é a regra 3, que confere os
    arquivos reais do PR; esta só impede juntar sozinho uma ficha que PERMITE mexer fora de teste.
    """
    g = glob.strip().replace("\\", "/")
    if not g or g.startswith("/") or ".." in g.split("/"):
        return False
    return bool(re_teste.search(g))


def avaliar_checks(
    latest: list[dict],
    todos: list[dict],
    status: dict | None,
    obrigatorios: list[str],
) -> list[str]:
    """Motivos pelos quais os checks da cabeça NÃO bastam (lista vazia = todos verdes).

    `latest`: check-runs mais recentes por nome; `todos`: todas as execuções (só para o caso do `skipped`);
    `status`: estado combinado dos commit statuses (ou None); `obrigatorios`: contextos exigidos pela proteção.
    """
    motivos: list[str] = []
    statuses = list((status or {}).get("statuses") or [])
    if not latest and not statuses:
        return ["nenhum check na cabeça do PR (NÃO MEDIDO: sem checks não há o que provar)"]

    com_sucesso_em_qualquer_execucao = {c.get("name") for c in todos if c.get("conclusion") == "success"}
    aprovados: set[str] = set()
    for c in latest:
        nome = c.get("name") or "(sem nome)"
        if c.get("status") != "completed":
            motivos.append(f"check `{nome}` ainda não terminou (estado `{c.get('status')}`)")
            continue
        conclusao = c.get("conclusion")
        if conclusao == "success":
            aprovados.add(nome)
        elif conclusao == "skipped" and eh_check_de_escopo_ou_ficha(nome):
            if nome in com_sucesso_em_qualquer_execucao:
                aprovados.add(nome)
            else:
                motivos.append(f"check `{nome}` foi pulado (`skipped`) e não há outro de mesmo nome com sucesso")
        else:
            motivos.append(f"check `{nome}` terminou com `{conclusao}`")

    # Alguns checks não são check-run (status clássico). Pendente, falho ou erro reprova.
    if statuses:
        for s in statuses:
            contexto = s.get("context") or "(sem contexto)"
            if s.get("state") == "success":
                aprovados.add(contexto)
            else:
                motivos.append(f"status `{contexto}` está `{s.get('state')}`")

    for c in latest:
        nome = c.get("name") or ""
        if eh_check_de_mutacao(nome) and nome not in aprovados:
            motivos.append(f"o check de mutação `{nome}` não está verde")

    for contexto in obrigatorios:
        if contexto not in aprovados:
            motivos.append(f"o check obrigatório `{contexto}` não existe ou não passou")
    return motivos


def checar_pr(pr: dict, repo: str, base: str) -> tuple[list[str], int | None]:
    """Regra 1 (e a parte do 5 que o JSON do PR já diz). Devolve (motivos, número da ficha)."""
    motivos: list[str] = []
    usuario = pr.get("user") or {}
    login = usuario.get("login", "")
    if login not in AUTORES_PR or usuario.get("type") != "Bot":
        motivos.append(f"o autor `{login or '?'}` não é um dos bots do agente ({', '.join(AUTORES_PR)})")
    if not (pr.get("title") or "").startswith(PREFIXO_TITULO):
        motivos.append(f"o título não começa por `{PREFIXO_TITULO}`")
    if pr.get("state") != "open" or pr.get("merged"):
        motivos.append("o PR não está aberto")
    if pr.get("draft"):
        motivos.append("o PR é rascunho")
    cabeca = (pr.get("head") or {}).get("repo") or {}
    if cabeca.get("full_name") != repo:
        motivos.append("a branch do PR não é do próprio repositório")
    if (pr.get("base") or {}).get("ref") != base:
        motivos.append(f"o PR não mira `{base}`")
    corpo = (pr.get("body") or "").replace("\r\n", "\n").replace("\r", "\n")
    m = escopo._RE_FICHA_NUM.search(corpo)  # noqa: SLF001 - a mesma regra de "Ficha: #N" do escopo.yml
    if not m:
        motivos.append("o corpo não tem a linha `Ficha: #N`")
        return motivos, None
    return motivos, int(m.group(1))


def checar_mergeable(pr: dict) -> list[str]:
    if pr.get("mergeable") is None:
        return ["NÃO MEDIDO: o GitHub ainda não calculou se o PR é mergeable (valor nulo)"]
    if pr.get("mergeable") is not True:
        return ["o PR não é mergeable (conflito com a base)"]
    if pr.get("mergeable_state") == "behind":
        return [MOTIVO_ATRASADO]
    if pr.get("mergeable_state") not in ESTADOS_MERGEAVEIS:
        return [f"estado de junção `{pr.get('mergeable_state')}` (esperado: {', '.join(ESTADOS_MERGEAVEIS)})"]
    return []


def checar_arquivos(arquivos: list[escopo.ArquivoPR], ficha: escopo.Ficha, re_teste: re.Pattern[str]) -> list[str]:
    """Regras 2 (parte do tamanho) e 3."""
    motivos: list[str] = []
    for a in arquivos:
        caminhos = [a.caminho] + ([a.anterior] if a.anterior and a.anterior != a.caminho else [])
        for c in caminhos:
            if escopo.casa(c, escopo.PROTEGIDOS_PADRAO, em_qualquer_nivel=True):
                motivos.append(f"`{escopo._limpar(c)}` é arquivo PROTEGIDO")  # noqa: SLF001
            elif not re_teste.search(c):
                motivos.append(f"`{escopo._limpar(c)}` não é arquivo de teste")  # noqa: SLF001
            elif not escopo.casa(c, ficha.permitidos):
                motivos.append(f"`{escopo._limpar(c)}` está fora dos permitidos da ficha")  # noqa: SLF001
        if a.status == "removed":
            motivos.append(f"`{escopo._limpar(a.caminho)}` foi removido (apagar teste não se junta sozinho)")  # noqa: SLF001
    if not any(a.status != "removed" for a in arquivos):
        motivos.append("o PR não adiciona nem altera nenhum arquivo")
    total = sum(a.adicoes + a.remocoes for a in arquivos)
    if total > ficha.max_diff:
        motivos.append(f"o diff tem {total} linhas; o máximo da ficha é {ficha.max_diff}")
    return motivos


def checar_ficha(issue: dict, numero: int, re_teste: re.Pattern[str]) -> tuple[list[str], escopo.Ficha | None]:
    """Regra 2: ficha confiável (rótulo `ficha`, autor OWNER) e permitidos só de teste."""
    try:
        ficha = escopo.ler_ficha(issue, numero, AUTORES_FICHA)
    except escopo.ErroFicha as e:
        return [f"ficha #{numero}: {e}"], None
    fora = [g for g in ficha.permitidos if not glob_so_de_teste(g, re_teste)]
    if fora:
        return [f"a ficha #{numero} permite caminho que não é só de teste: " + ", ".join(f"`{escopo._limpar(g)}`" for g in fora)], ficha  # noqa: SLF001
    return [], ficha


# --------------------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------------------


def _json_linhas(texto: str) -> list[dict]:
    saida = []
    for linha in texto.splitlines():
        if linha.strip():
            try:
                saida.append(json.loads(linha))
            except json.JSONDecodeError as e:
                raise escopo.ErroNaoMedido(f"resposta inválida da API: {e}") from e
    return saida


def buscar_pr(gh, repo: str, numero: int, dormir=time.sleep) -> dict:
    """O GitHub calcula `mergeable` sob demanda: nulo logo após uma mudança. Tenta de novo; nulo ao fim = NÃO MEDIDO."""
    pr: dict = {}
    for tentativa in range(TENTATIVAS_MERGEABLE):
        try:
            pr = json.loads(gh(["api", f"repos/{repo}/pulls/{numero}"]))
        except json.JSONDecodeError as e:
            raise escopo.ErroNaoMedido(f"resposta inválida da API ao ler o PR #{numero}") from e
        if pr.get("mergeable") is not None:
            break
        if tentativa < TENTATIVAS_MERGEABLE - 1:
            dormir(3)
    return pr


def buscar_check_runs(gh, repo: str, sha: str, todos: bool = False) -> list[dict]:
    jq = ".check_runs[] | {name, status, conclusion}"
    filtro = "&filter=all" if todos else ""
    return _json_linhas(gh(["api", "--paginate", f"repos/{repo}/commits/{sha}/check-runs?per_page=100{filtro}", "--jq", jq]))


def buscar_status(gh, repo: str, sha: str) -> dict:
    try:
        bruto = json.loads(gh(["api", f"repos/{repo}/commits/{sha}/status"]))
    except json.JSONDecodeError as e:
        raise escopo.ErroNaoMedido("resposta inválida da API ao ler os statuses") from e
    return {"statuses": [{"context": s.get("context"), "state": s.get("state")} for s in bruto.get("statuses") or []]}


def buscar_obrigatorios(gh, repo: str, base: str) -> list[str]:
    """Contextos exigidos pela proteção do branch. Ilegível = NÃO MEDIDO (não junta no escuro)."""
    try:
        ramo = json.loads(gh(["api", f"repos/{repo}/branches/{base}"]))
    except json.JSONDecodeError as e:
        raise escopo.ErroNaoMedido("resposta inválida da API ao ler o branch-base") from e
    if ramo.get("protected") is False:
        return []
    protecao = ramo.get("protection")
    if not isinstance(protecao, dict):
        raise escopo.ErroNaoMedido(f"não consegui ler a proteção de `{base}` (checks obrigatórios desconhecidos)")
    checks = protecao.get("required_status_checks") or {}
    contextos = checks.get("contexts")
    if contextos is None:
        contextos = [c.get("context") for c in checks.get("checks") or []]
    return [c for c in contextos if c]


def avaliar_pr(gh, repo: str, numero: int, base: str, re_teste: re.Pattern[str], dormir=time.sleep) -> Decisao:
    """Aplica as 5 regras a UM PR. Nunca levanta: falha de medição vira Decisao(nao_medido=True)."""
    d = Decisao(numero=numero)
    try:
        pr = buscar_pr(gh, repo, numero, dormir)
        d.sha = (pr.get("head") or {}).get("sha", "")
        d.ja_pronto = any((r.get("name") if isinstance(r, dict) else r) == ROTULO_PRONTO for r in pr.get("labels") or [])
        m = _RE_CUSTO.search(pr.get("body") or "")
        d.custo = m.group(1).strip() if m else ""

        motivos, d.ficha = checar_pr(pr, repo, base)
        d.motivos += motivos
        if not d.sha:
            d.motivos.append("o PR não informa o commit da cabeça (NÃO MEDIDO)")
            d.nao_medido = True
            return d

        ficha = None
        if d.ficha is not None:
            motivos, ficha = checar_ficha(escopo.buscar_issue(gh, repo, d.ficha), d.ficha, re_teste)
            d.motivos += motivos
        if ficha is not None:
            d.motivos += checar_arquivos(escopo.buscar_arquivos(gh, repo, numero), ficha, re_teste)

        if not d.motivos:  # só gasta as chamadas de checks quando o resto já passou
            d.motivos += avaliar_checks(
                buscar_check_runs(gh, repo, d.sha),
                buscar_check_runs(gh, repo, d.sha, todos=True),
                buscar_status(gh, repo, d.sha),
                buscar_obrigatorios(gh, repo, base),
            )
        d.motivos += checar_mergeable(pr)
        if any("NÃO MEDIDO" in m for m in d.motivos):
            d.nao_medido = True
    except escopo.ErroNaoMedido as e:
        d.motivos.append(f"NÃO MEDIDO: {escopo._limpar(str(e))}")  # noqa: SLF001
        d.nao_medido = True
    d.juntar = not d.motivos and not d.nao_medido
    return d


def candidatos(gh, repo: str) -> list[int]:
    """PRs abertos que passam no portão barato da regra 1 (autor bot + título); o resto nem é examinado."""
    jq = ".[] | {number, login: .user.login, title}"
    achados = _json_linhas(gh(["api", "--paginate", f"repos/{repo}/pulls?state=open&per_page=100", "--jq", jq]))
    return [
        int(p["number"])
        for p in achados
        if p.get("login") in AUTORES_PR and (p.get("title") or "").startswith(PREFIXO_TITULO)
    ]


# --------------------------------------------------------------------------------------
# Ações
# --------------------------------------------------------------------------------------


def etiquetar_pronto(gh, repo: str, d: Decisao, aviso: str = "") -> None:
    if d.ja_pronto:  # já avisado nesta cabeça: não repete o comentário a cada rodada
        return
    try:
        gh(["label", "create", ROTULO_PRONTO, "--repo", repo, "--color", "0E8A16", "--description", "Só teste, checks verdes: pode juntar"])
    except escopo.ErroNaoMedido:
        pass  # já existe
    gh(["pr", "edit", str(d.numero), "--repo", repo, "--add-label", ROTULO_PRONTO])
    gh(["pr", "comment", str(d.numero), "--repo", repo, "--body", MSG_PRONTO + (f" {aviso}" if aviso else "")])


def juntar(gh, repo: str, d: Decisao) -> None:
    gh(["pr", "merge", str(d.numero), "--repo", repo, "--squash", "--delete-branch", "--match-head-commit", d.sha])
    gh(["pr", "comment", str(d.numero), "--repo", repo, "--body", MSG_JUNTADO])
    custo = f" Custo estimado pelo SDK: {d.custo}." if d.custo else ""
    if d.ficha is not None:
        try:
            gh(["issue", "comment", str(d.ficha), "--repo", repo, "--body", f"PR #{d.numero} juntado automaticamente (ficha só de teste, todos os checks verdes).{custo}"])
        except escopo.ErroNaoMedido:
            pass  # o comentário na ficha é registro; a junção já aconteceu


def agir(gh, repo: str, d: Decisao, acao: str, dry_run: bool, atualizar: bool = True) -> str:
    """Executa a decisão. Devolve uma linha de resultado; levanta ErroNaoMedido só se nem o plano B funcionou."""
    if d.so_atrasado:
        if dry_run:
            return "dry-run: a branch seria atualizada com a base"
        if not atualizar:
            return "branch atrás da base; nada a fazer (atualização desligada)"
        gh(["pr", "update-branch", str(d.numero), "--repo", repo])
        return "branch atualizada com a base; o CI roda de novo e a próxima rodada junta"
    if not d.juntar:
        return "nada a fazer"
    if dry_run:
        return "dry-run: nada foi alterado"
    if acao == "etiquetar":
        etiquetar_pronto(gh, repo, d)
        return "etiquetado `estado:pode-juntar` (sem juntar)"
    try:
        juntar(gh, repo, d)
        return "JUNTADO (squash)"
    except escopo.ErroNaoMedido as e:
        etiquetar_pronto(gh, repo, d, aviso="(a junção automática foi recusada; junte com um comando)")
        raise escopo.ErroNaoMedido(f"junção recusada, caí para o rótulo `{ROTULO_PRONTO}`: {e}") from e


# --------------------------------------------------------------------------------------
# Execução
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None, env: dict | None = None, gh=escopo.gh_cli, dormir=time.sleep) -> int:
    env = dict(os.environ if env is None else env)
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--repo", default=env.get("GH_REPO", ""), help="dono/repositório (ou GH_REPO)")
    p.add_argument("--pr", type=int, default=None, help="examina só este PR (aparece o motivo completo se não passar)")
    p.add_argument("--base", default="main", help="branch-base aceito (padrão: main)")
    p.add_argument("--acao", choices=("juntar", "etiquetar"), default="juntar")
    p.add_argument("--dry-run", action="store_true", help="decide e imprime; não altera nada")
    p.add_argument("--sem-atualizar-branch", action="store_true", help="não atualiza a branch do PR que só está atrás da base")
    p.add_argument("--regex-testes", default=env.get("REGEX_TESTES") or escopo.REGEX_TESTES_PADRAO)
    args = p.parse_args(argv)

    destino = env.get("GITHUB_STEP_SUMMARY")
    linhas_md: list[str] = []

    def dizer(texto: str) -> None:
        print(texto)
        linhas_md.append(texto)

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        print("::error::NÃO MEDIDO: --repo (ou GH_REPO) ausente ou inválido.")
        return 1
    try:
        re_teste = re.compile(args.regex_testes)
    except re.error as e:
        print(f"::error::NÃO MEDIDO: regex de testes inválida: {e}")
        return 1

    try:
        numeros = [args.pr] if args.pr is not None else candidatos(gh, args.repo)
    except escopo.ErroNaoMedido as e:
        print(f"::error::NÃO MEDIDO: não consegui listar os PRs: {escopo._limpar(str(e))}")  # noqa: SLF001
        return 1

    dizer(f"## juntar-so-teste em {args.repo}" + (" (dry-run)" if args.dry_run else ""))
    if not numeros:
        dizer("- nenhum PR de agente aberto.")
    saida = 0
    for n in numeros:
        d = avaliar_pr(gh, args.repo, n, args.base, re_teste, dormir)
        dizer(f"- {d.resumo()}")
        for m in d.motivos:
            dizer(f"    - {m}")
        if d.nao_medido:
            saida = 1
        try:
            resultado = agir(gh, args.repo, d, args.acao, args.dry_run, not args.sem_atualizar_branch)
            if d.juntar or d.so_atrasado:
                dizer(f"    - {resultado}")
        except escopo.ErroNaoMedido as e:
            dizer(f"    - {escopo._limpar(str(e))}")  # noqa: SLF001
            saida = 1

    if destino:
        with open(destino, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(linhas_md) + "\n")
    return saida


if __name__ == "__main__":
    for _fluxo in (sys.stdout, sys.stderr):  # console do Windows em cp1252 quebraria os acentos do relato
        try:
            _fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
