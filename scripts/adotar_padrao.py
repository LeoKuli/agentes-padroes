"""adotar-padrao: monta o kit de agentes (v2) num repositório SEM sobrescrever o que já existe.

Uso:
    python scripts/adotar_padrao.py <pasta-do-repositorio> [--nome NOME] [--devcontainer] [--simular]

Cada arquivo do kit é copiado só se o destino não existe ("criado"); o que existe fica como está ("mantido").
Os PREENCHER que vierem nos modelos têm de virar conteúdo real: o CI de conformidade reprova enquanto sobrar algum.
Só biblioteca padrão; roda igual no Windows, no Linux e no CI.
"""
from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

RAIZ_KIT = Path(__file__).resolve().parent.parent / "templates"

# (origem em templates/, destino no repositório, opcional?)
KIT: list[tuple[str, str, bool]] = [
    ("AGENTS.md", "AGENTS.md", False),
    ("CLAUDE.md", "CLAUDE.md", False),
    ("GEMINI.md", "GEMINI.md", False),
    ("github/copilot-instructions.md", ".github/copilot-instructions.md", False),
    ("docs/ESTADO.md", "docs/ESTADO.md", False),
    ("docs/GLOSSARIO.md", "docs/GLOSSARIO.md", False),
    ("docs/decisoes/README.md", "docs/decisoes/README.md", False),
    ("agents-skills/README.md", ".agents/skills/README.md", False),
    ("mcp.json", ".mcp.json", False),
    ("env.example", ".env.example", False),
    ("verificar", "scripts/verificar", False),
    ("conformidade-caller.yml", ".github/workflows/conformidade.yml", False),
    (".gitleaks.toml", ".gitleaks.toml", False),
    ("devcontainer.json", ".devcontainer/devcontainer.json", True),
]


def adotar(repo: Path, nome: str, devcontainer: bool = False, simular: bool = False) -> list[tuple[str, str]]:
    """Devolve [(situação, destino)], situação em {criado, mantido, pulado}."""
    if not repo.is_dir():
        raise SystemExit(f"adotar-padrao: pasta não existe: {repo}")
    saida: list[tuple[str, str]] = []
    for origem, destino, opcional in KIT:
        alvo = repo / destino
        if opcional and not devcontainer:
            saida.append(("pulado", destino))
            continue
        if alvo.exists() or (destino == ".devcontainer/devcontainer.json" and (repo / ".devcontainer.json").exists()):
            saida.append(("mantido", destino))
            continue
        texto = (RAIZ_KIT / origem).read_text(encoding="utf-8").replace("{{NOME}}", nome)
        if not simular:
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with open(alvo, "w", encoding="utf-8", newline="\n") as f:
                f.write(texto)
            if destino == "scripts/verificar":
                alvo.chmod(alvo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        saida.append(("criado", destino))
    return saida


def avisos(repo: Path) -> list[str]:
    a = []
    claude = repo / "CLAUDE.md"
    if claude.exists() and "@AGENTS.md" not in claude.read_text(encoding="utf-8", errors="replace"):
        a.append("CLAUDE.md já existia sem @AGENTS.md: mova o conteúdo para AGENTS.md e deixe só '@AGENTS.md'.")
    if (repo / "Makefile").exists() and not (repo / "scripts" / "verificar").exists():
        a.append("há Makefile: se ele já tem o comando único, um alvo 'verificar:' basta.")
    gi = repo / ".gitignore"
    if not gi.exists() or ".env" not in gi.read_text(encoding="utf-8", errors="replace"):
        a.append(".gitignore não exclui .env: acrescente '.env' (o .env.example continua versionado).")
    return a


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="adotar-padrao", description=__doc__.splitlines()[0])
    ap.add_argument("repo")
    ap.add_argument("--nome", default=None, help="nome do projeto (padrão: nome da pasta)")
    ap.add_argument("--devcontainer", action="store_true", help="incluir .devcontainer/devcontainer.json")
    ap.add_argument("--simular", action="store_true", help="só mostra o que faria")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    nome = a.nome or repo.name
    res = adotar(repo, nome, a.devcontainer, a.simular)
    for situacao, destino in res:
        print(f"{situacao:8} {destino}")
    for aviso in avisos(repo):
        print(f"atenção  {aviso}")
    criados = sum(1 for s, _ in res if s == "criado")
    print(f"\nadotar-padrao: {criados} criado(s), {sum(1 for s, _ in res if s == 'mantido')} mantido(s)"
          + (" (simulação)" if a.simular else ""))
    print("Próximo passo: trocar todo PREENCHER por conteúdo real e rodar a conformidade:")
    print(f"  python {Path(__file__).with_name('conformidade.py')} --raiz {repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
