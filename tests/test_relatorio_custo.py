"""Testes do relatório de custo dos agentes (scripts/relatorio_custo.py), sem rede."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import agente_openhands as ag  # noqa: E402
import relatorio_custo as rc  # noqa: E402


def _comentario(**kw):
    base = {"repo": "LeoKuli/x", "ficha": "1", "modelo": "haiku", "resultado": "pr", "inicio": "2026-10-28T10:00:00Z",
            "fim": "2026-10-28T10:30:00Z", "run": "1", "usd": "0.1000"}
    base.update(kw)
    return ag.montar_registro_custo(base)


def test_o_relatorio_le_o_comentario_que_o_workflow_escreve():
    e = rc.ler_marca(_comentario(usd="0.0934", run="77"))
    assert e is not None and e.usd == 0.0934 and e.run == "77"


def test_comentario_sem_marca_e_ignorado():
    assert rc.ler_marca("PR aberto por agente") is None


def test_nao_medido_nao_entra_como_zero():
    e = rc.ler_marca(_comentario(usd=ag.NAO_MEDIDO))
    linhas = rc.resumir([e], set())
    assert linhas[0]["usd"] == 0 and linhas[0]["nao_medidas"] == 1
    assert "NÃO MEDIDO" in rc.tabela(linhas, 0)


def test_custo_por_pr_juntado():
    es = [rc.ler_marca(_comentario(run="1", usd="0.10")), rc.ler_marca(_comentario(run="2", usd="0.30", resultado="falha"))]
    linhas = rc.resumir(es, juntados={"1"})
    assert linhas[0]["usd"] == 0.4 and linhas[0]["juntados"] == 1 and linhas[0]["usd_por_juntado"] == 0.4


def test_execucoes_simultaneas_na_mesma_chave_sao_apontadas():
    a = rc.ler_marca(_comentario(run="1", inicio="2026-10-28T10:00:00Z", fim="2026-10-28T10:30:00Z"))
    b = rc.ler_marca(_comentario(run="2", inicio="2026-10-28T10:20:00Z", fim="2026-10-28T10:50:00Z"))
    c = rc.ler_marca(_comentario(run="3", inicio="2026-10-28T11:00:00Z", fim="2026-10-28T11:10:00Z"))
    assert rc.sobrepostas([a, b, c]) == {"1", "2"}
