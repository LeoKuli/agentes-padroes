"""Junção automática de PR de agente cuja ficha é só de teste: cada regra tem o seu caso que reprova."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import escopo  # noqa: E402
import juntar_so_teste as jt  # noqa: E402

REPO = "LeoKuli/exemplo"
RE_TESTE = re.compile(escopo.REGEX_TESTES_PADRAO)
SHA = "a" * 40
OBRIGATORIOS = ["pronto", "ficha / ficha", "segredos / gitleaks"]


def _ficha(permitidos="tests/**", autor="OWNER", rotulos=("ficha",), max_diff=200):
    return {
        "number": 7,
        "author_association": autor,
        "labels": [{"name": r} for r in rotulos],
        "body": f"### Arquivos permitidos\n\n{permitidos}\n\n### Tamanho máximo do diff\n\n{max_diff}\n",
    }


def _pr(**mudancas):
    base = {
        "number": 9,
        "state": "open",
        "merged": False,
        "draft": False,
        "title": "[agente:deepseek] cobre o relogio",
        "body": "Ficha: #7\n\nCloses #7\n\nCusto estimado pelo SDK: US$ 0.0123\n",
        "user": {"login": "kuligovski-portao[bot]", "type": "Bot"},
        "head": {"sha": SHA, "repo": {"full_name": REPO}},
        "base": {"ref": "main"},
        "mergeable": True,
        "mergeable_state": "blocked",
        "labels": [],
    }
    base.update(mudancas)
    return base


def _check(nome, conclusao="success", status="completed"):
    return {"name": nome, "status": status, "conclusion": conclusao if status == "completed" else None}


class FakeGh:
    """Dublê do `gh`: responde as leituras com os dados do cenário e GRAVA as escritas."""

    def __init__(self):
        self.pr = _pr()
        self.issue = _ficha()
        self.arquivos = [("tests/test_relogio.py", "added", 30, 0)]
        self.latest = [_check(n) for n in ("pronto", "ficha / ficha", "segredos / gitleaks", "escopo / escopo")]
        self.todos = None  # None = igual a latest
        self.status = []
        self.branch = {"protected": True, "protection": {"required_status_checks": {"contexts": list(OBRIGATORIOS)}}}
        self.abertos = []
        self.falha_na_escrita = {}  # prefixo do comando -> mensagem de erro
        self.escritas = []
        self.leituras = []

    def __call__(self, args):
        if args[0] == "api":
            return self._ler(args)
        return self._escrever(args)

    def _ler(self, args):
        caminho = next(a for a in args if a.startswith("repos/"))
        self.leituras.append(caminho)
        if caminho == f"repos/{REPO}/pulls/9":
            return json.dumps(self.pr)
        if caminho == f"repos/{REPO}/issues/7":
            return json.dumps(self.issue)
        if caminho.startswith(f"repos/{REPO}/pulls/9/files"):
            return "\n".join(
                json.dumps({"filename": f, "previous_filename": None, "status": s, "additions": a, "deletions": d})
                for f, s, a, d in self.arquivos
            )
        if "/check-runs" in caminho:
            runs = self.latest if "filter=all" not in caminho else (self.todos if self.todos is not None else self.latest)
            return "\n".join(json.dumps(c) for c in runs)
        if caminho == f"repos/{REPO}/commits/{SHA}/status":
            return json.dumps({"statuses": self.status})
        if caminho == f"repos/{REPO}/branches/main":
            return json.dumps(self.branch)
        if caminho.startswith(f"repos/{REPO}/pulls?state=open"):
            return "\n".join(json.dumps(p) for p in self.abertos)
        raise AssertionError(f"leitura não prevista: {args}")

    def _escrever(self, args):
        for prefixo, erro in self.falha_na_escrita.items():
            if " ".join(args).startswith(prefixo):
                raise escopo.ErroNaoMedido(erro)
        self.escritas.append(args)
        return ""

    def escreveu(self, *palavras):
        return [e for e in self.escritas if all(p in e for p in palavras)]


def _decidir(gh):
    return jt.avaliar_pr(gh, REPO, 9, "main", RE_TESTE, dormir=lambda _s: None)


def _cenario_verde():
    return FakeGh()


# ------------------------------------------------------------------ os 5 casos pedidos


def test_tudo_verde_e_so_teste_junta():
    d = _decidir(_cenario_verde())
    assert d.motivos == [] and d.juntar and not d.nao_medido
    assert d.sha == SHA and d.ficha == 7 and d.custo == "US$ 0.0123"


def test_um_arquivo_de_lib_nao_junta():
    gh = _cenario_verde()
    gh.arquivos = [("tests/test_relogio.py", "added", 30, 0), ("src/relogio.py", "modified", 3, 1)]
    d = _decidir(gh)
    assert not d.juntar
    assert any("`src/relogio.py` não é arquivo de teste" in m for m in d.motivos)


def test_check_pendente_nao_junta():
    gh = _cenario_verde()
    gh.latest[0] = _check("pronto", status="in_progress")
    d = _decidir(gh)
    assert not d.juntar and any("ainda não terminou" in m for m in d.motivos)


def test_ficha_com_permitido_fora_de_teste_nao_junta():
    gh = _cenario_verde()
    gh.issue = _ficha(permitidos="tests/**\nsrc/relogio.py")
    d = _decidir(gh)
    assert not d.juntar and any("não é só de teste" in m and "src/relogio.py" in m for m in d.motivos)


def test_corpo_sem_ficha_nao_junta():
    gh = _cenario_verde()
    gh.pr = _pr(body="Mudança sem a linha de ficha.\n")
    d = _decidir(gh)
    assert not d.juntar and any("Ficha: #N" in m for m in d.motivos)
    assert not [c for c in gh.leituras if "/issues/" in c], "sem ficha, nem busca a Issue"


# ------------------------------------------------------------------ regra 1 (o PR)


@pytest.mark.parametrize(
    "mudanca,trecho",
    [
        ({"user": {"login": "LeoKuli", "type": "User"}}, "não é um dos bots"),
        ({"user": {"login": "kuligovski-portao[bot]", "type": "User"}}, "não é um dos bots"),
        ({"user": {"login": "dependabot[bot]", "type": "Bot"}}, "não é um dos bots"),
        ({"title": "fix: conserta o relógio"}, "título"),
        ({"state": "closed"}, "não está aberto"),
        ({"merged": True}, "não está aberto"),
        ({"draft": True}, "rascunho"),
        ({"head": {"sha": SHA, "repo": {"full_name": "fulano/exemplo"}}}, "próprio repositório"),
        ({"head": {"sha": SHA, "repo": None}}, "próprio repositório"),
        ({"base": {"ref": "develop"}}, "não mira"),
    ],
)
def test_regra_1_cada_sinal_reprova(mudanca, trecho):
    gh = _cenario_verde()
    gh.pr = _pr(**mudanca)
    d = _decidir(gh)
    assert not d.juntar and any(trecho in m for m in d.motivos), d.motivos


def test_o_actions_bot_tambem_vale_como_autor():
    gh = _cenario_verde()
    gh.pr = _pr(user={"login": "github-actions[bot]", "type": "Bot"})
    assert _decidir(gh).juntar


def test_ficha_citada_so_por_id_com_closes_nao_basta():
    """O corpo do agente sempre traz `Ficha: #N`; o formato alternativo do escopo.yml é largo demais aqui."""
    gh = _cenario_verde()
    gh.pr = _pr(body="Ficha: VID-003\n\nCloses #7\n")
    d = _decidir(gh)
    assert not d.juntar and any("Ficha: #N" in m for m in d.motivos)


# ------------------------------------------------------------------ regra 2 (a ficha)


@pytest.mark.parametrize(
    "ficha,trecho",
    [
        (_ficha(autor="MEMBER"), "MEMBER"),
        (_ficha(autor="CONTRIBUTOR"), "CONTRIBUTOR"),
        (_ficha(rotulos=("bug",)), "rótulo `ficha`"),
        (_ficha(permitidos="**"), "não é só de teste"),
        (_ficha(permitidos="*"), "não é só de teste"),
        (_ficha(permitidos="src/**"), "não é só de teste"),
        (_ficha(permitidos="tests/../src/x.py"), "não é só de teste"),
        (_ficha(permitidos="/tests/**"), "não é só de teste"),
        (_ficha(permitidos="_No response_"), "Arquivos permitidos"),
    ],
)
def test_regra_2_ficha_que_nao_serve_reprova(ficha, trecho):
    gh = _cenario_verde()
    gh.issue = ficha
    d = _decidir(gh)
    assert not d.juntar and any(trecho in m for m in d.motivos), d.motivos


@pytest.mark.parametrize("permitidos", ["tests/**", "tests/test_x.py", "**/tests/**", "src/test_x.py\ntests/**", "pkg/x_test.py", "web/a.test.ts"])
def test_globs_de_teste_passam(permitidos):
    for g in permitidos.splitlines():
        assert jt.glob_so_de_teste(g, RE_TESTE), g


def test_a_issue_que_e_um_pr_nao_vale_como_ficha():
    gh = _cenario_verde()
    gh.issue = dict(_ficha(), pull_request={"url": "x"})
    assert not _decidir(gh).juntar


# ------------------------------------------------------------------ regra 3 (os arquivos)


@pytest.mark.parametrize(
    "arquivos,trecho",
    [
        ([("tests/test_a.py", "added", 5, 0), ("README.md", "modified", 1, 1)], "README.md"),
        ([("tests/test_a.py", "added", 5, 0), (".github/tests/x.yml", "added", 1, 0)], "PROTEGIDO"),
        ([("tests/test_a.py", "added", 5, 0), ("AGENTS.md", "modified", 1, 0)], "AGENTS.md"),
        ([("tests/test_a.py", "added", 5, 0), ("tests/test_b.py", "removed", 0, 9)], "removido"),
        ([("tests/test_a.py", "removed", 0, 9)], "removido"),
        ([("tests/test_a.py", "added", 150, 100)], "máximo da ficha"),
        ([("outro/test_a.py", "added", 5, 0)], "fora dos permitidos"),
    ],
)
def test_regra_3_cada_arquivo_ruim_reprova(arquivos, trecho):
    gh = _cenario_verde()
    gh.arquivos = arquivos
    d = _decidir(gh)
    assert not d.juntar and any(trecho in m for m in d.motivos), d.motivos


def test_renomear_para_dentro_de_teste_a_partir_de_lib_reprova():
    gh = _cenario_verde()
    gh.arquivos = []
    gh.arquivos = [("tests/test_a.py", "renamed", 0, 0)]
    gh_json = gh._ler

    def com_anterior(args):
        saida = gh_json(args)
        if "/files" in " ".join(args):
            d = json.loads(saida)
            d["previous_filename"] = "src/a.py"
            return json.dumps(d)
        return saida

    gh._ler = com_anterior
    d = _decidir(gh)
    assert not d.juntar and any("`src/a.py` não é arquivo de teste" in m for m in d.motivos)


def test_pr_sem_nenhum_arquivo_e_nao_medido():
    gh = _cenario_verde()
    gh.arquivos = []
    d = _decidir(gh)
    assert not d.juntar and d.nao_medido


def test_reprovado_antes_dos_checks_nem_consulta_os_checks():
    gh = _cenario_verde()
    gh.arquivos.append(("src/lib.py", "modified", 1, 0))
    assert not _decidir(gh).juntar
    assert not [c for c in gh.leituras if "/check-runs" in c or c.endswith("/status")]


# ------------------------------------------------------------------ regra 4 (os checks)


def test_check_falho_nao_junta():
    gh = _cenario_verde()
    gh.latest[0] = _check("pronto", "failure")
    d = _decidir(gh)
    assert not d.juntar and any("terminou com `failure`" in m for m in d.motivos)


@pytest.mark.parametrize("conclusao", ["cancelled", "timed_out", "neutral", "action_required", "stale", "skipped"])
def test_conclusao_que_nao_e_sucesso_reprova(conclusao):
    gh = _cenario_verde()
    gh.latest[0] = _check("pronto", conclusao)
    assert not _decidir(gh).juntar


def test_skipped_de_escopo_ou_ficha_vale_so_com_irmao_de_mesmo_nome_com_sucesso():
    gh = _cenario_verde()
    gh.latest[3] = _check("escopo / escopo", "skipped")
    d = _decidir(gh)
    assert not d.juntar and any("pulado" in m for m in d.motivos)

    gh.todos = gh.latest + [_check("escopo / escopo", "success")]
    assert _decidir(gh).juntar


def test_skipped_de_outro_check_nunca_vale_nem_com_irmao_verde():
    gh = _cenario_verde()
    gh.latest[0] = _check("pronto", "skipped")
    gh.todos = gh.latest + [_check("pronto", "success")]
    assert not _decidir(gh).juntar


@pytest.mark.parametrize("nome", ["mutacao / mutacao", "Mutação da ficha", "mutacao-sob-demanda"])
def test_check_de_mutacao_tem_de_estar_verde(nome):
    gh = _cenario_verde()
    gh.latest.append(_check(nome, "failure"))
    d = _decidir(gh)
    assert not d.juntar and any("mutação" in m for m in d.motivos)

    gh.latest[-1] = _check(nome, "success")
    assert _decidir(gh).juntar

    gh.latest[-1] = _check(nome, "skipped")
    assert not _decidir(gh).juntar, "mutação pulada não prova nada"


def test_check_obrigatorio_ausente_nao_junta():
    gh = _cenario_verde()
    del gh.latest[0]  # o CI ainda nem criou o `pronto`
    d = _decidir(gh)
    assert not d.juntar and any("obrigatório `pronto`" in m for m in d.motivos)


def test_status_classico_pendente_ou_falho_reprova():
    gh = _cenario_verde()
    gh.status = [{"context": "ci/externo", "state": "pending"}]
    assert not _decidir(gh).juntar
    gh.status = [{"context": "ci/externo", "state": "success"}]
    assert _decidir(gh).juntar


def test_sem_nenhum_check_e_nao_medido():
    gh = _cenario_verde()
    gh.latest = []
    gh.branch = {"protected": False}
    d = _decidir(gh)
    assert not d.juntar and d.nao_medido


def test_protecao_ilegivel_e_nao_medido_e_nunca_verde():
    gh = _cenario_verde()
    gh.branch = {"protected": True}  # a API não devolveu o bloco `protection`
    d = _decidir(gh)
    assert not d.juntar and d.nao_medido and any("proteção" in m for m in d.motivos)


def test_branch_sem_protecao_usa_so_os_checks_da_cabeca():
    gh = _cenario_verde()
    gh.branch = {"protected": False}
    assert _decidir(gh).juntar


def test_obrigatorios_lidos_do_formato_checks_quando_nao_ha_contexts():
    gh = _cenario_verde()
    gh.branch = {"protected": True, "protection": {"required_status_checks": {"checks": [{"context": "pronto"}, {"context": "inexistente"}]}}}
    d = _decidir(gh)
    assert not d.juntar and any("`inexistente`" in m for m in d.motivos)


# ------------------------------------------------------------------ regra 5 (mergeable)


@pytest.mark.parametrize("mergeable,estado", [(False, "dirty"), (False, "blocked"), (True, "behind"), (True, "unstable"), (True, "unknown")])
def test_nao_mergeable_nao_junta(mergeable, estado):
    gh = _cenario_verde()
    gh.pr = _pr(mergeable=mergeable, mergeable_state=estado)
    d = _decidir(gh)
    assert not d.juntar and not d.nao_medido


def test_mergeable_nulo_tenta_de_novo_e_no_fim_e_nao_medido():
    gh = _cenario_verde()
    gh.pr = _pr(mergeable=None, mergeable_state="unknown")
    esperas = []
    d = jt.avaliar_pr(gh, REPO, 9, "main", RE_TESTE, dormir=esperas.append)
    assert not d.juntar and d.nao_medido
    assert len(esperas) == jt.TENTATIVAS_MERGEABLE - 1
    assert [c for c in gh.leituras if c.endswith("/pulls/9")].__len__() == jt.TENTATIVAS_MERGEABLE


def test_api_fora_e_nao_medido_nunca_verde():
    class Fora:
        def __call__(self, args):
            raise escopo.ErroNaoMedido("gh api falhou: 502")

    d = jt.avaliar_pr(Fora(), REPO, 9, "main", RE_TESTE, dormir=lambda _s: None)
    assert not d.juntar and d.nao_medido


# ------------------------------------------------------------------ ações


def test_dry_run_decide_mas_nao_escreve(capsys):
    gh = _cenario_verde()
    codigo = jt.main(["--repo", REPO, "--pr", "9", "--dry-run"], env={}, gh=gh, dormir=lambda _s: None)
    saida = capsys.readouterr().out
    assert codigo == 0 and "PR #9: JUNTAR" in saida and "dry-run" in saida
    assert gh.escritas == []


def test_junta_por_squash_travado_na_cabeca_e_comenta_no_pr_e_na_ficha():
    gh = _cenario_verde()
    assert jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None) == 0
    merge = gh.escreveu("pr", "merge")[0]
    assert merge == ["pr", "merge", "9", "--repo", REPO, "--squash", "--delete-branch", "--match-head-commit", SHA]
    comentario_pr = gh.escreveu("pr", "comment")[0]
    assert jt.MSG_JUNTADO in comentario_pr
    comentario_ficha = gh.escreveu("issue", "comment")[0]
    assert comentario_ficha[2] == "7" and "US$ 0.0123" in comentario_ficha[-1]


def test_o_que_nao_passa_nunca_chama_o_merge(capsys):
    gh = _cenario_verde()
    gh.arquivos.append(("src/lib.py", "modified", 1, 0))
    assert jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert gh.escritas == []
    assert "NÃO JUNTAR" in capsys.readouterr().out


def test_acao_etiquetar_comenta_e_etiqueta_sem_juntar():
    gh = _cenario_verde()
    assert jt.main(["--repo", REPO, "--pr", "9", "--acao", "etiquetar"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert not gh.escreveu("pr", "merge")
    assert gh.escreveu("pr", "edit", "--add-label", jt.ROTULO_PRONTO)
    assert jt.MSG_PRONTO in gh.escreveu("pr", "comment")[0][-1]


def test_etiquetar_nao_repete_o_aviso_na_rodada_seguinte():
    gh = _cenario_verde()
    gh.pr = _pr(labels=[{"name": jt.ROTULO_PRONTO}])
    assert jt.main(["--repo", REPO, "--pr", "9", "--acao", "etiquetar"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert gh.escritas == []


def test_juncao_recusada_cai_para_o_rotulo_e_sai_com_erro(capsys):
    gh = _cenario_verde()
    gh.falha_na_escrita = {"pr merge": "gh pr merge falhou: Pull request is not mergeable: required review"}
    codigo = jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None)
    assert codigo == 1
    assert gh.escreveu("pr", "edit", "--add-label", jt.ROTULO_PRONTO)
    assert "recusada" in capsys.readouterr().out


def test_lista_so_os_prs_de_agente_e_examina_cada_um(capsys):
    gh = _cenario_verde()
    gh.abertos = [
        {"number": 9, "login": "kuligovski-portao[bot]", "title": "[agente:qwen] x"},
        {"number": 3, "login": "LeoKuli", "title": "[agente:qwen] feito à mão"},
        {"number": 4, "login": "github-actions[bot]", "title": "chore: outra automação"},
    ]
    assert jt.candidatos(gh, REPO) == [9]
    assert jt.main(["--repo", REPO, "--dry-run"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert capsys.readouterr().out.count("PR #") == 1


def test_sem_pr_de_agente_nao_faz_nada(capsys):
    gh = _cenario_verde()
    assert jt.main(["--repo", REPO, "--dry-run"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert "nenhum PR de agente aberto" in capsys.readouterr().out


def test_argumentos_ruins_sao_nao_medido(capsys):
    assert jt.main(["--repo", "sem-barra"], env={}, gh=_cenario_verde()) == 1
    assert jt.main(["--repo", REPO, "--regex-testes", "(", "--pr", "9"], env={}, gh=_cenario_verde()) == 1
    assert "NÃO MEDIDO" in capsys.readouterr().out


def test_resumo_vai_para_o_step_summary(tmp_path):
    gh = _cenario_verde()
    destino = tmp_path / "resumo.md"
    jt.main(["--repo", REPO, "--pr", "9", "--dry-run"], env={"GITHUB_STEP_SUMMARY": str(destino)}, gh=gh, dormir=lambda _s: None)
    assert "PR #9: JUNTAR" in destino.read_text(encoding="utf-8")


def test_decisoes_nao_mudam_o_cenario_de_outro_teste():
    """Guarda do próprio teste: o cenário verde é fresco a cada chamada."""
    a, b = _cenario_verde(), _cenario_verde()
    a.latest[0] = _check("pronto", "failure")
    assert _decidir(b).juntar and copy.deepcopy(b.latest[0])["conclusion"] == "success"


# ------------------------------------------------------------------ branch atrás da base (proteção estrita)


def test_so_atrasada_atualiza_a_branch_e_nao_junta_nesta_rodada():
    gh = _cenario_verde()
    gh.pr = _pr(mergeable_state="behind")
    d = _decidir(gh)
    assert d.so_atrasado and not d.juntar
    assert jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None) == 0
    assert gh.escreveu("pr", "update-branch", "9")
    assert not gh.escreveu("pr", "merge")


def test_atrasada_com_outro_motivo_nao_atualiza_e_dry_run_nao_escreve():
    gh = _cenario_verde()
    gh.pr = _pr(mergeable_state="behind")
    gh.latest[0] = _check("pronto", status="in_progress")  # ainda pendente: atualizar agora só duplicaria o CI
    d = _decidir(gh)
    assert not d.so_atrasado
    jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None)
    assert gh.escritas == []

    gh = _cenario_verde()
    gh.pr = _pr(mergeable_state="behind")
    jt.main(["--repo", REPO, "--pr", "9", "--dry-run"], env={}, gh=gh, dormir=lambda _s: None)
    assert gh.escritas == []
    jt.main(["--repo", REPO, "--pr", "9", "--sem-atualizar-branch"], env={}, gh=gh, dormir=lambda _s: None)
    assert gh.escritas == []


def test_atrasada_que_e_de_arquivo_de_lib_nunca_e_atualizada():
    gh = _cenario_verde()
    gh.pr = _pr(mergeable_state="behind")
    gh.arquivos.append(("src/lib.py", "modified", 1, 0))
    jt.main(["--repo", REPO, "--pr", "9"], env={}, gh=gh, dormir=lambda _s: None)
    assert gh.escritas == []
