---
status: aceito
date: 2026-11-23
decision-makers: dono
---

# Exigir docs/ESTADO.md datado e reprovar no CI o estado vencido além de 30 dias

## Contexto e problema

Para agentes de longa duração, a Anthropic recomenda arquivo de progresso, histórico do git, lista de tarefas e
preparo do ambiente. Sem um arquivo de retomada, cada sessão nova reconstrói o contexto, e o que foi decidido numa
sessão some na outra. Os agentes seguem ADRs, mas obedecem até os vencidos.

## Fatores da decisão

- Retomar em minutos, com qualquer modelo.
- Verificação que não reprova não é verificação: uma regra "atualize o estado" sem CI não se sustenta.
- Repositórios pausados não podem virar alarme permanente.

## Opções consideradas

- Só recomendar o ESTADO.md no AGENTS.md.
- Conformidade no CI: AGENTS.md presente, ESTADO.md com `Atualizado em: AAAA-MM-DD` dentro de N dias, ao menos um
  ADR com status válido, ponteiros corretos, comando único, `.mcp.json` sem segredo literal, nenhuma marca de preenchimento sobrando.

## Decisão

Escolhida: conformidade no CI, com N = 30 dias por padrão (o repositório pode mudar `dias-maximos`). O workflow roda
em PR e em push na branch padrão, não por agenda: um repositório pausado só reprova quando alguém volta a mexer nele,
que é exatamente quando o estado precisa ser renovado. Conflito de tarefa com ADR aceito: o agente para e pergunta.

### Consequências

- Bom: o próximo agente sempre encontra estado recente; ADR sem status é pego.
- Ruim: um PR num repositório parado há mais de 30 dias precisa tocar também o ESTADO.md.

## Mais informações

`scripts/conformidade.py`, `tests/test_conformidade.py`, `.github/workflows/conformidade.yml`.
