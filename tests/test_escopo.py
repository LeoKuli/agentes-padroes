import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import escopo  # noqa: E402
from escopo import ArquivoPR, ErroFicha, ErroNaoMedido  # noqa: E402

PROT = escopo.PROTEGIDOS_PADRAO
TESTE = escopo.REGEX_TESTES_PADRAO


def arq(caminho, add=10, rem=0, status="modified", anterior=None):
    return ArquivoPR(caminho, anterior, status, add, rem)


def rodar(arquivos, permitidos=("src/**", "tests/**"), max_diff=300, protegidos=PROT):
    return escopo.verificar(list(arquivos), list(permitidos), max_diff, list(protegidos), TESTE)


# ---------------------------------------------------------------- escopo

def test_dentro_do_escopo_passa():
    r = rodar([arq("src/a.py"), arq("tests/test_a.py")])
    assert r.violacoes == []
    assert r.total_linhas == 20


def test_arquivo_fora_do_permitido_reprova():
    r = rodar([arq("src/a.py"), arq("docs/x.md"), arq("tests/test_a.py")])
    assert len(r.violacoes) == 1
    assert "docs/x.md" in r.violacoes[0] and "FORA" in r.violacoes[0]


def test_protegido_reprova_mesmo_se_permitido():
    r = rodar([arq(".github/workflows/ci.yml"), arq("tests/test_a.py")], permitidos=[".github/**", "tests/**"])
    assert any("PROTEGIDO" in v and ".github/workflows/ci.yml" in v for v in r.violacoes)
    assert not any("FORA" in v for v in r.violacoes)


@pytest.mark.parametrize(
    "caminho",
    ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS", "AGENTS.md", "sub/AGENTS.md",
     "constitution.md", ".specify/memory/constitution.md"],
)
def test_protegidos_padrao_valem_em_qualquer_nivel(caminho):
    r = rodar([arq(caminho), arq("tests/test_a.py")], permitidos=["**", "tests/**"])
    assert any("PROTEGIDO" in v for v in r.violacoes), caminho


def test_protegido_extra():
    r = rodar([arq("src/pisos.json"), arq("tests/test_a.py")], protegidos=PROT + ["**/pisos.json"])
    assert any("PROTEGIDO" in v for v in r.violacoes)


def test_limite_de_tamanho_soma_adicoes_e_remocoes():
    r = rodar([arq("src/a.py", add=200, rem=101), arq("tests/test_a.py")], max_diff=300)
    assert any("311" in v and "300" in v for v in r.violacoes)
    # no limite exato, passa
    assert rodar([arq("src/a.py", add=150, rem=100), arq("tests/test_a.py", add=50)], max_diff=300).violacoes == []


def test_sem_arquivo_de_teste_reprova():
    r = rodar([arq("src/a.py")])
    assert any("TESTE" in v for v in r.violacoes)


def test_teste_removido_nao_conta():
    r = rodar([arq("src/a.py"), arq("tests/test_a.py", add=0, rem=5, status="removed")])
    assert any("TESTE" in v for v in r.violacoes)


@pytest.mark.parametrize(
    "caminho",
    ["tests/x.py", "pkg/test/x.js", "src/__tests__/a.js", "src/a_test.go", "src/a.test.ts", "spec/a_spec.rb", "src/test_a.py"],
)
def test_padroes_de_teste_reconhecidos(caminho):
    r = rodar([arq(caminho)], permitidos=["**"])
    assert not any("TESTE" in v for v in r.violacoes), caminho


def test_renomear_protegido_para_permitido_reprova():
    r = rodar([arq("src/x.yml", status="renamed", anterior=".github/workflows/x.yml"), arq("tests/test_a.py")], permitidos=["src/**", "tests/**"])
    assert any("PROTEGIDO" in v and ".github/workflows/x.yml" in v for v in r.violacoes)


def test_renomear_de_fora_do_permitido_reprova():
    r = rodar([arq("src/x.py", status="renamed", anterior="docs/x.py"), arq("tests/test_a.py")])
    assert any("docs/x.py" in v and "FORA" in v for v in r.violacoes)


def test_regex_de_teste_invalida_e_nao_medido():
    with pytest.raises(ErroNaoMedido):
        escopo.verificar([arq("a")], ["**"], 10, [], "(")


