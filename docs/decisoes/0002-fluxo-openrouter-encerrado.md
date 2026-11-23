---
status: aceito
date: 2026-11-03
decision-makers: dono
---

# Encerrar a execução de fichas por modelos do OpenRouter; desenvolver com Claude na assinatura

## Contexto e problema

Desde 2026-10-17, fichas (Issues autocontidas) eram executadas por modelos baratos via OpenRouter, dentro do
GitHub Actions (`agente-openhands.yml`). Em 2026-11-03 o dono decidiu parar esse caminho.

## Fatores da decisão

- Custo por uso fora da assinatura e chave de API a guardar.
- Taxa de falha das execuções e o tempo de revisão gasto nelas.

## Opções consideradas

- Manter o fluxo de fichas pelo OpenRouter.
- Desenvolver com Claude na assinatura (sem sessão de API paga), mantendo o kit agnóstico para qualquer modelo.

## Decisão

Escolhida: desenvolvimento com Claude na assinatura. Nada de chave do OpenRouter nem sessão de API paga por uso. Os
workflows de ficha (`ficha`, `escopo`, `mutacao-ficha`, `agente-openhands`) ficam no repositório como histórico e
para quem quiser reutilizar com outro executor, mas nenhum repositório do dono deve ligar o `agente-openhands`.

### Consequências

- Bom: custo previsível; nenhuma chave de provedor para guardar.
- Ruim: a agnosticidade passa a depender do kit (AGENTS.md, ESTADO.md, ADR), não de um executor barato pronto.

## Mais informações

`docs/OPENHANDS.md` (pesquisa e configuração do fluxo antigo). O repositório `padroes` foi arquivado em 2026-11-23.
