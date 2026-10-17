"""Unit tests for scripts/agente_openhands.py (the guards and the prompt, no SDK needed)."""
import json
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
