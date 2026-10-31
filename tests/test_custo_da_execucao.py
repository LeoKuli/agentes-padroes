"""30/10/2026: o custo de uma execucao de agente. A diferenca do gasto da chave OpenRouter atrasa (o contador atualiza
depois) e mistura execucoes simultaneas na mesma chave; so vale como custo DESTA execucao quando bate com a estimativa
do SDK. Os numeros sao os medidos nos logs de 30/10. Cada teste executa o modulo real e traz o controle positivo."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import agente_openhands as ag  # noqa: E402


def test_caso_de_30_10_contador_atrasado_e_nao_medido():
    # MAN-105: o SDK estimou US$ 0,46 e a chave leu o mesmo valor antes e depois; o PR dizia "US$ 0.0000"
    r = ag.custo_da_execucao("12.457535", "12.457535", "0.4609547")
    assert r == {"chave": ag.NAO_MEDIDO, "sdk": "0.4610", "rotulo": "nao_medido"}
    # controle positivo: com o contador ja atualizado, a mesma execucao bate com o SDK
    assert ag.custo_da_execucao("12.457535", "12.918490", "0.4609547")["rotulo"] == "execucao"


def test_janela_sobreposta_nao_e_atribuida_a_execucao():
    # MYR-071: a chave subiu 0,42 numa execucao que o SDK estima em 0,016 (a MYR-072 rodou junto)
    r = ag.custo_da_execucao("12.085598", "12.504986", "0.016323087")
    assert r == {"chave": "0.4194", "sdk": "0.0163", "rotulo": "janela"}
    # controle positivo: MYR-077, sozinha na chave, bate com o SDK
    assert ag.custo_da_execucao("13.609355", "13.825079", "0.253473")["rotulo"] == "execucao"


def test_sem_estimativa_do_sdk_a_chave_nao_e_atribuida():
    assert ag.custo_da_execucao("1.0", "1.5", ag.NAO_MEDIDO) == {"chave": "0.5000", "sdk": ag.NAO_MEDIDO, "rotulo": "janela"}
    # controle positivo: com o SDK proximo, e desta execucao
    assert ag.custo_da_execucao("1.0", "1.5", "0.48")["rotulo"] == "execucao"


def test_modelo_nao_chamado_custa_zero_e_o_resto_nunca():
    assert ag.custo_da_execucao("2", "2", "0") == {"chave": "0.0000", "sdk": "0.0000", "rotulo": "execucao"}
    assert ag.custo_da_execucao("2", "2", "0.15")["chave"] == ag.NAO_MEDIDO, "chamou o modelo: zero e NAO MEDIDO"


def test_corpo_do_pr_traz_as_duas_medidas_com_o_rotulo_certo():
    corpo = ag.montar_corpo_pr(3, "sonnet", "m", "https://r", [], custo="0.4194", custo_sdk="0.0163", custo_rotulo="janela")
    assert "Estimativa do SDK (não é fatura): US$ 0.0163" in corpo
    assert "US$ 0.4194 na janela da execução, não atribuível" in corpo
    assert "Custo estimado pelo SDK" not in corpo, "o rotulo antigo chamava a chave de estimativa do SDK"
    # controle positivo: quando bate, o PR diz que e desta execucao
    bate = ag.montar_corpo_pr(3, "sonnet", "m", "https://r", [], custo="0.2157", custo_sdk="0.2535", custo_rotulo="execucao")
    assert "US$ 0.2157, desta execução" in bate


def test_comando_custo_escreve_a_saida_do_workflow(tmp_path, monkeypatch):
    saida = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(saida))
    monkeypatch.setenv("USO_ANTES", "12.457535")
    monkeypatch.setenv("USO_DEPOIS", "12.457535")
    monkeypatch.setenv("CUSTO_SDK", "0.4609547")
    assert ag.main(["x", "custo"]) == 0
    assert saida.read_text(encoding="utf-8").splitlines() == ["custo=", "custo_sdk=0.4610", "custo_rotulo=nao_medido"]
    # controle positivo: com medida que bate, o custo sai preenchido
    saida.unlink()
    monkeypatch.setenv("USO_DEPOIS", "12.918490")
    assert ag.main(["x", "custo"]) == 0
    assert saida.read_text(encoding="utf-8").splitlines() == ["custo=0.4610", "custo_sdk=0.4610", "custo_rotulo=execucao"]


def test_registro_so_conta_a_chave_quando_ela_bate(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setenv("USO_ANTES", "12.085598")
    monkeypatch.setenv("USO_DEPOIS", "12.504986")
    monkeypatch.setenv("CUSTO_SDK", "0.016323087")
    assert ag.main(["x", "registro-custo"]) == 0
    marca = json.loads(re.search(r"<!-- custo-agente v1 (\{.*\}) -->", capsys.readouterr().out).group(1))
    assert marca["usd"] == ag.NAO_MEDIDO, "janela sobreposta: o relatorio nao soma"
    assert (marca["usd_chave"], marca["sdk_usd"], marca["rotulo"]) == ("0.4194", "0.0163", "janela")
    # controle positivo: quando bate, o relatorio soma o valor da chave
    monkeypatch.setenv("USO_ANTES", "13.609355")
    monkeypatch.setenv("USO_DEPOIS", "13.825079")
    monkeypatch.setenv("CUSTO_SDK", "0.253473")
    assert ag.main(["x", "registro-custo"]) == 0
    marca = json.loads(re.search(r"<!-- custo-agente v1 (\{.*\}) -->", capsys.readouterr().out).group(1))
    assert marca["usd"] == "0.2157"
