#!/usr/bin/env python3
"""Relatório do custo dos agentes externos (OpenRouter), a partir dos comentários `custo-agente v1` das fichas.

Responde à pergunta do dono (28/10/2026): o fluxo de fichas com modelos baratos compensa a médio e longo prazo?
Para cada repositório e modelo: execuções, custo medido, PRs abertos, PRs juntados e custo por PR juntado.

Uso:  python3 scripts/relatorio_custo.py --desde 2026-10-28 [--ate 2026-11-04] [--repos LeoKuli/a,LeoKuli/b]
Sem --repos, varre todos os repositórios do dono que têm .github/workflows/agente.yml.
Precisa do `gh` autenticado. Só lê; nada é escrito no GitHub.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass

NAO_MEDIDO = "NÃO MEDIDO"
_RE_MARCA = re.compile(r"<!-- custo-agente v1 (\{.*?\}) -->", re.S)


@dataclass(frozen=True)
class Execucao:
    repo: str
    ficha: str
    modelo: str
    resultado: str
    inicio: str
    fim: str
    run: str
    usd: float | None  # None = NÃO MEDIDO


def ler_marca(corpo: str) -> Execucao | None:
    """Um comentário de custo vira uma Execucao; qualquer outra coisa, None."""
    m = _RE_MARCA.search(corpo or "")
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    try:
        usd = float(d.get("usd", ""))
    except ValueError:
        usd = None
    return Execucao(
        repo=d.get("repo", ""), ficha=str(d.get("ficha", "")), modelo=d.get("modelo", ""),
        resultado=d.get("resultado", ""), inicio=d.get("inicio", ""), fim=d.get("fim", ""),
        run=str(d.get("run", "")), usd=usd,
    )


def sobrepostas(execucoes: list[Execucao]) -> set[str]:
    """Runs que rodaram ao mesmo tempo que outra no MESMO repositório (mesma chave): o custo delas se mistura."""
    marcadas: set[str] = set()
    por_repo: dict[str, list[Execucao]] = defaultdict(list)
    for e in execucoes:
        if e.inicio and e.fim:
            por_repo[e.repo].append(e)
    for lista in por_repo.values():
        for i, a in enumerate(lista):
            for b in lista[i + 1:]:
                if a.inicio < b.fim and b.inicio < a.fim:
                    marcadas.update({a.run, b.run})
    return marcadas


def resumir(execucoes: list[Execucao], juntados: set[str]) -> list[dict]:
    """Linhas por (repo, modelo). `juntados` = runs cujo PR foi juntado."""
    grupos: dict[tuple[str, str], list[Execucao]] = defaultdict(list)
    for e in execucoes:
        grupos[(e.repo, e.modelo)].append(e)
    linhas = []
    for (repo, modelo), lista in sorted(grupos.items()):
        medidas = [e.usd for e in lista if e.usd is not None]
        total = sum(medidas)
        prs = sum(1 for e in lista if e.resultado == "pr")
        junt = sum(1 for e in lista if e.run in juntados)
        linhas.append({
            "repo": repo, "modelo": modelo, "execucoes": len(lista),
            "nao_medidas": len(lista) - len(medidas), "usd": round(total, 4),
            "prs": prs, "juntados": junt,
            "usd_por_juntado": round(total / junt, 4) if junt else None,
        })
    return linhas


def tabela(linhas: list[dict], sobrep: int) -> str:
    out = ["| Repositório | Modelo | Execuções | Custo medido (US$) | PRs | Juntados | US$ por PR juntado |",
           "|---|---|---|---|---|---|---|"]
    for l in linhas:
        custo = f"{l['usd']:.4f}" + (f" (+{l['nao_medidas']} {NAO_MEDIDO})" if l["nao_medidas"] else "")
        por = f"{l['usd_por_juntado']:.4f}" if l["usd_por_juntado"] is not None else "sem PR juntado"
        out.append(f"| {l['repo']} | {l['modelo']} | {l['execucoes']} | {custo} | {l['prs']} | {l['juntados']} | {por} |")
    total = sum(l["usd"] for l in linhas)
    junt = sum(l["juntados"] for l in linhas)
    out.append("")
    out.append(f"Total medido: US$ {total:.4f} · PRs juntados: {junt} · "
               f"US$ por PR juntado: {(total / junt):.4f}" if junt else f"Total medido: US$ {total:.4f} · nenhum PR juntado")
    if sobrep:
        out.append(f"Atenção: {sobrep} execuções rodaram ao mesmo tempo que outra na mesma chave; o custo delas se mistura.")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- GitHub (só leitura)


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _repos_com_agente(dono: str) -> list[str]:
    nomes = json.loads(_gh("repo", "list", dono, "--limit", "200", "--json", "nameWithOwner"))
    achados = []
    for n in nomes:
        r = n["nameWithOwner"]
        try:
            _gh("api", f"repos/{r}/contents/.github/workflows/agente.yml", "--jq", ".name")
            achados.append(r)
        except subprocess.CalledProcessError:
            continue
    return achados


def _execucoes(repo: str, desde: str, ate: str) -> list[Execucao]:
    linhas = _gh("api", "--paginate", f"repos/{repo}/issues/comments?since={desde}T00:00:00Z&per_page=100",
                 "--jq", ".[] | {body, created_at} | tojson")
    comentarios = [json.loads(l) for l in linhas.splitlines() if l.strip()]
    saida = []
    for c in comentarios:
        if c["created_at"][:10] > ate:
            continue
        e = ler_marca(c["body"])
        if e:
            saida.append(e)
    return saida


def _runs_juntados(repo: str, desde: str) -> set[str]:
    prs = json.loads(_gh("pr", "list", "--repo", repo, "--state", "merged", "--limit", "200",
                         "--search", f"merged:>={desde}", "--json", "headRefName"))
    runs = set()
    for p in prs:
        m = re.match(r"^agente/ficha-\d+-[a-z0-9._-]+-(\d+)$", p["headRefName"])
        if m:
            runs.add(m.group(1))
    return runs


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--ate", default="9999-12-31")
    ap.add_argument("--repos", default="")
    ap.add_argument("--dono", default="LeoKuli")
    a = ap.parse_args(argv)
    repos = [r for r in a.repos.split(",") if r] or _repos_com_agente(a.dono)
    execucoes: list[Execucao] = []
    juntados: set[str] = set()
    for r in repos:
        execucoes += _execucoes(r, a.desde, a.ate)
        juntados |= _runs_juntados(r, a.desde)
    sys.stdout.write(f"# Custo dos agentes externos (OpenRouter), {a.desde} a {a.ate if a.ate != '9999-12-31' else 'hoje'}\n\n")
    sys.stdout.write(tabela(resumir(execucoes, juntados), len(sobrepostas(execucoes))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