def test_nome_de_arquivo_hostil_nao_quebra_o_markdown():
    r = rodar([arq("src/a`\n::error::x.py"), arq("tests/test_a.py")], permitidos=["tests/**"])
    assert all("\n" not in v and "`\n" not in v for v in r.violacoes)


# ---------------------------------------------------------------- globs

@pytest.mark.parametrize(
    "padrao,caminho,esperado",
    [
        ("src/**", "src/a.py", True),
        ("src/**", "src/a/b/c.py", True),
        ("src/**", "src", False),
        ("src/**", "other/src/a.py", False),
        ("src/*.py", "src/a.py", True),
        ("src/*.py", "src/sub/a.py", False),
        ("**/*.py", "a.py", True),
        ("**/*.py", "x/y/a.py", True),
        ("**/*.py", "x/y/a.js", False),
        ("src/**/test_*.py", "src/test_a.py", True),
        ("src/**/test_*.py", "src/a/b/test_a.py", True),
        ("src/**/test_*.py", "src/a/b/x.py", False),
        ("src/a?.py", "src/ab.py", True),
        ("src/a?.py", "src/abc.py", False),
        ("src/", "src/a/b.py", True),
        ("./src/**", "src/a.py", True),
        ("/src/**", "src/a.py", True),
        ("src/a.py", "src/a.py", True),
        ("src/a.py", "src/axpy", False),
        ("src/[ab].py", "src/a.py", True),
        ("src/[!ab].py", "src/a.py", False),
        ("**", "qualquer/coisa.txt", True),
    ],
)
def test_globs(padrao, caminho, esperado):
    assert bool(escopo.glob_para_regex(padrao).fullmatch(caminho)) is esperado


def test_glob_sem_barra_so_casa_na_raiz_nos_permitidos():
    assert escopo.casa("sub/README.md", ["README.md"]) is None
    assert escopo.casa("README.md", ["README.md"]) == "README.md"
    assert escopo.casa("sub/README.md", ["README.md"], em_qualquer_nivel=True) == "README.md"


# ---------------------------------------------------------------- ficha no PR

@pytest.mark.parametrize(
    "corpo,esperado",
    [
        ("Ficha: #12\n\nresto", 12),
        ("texto\r\nFicha:#7\r\n", 7),
        ("Ficha: MKT-012\n\nCloses #34", 34),
        ("Ficha: MKT-012\nFecha #5", 5),
        ("Ficha: CRM-1\nfixes #9", 9),
        ("Ficha: MKT-012", None),            # ID sem número de Issue
        ("Closes #3", None),                  # sem linha Ficha
        ("Ficha: #12 e mais coisa", None),    # a linha precisa ser só isso
        ("Ficha: MKT-012\nCloses outro/repo#3", None),
        ("", None),
        (None, None),
    ],
)
def test_numero_da_ficha(corpo, esperado):
    assert escopo.numero_da_ficha(corpo) == esperado


def test_ficha_numerica_tem_precedencia():
    assert escopo.numero_da_ficha("Ficha: #1\nCloses #2") == 1


# ---------------------------------------------------------------- corpo da Issue Form

ISSUE_BODY = """### Spec

specs/001-x/spec.md

### Nível

2

### Objetivo

Corrigir X.
### nao e secao? sim e: heading dentro do valor

### Arquivos permitidos

- `src/**`
tests/**
```
docs/extra.md
```

### Arquivos proibidos

_No response_

### Tamanho máximo do diff (linhas)

150 linhas

### Fora do escopo

nada
"""


def issue(body=ISSUE_BODY, labels=("ficha",), assoc="OWNER", **extra):
    return {"body": body, "labels": [{"name": n} for n in labels], "author_association": assoc, **extra}


def test_ler_ficha_extrai_globs_e_tamanho():
    f = escopo.ler_ficha(issue(), 5)
    assert f.permitidos == ["src/**", "tests/**", "docs/extra.md"]
    assert f.max_diff == 150
    assert f.numero == 5


def test_ler_ficha_com_crlf():
    f = escopo.ler_ficha(issue(ISSUE_BODY.replace("\n", "\r\n")), 5)
    assert f.permitidos[0] == "src/**" and f.max_diff == 150


def test_ficha_sem_permitidos_e_erro():
    corpo = "### Arquivos permitidos\n\n_No response_\n\n### Tamanho máximo do diff (linhas)\n\n300\n"
    with pytest.raises(ErroFicha, match="permitidos"):
        escopo.ler_ficha(issue(corpo), 5)


