"""Conformidade do kit de agentes (LeoKuli/agentes-padroes v2).

Confere se qualquer modelo consegue retomar o repositório só com o que está nele:

- AGENTS.md na raiz, sem PREENCHER sobrando;
- docs/ESTADO.md com "Atualizado em: AAAA-MM-DD" dentro do limite de dias, sem PREENCHER;
- ao menos um ADR em docs/decisoes/NNNN-*.md, cada um com status válido;
- CLAUDE.md (se houver) com @AGENTS.md; GEMINI.md e .github/copilot-instructions.md (se houver) citando AGENTS.md;
- comando único: scripts/verificar (sem PREENCHER) ou alvo "verificar:" no Makefile;
- .mcp.json (se houver) é JSON válido e não traz valor literal em "env" (só ${VAR}).

Só biblioteca padrão. Saída: uma linha OK/FALHA por item; código 1 se houver FALHA.
Uso: python scripts/conformidade.py --raiz . [--dias 30] [--hoje AAAA-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

MARCA = "PREENCHER"
RE_DATA = re.compile(r"^Atualizado em:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
RE_ADR = re.compile(r"^\d{4}-[a-z0-9][a-z0-9-]*\.md$")
RE_STATUS = re.compile(r"^status:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
STATUS_VALIDOS = re.compile(
    r"^(proposto|aceito|rejeitado|obsoleto|substitu[ií]do por \d{4}"
    r"|proposed|accepted|rejected|deprecated|superseded by \d{4})$",
    re.IGNORECASE,
)
RE_VAR = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


def _ler(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _frontmatter(texto: str) -> str:
    if texto.startswith("---"):
        fim = texto.find("\n---", 3)
        if fim != -1:
            return texto[3:fim]
    return ""


def verificar(raiz: Path, dias: int, hoje: dt.date) -> list[tuple[bool, str]]:
    r: list[tuple[bool, str]] = []

    agents = _ler(raiz / "AGENTS.md")
    if agents is None or not agents.strip():
        r.append((False, "AGENTS.md ausente ou vazio na raiz"))
    elif MARCA in agents:
        r.append((False, f"AGENTS.md ainda tem {agents.count(MARCA)} {MARCA}"))
    else:
        r.append((True, "AGENTS.md presente e preenchido"))

    estado = _ler(raiz / "docs" / "ESTADO.md")
    if estado is None:
        r.append((False, "docs/ESTADO.md ausente"))
    else:
        m = RE_DATA.search(estado)
        if MARCA in estado:
            r.append((False, f"docs/ESTADO.md ainda tem {estado.count(MARCA)} {MARCA}"))
        elif not m:
            r.append((False, "docs/ESTADO.md sem a linha 'Atualizado em: AAAA-MM-DD'"))
        else:
            try:
                data = dt.date.fromisoformat(m.group(1))
            except ValueError:
                r.append((False, f"docs/ESTADO.md: data inválida {m.group(1)}"))
            else:
                idade = (hoje - data).days
                if idade < 0:
                    r.append((False, f"docs/ESTADO.md datado no futuro ({data})"))
                elif idade > dias:
                    r.append((False, f"docs/ESTADO.md vencido: {idade} dias (limite {dias}); atualize o estado"))
                else:
                    r.append((True, f"docs/ESTADO.md em dia ({idade} dias)"))

    pasta = raiz / "docs" / "decisoes"
    adrs = sorted(p for p in pasta.glob("*.md") if RE_ADR.match(p.name) and not p.name.startswith("0000")) \
        if pasta.is_dir() else []
    if not adrs:
        r.append((False, "nenhum ADR em docs/decisoes/NNNN-*.md"))
    else:
        ruins = []
        for p in adrs:
            texto = _ler(p) or ""
            m = RE_STATUS.search(_frontmatter(texto))
            if not m or not STATUS_VALIDOS.match(m.group(1)):
                ruins.append(p.name)
            elif MARCA in texto:
                ruins.append(p.name + f" ({MARCA})")
        if ruins:
            r.append((False, "ADR sem status válido no frontmatter: " + ", ".join(ruins)))
        else:
            r.append((True, f"{len(adrs)} ADR(s) com status válido"))

    claude = _ler(raiz / "CLAUDE.md")
    if claude is not None:
        if "@AGENTS.md" in claude:
            r.append((True, "CLAUDE.md aponta para @AGENTS.md"))
        else:
            r.append((False, "CLAUDE.md existe sem @AGENTS.md (mova o conteúdo para AGENTS.md)"))
    for nome in ("GEMINI.md", ".github/copilot-instructions.md"):
        texto = _ler(raiz / nome)
        if texto is not None:
            r.append(("AGENTS.md" in texto, f"{nome} {'aponta' if 'AGENTS.md' in texto else 'NÃO aponta'} para AGENTS.md"))

    verif = _ler(raiz / "scripts" / "verificar")
    make = _ler(raiz / "Makefile") or ""
    if verif is not None:
        if MARCA in verif:
            r.append((False, f"scripts/verificar ainda tem {MARCA}"))
        else:
            r.append((True, "comando único scripts/verificar"))
    elif re.search(r"^verificar\s*:", make, re.MULTILINE):
        r.append((True, "comando único make verificar"))
    else:
        r.append((False, "sem comando único (scripts/verificar ou alvo 'verificar:' no Makefile)"))

    mcp = _ler(raiz / ".mcp.json")
    if mcp is not None:
        try:
            dados = json.loads(mcp)
        except json.JSONDecodeError as e:
            r.append((False, f".mcp.json inválido: {e}"))
        else:
            literais = []
            for nome, srv in (dados.get("mcpServers") or {}).items():
                for chave, valor in ((srv or {}).get("env") or {}).items():
                    if isinstance(valor, str) and valor and not RE_VAR.match(valor):
                        literais.append(f"{nome}.{chave}")
            if literais:
                r.append((False, ".mcp.json com valor literal em env (use ${VAR}): " + ", ".join(literais)))
            else:
                r.append((True, ".mcp.json sem segredo literal"))
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", default=".")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--hoje", default=None, help="data de referência (testes)")
    a = ap.parse_args(argv)
    hoje = dt.date.fromisoformat(a.hoje) if a.hoje else dt.date.today()
    resultados = verificar(Path(a.raiz), a.dias, hoje)
    for ok, msg in resultados:
        print(("OK     " if ok else "FALHA  ") + msg)
    falhas = sum(1 for ok, _ in resultados if not ok)
    print(f"\nconformidade: {'APROVADO' if not falhas else f'REPROVADO ({falhas} falha(s))'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
