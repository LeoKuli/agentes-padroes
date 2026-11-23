"""O verificador de conformidade reprova o que tem de reprovar (com controle positivo)."""
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import adotar_padrao  # noqa: E402
import conformidade  # noqa: E402

HOJE = dt.date(2026, 11, 23)


def _repo_bom(p: Path) -> Path:
    (p / "docs" / "decisoes").mkdir(parents=True)
    (p / "scripts").mkdir()
    (p / "AGENTS.md").write_text("# AGENTS.md — x\nconteúdo real\n", encoding="utf-8")
    (p / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (p / "docs" / "ESTADO.md").write_text("# Estado\n\nAtualizado em: 2026-11-20\n", encoding="utf-8")
    (p / "docs" / "decisoes" / "0001-usar-x.md").write_text("---\nstatus: aceito\ndate: 2026-11-23\n---\n# X\n",
                                                            encoding="utf-8")
    (p / "scripts" / "verificar").write_text("#!/usr/bin/env bash\npytest\n", encoding="utf-8")
    return p


def _falhas(p: Path, dias=30):
    return [m for ok, m in conformidade.verificar(p, dias, HOJE) if not ok]


def test_controle_positivo_repo_bom_aprova(tmp_path):
    assert _falhas(_repo_bom(tmp_path)) == []


def test_sem_agents_reprova(tmp_path):
    p = _repo_bom(tmp_path)
    (p / "AGENTS.md").unlink()
    assert any("AGENTS.md ausente" in f for f in _falhas(p))


def test_estado_vencido_reprova_e_no_limite_aprova(tmp_path):
    p = _repo_bom(tmp_path)
    assert _falhas(p, dias=3) == []          # 20/11 -> 23/11 = 3 dias: no limite, aprova
    falhas = _falhas(p, dias=2)
    assert len(falhas) == 1 and "vencido: 3 dias" in falhas[0]


def test_estado_sem_data_ou_futuro_reprova(tmp_path):
    p = _repo_bom(tmp_path)
    (p / "docs" / "ESTADO.md").write_text("# Estado\nsem data\n", encoding="utf-8")
    assert any("Atualizado em" in f for f in _falhas(p))
    (p / "docs" / "ESTADO.md").write_text("Atualizado em: 2027-01-01\n", encoding="utf-8")
    assert any("futuro" in f for f in _falhas(p))


@pytest.mark.parametrize("arquivo", ["AGENTS.md", "docs/ESTADO.md", "scripts/verificar"])
def test_preencher_sobrando_reprova(tmp_path, arquivo):
    p = _repo_bom(tmp_path)
    alvo = p / arquivo
    alvo.write_text(alvo.read_text(encoding="utf-8") + "\nPREENCHER: algo\n", encoding="utf-8")
    assert any("PREENCHER" in f for f in _falhas(p))


def test_adr_sem_status_ou_ausente_reprova(tmp_path):
    p = _repo_bom(tmp_path)
    adr = p / "docs" / "decisoes" / "0001-usar-x.md"
    adr.write_text("# X sem frontmatter\nstatus: aceito\n", encoding="utf-8")  # status fora do frontmatter
    assert any("ADR sem status" in f for f in _falhas(p))
    adr.write_text("---\nstatus: talvez\n---\n", encoding="utf-8")
    assert any("ADR sem status" in f for f in _falhas(p))
    adr.write_text("---\nstatus: substituído por 0002\n---\n", encoding="utf-8")
    assert _falhas(p) == []
    adr.unlink()
    assert any("nenhum ADR" in f for f in _falhas(p))


def test_claude_md_sem_ponteiro_reprova(tmp_path):
    p = _repo_bom(tmp_path)
    (p / "CLAUDE.md").write_text("instruções só para um modelo\n", encoding="utf-8")
    assert any("CLAUDE.md existe sem @AGENTS.md" in f for f in _falhas(p))


def test_makefile_verificar_vale_como_comando_unico(tmp_path):
    p = _repo_bom(tmp_path)
    (p / "scripts" / "verificar").unlink()
    assert any("sem comando único" in f for f in _falhas(p))
    (p / "Makefile").write_text("verificar: \n\tpytest\n", encoding="utf-8")
    assert _falhas(p) == []


def test_mcp_com_segredo_literal_reprova(tmp_path):
    p = _repo_bom(tmp_path)
    (p / ".mcp.json").write_text(json.dumps({"mcpServers": {"x": {"command": "x", "env": {"TOKEN": "${TOKEN}"}}}}),
                                 encoding="utf-8")
    assert _falhas(p) == []
    (p / ".mcp.json").write_text(json.dumps({"mcpServers": {"x": {"env": {"TOKEN": "abc123"}}}}), encoding="utf-8")
    assert any("valor literal" in f for f in _falhas(p))


def test_main_codigo_de_saida(tmp_path, capsys):
    p = _repo_bom(tmp_path)
    assert conformidade.main(["--raiz", str(p), "--hoje", "2026-11-23"]) == 0
    assert conformidade.main(["--raiz", str(p), "--hoje", "2027-11-23"]) == 1
    assert "REPROVADO" in capsys.readouterr().out


# ---------- adotar-padrao ----------

def test_adotar_cria_kit_e_modelo_cru_reprova(tmp_path):
    res = dict((d, s) for s, d in adotar_padrao.adotar(tmp_path, "proj"))
    assert res["AGENTS.md"] == "criado" and res["docs/ESTADO.md"] == "criado"
    assert res[".devcontainer/devcontainer.json"] == "pulado"
    assert "proj" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "{{NOME}}" not in (tmp_path / "docs" / "ESTADO.md").read_text(encoding="utf-8")
    # o modelo cru não passa: sobram PREENCHER e não há ADR
    falhas = _falhas(tmp_path)
    assert any("AGENTS.md ainda tem" in f for f in falhas)
    assert any("nenhum ADR" in f for f in falhas)
    # os ponteiros do kit já nascem conformes
    assert not any("CLAUDE.md" in f or "GEMINI.md" in f or "copilot" in f or ".mcp.json" in f for f in falhas)


def test_adotar_nao_sobrescreve(tmp_path):
    (tmp_path / "AGENTS.md").write_text("meu conteúdo\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("antigo\n", encoding="utf-8")
    res = dict((d, s) for s, d in adotar_padrao.adotar(tmp_path, "proj"))
    assert res["AGENTS.md"] == "mantido" and res["CLAUDE.md"] == "mantido"
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "meu conteúdo\n"
    assert any("CLAUDE.md já existia" in a for a in adotar_padrao.avisos(tmp_path))
    # segunda passada: tudo mantido, nada criado
    assert all(s != "criado" for s, _ in adotar_padrao.adotar(tmp_path, "proj"))


def test_adotar_simular_nao_escreve(tmp_path):
    res = adotar_padrao.adotar(tmp_path, "proj", simular=True)
    assert any(s == "criado" for s, _ in res)
    assert list(tmp_path.iterdir()) == []


def test_adotar_devcontainer_opcional(tmp_path):
    adotar_padrao.adotar(tmp_path, "proj", devcontainer=True)
    dados = json.loads((tmp_path / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
    assert dados["name"] == "proj"


def test_kit_aponta_para_arquivos_que_existem():
    for origem, _, _ in adotar_padrao.KIT:
        assert (adotar_padrao.RAIZ_KIT / origem).is_file(), origem


def test_o_proprio_padroes_e_conforme():
    """Controle sobre o próprio repositório: o agentes-padroes adota o kit que exige dos outros."""
    falhas = [m for ok, m in conformidade.verificar(RAIZ, 3650, dt.date.today()) if not ok]
    assert falhas == []


def test_workflow_conformidade_valido():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((RAIZ / ".github" / "workflows" / "conformidade.yml").read_text(encoding="utf-8"))
    gatilho = doc.get("on", doc.get(True))
    assert gatilho["workflow_call"]["inputs"]["dias-maximos"]["default"] == 30
    chamador = yaml.safe_load((RAIZ / "templates" / "conformidade-caller.yml").read_text(encoding="utf-8"))
    assert chamador["jobs"]["conformidade"]["uses"].startswith("LeoKuli/agentes-padroes/.github/workflows/conformidade.yml@")


def test_iniciar_projeto_limpa_o_kit(tmp_path):
    """Repositório criado pelo template: iniciar-projeto deixa só o kit adotado."""
    copia = tmp_path / "novo"
    shutil.copytree(RAIZ, copia, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    import iniciar_projeto  # noqa: E402
    iniciar_projeto.iniciar(copia, "novo", forcar=True)
    assert not (copia / "templates").exists() and not (copia / "tests").exists()
    assert (copia / "AGENTS.md").is_file() and (copia / "scripts" / "verificar").is_file()
    assert "novo" in (copia / "AGENTS.md").read_text(encoding="utf-8")
    assert not (copia / "docs" / "decisoes" / "0001-agents-md-fonte-unica.md").exists()
    assert sorted(p.name for p in (copia / ".github" / "workflows").iterdir()) == ["conformidade.yml"]
