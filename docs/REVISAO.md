# Funil de revisão

Como um PR de agente externo vira código aceito, gastando o mínimo de modelo forte. Tudo acontece no GitHub:
a **tarefa é uma Issue** (a ficha), a **entrega é um PR de um fork**, e os **comentários de revisão são ordens
de serviço**. Como o agente trabalha e pergunta: [`COMUNICACAO.md`](https://github.com/LeoKuli/agentes-padroes/blob/main/docs/COMUNICACAO.md).

## Regras de entrada

- **Fork, não branch.** O agente tem acesso só de leitura ao repositório e abre o PR de um fork dele. Ele nunca
  empurra para o repositório do dono.
- **Limite de WIP: 2 PRs abertos por agente.** O terceiro só abre quando um dos dois for aceito ou devolvido.
- **Um PR por ficha**, com `Ficha: #<número da Issue>` na descrição. Sem isso, o job `escopo` reprova.
- **Aprovação do dono para rodar workflow de fork.** Antes de clicar em "Approve and run":
  1. abrir a aba *Files changed* e olhar o diff de `.github/` e de qualquer arquivo de configuração de CI;
  2. se o PR toca `.github/`, CODEOWNERS ou `AGENTS.md`, **não aprovar**: devolver (o `escopo` também reprova);
  3. só então aprovar. Cada novo push exige nova aprovação.

### PR aberto por agente dentro do GitHub (rótulo `agente:<modelo>`)

Segundo caminho de entrada, sem fork (ver `COMUNICACAO.md`, seção 6, e `OPENHANDS.md`). O PR nasce de uma
branch `agente/ficha-<n>-<modelo>-<run>` no próprio repositório, aberto pelo `GITHUB_TOKEN`:

- **Com o app `kuligovski-portao` (segredo `PORTAO_APP_KEY` repassado pelo chamador) o CI roda sozinho** e o PR
  nasce de `kuligovski-portao[bot]`; o passo 3 abaixo (fechar/reabrir) deixa de ser necessário, mas o diff continua
  sendo lido antes de aprovar. Sem a chave, vale o que segue.
- **O CI não roda sozinho** (PR criado por `GITHUB_TOKEN` não dispara workflows; no máximo fica esperando
  aprovação). Nada do funil abaixo começa antes do passo do mantenedor.
- **O `GITHUB_TOKEN` não altera `.github/workflows/`**, e o workflow ainda descarta do patch qualquer mudança em
  `.github/`. Mesmo assim o diff é lido, porque outros arquivos de CI ou configuração (Makefile, scripts de
  teste, `package.json`, `pyproject.toml`) também podem mudar o que o CI executa.
- **Passo do mantenedor, antes do CI:**
  1. abrir *Files changed* e ler o diff inteiro, com atenção a `.github/`, a CI e configuração de teste, a
     arquivo novo fora da ficha e a qualquer texto que pareça chave, telefone, CPF ou nome real;
  2. se algo disso aparecer, **não disparar o CI**: comentar o motivo e fechar (`estado:devolvida`);
  3. se estiver limpo, **fechar e reabrir o PR** (ou "Approve workflows to run"). Só então o CI roda e o funil
     segue da etapa 1.
- O limite de 2 PRs abertos por agente conta o rótulo `agente:<modelo>`: com 2 PRs `agente:<modelo>` abertos,
  não se aplica um terceiro rótulo desse modelo.

## O funil, em ordem (o mais barato primeiro)

| # | Etapa | Quem executa | O que reprova | Custo |
|---|---|---|---|---|
| 1 | **CI** do repositório | GitHub Actions | o comando de aceite da ficha falha | zero de modelo |
| 2 | **Escopo** (`escopo.yml`) | GitHub Actions | arquivo fora dos permitidos, arquivo protegido, diff maior que o máximo, nenhum teste tocado, ficha ausente ou inválida | zero de modelo |
| 3 | **gitleaks + ficha** (`segredos.yml`, `ficha.yml`) | GitHub Actions | credencial ou dado pessoal no diff; linha `Ficha:` ausente | zero de modelo |
| 4 | **Mutação nos arquivos tocados** | bancada do dono | a mutação da ficha sobrevive, ou morre por asserção lateral | CPU da bancada |
| 5 | **Pré-revisão** por modelo barato | modelo barato | itens do checklist abaixo | baixo |
| 6 | **Revisão final** por modelo forte | modelo forte | 1 dos 3 veredictos abaixo | alto |

Cada etapa só roda se a anterior passou. Um PR que reprova nas etapas 1–3 volta ao agente **sem gastar modelo**.

### Etapa 4 — mutação (automática + bancada)

**Conferência automática da mutação da ficha** (`mutacao-ficha.yml`, `scripts/mutacao_da_ficha.py`): em PR de
agente (autor `github-actions[bot]`, com `Ficha: #N`), lê a seção "Mutação que tem de morrer" da Issue, exige que o
trecho a trocar apareça EXATAMENTE 1 vez no arquivo, aplica, roda o comando de teste do repositório (tem de
REPROVAR), restaura o arquivo e roda o comando na árvore limpa (tem de PASSAR). Ficha sem a seção, âncora que não casa
ou tempo esgotado = NÃO MEDIDO = job vermelho. O resumo do job traz a tabela e a cauda da saída de cada mutante: o
script prova que o teste reprova, mas **que reprovou na asserção indicada continua sendo leitura do revisor**
(só o mutante que nem importa/compila é recusado sozinho).

**Mutação pesada da bancada** (a ferramenta de mutação do repositório):

A mutação é pesada e roda fora do GitHub-hosted runner (na bancada). Por isso:

- **só depois da aprovação do dono** (a mesma que libera o workflow do fork), nunca automática em PR de fora;
- dispara por `push` na bancada ou `workflow_dispatch`, **limitada aos arquivos que o PR tocou**;
- critério: a mutação indicada na ficha **tem de morrer, na asserção indicada**. Morreu por outra asserção =
  a trava que se acha que protege não é a que protege; conta como sobrevivente.

### Etapa 5 — checklist da pré-revisão (modelo barato)

O modelo barato lê **só o diff e a ficha** e responde sim/não a cada item. Qualquer "não" vira comentário
no PR e o PR volta ao agente (`estado:corrigir`) sem passar pela etapa 6.

1. Todo critério de pronto da ficha tem evidência no PR (comando colado com resultado)?
2. O teste novo executa o código real, e há um controle positivo?
3. Algum teste existente foi enfraquecido, pulado, apagado ou teve a asserção afrouxada?
4. O diff contém algo que a ficha não pediu (refatoração, renomeação, dependência nova)?
5. Há telefone, CPF, e-mail, nome real ou dado de paciente, ou chamada a produção?
6. A descrição traz o que ficou fora do escopo e as dúvidas, ou omite onde a ficha era ambígua?
7. Mensagens de commit em Conventional Commits, em português nos textos e inglês no código?

### Etapa 6 — revisão final (modelo forte)

O modelo forte recebe o diff, a ficha, o resultado das etapas 1–5 e decide **uma** das três saídas:

| Veredito | Quando | O que acontece |
|---|---|---|
| **aprovado** | cumpre a ficha, sem pendência | revisão "Approve"; o dono faz o merge; rótulo some; a ficha é fechada pelo `Closes #n` |
| **corrigir** | cumpre a ficha, mas há **no máximo 3 itens** objetivos a ajustar | revisão "Request changes" com os itens numerados, cada um uma ordem de serviço (arquivo, linha, o que mudar, como conferir); rótulo `estado:corrigir` |
| **devolvida** | errou o rumo, mais de 3 itens, ou a ficha é que estava errada | PR fechado com o motivo; rótulo `estado:devolvida`; a ficha é refeita ou sobe de nível |

Regras do veredito:

- Comentário de revisão é **ordem de serviço**: um problema, o lugar exato, a correção esperada e o comando que
  prova. Nada de "melhore a legibilidade".
- **Máximo de 2 rodadas.** Se o PR não está aprovado depois da 2ª rodada de correção, ele **não** ganha uma 3ª:
  - ou a **ficha é reescrita** (menor, mais precisa) e o trabalho recomeça em PR novo;
  - ou o **nível sobe** (`nivel-N+1`) e a ficha vai para um modelo mais forte;
  - ou **escala para o dono** quando a causa é uma decisão de produto.
- O revisor nunca corrige o PR do agente por conta própria: quem muda o código é o agente (ou uma ficha nova).

## Métricas por modelo (toda semana)

Uma linha por modelo (rótulo `agente:<modelo>`), contadas sobre os PRs fechados na semana:

| Métrica | Como medir |
|---|---|
| **Aceitos de primeira** | PR aprovado sem passar por `estado:corrigir` / PRs fechados |
| **Rodadas** | média de rodadas de revisão até aprovar |
| **CI vermelho** | PRs com alguma das etapas 1–3 vermelhas no primeiro push / PRs abertos |
| **Tempo** | da mensagem "pegando" até o merge (mediana) |

Uso: a taxa de aceitos de primeira decide o **nível** que o modelo pode pegar (sobe com taxa alta e estável,
desce com CI vermelho recorrente ou devoluções). Medição que falhou é registrada como **NÃO MEDIDO**, nunca
como zero.
