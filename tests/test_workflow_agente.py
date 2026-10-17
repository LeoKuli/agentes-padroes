"""O workflow do agente OpenHands, o chamador e o script precisam concordar entre si."""
import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import agente_openhands as ag  # noqa: E402
import escopo  # noqa: E402

yaml = pytest.importorskip("yaml")


def _carregar(*partes):
    return yaml.safe_load(RAIZ.joinpath(*partes).read_text(encoding="utf-8"))


def _wf():
    return _carregar(".github", "workflows", "agente-openhands.yml")


def _gatilho(doc):
    return doc.get("on", doc.get(True))  # PyYAML lê `on` como True


def test_workflow_e_reutilizavel_com_as_entradas_combinadas():
    call = _gatilho(_wf())["workflow_call"]
    assert {"maintainer", "modelos", "max_iterations", "timeout_minutes", "base_branch", "sdk_version"} <= set(call["inputs"])
    assert call["inputs"]["maintainer"]["default"] == "LeoKuli"
    assert set(json.loads(call["inputs"]["modelos"]["default"])) == {"deepseek", "qwen"}
    assert call["secrets"]["LLM_API_KEY"]["required"] is True
    assert call["secrets"]["LLM_BASE_URL"]["required"] is False
    assert not [n for n in call["secrets"] if "PAT" in n.replace("PADROES", "")], "nenhum PAT"
    # a versão do SDK vem fixa (nunca @main nem faixa)
    assert re.fullmatch(r"\d+\.\d+\.\d+", call["inputs"]["sdk_version"]["default"])


def test_job_so_roda_com_as_travas():
    job = _wf()["jobs"]["agente"]
    cond = " ".join(str(job["if"]).split())
    assert "github.event.action == 'labeled'" in cond
    assert "startsWith(github.event.label.name, 'agente:')" in cond
    assert "contains(github.event.issue.labels.*.name, 'ficha')" in cond
    assert "github.event.sender.login == inputs.maintainer" in cond
    assert "inputs.timeout_minutes" in str(job["timeout-minutes"])


def test_so_o_agente_escolhe_o_runner_e_o_padrao_e_o_github():
    wf = _wf()
    for nome, job in wf["jobs"].items():
        if nome == "agente":
            assert job["runs-on"] == "${{ fromJSON(inputs.runner) }}"
        else:  # publicar/avisar têm token com escrita: sempre no GitHub, nunca na bancada
            assert job["runs-on"] == "ubuntu-latest", nome
    entrada = _gatilho(wf)["workflow_call"]["inputs"]["runner"]
    assert json.loads(entrada["default"]) == "ubuntu-latest"


def test_quem_roda_o_agente_nao_escreve_e_quem_escreve_nao_roda_o_agente():
    jobs = _wf()["jobs"]
    assert jobs["agente"]["permissions"] == {"contents": "read"}
    assert jobs["publicar"]["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write"}
    assert "agente_openhands.py\" rodar" not in yaml.safe_dump(jobs["publicar"])
    assert "persist-credentials" in yaml.safe_dump(jobs["agente"])
    for passo in jobs["agente"]["steps"]:
        if passo.get("uses", "").startswith("actions/checkout"):
            assert passo["with"].get("persist-credentials") is False, passo.get("name")


def test_texto_nao_confiavel_nunca_e_interpolado_num_run():
    """Título, corpo e rótulo da Issue chegam por env, nunca dentro do script do passo."""
    proibido = re.compile(r"\$\{\{\s*(github\.event\.(issue|comment|label|pull_request)\.(title|body|name)|inputs\.modelos)")
    for nome, job in _wf()["jobs"].items():
        for passo in job["steps"]:
            assert not proibido.search(passo.get("run", "")), f"{nome}: {passo.get('name')}"


def test_actions_de_terceiros_fixadas_por_sha():
    for job in _wf()["jobs"].values():
        for passo in job["steps"]:
            if "uses" in passo:
                assert re.search(r"@[0-9a-f]{40}$", passo["uses"]), passo["uses"]


def test_comentario_do_pr_e_o_texto_combinado():
    texto = ag.montar_comentario_pr("qwen", "openrouter/qwen/qwen3-coder")
    assert texto == (
        "PR aberto por agente (modelo openrouter/qwen/qwen3-coder, rótulo `agente:qwen`). A checagem NÃO roda sozinha: "
        "o mantenedor revisa o diff, em especial .github/, e fecha/reabre o PR para disparar o CI."
    )


def test_corpo_do_pr_passa_no_verificador_de_ficha_e_no_ficha_yml():
    corpo = ag.montar_corpo_pr(7, "deepseek", "m", "u", [".github/workflows/x.yml"])
    assert escopo._RE_FICHA_NUM.search(corpo).group(1) == "7"
    padrao = _gatilho(_carregar(".github", "workflows", "ficha.yml"))["workflow_call"]["inputs"]["pattern"]["default"]
    assert re.search(rf"^Ficha:\s*({padrao})\s*$", corpo.replace("\r", ""), re.MULTILINE)


def test_o_workflow_chama_so_subcomandos_que_o_script_tem():
    texto = (RAIZ / ".github" / "workflows" / "agente-openhands.yml").read_text(encoding="utf-8")
    usados = set(re.findall(r"agente_openhands\.py\"? (\S+)", texto))
    assert usados <= set(ag.COMANDOS), usados - set(ag.COMANDOS)
    assert {"modelo", "prompt", "rodar", "pr-corpo", "pr-comentario"} <= usados


def test_caller_chama_o_workflow_com_o_gatilho_certo():
    doc = _carregar("templates", "agente-openhands-caller.yml")
    assert _gatilho(doc) == {"issues": {"types": ["labeled"]}}
    job = doc["jobs"]["agente"]
    assert job["uses"].startswith("LeoKuli/agentes-padroes/.github/workflows/agente-openhands.yml@")
    assert set(json.loads(job["with"]["modelos"])) == {"deepseek", "qwen"}
    assert "LLM_API_KEY" in job["secrets"]
    assert doc["permissions"] == {"contents": "write", "pull-requests": "write", "issues": "write"}
    # todo input que o chamador passa existe no workflow chamado
    assert set(job["with"]) <= set(_gatilho(_wf())["workflow_call"]["inputs"])