def test_ficha_sem_tamanho_e_erro():
    corpo = "### Arquivos permitidos\n\nsrc/**\n\n### Tamanho máximo do diff (linhas)\n\nmuitas\n"
    with pytest.raises(ErroFicha, match="Tamanho"):
        escopo.ler_ficha(issue(corpo), 5)


def test_issue_sem_rotulo_ficha_e_erro():
    with pytest.raises(ErroFicha, match="rótulo"):
        escopo.ler_ficha(issue(labels=("duvida",)), 5)


def test_issue_de_estranho_e_erro():
    with pytest.raises(ErroFicha, match="vínculo"):
        escopo.ler_ficha(issue(assoc="NONE"), 5)


def test_pr_citado_como_ficha_e_erro():
    with pytest.raises(ErroFicha, match="pull request"):
        escopo.ler_ficha(issue(pull_request={"url": "x"}), 5)


# ---------------------------------------------------------------- main (com gh falso)

class GhFalso:
    def __init__(self, issue_json, arquivos, falhar=False):
        self.issue_json, self.arquivos, self.falhar = issue_json, arquivos, falhar
        self.chamadas = []

    def __call__(self, args):
        self.chamadas.append(args)
        if self.falhar:
            raise ErroNaoMedido("API fora do ar")
        if args[1].startswith("repos/") and "/issues/" in args[1]:
            return json.dumps(self.issue_json)
        return "\n".join(
            json.dumps({"filename": a.caminho, "previous_filename": a.anterior, "status": a.status,
                        "additions": a.adicoes, "deletions": a.remocoes})
            for a in self.arquivos
        )


def env_base(tmp_path, corpo="Ficha: #5"):
    return {"PR_BODY": corpo, "GH_REPO": "LeoKuli/x", "PR_NUMBER": "9",
            "GITHUB_STEP_SUMMARY": str(tmp_path / "resumo.md")}


def test_main_verde(tmp_path):
    gh = GhFalso(issue(), [arq("src/a.py"), arq("tests/test_a.py")])
    assert escopo.main(env_base(tmp_path), gh) == 0
    resumo = (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert "dentro do escopo" in resumo and "#5" in resumo
    assert gh.chamadas[0] == ["api", "repos/LeoKuli/x/issues/5"]


def test_main_vermelho_lista_violacoes_em_portugues(tmp_path, capsys):
    gh = GhFalso(issue(), [arq(".github/a.yml"), arq("src/a.py", add=500)])
    assert escopo.main(env_base(tmp_path), gh) == 1
    resumo = (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert "PROTEGIDO" in resumo and "linhas alteradas" in resumo and "TESTE" in resumo
    assert "::error::" in capsys.readouterr().out


def test_main_sem_ficha_no_pr(tmp_path):
    gh = GhFalso(issue(), [])
    assert escopo.main(env_base(tmp_path, corpo="sem nada"), gh) == 1
    assert "Ficha: #" in (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert gh.chamadas == []


def test_main_falha_de_api_e_nao_medido_nunca_verde(tmp_path):
    gh = GhFalso(issue(), [], falhar=True)
    assert escopo.main(env_base(tmp_path), gh) == 1
    assert "NÃO MEDIDO" in (tmp_path / "resumo.md").read_text(encoding="utf-8")


def test_main_zero_arquivos_e_nao_medido(tmp_path):
    gh = GhFalso(issue(), [])
    assert escopo.main(env_base(tmp_path), gh) == 1
    assert "NÃO MEDIDO" in (tmp_path / "resumo.md").read_text(encoding="utf-8")


def test_main_repo_invalido(tmp_path):
    env = env_base(tmp_path)
    env["GH_REPO"] = "x; rm -rf /"
    assert escopo.main(env, GhFalso(issue(), [])) == 1


def test_main_protegidos_extra_e_regex_de_teste(tmp_path):
    env = env_base(tmp_path)
    env["PROTEGIDOS_EXTRA"] = "src/pisos.json"
    env["REGEX_TESTES"] = r"^qa/"
    gh = GhFalso(issue(ISSUE_BODY.replace("src/**", "src/**\nqa/**")), [arq("src/pisos.json"), arq("qa/a.py")])
    assert escopo.main(env, gh) == 1
    resumo = (tmp_path / "resumo.md").read_text(encoding="utf-8")
    assert "src/pisos.json" in resumo and "PROTEGIDO" in resumo
    assert "TESTE" not in resumo.split("### Violações")[1]
