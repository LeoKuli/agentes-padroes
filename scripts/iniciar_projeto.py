"""iniciar-projeto: transforma um repositório criado pelo template LeoKuli/agentes-padroes num projeto novo.

Uso (dentro do repositório novo, logo depois de criá-lo pelo template):
    python scripts/iniciar_projeto.py [--nome NOME]

Apaga tudo o que veio do agentes-padroes (menos .git) e monta só o kit de agentes, via adotar-padrao.
As skills compartilhadas e as regras do dono ficam em um lugar só (o agentes-padroes) e são citadas por link.
Recusa rodar no próprio agentes-padroes.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adotar_padrao  # noqa: E402

README = """# {nome}

Projeto criado pelo template [LeoKuli/agentes-padroes](https://github.com/LeoKuli/agentes-padroes).

Comece pelo [`AGENTS.md`](AGENTS.md) e pelo [`docs/ESTADO.md`](docs/ESTADO.md). O comando único de pronto é
`bash scripts/verificar`.
"""


def _e_o_proprio_padroes(raiz: Path) -> bool:
    try:
        url = subprocess.run(["git", "-C", str(raiz), "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=False).stdout
    except OSError:
        return False
    return "agentes-padroes" in url


def iniciar(raiz: Path, nome: str, forcar: bool = False) -> None:
    if not (raiz / "scripts" / "conformidade.py").exists() or not (raiz / "templates").is_dir():
        raise SystemExit("iniciar-projeto: esta pasta não veio do template agentes-padroes")
    if not forcar and _e_o_proprio_padroes(raiz):
        raise SystemExit("iniciar-projeto: recusado no próprio agentes-padroes")
    with tempfile.TemporaryDirectory() as tmp:
        kit = Path(tmp) / "templates"
        shutil.copytree(raiz / "templates", kit)
        for item in raiz.iterdir():
            if item.name == ".git":
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()
        original = adotar_padrao.RAIZ_KIT
        adotar_padrao.RAIZ_KIT = kit
        try:
            adotar_padrao.adotar(raiz, nome)
        finally:
            adotar_padrao.RAIZ_KIT = original
    (raiz / "README.md").write_text(README.format(nome=nome), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="iniciar-projeto", description=__doc__.splitlines()[0])
    ap.add_argument("--nome", default=None)
    a = ap.parse_args(argv)
    raiz = Path(__file__).resolve().parent.parent
    iniciar(raiz, a.nome or raiz.name)
    print("iniciar-projeto: kit montado. Troque todo PREENCHER e escreva o ADR 0001; depois rode bash scripts/verificar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
