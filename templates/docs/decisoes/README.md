# Decisões de arquitetura (ADR)

Cada decisão que molda o projeto mora num arquivo `NNNN-titulo-curto.md` (numeração crescente, nunca
reaproveitada), no formato [MADR](https://adr.github.io/madr/). O CI de conformidade exige ao menos um ADR e um
`status` válido em cada um.

**Regra para agentes:** se a tarefa conflita com um ADR `aceito`, pare e pergunte ao dono. Para mudar uma decisão,
escreva um ADR novo com `status: aceito` e marque o antigo como `substituído por NNNN`; nunca edite o mérito de um
ADR aceito.

Status válidos: `proposto`, `aceito`, `rejeitado`, `obsoleto`, `substituído por NNNN`.

## Índice

| Nº | Título | Status |
|---|---|---|
| PREENCHER | | |

## Modelo (copie para `NNNN-titulo-curto.md`)

```markdown
---
status: aceito
date: AAAA-MM-DD
decision-makers: dono
---

# Título curto, no imperativo ("Usar X para Y")

## Contexto e problema

Duas a cinco frases: a situação e a pergunta que exigiu decisão.

## Fatores da decisão

- fator 1 (ex.: custo, prazo, risco de perder dado)

## Opções consideradas

- Opção A
- Opção B

## Decisão

Escolhida: "Opção A", porque <motivo ligado aos fatores>.

### Consequências

- Bom: ...
- Ruim: ...

## Mais informações

Links para spec, PR, medição ou registro que embasou a decisão.
```
