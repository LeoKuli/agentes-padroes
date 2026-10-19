"""O workflow mutacao-ficha.yml e o script precisam concordar entre si."""
import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

yaml = pytest.importorskip("yaml")


def _wf():
    return yaml.safe_load((RAIZ / ".github" / "workflows" / "mutacao-ficha.yml").read_text(encoding="utf-8"))


def _call():
    doc = _wf()
    return doc.get("on", doc.get(True))["workflow_call"]  # PyYAML lê `on` como True


def test_entradas_combinadas():
    entradas = _call()["inputs"]
    assert entradas["comando_teste"]["required"] is True
    assert json.loads(entradas["runner"]["default"]) == "ubuntu-24.04"
    assert not entradas["preparar"].get("required")
    assert entradas["preparar"]["default"] == ""


def test_so_roda_em_pr_de_agente_com_ficha():
    job = _wf()["jobs"]["mutacao"]
    cond = " ".join(str(job["if"]).split())
    assert "github.event.pull_request.user.login == 'github-actions[bot]'" in cond
    assert "contains(github.event.pull_request.body, 'Ficha: #')" in cond
    assert "&&" in cond


def test_permissoes_so_de_leitura():
    assert _wf()["permissions"] == {"contents": "read", "issues": "read", "pull-requests": "read"}


def test_runner_vem_da_entrada():
    assert _wf()["jobs"]["mutacao"]["runs-on"] == "${{ fromJSON(inputs.runner) }}"


def test_checkouts_nao_persistem_credencial_e_o_codigo_do_pr_fica_isolado_dos_scripts():
    passos = _wf()["jobs"]["mutacao"]["steps"]
    cheques = [p for p in passos if p.get("uses", "").startswith("actions/checkout")]
    assert len(cheques) == 2
    for p in cheques:
        assert p["with"].get("persist-credentials") is False
    codigo = next(p for p in cheques if "repository" not in p["with"])
    assert codigo["with"]["path"] == "codigo" and codigo["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    padroes = next(p for p in cheques if "repository" in p["with"])
    assert padroes["with"]["repository"] == "LeoKuli/agentes-padroes" and padroes["with"]["path"] == "_padroes"


def test_texto_nao_confiavel_e_comandos_nunca_sao_interpolados_num_run():
    proibido = re.compile(r"\$\{\{\s*(github\.event\.|inputs\.)")
    for passo in _wf()["jobs"]["mutacao"]["steps"]:
        assert not proibido.search(passo.get("run", "")), passo.get("name")


def test_o_passo_do_script_recebe_o_que_o_script_le():
    passo = next(p for p in _wf()["jobs"]["mutacao"]["steps"] if "mutacao_da_ficha.py" in p.get("run", ""))
    assert {"PR_BODY", "GH_REPO", "GH_TOKEN", "COMANDO_TESTE", "TIMEOUT_SEGUNDOS", "AUTORES_FICHA"} <= set(passo["env"])
    assert passo["working-directory"] == "codigo"
    import mutacao_da_ficha as mf

    fonte = (RAIZ / "scripts" / "mutacao_da_ficha.py").read_text(encoding="utf-8")
    for nome in passo["env"]:
        assert f'"{nome}"' in fonte, f"o script não lê {nome}"
    assert "GH_TOKEN" in mf.VARIAVEIS_RETIDAS  # e o comando de teste não o recebe


def test_o_preparo_so_roda_se_pedido_e_na_pasta_do_codigo():
    passo = next(p for p in _wf()["jobs"]["mutacao"]["steps"] if p.get("name", "").startswith("Preparar"))
    assert passo["if"] == "inputs.preparar != ''"
    assert passo["working-directory"] == "codigo"
