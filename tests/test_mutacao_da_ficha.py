"""Conferência automática da mutação da ficha: executa o script de verdade contra projetos de brinquedo."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import escopo  # noqa: E402
import mutacao_da_ficha as mf  # noqa: E402
from mutacao_da_ficha import ErroNaoMedido, Mutacao  # noqa: E402

PY = f'"{sys.executable}"'

CODIGO = 'def f(x):\n    return x.rstrip("?&")\n'
TESTE_BOM = 'import mod\nassert mod.f("a?&") == "a"\nassert mod.f("a") == "a"\n'
TESTE_FROUXO = 'import mod\nassert mod.f("a") == "a"\n'  # não enxerga o defeito: o mutante sobrevive


def projeto(tmp_path, codigo=CODIGO, teste=TESTE_BOM, crlf=False):
    if crlf:
        codigo = codigo.replace("\n", "\r\n")
    (tmp_path / "mod.py").write_bytes(codigo.encode("utf-8"))
    (tmp_path / "check.py").write_text(teste, encoding="utf-8")
    return tmp_path


CMD = f"{PY} -B check.py"
M_OK = Mutacao("", "mod.py", '    return x.rstrip("?&")', "    return x")


# ---------------------------------------------------------------- leitura da seção

BLOCO = """- Mutação, em `assistente/orquestrador/regras.py`: trocar

```python
    return url.rstrip("?&")
```

por

```python
    return url
```

- Asserção que a mata: a igualdade com `"https://exemplo.com/p"` no caso do `&` sobrando.
- Como conferir: aplique a troca, rode `python -B -m unittest x`, veja o teste reprovar, e desfaça com
  `git checkout -- assistente/orquestrador/regras.py`. A mutação não entra no PR.
