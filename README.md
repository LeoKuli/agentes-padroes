# padroes

O contrato compartilhado que permite que **qualquer modelo de IA** contribua com os projetos do dono,
sem acesso à VPS, à produção, a segredos ou a dados de paciente. Só pull request.


## A ideia em quatro linhas

1. Um modelo forte desenha a arquitetura e escreve as **fichas de tarefa**.
2. Qualquer modelo executa **uma ficha por pull request**.
3. O **CI** e um revisor forte aceitam ou recusam o PR. Só o portão da VPS põe código no ar.
4. A taxa de aceitação de cada modelo decide o **nível** de tarefa que ele pode pegar.

## O que há aqui

| Caminho | Para quê |
|---|---|
| `templates/AGENTS.md` | Modelo de instruções abertas para o repositório (padrão aberto AGENTS.md) |
| `templates/FICHA-DE-TAREFA.md` | Ficha autocontida: objetivo, arquivos permitidos/proibidos, comando de aceite, teste e mutação |
| `templates/pull_request_template.md` | Checklist do PR, referenciando a ficha |
| `templates/CODEOWNERS.example` | Protege CI, constituição, templates de spec, testes de arquitetura e limiares de mutação |
| `templates/.gitleaks.toml` | Regras de segredo e de dado pessoal (CPF, telefone, e-mail) |
| `.github/workflows/segredos.yml` | Workflow reutilizável: gitleaks no diff do PR |
| `.github/workflows/ficha.yml` | Workflow reutilizável: o PR precisa citar uma ficha (`Ficha: #123` ou `Ficha: ID`) |
| `.github/workflows/escopo.yml` | Workflow reutilizável: confere o PR contra a ficha (Issue): arquivos permitidos/protegidos, tamanho do diff, teste presente |
| `.github/workflows/agente-openhands.yml` | Workflow reutilizável: agente OpenHands dentro do GitHub Actions, disparado pelo rótulo `agente:<modelo>` numa ficha; abre PR sem rodar o CI |
| `templates/agente-openhands-caller.yml` | O chamador pequeno que cada repositório copia para `.github/workflows/agente.yml` |
| `docs/OPENHANDS.md` | Pesquisa (resolver V0 removido; SDK V1 fixado), travas, passos do dono, custo |
| `.github/workflows/teste-padroes.yml` | CI deste repositório (pytest) |
| `templates/ISSUE_TEMPLATE/` | Formulários de Issue: `ficha.yml` (a ficha), `duvida.yml`, `config.yml` |
| `templates/labels.json` + `scripts/aplicar-labels.sh` | Rótulos padrão (estado, nível, prioridade) e o script que os aplica a um repositório |
| `scripts/escopo.py` + `tests/` | O verificador de escopo e seus testes |
| `docs/REVISAO.md` | O funil de revisão: CI, escopo, gitleaks, mutação, pré-revisão barata, revisão forte |
| `docs/COMUNICACAO.md` | Como o agente pega tarefa, pergunta, entrega e responde à revisão |

## Como um repositório usa isto

1. Copiar `templates/AGENTS.md` para a raiz, preencher todas as seções e fazer o `CLAUDE.md` conter
   apenas `@AGENTS.md`.
2. Copiar `templates/FICHA-DE-TAREFA.md` para `docs/fichas/` (uma cópia preenchida por tarefa) e
   `templates/pull_request_template.md` para `.github/pull_request_template.md`.
3. Copiar `templates/CODEOWNERS.example` para `.github/CODEOWNERS` e ajustar os caminhos reais.
4. Copiar `templates/.gitleaks.toml` para a raiz do repositório.
5. Chamar os workflows reutilizáveis num workflow do próprio repositório:

```yaml
# .github/workflows/padroes.yml
name: padroes
on:
  pull_request:
jobs:
  segredos:
    uses: LeoKuli/agentes-padroes/.github/workflows/segredos.yml@main
  ficha:
    uses: LeoKuli/agentes-padroes/.github/workflows/ficha.yml@main
  escopo:
    uses: LeoKuli/agentes-padroes/.github/workflows/escopo.yml@main
    permissions:
      contents: read
      issues: read
      pull-requests: read
    # Só se o GITHUB_TOKEN não alcançar o padroes (privado): crie a credencial PADROES_TOKEN
    # (leitura só do padroes) e acrescente aqui "secrets: inherit".
```

Para a troca por Issues: copiar `templates/ISSUE_TEMPLATE/` para `.github/ISSUE_TEMPLATE/` e rodar
`scripts/aplicar-labels.sh LeoKuli/<repo>` uma vez. O fluxo completo está em
[`docs/COMUNICACAO.md`](docs/COMUNICACAO.md) e [`docs/REVISAO.md`](docs/REVISAO.md).

Como este repositório é privado, o repositório que chama precisa estar autorizado a usar os
workflows dele (Settings > Actions > General > Access, em `padroes`). Isso é configuração do dono.

6. Exigir esses checks, o CI do projeto e 1 revisão na `main` (proteção de branch: decisão do dono).

## Regra de ouro

Agente externo **nunca** toca VPS, produção, segredo ou dado de paciente, e **nunca** altera
testes de arquitetura, pisos, CODEOWNERS, configuração de CI ou limiares de mutação.
