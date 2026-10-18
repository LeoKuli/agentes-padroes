"""ficha, escopo, segredos e mutacao-ficha escolhem o runner por entrada; o padrão é o GitHub.

O job que usa a chave do app (publicar/juntar-so-teste) e o que tem escrita nunca escolhe: fica
no GitHub (coberto por test_workflow_agente.py e test_workflow_juntar_so_teste.py).
"""
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
yaml = pytest.importorskip("yaml")

# arquivo -> nome do único job
WORKFLOWS = {
    "ficha.yml": "ficha",
    "escopo.yml": "escopo",
    "segredos.yml": "gitleaks",
    "mutacao-ficha.yml": "mutacao",
}


def _wf(arquivo):
    return yaml.safe_load((RAIZ / ".github" / "workflows" / arquivo).read_text(encoding="utf-8"))


def _entradas(doc):
    return doc.get("on", doc.get(True))["workflow_call"]["inputs"]  # PyYAML lê `on` como True


@pytest.mark.parametrize("arquivo", sorted(WORKFLOWS))
def test_a_entrada_runner_existe_e_o_padrao_e_o_github(arquivo):
    entrada = _entradas(_wf(arquivo))["runner"]
    assert entrada["type"] == "string"
    assert json.loads(entrada["default"]) == "ubuntu-latest"


@pytest.mark.parametrize("arquivo", sorted(WORKFLOWS))
def test_o_job_roda_onde_a_entrada_manda(arquivo):
    jobs = _wf(arquivo)["jobs"]
    assert list(jobs) == [WORKFLOWS[arquivo]]
    assert jobs[WORKFLOWS[arquivo]]["runs-on"] == "${{ fromJSON(inputs.runner) }}"


@pytest.mark.parametrize("arquivo", sorted(WORKFLOWS))
def test_o_token_so_le_e_nenhum_token_de_app_nem_chave_de_escrita(arquivo):
    doc = _wf(arquivo)
    perms = doc["permissions"]
    assert all(v == "read" for v in perms.values()), perms
    texto = (RAIZ / ".github" / "workflows" / arquivo).read_text(encoding="utf-8")
    assert "create-github-app-token" not in texto
    assert "APP_PRIVATE_KEY" not in texto and "app-id" not in texto


def test_a_unica_credencial_alem_do_github_token_e_o_padroes_token_do_escopo():
    """Documenta por que o escopo continua no GitHub nos chamadores que repassam PADROES_TOKEN."""
    for arquivo in WORKFLOWS:
        texto = (RAIZ / ".github" / "workflows" / arquivo).read_text(encoding="utf-8")
        outras = {linha.strip() for linha in texto.splitlines() if "secrets." in linha and "#" not in linha.split("secrets.")[0]}
        if arquivo == "escopo.yml":
            assert outras == {"token: ${{ secrets.PADROES_TOKEN || github.token }}"}
        else:
            assert not outras, (arquivo, outras)
