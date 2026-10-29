"""Unit tests for scripts/agente_openhands.py (the guards and the prompt, no SDK needed)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agente_openhands as ag  # noqa: E402

MODELOS = json.dumps({"deepseek": "openrouter/deepseek/deepseek-chat", "qwen": "openrouter/qwen/qwen3-coder"})


def evento(**sobre):
    base = {
        "action": "labeled",
        "sender": {"login": "LeoKuli"},
        "label": {"name": "agente:deepseek"},
        "issue": {
            "number": 5,
            "title": "[FICHA] algo",
            "body": "### Objetivo\n\nfazer x",
            "author_association": "OWNER",
            "labels": [{"name": "ficha"}, {"name": "agente:deepseek"}],
        },
    }
    base.update(sobre)
    return base


def test_resolve_o_modelo_pelo_sufixo():
    assert ag.resolver_modelo("agente:deepseek", MODELOS) == ("deepseek", "openrouter/deepseek/deepseek-chat")
    assert ag.resolver_modelo("agente:qwen", MODELOS)[1] == "openrouter/qwen/qwen3-coder"


def test_sufixo_desconhecido_falha_com_mensagem_clara():
    with pytest.raises(ag.ErroAgente) as e:
        ag.resolver_modelo("agente:gpt", MODELOS)
    msg = str(e.value)
    assert "agente:gpt" in msg and "agente:deepseek" in msg and "agente:qwen" in msg


@pytest.mark.parametrize("rotulo", ["ficha", "agente:", "agente:A B", "agente:../x", "agente:UPPER", "agente:a;b"])
def test_rotulo_malformado_falha(rotulo):
    with pytest.raises(ag.ErroAgente):
        ag.resolver_modelo(rotulo, MODELOS)


@pytest.mark.parametrize("modelos", ["não é json", "[]", '{"a": 1}', '{"a": "x y"}', '{"a": "$(id)"}'])
def test_mapa_de_modelos_invalido_falha(modelos):
    with pytest.raises(ag.ErroAgente):
        ag.resolver_modelo("agente:a", modelos)


def test_evento_valido_passa():
    ag.validar_evento(evento(), "LeoKuli")


@pytest.mark.parametrize(
    "mutacao, trecho",
    [
        ({"sender": {"login": "intruso"}}, "não é o mantenedor"),
        ({"action": "opened"}, "labeled"),
        ({"issue": {"number": 5, "labels": [{"name": "outra"}], "author_association": "OWNER"}}, "rótulo `ficha`"),
        ({"issue": {"number": 5, "labels": [{"name": "ficha"}], "author_association": "NONE"}}, "papel confiável"),
        ({"issue": {"number": 5, "labels": [{"name": "ficha"}], "author_association": "OWNER", "pull_request": {}}}, "pull request"),
    ],
)
def test_evento_fora_das_travas_falha(mutacao, trecho):
    with pytest.raises(ag.ErroAgente) as e:
        ag.validar_evento(evento(**mutacao), "LeoKuli")
    assert trecho in str(e.value)


def test_prompt_traz_a_ficha_e_as_regras():
    prompt = ag.montar_prompt(evento()["issue"])
    assert "FICHA #5" in prompt and "fazer x" in prompt
    assert ".github/" in prompt and "não rode git" in prompt


def test_prompt_recusa_ficha_vazia_ou_gigante():
    with pytest.raises(ag.ErroAgente):
        ag.montar_prompt({"number": 1, "title": "t", "body": "  "})
    with pytest.raises(ag.ErroAgente):
        ag.montar_prompt({"number": 1, "title": "t", "body": "x" * (ag.TETO_PROMPT + 1)})


def test_prompt_com_chaves_no_texto_nao_quebra_o_molde():
    corpo = "usar {chave} e {0} e %s"
    assert corpo in ag.montar_prompt({"number": 2, "title": "t {x}", "body": corpo})


def test_corpo_do_pr_lista_o_que_foi_descartado():
    corpo = ag.montar_corpo_pr(3, "qwen", "m", "https://r", [".github/workflows/ci.yml"])
    assert "descartadas" in corpo and "`.github/workflows/ci.yml`" in corpo
    assert "descartadas" not in ag.montar_corpo_pr(3, "qwen", "m", "https://r", [])


def test_cli_modelo_escreve_as_saidas(tmp_path, monkeypatch):
    ev = tmp_path / "evento.json"
    ev.write_text(json.dumps(evento(label={"name": "agente:qwen"})), encoding="utf-8")
    out = tmp_path / "saida.txt"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("MAINTAINER", "LeoKuli")
    monkeypatch.setenv("MODELOS", MODELOS)
    assert ag.main(["x", "modelo"]) == 0
    assert out.read_text(encoding="utf-8").splitlines() == [
        "sufixo=qwen",
        "modelo=openrouter/qwen/qwen3-coder",
        "numero=5",
    ]


def test_cli_modelo_sufixo_desconhecido_sai_com_erro(tmp_path, monkeypatch, capsys):
    ev = tmp_path / "evento.json"
    ev.write_text(json.dumps(evento(label={"name": "agente:zzz"})), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    monkeypatch.setenv("MAINTAINER", "LeoKuli")
    monkeypatch.setenv("MODELOS", MODELOS)
    assert ag.main(["x", "modelo"]) == 1
    assert capsys.readouterr().out.startswith("::error::")


def test_rodar_sem_chave_falha_sem_importar_o_sdk(monkeypatch, capsys):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert ag.main(["x", "rodar"]) == 1
    assert "LLM_API_KEY" in capsys.readouterr().out


FICHA_OK = (
    "### Arquivos permitidos\n\ntests/test_radar_num.py\n\n"
    "### Tamanho máximo do diff (linhas)\n\n60\n"
)


def issue_ficha(corpo=FICHA_OK):
    return {"number": 4, "body": corpo, "author_association": "OWNER", "labels": [{"name": "ficha"}]}


FICHA_29 = (Path(__file__).resolve().parent / "fixtures" / "ficha_crm_oralunic_29.md").read_text(encoding="utf-8")


def _sdk_falso(monkeypatch):
    """Dublê do SDK do OpenHands (o cliente da OpenRouter): registra cada LLM criado."""
    import types

    chamadas = []

    class LLM:
        def __init__(self, **config):
            chamadas.append(config.get("model"))

    class Conversation:
        def __init__(self, **_):
            self.state = types.SimpleNamespace(execution_status="finished")
            self.conversation_stats = types.SimpleNamespace(
                get_combined_metrics=lambda: types.SimpleNamespace(accumulated_cost=0.01)
            )

        def send_message(self, _):
            pass

        def run(self):
            pass

    sdk = types.ModuleType("openhands.sdk")
    sdk.LLM, sdk.Conversation = LLM, Conversation
    preset = types.ModuleType("openhands.tools.preset.default")
    preset.get_default_agent = lambda **_: object()
    for nome, mod in {
        "openhands": types.ModuleType("openhands"),
        "openhands.sdk": sdk,
        "openhands.tools": types.ModuleType("openhands.tools"),
        "openhands.tools.preset": types.ModuleType("openhands.tools.preset"),
        "openhands.tools.preset.default": preset,
    }.items():
        monkeypatch.setitem(sys.modules, nome, mod)
    return chamadas


def _rodar(tmp_path, monkeypatch, corpo):
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"issue": issue_ficha(corpo)}), encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    monkeypatch.setenv("PROMPT_FILE", str(prompt))
    monkeypatch.setenv("LLM_API_KEY", "chave-ficticia")
    monkeypatch.setenv("LLM_MODEL", "openrouter/teste/modelo")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    chamadas = _sdk_falso(monkeypatch)
    return ag.main(["x", "rodar"]), chamadas


def test_rodar_ficha_ilegivel_para_antes_do_modelo(tmp_path, monkeypatch, capsys):
    # crm-oralunic#29 (29/10): "## " e sem tamanho máximo; o modelo rodou (US$ 0,40) e o patch foi jogado fora.
    codigo, chamadas = _rodar(tmp_path, monkeypatch, FICHA_29)
    saida = capsys.readouterr().out
    assert codigo == 1
    assert chamadas == [], "o cliente da OpenRouter não pode ser chamado com ficha ilegível"
    assert "::error::ficha ilegível" in saida and "###" in saida


def test_rodar_ficha_legivel_chama_o_modelo(tmp_path, monkeypatch):
    """Controle positivo: a mesma ficha com "### " chega ao modelo."""
    codigo, chamadas = _rodar(tmp_path, monkeypatch, FICHA_OK)
    assert codigo == 0
    assert chamadas == ["openrouter/teste/modelo"]


def test_prompt_de_ficha_ilegivel_nao_e_gravado(tmp_path, monkeypatch, capsys):
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"issue": issue_ficha(FICHA_29)}), encoding="utf-8")
    prompt = tmp_path / "prompt.txt"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    monkeypatch.setenv("PROMPT_FILE", str(prompt))
    assert ag.main(["x", "prompt"]) == 1
    assert not prompt.exists()
    assert "::error::ficha ilegível" in capsys.readouterr().out
    # controle positivo: com "### " o prompt é gravado
    ev.write_text(json.dumps({"issue": issue_ficha()}), encoding="utf-8")
    assert ag.main(["x", "prompt"]) == 0
    assert prompt.exists()


def test_fora_da_ficha_descarta_o_lixo_e_mantem_o_permitido():
    # Caso real 17/10 (video-edicao #7): o kimi gravou a saída de um `git diff` num arquivo "tatus --short".
    fora = ag.fora_da_ficha(issue_ficha(), ["tests/test_radar_num.py", "tatus --short", "radar/coleta.py", ""])
    assert fora == ["tatus --short", "radar/coleta.py"]


def test_fora_da_ficha_controle_positivo_tudo_permitido():
    assert ag.fora_da_ficha(issue_ficha(), ["tests/test_radar_num.py"]) == []


def test_fora_da_ficha_ilegivel_falha_fechado():
    with pytest.raises(ag.ErroAgente):
        ag.fora_da_ficha(issue_ficha("### Objetivo\n\nsem seções de escopo"), ["qualquer.py"])


def test_cli_fora_da_ficha_le_e_escreve_separado_por_nul(tmp_path, monkeypatch, capsysbinary):
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"issue": issue_ficha()}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(ev))
    import io

    entrada = io.TextIOWrapper(io.BytesIO("tests/test_radar_num.py\0tatus --short\0".encode()), encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", entrada)
    assert ag.main(["x", "fora-da-ficha"]) == 0
    assert capsysbinary.readouterr().out == b"tatus --short\0"


def test_corpo_do_pr_traz_o_custo_e_o_que_saiu_da_ficha():
    corpo = ag.montar_corpo_pr(3, "kimi", "m", "https://r", [], ["tatus --short"], "0.29")
    assert "US$ 0.29" in corpo
    assert "`tatus --short`" in corpo and "FORA dos permitidos" in corpo
    sem = ag.montar_corpo_pr(3, "kimi", "m", "https://r", [])
    assert "NÃO MEDIDO" in sem and "FORA dos permitidos" not in sem


# ---------------------------------------------------------------- custo medido (28/10/2026)


def test_uso_da_chave_le_o_gasto_do_openrouter():
    assert ag.uso_da_chave({"data": {"usage": 7.19, "limit": 50}}) == 7.19
    assert ag.uso_da_chave({"data": {"usage": 0}}) == 0.0


def test_uso_da_chave_sem_numero_e_nao_medido():
    for resposta in ({}, {"data": {}}, {"data": {"usage": None}}, {"data": {"usage": "7"}}, {"data": {"usage": True}}, {"data": {"usage": -1}}, []):
        assert ag.uso_da_chave(resposta) is None


def test_custo_medido_e_a_diferenca_do_gasto():
    assert ag.custo_medido("7.100000", "7.193400") == "0.0934"
    assert ag.custo_medido("2", "2") == "0.0000"


def test_custo_sem_medicao_nunca_vira_zero():
    assert ag.custo_medido(ag.NAO_MEDIDO, "7.19") == ag.NAO_MEDIDO
    assert ag.custo_medido("7.19", "") == ag.NAO_MEDIDO
    assert ag.custo_medido("7.19", "7.10") == ag.NAO_MEDIDO


def test_registro_de_custo_tem_marca_legivel_por_maquina():
    texto = ag.montar_registro_custo(
        {"repo": "LeoKuli/x", "ficha": "62", "modelo": "m", "resultado": "pr", "inicio": "a", "fim": "b", "run": "1", "usd": "0.0934"}
    )
    assert "US$ 0.0934" in texto
    marca = re.search(r"<!-- custo-agente v1 (\{.*\}) -->", texto)
    assert marca is not None
    assert json.loads(marca.group(1))["usd"] == "0.0934"


def test_registro_sem_medicao_diz_nao_medido():
    texto = ag.montar_registro_custo({"usd": ag.NAO_MEDIDO, "modelo": "m"})
    assert "**NÃO MEDIDO**" in texto
    assert "US$" not in texto.split("\n")[0]
