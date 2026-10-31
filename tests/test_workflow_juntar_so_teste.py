"""O workflow reutilizável da junção automática, o chamador e o script precisam concordar entre si."""
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import juntar_so_teste as jt  # noqa: E402

yaml = pytest.importorskip("yaml")


def _carregar(*partes):
    return yaml.safe_load(RAIZ.joinpath(*partes).read_text(encoding="utf-8"))


def _wf():
    return _carregar(".github", "workflows", "juntar-so-teste.yml")


def _gatilho(doc):
    return doc.get("on", doc.get(True))  # PyYAML lê `on` como True


def _caller():
    return _carregar("templates", "juntar-so-teste-caller.yml")


def test_workflow_e_reutilizavel_com_as_entradas_combinadas():
    call = _gatilho(_wf())["workflow_call"]
    assert set(call["inputs"]) == {"pr", "dry_run", "acao", "base", "regex_testes"}
    assert call["inputs"]["dry_run"]["default"] is False
    assert call["inputs"]["acao"]["default"] == "juntar"
    assert call["secrets"]["PORTAO_APP_KEY"]["required"] is True


def test_token_do_app_e_o_unico_com_escrita_e_so_o_necessario():
    wf = _wf()
    assert wf["permissions"] == {"contents": "read"}  # o GITHUB_TOKEN do job só lê
    passos = wf["jobs"]["juntar"]["steps"]
    app = [p for p in passos if str(p.get("uses", "")).startswith("actions/create-github-app-token@")]
    assert len(app) == 1
    com = app[0]["with"]
    assert com["app-id"] == 5363413
    assert com["private-key"] == "${{ secrets.PORTAO_APP_KEY }}"
    assert {k: v for k, v in com.items() if k.startswith("permission-")} == {
        "permission-contents": "write",
        "permission-pull-requests": "write",
        "permission-issues": "write",
        "permission-checks": "read",
        "permission-statuses": "read",
    }
    assert "permission-workflows" not in com and "permission-administration" not in com


def test_actions_de_terceiros_fixadas_por_sha():
    for passo in _wf()["jobs"]["juntar"]["steps"]:
        if "uses" in passo:
            assert re.search(r"@[0-9a-f]{40}$", passo["uses"]), passo["uses"]


def test_entradas_chegam_por_env_nunca_dentro_do_script():
    for passo in _wf()["jobs"]["juntar"]["steps"]:
        assert "${{" not in passo.get("run", ""), passo.get("name")
    passo = [p for p in _wf()["jobs"]["juntar"]["steps"] if p.get("name") == "Decidir e juntar"][0]
    assert passo["env"]["GH_TOKEN"] == "${{ steps.app.outputs.token }}"
    assert "python3 _padroes/scripts/juntar_so_teste.py" in passo["run"]
    # o número do PR é validado como inteiro antes de virar argumento
    assert "grep -Eq '^[0-9]+$'" in passo["run"]


def test_o_script_chamado_existe_e_aceita_os_argumentos_que_o_workflow_passa():
    passo = [p for p in _wf()["jobs"]["juntar"]["steps"] if p.get("name") == "Decidir e juntar"][0]
    for opcao in re.findall(r"--[a-z][a-z-]*", passo["run"]):
        assert opcao in (RAIZ / "scripts" / "juntar_so_teste.py").read_text(encoding="utf-8"), opcao


def test_nao_ha_duas_rodadas_ao_mesmo_tempo_no_mesmo_repositorio():
    conc = _wf()["concurrency"]
    assert "github.repository" in conc["group"] and conc["cancel-in-progress"] is False


def test_caller_dispara_por_evento_e_tem_rede_de_seguranca_barata():
    gatilho = _gatilho(_caller())
    assert set(gatilho) == {"workflow_dispatch", "workflow_run", "schedule"}
    assert gatilho["workflow_run"]["types"] == ["completed"]
    cron = gatilho["schedule"][0]["cron"].split()
    assert cron[1].startswith("*/") and int(cron[1][2:]) >= 6, "em repositório privado, */10 estoura os minutos de Actions"


def test_caller_so_age_em_branch_de_agente_quando_vem_de_workflow_run():
    job = _caller()["jobs"]["juntar"]
    cond = " ".join(str(job["if"]).split())
    assert "github.event_name != 'workflow_run'" in cond
    assert "startsWith(github.event.workflow_run.head_branch, 'agente/')" in cond


def test_caller_chama_o_workflow_e_repassa_so_o_que_ele_declara():
    job = _caller()["jobs"]["juntar"]
    assert job["uses"].startswith("LeoKuli/agentes-padroes/.github/workflows/juntar-so-teste.yml@")
    chamado = _gatilho(_wf())["workflow_call"]
    assert set(job["with"]) <= set(chamado["inputs"])
    assert set(job["secrets"]) == {"PORTAO_APP_KEY"} <= set(chamado["secrets"])
    assert job["secrets"]["PORTAO_APP_KEY"] == "${{ secrets.PORTAO_APP_KEY }}"
    assert job["permissions"] == {"contents": "read"}


def test_o_agente_abre_pr_com_o_titulo_e_o_autor_que_a_juncao_espera():
    """O elo entre as duas pontas: o PR que o agente abre tem de passar na regra 1 da junção."""
    import agente_openhands as ag

    texto = (RAIZ / ".github" / "workflows" / "agente-openhands.yml").read_text(encoding="utf-8")
    assert '--title "[agente:${SUFIXO}]' in texto and jt.PREFIXO_TITULO == "[agente:"
    corpo = ag.montar_corpo_pr(7, "deepseek", "m", "u", [], custo="0.01", ci_sozinho=True, custo_sdk="0.01")
    pr = {
        "user": {"login": "kuligovski-portao[bot]", "type": "Bot"},
        "title": "[agente:deepseek] algo",
        "body": corpo,
        "state": "open",
        "head": {"repo": {"full_name": "LeoKuli/x"}},
        "base": {"ref": "main"},
    }
    motivos, ficha = jt.checar_pr(pr, "LeoKuli/x", "main")
    assert motivos == [] and ficha == 7
    assert jt._RE_CUSTO.search(corpo).group(1) == "US$ 0.01"
