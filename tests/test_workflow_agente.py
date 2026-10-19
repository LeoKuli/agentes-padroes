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
            assert job["runs-on"] == "ubuntu-24.04", nome
    entrada = _gatilho(wf)["workflow_call"]["inputs"]["runner"]
    assert json.loads(entrada["default"]) == "ubuntu-24.04"


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
    # todo segredo que o chamador repassa existe no workflow chamado
    assert set(job["secrets"]) <= set(_gatilho(_wf())["workflow_call"]["secrets"])


# ---------------------------------------------------------------- token do app (o CI dispara sozinho)

APP_ID = 5363413


def _passo_do_app(job):
    achados = [p for p in job["steps"] if str(p.get("uses", "")).startswith("actions/create-github-app-token@")]
    assert len(achados) == 1, "o token do app é gerado uma única vez, no job publicar"
    return achados[0]


def test_chave_do_app_e_segredo_opcional_do_workflow_call():
    call = _gatilho(_wf())["workflow_call"]
    assert call["secrets"]["PORTAO_APP_KEY"]["required"] is False  # sem ela, cai para o GITHUB_TOKEN
    caller = _carregar("templates", "agente-openhands-caller.yml")["jobs"]["agente"]["secrets"]
    assert caller["PORTAO_APP_KEY"] == "${{ secrets.PORTAO_APP_KEY }}"


def test_token_do_app_so_existe_no_job_publicar():
    jobs = _wf()["jobs"]
    for nome in ("agente", "avisar"):
        texto = yaml.safe_dump(jobs[nome])
        assert "create-github-app-token" not in texto, nome
        assert "PORTAO_APP_KEY" not in texto, nome
        assert "steps.app" not in texto, nome
    passo = _passo_do_app(jobs["publicar"])
    assert passo["with"]["app-id"] == APP_ID
    assert passo["with"]["private-key"] == "${{ secrets.PORTAO_APP_KEY }}"
    assert re.search(r"@[0-9a-f]{40}$", passo["uses"])


def test_token_do_app_tem_permissoes_minimas_e_nunca_workflows():
    com = _passo_do_app(_wf()["jobs"]["publicar"])["with"]
    permissoes = {k: v for k, v in com.items() if k.startswith("permission-")}
    assert permissoes == {
        "permission-contents": "write",
        "permission-pull-requests": "write",
        "permission-issues": "write",
    }
    assert "permission-workflows" not in com  # o app não altera .github/workflows


def test_sem_a_chave_o_passo_do_app_e_pulado_e_o_fluxo_cai_para_o_github_token():
    job = _wf()["jobs"]["publicar"]
    passo = _passo_do_app(job)
    assert passo["if"] == "env.TEM_CHAVE_APP == 'true'"
    # a chave nunca entra no ambiente: o job só guarda se ela veio
    assert job["env"] == {"TEM_CHAVE_APP": "${{ secrets.PORTAO_APP_KEY != '' }}"}
    # o checkout (que fixa a credencial do push) e o gh usam o do app, com o GITHUB_TOKEN de reserva
    usa_app = "${{ steps.app.outputs.token || github.token }}"
    checkout_repo = [p for p in job["steps"] if p.get("with", {}).get("path") == "repo"][0]
    assert checkout_repo["with"]["token"] == usa_app
    abrir_pr = [p for p in job["steps"] if p.get("name", "").startswith("Commitar, empurrar")][0]
    assert abrir_pr["env"]["GH_TOKEN"] == usa_app
    assert abrir_pr["env"]["CI_SOZINHO"] == "${{ steps.app.outputs.token != '' }}"
    # a mensagem do fallback continua dizendo que o CI não roda sozinho
    assert "O CI não roda sozinho" in abrir_pr["run"]
    assert "O CI roda sozinho" in abrir_pr["run"]


def test_o_app_vem_antes_de_qualquer_checkout_do_job_publicar():
    passos = _wf()["jobs"]["publicar"]["steps"]
    posicao_app = next(i for i, p in enumerate(passos) if str(p.get("uses", "")).startswith("actions/create-github-app-token"))
    primeiro_checkout = next(i for i, p in enumerate(passos) if str(p.get("uses", "")).startswith("actions/checkout"))
    assert posicao_app < primeiro_checkout


def test_texto_do_pr_muda_conforme_o_ci_dispare_sozinho():
    sem = ag.montar_corpo_pr(7, "deepseek", "m", "u", [])
    com = ag.montar_corpo_pr(7, "deepseek", "m", "u", [], ci_sozinho=True)
    assert "o CI **não** roda sozinho" in sem and "fecha/reabre" in sem
    assert "o CI roda sozinho" in com and "fecha/reabre" not in com and "GITHUB_TOKEN" not in com
    assert escopo._RE_FICHA_NUM.search(com).group(1) == "7"  # a linha da ficha não muda
    assert "NÃO roda sozinha" in ag.montar_comentario_pr("qwen", "m")
    assert "o CI roda sozinho" in ag.montar_comentario_pr("qwen", "m", ci_sozinho=True)


def test_comandos_leem_ci_sozinho_do_ambiente(monkeypatch, capsys):
    monkeypatch.setenv("SUFIXO", "qwen")
    monkeypatch.setenv("MODELO", "m")
    for valor, esperado in (("true", True), ("TRUE", True), ("false", False), ("", False)):
        monkeypatch.setenv("CI_SOZINHO", valor)
        ag.cmd_pr_comentario()
        assert ("o CI roda sozinho" in capsys.readouterr().out) is esperado, valor
    monkeypatch.delenv("CI_SOZINHO")
    ag.cmd_pr_comentario()
    assert "NÃO roda sozinha" in capsys.readouterr().out


def test_a_instalacao_do_sdk_usa_o_arquivo_de_restricoes_com_litellm_e_mcp_fixos():
    """18/10/2026: litellm 1.106.0 + mcp 1.30.0 quebrou o agente (ImportError CacheableResult)."""
    passos = {p.get("name", ""): p for p in _wf()["jobs"]["agente"]["steps"]}
    run = passos["Instalar o OpenHands SDK (versão fixa)"]["run"]
    linha = next(l for l in run.splitlines() if "pip install" in l and not l.lstrip().startswith("#"))
    assert "-c _padroes/constraints/agente-openhands.txt" in linha
    restricoes = (RAIZ / "constraints" / "agente-openhands.txt").read_text(encoding="utf-8")
    fixos = {l.split("==")[0]: l.split("==")[1] for l in restricoes.splitlines() if "==" in l and not l.startswith("#")}
    assert set(fixos) == {"litellm", "mcp"}
    assert all(re.fullmatch(r"\d+\.\d+\.\d+", v) for v in fixos.values())
