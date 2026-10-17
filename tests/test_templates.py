"""Os modelos e o verificador de escopo precisam concordar entre si."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import escopo  # noqa: E402

yaml = pytest.importorskip("yaml")


def carregar(nome):
    return yaml.safe_load((RAIZ / "templates" / "ISSUE_TEMPLATE" / nome).read_text(encoding="utf-8"))


def test_ficha_form_tem_os_campos_que_o_verificador_le():
    form = carregar("ficha.yml")
    rotulos = {c["attributes"]["label"] for c in form["body"] if "label" in c.get("attributes", {})}
    assert "Arquivos permitidos" in rotulos
    assert any(r.startswith("Tamanho máximo do diff") for r in rotulos)
    assert form["title"] == "[FICHA] "
    assert form["labels"] == ["ficha", "estado:pronta"]


def test_ficha_form_campos_obrigatorios():
    form = carregar("ficha.yml")
    obrig = {c["id"] for c in form["body"] if c.get("validations", {}).get("required")}
    assert {"nivel", "objetivo", "permitidos", "aceite", "tamanho"} <= obrig
    tamanho = next(c for c in form["body"] if c.get("id") == "tamanho")
    assert tamanho["attributes"]["value"] == "300"


def test_corpo_gerado_pelo_form_e_lido_pelo_verificador():
    """Simula o que o GitHub grava (### Rótulo + valor) a partir do próprio ficha.yml."""
    form = carregar("ficha.yml")
    valores = {"permitidos": "src/regra/**\ntests/regra/**", "tamanho": "300", "aceite": "```bash\nmake pronto\n```"}
    partes = []
    for c in form["body"]:
        if c["type"] == "markdown":
            continue
        valor = valores.get(c["id"], "_No response_")
        partes.append(f"### {c['attributes']['label']}\n\n{valor}\n")
    ficha = escopo.ler_ficha(
        {"body": "\n".join(partes), "labels": [{"name": "ficha"}], "author_association": "OWNER"}, 1
    )
    assert ficha.permitidos == ["src/regra/**", "tests/regra/**"]
    assert ficha.max_diff == 300


def test_duvida_e_config():
    assert carregar("duvida.yml")["labels"] == ["duvida"]
    assert carregar("config.yml")["blank_issues_enabled"] is False


def test_labels_json():
    dados = json.loads((RAIZ / "templates" / "labels.json").read_text(encoding="utf-8"))
    nomes = [r["name"] for r in dados["labels"]]
    assert len(nomes) == len(set(nomes))
    obrigatorios = {"ficha", "duvida", "estado:pronta", "estado:em-andamento", "estado:revisao",
                    "estado:corrigir", "estado:devolvida", "nivel-1", "nivel-2", "nivel-3", "nivel-4", "prioridade:alta"}
    assert obrigatorios <= set(nomes)
    for r in dados["labels"] + [dados["sob_demanda"]["agente:<modelo>"]]:
        assert re.fullmatch(r"[0-9A-Fa-f]{6}", r["color"])
        assert 0 < len(r["description"]) <= 100  # limite do GitHub


def test_workflows_sao_yaml_valido():
    for nome in ("escopo.yml", "ficha.yml", "segredos.yml", "teste-padroes.yml", "agente-openhands.yml"):
        doc = yaml.safe_load((RAIZ / ".github" / "workflows" / nome).read_text(encoding="utf-8"))
        assert "jobs" in doc
    esc = yaml.safe_load((RAIZ / ".github" / "workflows" / "escopo.yml").read_text(encoding="utf-8"))
    gatilho = esc.get("on", esc.get(True))  # PyYAML lê `on` como True
    assert "workflow_call" in gatilho
    # o regex de testes do workflow é o mesmo do script
    assert gatilho["workflow_call"]["inputs"]["regex_testes"]["default"] == escopo.REGEX_TESTES_PADRAO
    prot = [p for p in gatilho["workflow_call"]["inputs"]["protegidos"]["default"].split("\n") if p]
    assert prot == escopo.PROTEGIDOS_PADRAO


@pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32", reason="sem bash POSIX (no Windows, o bash é o do WSL)")
@pytest.mark.parametrize("repo", ["Outro/x", "LeoKuli/x;y", "LeoKuli/", "LeoKuli/a b"])
def test_aplicar_labels_rejeita_repo_invalido(repo):
    p = subprocess.run(["bash", str(RAIZ / "scripts" / "aplicar-labels.sh"), repo],
                       capture_output=True, text=True, env={"DRY_RUN": "1", "PATH": __import__("os").environ["PATH"]})
    assert p.returncode == 2
    assert "DRY_RUN" not in p.stdout


@pytest.mark.skipif(shutil.which("bash") is None or sys.platform == "win32", reason="sem bash POSIX (no Windows, o bash é o do WSL)")
def test_aplicar_labels_dry_run_lista_todos():
    p = subprocess.run(["bash", str(RAIZ / "scripts" / "aplicar-labels.sh"), "LeoKuli/x", "agente:sonnet"],
                       capture_output=True, text=True, env={"DRY_RUN": "1", "PATH": __import__("os").environ["PATH"]})
    assert p.returncode == 0, p.stderr
    linhas = p.stdout.strip().splitlines()
    assert len(linhas) == 13
    assert linhas[-1].startswith("DRY_RUN: agente:sonnet | ")
