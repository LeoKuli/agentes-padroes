---
name: embasar-antes-de-mudar
description: Antes de qualquer alteração de código, conserto de defeito, detector novo, mudança de arquitetura ou proposta de abordagem, nomear a classe do problema, pesquisar a prática validada por profissionais da área e a armadilha dela, e citar a fonte. Proibido agir por intuição. Complementa `antes-de-afirmar` (afirmar) e `auditoria-de-software` (verificar); esta cobre decidir como fazer.
---

# Embasar antes de mudar

Em setembro de 2026, depois de uma noite inteira de defeitos encontrados, o dono estabeleceu:

> *"Busque na internet estratégias para encontrar estes erros, ajustá-los, auditar. Não podemos mais
> ter tantas falhas."* · *"Jamais fazer algo que não tenha embasamento."*

E antes disso: *"toda e qualquer alteração, ajuste, código novo deve se encaixar na arquitetura"*.

**O que motivou a regra:** cada defeito vinha sendo tratado como caso isolado, com o conserto inventado
na hora. Quando finalmente se pesquisou, **quatro defeitos daquela rodada eram a mesma família, com nome
e cura conhecidos há anos** — e o próprio conserto proposto (script de shell + cron, fora do código
versionado) era a mesma doença que se estava consertando.

## A regra

**Nenhuma mudança de código nasce de intuição.** Antes de escrever, responder três perguntas:

1. **Isto tem nome?** A classe de defeito ou a técnica quase sempre já foi catalogada. Procurar o nome
   antes de inventar a solução — o nome traz a literatura junto.
2. **Qual a prática validada?** Pesquisar (documentação oficial, papers, engenharia de empresas que
   operam isso em escala). Preferir fonte primária a blog de opinião.
3. **O que a fonte diz que dá errado?** Toda técnica tem armadilha documentada. Se a busca não trouxe a
   armadilha, a busca não terminou.

**Citar a fonte ao propor.** Sem fonte, é palpite — e palpite não entra em sistema que atende pessoas.

## Ordem das fontes, quando discordam

1. **A medição do próprio sistema** (o registro). Nenhuma fonte externa vence um número medido aqui.
2. **Documentação oficial** do produto, para fato de API.
3. **Engenharia publicada** por quem opera em escala (Google, Meta, GitHub, Airbnb, Mercari…).
4. **Literatura acadêmica** revisada — ótima para nomear a classe e para saber a taxa de erro.
5. **Blog/expert por último**, e nunca sozinho.

Fonte externa dá o **método**; o **número** é sempre do sistema. Foi assim que a taxa de mutante
equivalente publicada (4–39%) explicou um sintoma local sem ninguém precisar adivinhar.

## Classes que já viraram prática

| classe | o que a literatura chama | sintoma | fonte |
|---|---|---|---|
| Coluna lida por N, escrita por 0 | coluna **órfã / read-only** | coluna vazia não dá erro; ficou morta quase dois meses | [ColumnLens](https://rubygems.org/gems/columnlens) · [Ecto](https://geekmonkey.org/detecting-unused-database-columns-using-ecto-schemas/) |
| Job que roda e não produz | **dead man's switch + validação de saída** | job com zero saídas por dois meses | [crontap](https://crontap.com/blog/dead-man-switch-explained-for-developers) · [cronradar](https://cronradar.com/comparisons/cron-monitoring-best-practices) |
| Mutação que não prova nada | **mutante equivalente** (4–39%) | mutação morta pela asserção errada | [arXiv 2607.00511](https://arxiv.org/pdf/2607.00511) |
| Trocar sistema em produção | **Strangler Fig · Parallel Run** | — | ver [`migracao-de-sistema`](../migracao-de-sistema/SKILL.md) |
| Mover código sem cegar teste | **Parallel Change** | — | ver [`refatorar-sem-quebrar`](../refatorar-sem-quebrar/SKILL.md) |
| Contar chamadas sem errar | **AST, nunca regex** | 25% de erro na amostra | ver [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md) |

## Roteiro (antes de tocar no editor)

1. **Nomear a classe.** "Isto é um X?" Se não sabe o nome, pesquisar o nome primeiro.
2. **Pesquisar a prática** e a **armadilha** dela. Duas buscas no mínimo: como se faz, e como falha.
3. **Confrontar com a medição local.** A prática vale aqui? Medir a população antes de aplicar.
4. **Encaixar na arquitetura** (ver `docs/REGRAS-DO-DONO.md`, regra "Toda mudança entra pela
   arquitetura"): módulo com dependências injetadas, SQL na casa dele, decisão no código, cicatriz que
   executa, mutação **na trava certa**, portão.
5. **Citar a fonte** no comentário do código e na resposta ao dono.
6. Se a pesquisa **não achar** prática consolidada, dizer isso — e então a escolha é explicitamente do
   projeto, declarada como tal, com o risco escrito.

## O que NÃO é embasamento

- "Sempre fizemos assim aqui" — é inércia, não método.
- Um blog isolado sem fonte primária.
- Analogia com outro projeto sem medir se a população é parecida.
- **A intuição do agente**, por mais confiante que soe.

## Limite honesto

Pesquisar não substitui medir. A literatura diz **o que costuma acontecer**; só o registro do sistema diz
**o que aconteceu aqui**. Quando os dois discordam, o registro ganha e a discordância vira o achado — o
mesmo princípio da ISA 500 usado em [`auditar-dados-de-producao`](../auditar-dados-de-producao/SKILL.md).

Relacionadas: [`auditoria-de-software`](../auditoria-de-software/SKILL.md) ·
[`antes-de-afirmar`](../antes-de-afirmar/SKILL.md) · [`refatorar-sem-quebrar`](../refatorar-sem-quebrar/SKILL.md) ·
[`migracao-de-sistema`](../migracao-de-sistema/SKILL.md) · [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md)