"""

INLINE = """- Mutação A: em `lib/crm/funil.ex`, `contam_sla/0`, trocar `& &1.conta_sla?` por `&(not &1.conta_sla?)`. Morre na asserção de igualdade.
- Mutação B: trocar `Enum.map(& &1.chave)` por `Enum.map(& &1.ordem)`. Morre na asserção de igualdade.
- Desfaça as duas antes do commit: `lib/` não entra no PR.
"""


def test_le_mutacao_em_bloco_de_codigo_com_a_indentacao():
    (m,) = mf.extrair_mutacoes(BLOCO)
    assert m.arquivo == "assistente/orquestrador/regras.py"
    assert m.antes == '    return url.rstrip("?&")'
    assert m.depois == "    return url"
    assert m.rotulo == ""


def test_le_mutacoes_inline_e_herda_o_arquivo_da_anterior():
    a, b = mf.extrair_mutacoes(INLINE)
    assert (a.rotulo, a.arquivo, a.antes, a.depois) == ("A", "lib/crm/funil.ex", "& &1.conta_sla?", "&(not &1.conta_sla?)")
    assert (b.rotulo, b.arquivo, b.antes, b.depois) == ("B", "lib/crm/funil.ex", "Enum.map(& &1.chave)", "Enum.map(& &1.ordem)")


def test_texto_comum_que_cita_a_palavra_mutacao_no_meio_da_linha_nao_vira_mutacao():
    assert len(mf.extrair_mutacoes(BLOCO)) == 1  # "A mutação não entra no PR." não conta


def test_primeira_mutacao_sem_arquivo_e_erro():
    with pytest.raises(ErroNaoMedido, match="não diz o arquivo"):
        mf.extrair_mutacoes("- Mutação: trocar `a` por `b`.")


def test_secao_sem_o_par_trocar_por_e_erro_e_nao_zero_mutacoes():
    with pytest.raises(ErroNaoMedido, match="trocar"):
        mf.extrair_mutacoes("- Mutação, em `x.py`: inverter a condição.")
    with pytest.raises(ErroNaoMedido, match="nenhuma"):
        mf.extrair_mutacoes("Tem de morrer o que o teste novo pega.")


def test_secao_da_mutacao_vem_da_issue_form():
    corpo = "### Objetivo\n\nx\n\n### Mutação que tem de morrer\n\n" + BLOCO + "\n### Comando de aceite\n\nmake\n"
    assert "rstrip" in mf.secao_da_mutacao(corpo)
    assert mf.secao_da_mutacao("### Objetivo\n\nx\n") is None
    assert mf.secao_da_mutacao("### Mutação que tem de morrer\n\n_No response_\n") is None


# ---------------------------------------------------------------- execução

def test_caso_bom_o_mutante_morre_e_o_controle_passa(tmp_path):
    raiz = projeto(tmp_path)
    rel = mf.executar(raiz, [M_OK], CMD)
    assert rel.ok
    assert [l.veredito for l in rel.linhas] == ["morreu"]
    assert rel.controle.ok
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO  # restaurado


def test_ancora_ausente_falha_com_mensagem_clara_e_nao_roda_nada(tmp_path):
    raiz = projeto(tmp_path)
    rel = mf.executar(raiz, [Mutacao("", "mod.py", "return outra_coisa", "return x")], CMD)
    assert not rel.ok
    assert rel.linhas[0].veredito == "ÂNCORA NÃO CASA"
    assert "NÃO aparece" in rel.linhas[0].detalhe
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO


def test_ancora_repetida_falha(tmp_path):
    codigo = "def f(x):\n    return x.strip()\n\n\ndef g(x):\n    return x.strip()\n"
    raiz = projeto(tmp_path, codigo=codigo, teste="import mod\nassert mod.f(' a ') == 'a'\n")
    rel = mf.executar(raiz, [Mutacao("", "mod.py", "return x.strip()", "return x")], CMD)
    assert not rel.ok
    assert rel.linhas[0].veredito == "ÂNCORA NÃO CASA"
    assert "2 vezes" in rel.linhas[0].detalhe
    assert (raiz / "mod.py").read_text(encoding="utf-8") == codigo


def test_ancora_que_so_repete_por_sobreposicao_tambem_falha():
    assert mf.contar("aaa", "aa") == 2
    with pytest.raises(mf.AncoraNaoCasa, match="2 vezes"):
        mf.montar_mutante("aaa", "aa", "b")


def test_mutante_que_sobrevive_falha(tmp_path):
    raiz = projeto(tmp_path, teste=TESTE_FROUXO)
    rel = mf.executar(raiz, [M_OK], CMD)
    assert not rel.ok
    assert rel.linhas[0].veredito == "SOBREVIVEU"
    assert rel.controle.ok  # a árvore boa passa; o problema é o teste fraco
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO


def test_controle_positivo_vermelho_falha_mesmo_com_mutante_morto(tmp_path):
    raiz = projeto(tmp_path, teste="import mod\nassert mod.f('a?&') == 'nunca'\n")
    rel = mf.executar(raiz, [M_OK], CMD)
    assert rel.linhas[0].veredito == "morreu"
    assert not rel.controle.ok and rel.controle.veredito == "REPROVOU"
    assert not rel.ok


def test_mutante_que_nao_compila_nao_conta_como_morto(tmp_path):
    raiz = projeto(tmp_path)
    rel = mf.executar(raiz, [Mutacao("", "mod.py", '    return x.rstrip("?&")', "    return (")], CMD)
    assert rel.linhas[0].veredito == "SUSPEITO"
    assert not rel.ok


# Saídas reais do Gradle no MyReader (29/10/2026): compilação que falha NÃO é mutante morto.
GRADLE_NAO_COMPILA = [
    "e: file:///C:/proj/core/src/main/kotlin/x/LegacyKeys.kt:33:34 Argument type mismatch: actual type is 'Long?', but 'Long' was expected.",
    "   > Compilation error. See log for more details",
    "e: Unresolved reference 'StructureCard'.",
    "> Task :core:compileKotlin FAILED",
    "> Task :app:compileDebugKotlin FAILED",
    "> Task :app:compileDebugUnitTestKotlin FAILED",
    "> Task :core:compileTestKotlin FAILED",
    "> Android resource compilation failed",
    "Execution failed for task ':app:compileReleaseKotlin'.",
]

# Teste que reprova por asserção (JUnit 5 no :core, JUnit 4 no :app): é mutante morto de verdade.
GRADLE_TESTE_REPROVA = """> Task :core:test FAILED

LegacyKeysTest > duas antigas da mesma estrutura se juntam na mais antiga() FAILED
    org.opentest4j.AssertionFailedError at LegacyKeysTest.kt:27

RotulosTest > rotulos em portugues FAILED
    java.lang.AssertionError at RotulosTest.kt:21

264 tests completed, 2 failed

FAILURE: Build failed with an exception.

* What went wrong:
Execution failed for task ':core:test'.
> There were failing tests. See the report at: file:///C:/proj/core/build/reports/tests/test/index.html

