# Agente OpenHands dentro do GitHub Actions

Decisão do dono ("opção A"): um agente de IA externo (OpenHands, qualquer LLM) trabalha **dentro do
GitHub Actions**, disparado por um **rótulo** numa Issue-ficha, **sem conta de colaborador**. Ele abre um PR
que **não roda o CI sozinho**; o mantenedor revisa o diff e só então dispara o CI.

Implementação: [`.github/workflows/agente-openhands.yml`](../.github/workflows/agente-openhands.yml)
(workflow reutilizável) + [`templates/agente-openhands-caller.yml`](../templates/agente-openhands-caller.yml)
(o chamador que cada repositório copia) + [`scripts/agente_openhands.py`](../scripts/agente_openhands.py).

## 1. Pesquisa: como se roda o OpenHands no GitHub Actions hoje (17/10/2026)

Fontes consultadas em 17/10/2026 (API do GitHub e páginas oficiais).

### O resolver antigo não existe mais

O workflow reutilizável que a documentação antiga descrevia (`openhands-resolver.yml`, com `macro`,
`max_iterations`, `base_container_image`, `LLM_MODEL`, `target_branch`, `PAT_TOKEN`, `PAT_USERNAME`) foi
**removido do upstream em 23/04/2026** junto com todo o módulo `openhands.resolver` ("Removed the V0 resolver",
OpenHands/OpenHands#14062, commit `cc100c0d10fb`):

- <https://github.com/OpenHands/OpenHands/commit/cc100c0d10fbefcc35eb80936a926405801d941a>
- A última versão que o continha é o commit pai `7bc3300981fa` (`.github/workflows/openhands-resolver.yml`).
- A documentação em `docs.all-hands.dev/.../github-action` redireciona para `docs.openhands.dev`, e a página do
  resolver devolve 404. O repositório de documentação (`OpenHands/docs`) não tem mais página do resolver; só
  `sdk/guides/github-workflows/` (assign-reviews, pr-review, todo-management).

**Não adotamos o resolver V0 congelado.** Motivos: (a) o workflow dele instala `openhands-ai` **sem versão**
(`pip index versions` e pega a mais nova) e, depois da remoção, a mais nova nem tem o módulo `openhands.resolver`:
quebra na hora; (b) está sem manutenção; (c) usa um segredo fixo `OPENHANDS_BOT_GITHUB_PAT_PUBLIC` e o agente
recebe o token de escrita dentro da sandbox.

### O caminho atual: OpenHands SDK V1 em workflow de exemplo

O upstream mantém exemplos de workflow no repositório do SDK:
<https://github.com/OpenHands/software-agent-sdk/tree/main/examples/03_github_workflows>
(`01_basic_action/workflow.yml` + `agent_script.py`). Eles são **modelos para copiar**, não um workflow
reutilizável publicado. O exemplo básico:

| Item | Valor no exemplo do SDK |
|---|---|
| Instala | `openhands-sdk` e `openhands-tools` (no exemplo, direto do `main` do git: **não fixa versão**) |
| Variáveis | `LLM_MODEL`, `LLM_BASE_URL` (opcional), `PROMPT_STRING` ou `PROMPT_LOCATION` |
| Credencial | `LLM_API_KEY` (segredo do repositório; obrigatório) |
| Permissões | `contents: write`, `pull-requests: write`, `issues: write` com o **`GITHUB_TOKEN`** |
| PAT | **Não usa PAT.** `PAT_TOKEN`/`PAT_USERNAME` eram coisa do resolver V0 e nem lá eram obrigatórios: o V0 caía para `github.token` quando o PAT faltava |
| `macro`, `base_container_image`, `target_branch` | Não existem no SDK V1; o "macro" aqui é o **rótulo**, a imagem é a do runner, a branch-base é decidida por nós |

Versões: `openhands-sdk`/`openhands-tools` no PyPI, última `1.55.1` (16/10/2026); exige Python `>=3.12`.
Tag no GitHub: `OpenHands/software-agent-sdk` `v1.54.0` = commit `1d471742ea7b`.

### O que fixamos

- **`openhands-sdk==1.54.0` e `openhands-tools==1.54.0`** (PyPI, lançadas em 09/10/2026; tag
  `v1.54.0`, commit `1d471742ea7be017d013eaaa3080f5d28d5490cb`). Escolhida a penúltima série em vez da `1.55.x`
  (de 15–16/10) para não pegar versão com um dia de vida. Verificado localmente em 17/10: o pacote instala e
  `LLM`, `get_default_agent` e `Conversation(..., max_iteration_per_run=N)` existem com essa assinatura.
- Sobe-se de versão **de propósito**: trocar `sdk_version` no chamador (ou o default no workflow), rodar numa ficha
  de teste, conferir.
- O script do agente **não** é baixado do `main` do upstream: é o `scripts/agente_openhands.py` deste repositório,
  fixado junto com o YAML (`github.job_workflow_sha`).
- As actions de terceiros (`checkout`, `setup-python`, `upload/download-artifact`) estão fixadas por SHA.

### `GITHUB_TOKEN` basta, sem PAT

Sim. Nada no caminho atual exige PAT. Consequências boas e a conhecer (GitHub Docs, "Triggering a workflow from a
workflow": <https://docs.github.com/en/actions/using-workflows/triggering-a-workflow>):

1. **Eventos disparados pelo `GITHUB_TOKEN` não criam execuções de workflow**, salvo `workflow_dispatch` e
   `repository_dispatch`. Para `pull_request` com `opened`/`synchronize`/`reopened` a página descreve um estado
   **"approval-required"**: a execução fica esperando e alguém com permissão de escrita a libera em
   "Approve workflows to run". **NÃO MEDIDO em campo** qual dos dois comportamentos o repositório do dono mostra;
   o primeiro uso diz. Nos dois casos o passo do mantenedor é o mesmo: **revisar o diff antes**, depois
   fechar/reabrir o PR (a reabertura é feita por uma pessoa, então dispara o CI normalmente) ou aprovar a execução.
2. **O `GITHUB_TOKEN` não consegue alterar `.github/workflows/`** (a permissão `workflows` só existe para GitHub
   Apps/PAT): um push que mexa nisso é recusado. Além disso o workflow **descarta** do patch qualquer mudança em
   `.github/` e avisa no PR. Um PAT com escopo `workflow` poderia reescrever o CI; por isso não há PAT.
3. **O repositório precisa permitir "Allow GitHub Actions to create and approve pull requests"** (Settings >
   Actions > General > Workflow permissions). Sem isso o `gh pr create` falha com 403 e a branch fica empurrada
   para abrir o PR na mão. Isso é configuração de repositório e **é o dono quem liga** (ver a seção 3).

## 2. Como o workflow funciona

```
Issue com rótulo "ficha"  ──[mantenedor aplica "agente:<modelo>"]──▶  evento issues:labeled
  job agente   (contents: read, só a chave do LLM)
     1. confere as travas e escolhe o modelo pelo rótulo
     2. copia o código para uma pasta SEM .git e roda o agente nela (OpenHands SDK, N iterações)
     3. gera um patch (texto) comparando com uma cópia limpa; guarda o patch e o log como artefatos
  job publicar (outra máquina; contents/pull-requests/issues: write, GITHUB_TOKEN; NÃO roda o agente)
     4. aplica o patch SEM .github/, commita, empurra a branch agente/ficha-<n>-<modelo>-<run>
     5. abre o PR ("Ficha: #<n>" na descrição), comenta, põe os rótulos agente:<modelo> e estado:revisao
  job avisar   (só se não saiu PR) comenta na ficha por quê
```

Travas duras (todas testadas em `tests/test_workflow_agente.py` e `tests/test_agente_openhands.py`):

| Trava | Onde |
|---|---|
| Só `ubuntu-latest` | todos os jobs |
| Só roda se: Issue com rótulo `ficha` **e** rótulo recém-aplicado começa com `agente:` **e** `github.event.sender.login == maintainer` (padrão `LeoKuli`); senão o job é pulado | `if:` do job `agente` + repetido em código no passo "Conferir as travas" |
| Ficha aberta por alguém sem papel confiável (`OWNER,MEMBER,COLLABORATOR`) não é entregue ao modelo | `autores_ficha` |
| Modelo vem da entrada `modelos` (JSON sufixo→id); sufixo desconhecido **falha** com a lista dos conhecidos | `resolver_modelo` |
| `GITHUB_TOKEN`, nunca PAT | permissões por job |
| O agente roda **sem token de escrita** e **sem `.git`**; quem faz push é outro job, que só recebe texto | dois jobs |
| Chave só por `secrets:`; passa ao agente por `env` de um único passo, sai do ambiente do processo antes de abrir a sandbox, nunca é impressa | `LLM_API_KEY` |
| Limite de iterações (`max_iterations`, padrão 50) e `timeout-minutes` (`timeout_minutes`, padrão 45) | entradas |
| Patch máximo de 1 MiB; mudanças em `.github/` descartadas | passo do patch / `git apply --exclude` |
| Texto da Issue nunca é interpolado em `run:`; chega por `env` | testado |

**O que a separação em dois jobs não resolve:** o agente roda código arbitrário no runner e enxerga a
`LLM_API_KEY` (o processo dele a usa). Por isso a chave **precisa ter teto de gasto** e valer só para esse uso.
Tirar a chave do ambiente reduz vazamento acidental em log, não é isolamento.

Modelos: o rótulo `agente:deepseek` usa `openrouter/deepseek/deepseek-chat`; `agente:qwen` usa
`openrouter/qwen/qwen3-coder` (ids no formato LiteLLM, que o SDK usa). Confira o id exato na página do modelo
no provedor antes do primeiro uso; mude o mapa `modelos` no chamador.

## 3. Passos do dono (uma vez, e em cada repositório)

Estes passos são **seus**; nenhum agente cria conta, chave nem segredo.

1. **Conta no provedor do modelo** (sugestão: OpenRouter, que serve DeepSeek, Qwen e outros com uma chave só).
2. **Crie uma chave de API com teto de gasto** (no OpenRouter: limite de crédito na própria chave; em provedor
   direto, limite de gasto mensal da conta). Comece com um valor baixo (por exemplo, o custo de poucas fichas).
3. No repositório: **Settings > Secrets and variables > Actions > New repository secret**, nome **`LLM_API_KEY`**,
   cole a chave. Para provedor direto (sem OpenRouter), crie também o segredo `LLM_BASE_URL` com o endpoint dele
   e descomente a linha no chamador.
4. No repositório: **Settings > Actions > General > Workflow permissions**, ligue **"Allow GitHub Actions to
   create and approve pull requests"**. Sem isso o PR não abre.
5. No `LeoKuli/agentes-padroes` (privado): **Settings > Actions > General > Access**, permita o uso por repositórios
   privados do mesmo dono. Se preferir não, crie o segredo `PADROES_TOKEN` (leitura só do `padroes`) em cada
   repositório e descomente a linha no chamador.
6. **Rótulos:** `./scripts/aplicar-labels.sh LeoKuli/<repo> agente:deepseek agente:qwen`.
7. Copie `templates/agente-openhands-caller.yml` para `.github/workflows/agente.yml` e troque `@main` por um SHA
   do `padroes` depois de revisar. Esse arquivo passa pelo mesmo cuidado de qualquer mudança em `.github/`.
8. **Primeiro uso:** numa ficha pequena e de baixo risco, aplique `agente:deepseek` e acompanhe a aba Actions.

### Custo

- **OpenRouter**: cobra **5,5% na compra de créditos** (plano Standard; 8% no Business). Fonte:
  <https://openrouter.ai/pricing>.
- **BYOK pelo OpenRouter** (você usa a chave do provedor, o OpenRouter só roteia): **sem taxa até US$ 25 mil/mês**
  de inferência (a mesma página). Para o nosso volume, é como não ter taxa.
- **Chave direta do provedor** (DeepSeek, Alibaba/Qwen etc.) também funciona: segredo `LLM_BASE_URL` com o
  endpoint e o id do modelo no formato do provedor. Um passo a mais, sem intermediário.
- O que mais pesa é o número de iterações: `max_iterations: 50` e o teto de gasto da chave limitam o pior caso.
- O custo estimado pelo SDK aparece no fim do log do agente (artefato `agente-log`); se não vier, está
  **NÃO MEDIDO**, nunca zero.

## 4. O passo do mantenedor

1. Aplique `agente:<modelo>` na ficha. A ficha ganha comentário com o link do PR (ou do erro).
2. Abra o PR e leia **o diff inteiro**, com atenção a `.github/`, a configuração de CI, a arquivos novos fora do
   escopo e a qualquer coisa que pareça chave ou dado real. O texto da ficha vai ao modelo; o que o modelo
   devolve é código não confiável até você ler.
3. Se aprovar o diff: **feche e reabra o PR** (ou use "Approve workflows to run", se a execução estiver esperando).
   Isso dispara o CI do repositório (`padroes`: segredos, ficha, escopo, testes).
4. Se não aprovar: comente o que corrigir e feche. Não há `push` do agente; correção é nova rodada (remova e
   reaplique o rótulo, de preferência depois de melhorar a ficha) ou ficha nova.

## 5. Limites conhecidos

- O agente não vê `.git` e não roda o comando de aceite com o CI do repositório; ele pode rodar o comando que a
  ficha pede dentro da sandbox do runner. Quem mede de verdade é o CI depois da reabertura.
- Arquivos que o agente cria e o `.gitignore` do repositório não cobre entram no patch (por exemplo caches). O
  revisor vê no diff.
- Não há segunda rodada automática de correção pelo agente (decisão de manter o custo previsível).
- `actionlint` não foi rodado (não está instalado neste PC); o YAML foi validado com `yaml.safe_load` e os testes
  do repositório.