BUILD FAILED in 9s
"""


@pytest.mark.parametrize("linha", GRADLE_NAO_COMPILA)
def test_mutante_kotlin_que_nao_compila_e_suspeito(tmp_path, linha):
    raiz = projeto(tmp_path)
    resultado = mf.testar_mutacao(1, M_OK, raiz, CMD, lambda *_: (1, f"BUILD FAILED\n{linha}\n"), mf.TIMEOUT_PADRAO)
    assert resultado.veredito == "SUSPEITO", linha
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO  # restaurado


def test_teste_kotlin_que_reprova_por_assercao_continua_morto(tmp_path):
    raiz = projeto(tmp_path)
    resultado = mf.testar_mutacao(1, M_OK, raiz, CMD, lambda *_: (1, GRADLE_TESTE_REPROVA), mf.TIMEOUT_PADRAO)
    assert resultado.veredito == "morreu"  # controle: o sinal novo não engole o teste que reprova de verdade


def test_arquivo_e_restaurado_mesmo_quando_o_comando_explode(tmp_path):
    raiz = projeto(tmp_path)

    def explode(comando, cwd, timeout):
        assert "mod.py" and (raiz / "mod.py").read_text(encoding="utf-8") != CODIGO  # o mutante estava aplicado
        raise RuntimeError("falha do runner")

    with pytest.raises(RuntimeError):
        mf.executar(raiz, [M_OK], CMD, rodar=explode)
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO


def test_arquivo_e_restaurado_quando_o_tempo_estoura(tmp_path):
    raiz = projeto(tmp_path, teste="import time\ntime.sleep(30)\n")
    rel = mf.executar(raiz, [M_OK], CMD, timeout=1)
    assert rel.linhas[0].veredito == "NÃO MEDIDO" and "passou de 1s" in rel.linhas[0].detalhe
    assert rel.controle.veredito == "NÃO MEDIDO"
    assert not rel.ok
    assert (raiz / "mod.py").read_text(encoding="utf-8") == CODIGO


def test_arquivo_crlf_casa_a_ancora_da_ficha_e_volta_byte_a_byte(tmp_path):
    raiz = projeto(tmp_path, crlf=True)
    original = (raiz / "mod.py").read_bytes()
    rel = mf.executar(raiz, [Mutacao("", "mod.py", 'def f(x):\n    return x.rstrip("?&")', "def f(x):\n    return x")], CMD)
    assert rel.ok
    assert (raiz / "mod.py").read_bytes() == original


def test_trecho_com_indentacao_diferente_da_ficha_casa_aparado(tmp_path):
    raiz = projeto(tmp_path)
    rel = mf.executar(raiz, [Mutacao("", "mod.py", 'return x.rstrip("?&")', "return x")], CMD)
    assert rel.ok


def test_varias_mutacoes_cada_uma_parte_do_original(tmp_path):
    codigo = 'def f(x):\n    return x.rstrip("?&")\n\n\ndef g(x):\n    return x.lstrip("#")\n'
    teste = 'import mod\nassert mod.f("a?&") == "a"\nassert mod.g("#a") == "a"\n'
    raiz = projeto(tmp_path, codigo=codigo, teste=teste)
    ms = [M_OK, Mutacao("B", "mod.py", 'x.lstrip("#")', "x")]
    rel = mf.executar(raiz, ms, CMD)
    assert rel.ok and len(rel.linhas) == 2
    assert (raiz / "mod.py").read_text(encoding="utf-8") == codigo


@pytest.mark.parametrize("caminho", ["../fora.py", "/etc/passwd", "C:/x.py", "", "naoexiste.py", "."])
def test_caminho_fora_da_raiz_ou_inexistente_nao_e_medido(tmp_path, caminho):
    raiz = projeto(tmp_path)
    rel = mf.executar(raiz, [Mutacao("", caminho, "a", "b")], CMD)
    assert rel.linhas[0].veredito == "NÃO MEDIDO"
    assert not rel.ok


def test_o_comando_de_teste_nao_recebe_os_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "valor-que-nao-pode-vazar")
    monkeypatch.setenv("GITHUB_TOKEN", "outro-valor")
    monkeypatch.setenv("VARIAVEL_COMUM", "ok")
    (tmp_path / "env.py").write_text("import os\nprint(os.environ.get('GH_TOKEN'), os.environ.get('GITHUB_TOKEN'), os.environ.get('VARIAVEL_COMUM'))\n", encoding="utf-8")
    codigo, saida = mf.rodar_comando(f"{PY} env.py", tmp_path, 30)
    assert codigo == 0 and saida.split() == ["None", "None", "ok"]


def test_resumo_nao_deixa_a_saida_do_pr_injetar_comando_de_workflow(tmp_path):
    rel = mf.Relatorio(
        [mf.Linha(1, M_OK, False, "SOBREVIVEU", "x", "::error::falso\n```\nfim")],
        mf.Controle(True, "passou"),
    )
    md = mf.resumo(rel)
    assert "::error::" not in md and "```\n" not in md.replace("````", "")


# ---------------------------------------------------------------- main, de ponta a ponta (gh falso)

def corpo_ficha(secao=BLOCO):
    return (
        "### Objetivo\n\nx\n\n### Arquivos permitidos\n\ntests/**\n\n### Mutação que tem de morrer\n\n"
        + secao
        + "\n### Tamanho máximo do diff (linhas)\n\n40\n"
    )


def gh_falso(corpo, labels=("ficha",), assoc="OWNER"):
    issue = {"body": corpo, "labels": [{"name": n} for n in labels], "author_association": assoc}

    def gh(args):
        assert args[0] == "api" and args[1].endswith("/issues/7"), args
        return json.dumps(issue)

    return gh


def env_base(tmp_path, comando=CMD):
    return {"GH_REPO": "LeoKuli/x", "PR_BODY": "Ficha: #7", "COMANDO_TESTE": comando, "RAIZ": str(tmp_path), "GITHUB_STEP_SUMMARY": str(tmp_path / "resumo.md")}


SECAO_BRINQUEDO = '- Mutação, em `mod.py`: trocar\n\n```python\n    return x.rstrip("?&")\n```\n\npor\n\n```python\n    return x\n```\n'


def test_main_caso_bom_devolve_0_e_grava_a_tabela(tmp_path):
    projeto(tmp_path)
    rc = mf.main([], env_base(tmp_path), gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO)))
    assert rc == 0
    resumo = (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert "| 1 |" in resumo and "**morreu**" in resumo and "**passou**" in resumo


def test_main_mutante_que_sobrevive_devolve_1(tmp_path):
    projeto(tmp_path, teste=TESTE_FROUXO)
    assert mf.main([], env_base(tmp_path), gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO))) == 1
    assert "SOBREVIVEU" in (tmp_path / "resumo.md").read_text(encoding="utf-8")


def test_main_ficha_sem_secao_de_mutacao_e_nao_medido_e_falha(tmp_path):
    projeto(tmp_path)
    corpo = "### Objetivo\n\nx\n\n### Arquivos permitidos\n\ntests/**\n"
    assert mf.main([], env_base(tmp_path), gh=gh_falso(corpo)) == 1
    resumo = (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert "NÃO MEDIDO" in resumo and "Mutação que tem de morrer" in resumo


def test_main_secao_vazia_e_nao_medido(tmp_path):
    projeto(tmp_path)
    assert mf.main([], env_base(tmp_path), gh=gh_falso(corpo_ficha("_No response_\n"))) == 1


def test_main_issue_sem_rotulo_ficha_ou_de_estranho_reprova(tmp_path):
    projeto(tmp_path)
    assert mf.main([], env_base(tmp_path), gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO), labels=("bug",))) == 1
    assert mf.main([], env_base(tmp_path), gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO), assoc="NONE")) == 1


def test_main_pr_sem_ficha_ou_sem_comando_reprova(tmp_path):
    projeto(tmp_path)
    env = env_base(tmp_path)
    assert mf.main([], {**env, "PR_BODY": "sem ficha"}, gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO))) == 1
    assert mf.main([], {**env, "COMANDO_TESTE": " "}, gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO))) == 1


def test_main_falha_do_gh_e_nao_medido(tmp_path):
    projeto(tmp_path)

    def gh_fora(args):
        raise ErroNaoMedido("gh api falhou")

    assert mf.main([], env_base(tmp_path), gh=gh_fora) == 1


def test_main_aceita_ficha_e_repo_pela_linha_de_comando(tmp_path):
    projeto(tmp_path)
    env = {"GITHUB_STEP_SUMMARY": str(tmp_path / "resumo.md")}
    rc = mf.main(["--repo", "LeoKuli/x", "--ficha", "7", "--comando", CMD, "--raiz", str(tmp_path)], env, gh=gh_falso(corpo_ficha(SECAO_BRINQUEDO)))
    assert rc == 0
