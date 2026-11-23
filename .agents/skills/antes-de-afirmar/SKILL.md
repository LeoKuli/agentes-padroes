---
name: antes-de-afirmar
description: Disciplina obrigatória antes de afirmar ao dono POR QUE o sistema se comportou de um jeito, QUEM fez o quê, ou SE uma mudança funcionou. Complementa `auditar-dados-de-producao` (afirmação sobre dado); esta cobre afirmação sobre comportamento, e exige que toda explicação cite a linha de registro que a prova.
---

# Antes de afirmar

Em agosto de 2026, num único dia, a bancada e o portão de deploy pegaram quase todos os erros do
agente. **O que chegou ao dono foram só as afirmações.** É esse buraco que esta skill fecha.

Os erros daquele dia, pela causa raiz e não pelo sintoma:

| o que o agente disse | por que estava errado |
|---|---|
| "a integração aceita divergência e por isso criou um registro fantasma" | **não abriu o log da integração.** Ele dizia sucesso, com releitura confirmada |
| "o atendente silenciou o cliente com justificativa falsa" | **filtrou só mensagens públicas.** O envio por modelo (template) fica como nota privada — o atendente tinha mandado, 11 segundos antes |
| "'Sim' nesta etapa é aceite da proposta" | **não olhou o que veio ANTES.** Era o clique no botão de um lembrete automático |
| "faça pelo sistema antigo primeiro" | **contornou o defeito** em vez de consertar — e a integração existe justamente para unificar no sistema novo |

As três primeiras têm a mesma forma: **a explicação foi inventada e dita antes de ler o registro.** A
segunda acusava uma pessoa real.

## A regra

**Toda afirmação sobre comportamento cita a LINHA de registro que a prova.** Não "o código faz X" — o
código descreve intenção. A linha do registro descreve o que aconteceu.

Antes de explicar qualquer coisa, achar o registro certo. Todo sistema sério tem algo assim; o
projeto deve manter este mapa no `docs/ESTADO.md` ou num ADR:

| pergunta | onde costuma estar a resposta |
|---|---|
| "por que esse registro mudou ou sumiu?" | log da integração (intenção, resultado, releitura, autor) |
| "mandaram mensagem para esse cliente?" | log de envios, que distingue humano de automação — **não** a tabela de mensagens sozinha |
| "quem mudou essa etapa?" | tabela de eventos de etapa (evento, não coluna de estado) |
| "esse alerta chegou em alguém?" | a marca de leitura da notificação |
| "o que o cliente estava respondendo?" | a saída IMEDIATAMENTE anterior, inclusive privada |
| "quem silenciou e por quê?" | o registro de silenciamento |
| "a auditoria viu isso?" | os achados da auditoria, inclusive os resolvidos (guardam o histórico) |

**Armadilha nº 1:** mensagem enviada por modelo (template) muitas vezes não deixa saída pública. Toda
consulta "só saídas públicas" responde "ninguém falou com ele" sobre uma mensagem que a pessoa
**recebeu**.

**E nenhuma porta é a única.** Em agosto de 2026 duas clientes com compromisso no dia apareceram sem
registro de envio no log de envios — o agente estava a um passo de reportar "ficaram sem aviso". Elas
tinham sido avisadas por OUTRA porta (uma marca de lembrete na própria tabela de compromissos), e uma
delas respondeu "Sim". O job que "não enviou" estava **certo**: ele existe para não mandar duas vezes.

→ Antes de dizer "ninguém avisou", listar **todas** as portas de saída e conferir cada uma. Zero numa
porta é zero **naquela** porta.

## Conferir o EFEITO, nunca o retorno

Três erros do mesmo dia, todos "o comando rodou, logo funcionou":

- **Checagem de sintaxe da linguagem verde não prova SQL válido.** Subiu uma consulta com uma vírgula
  faltando; a bancada inteira passou, o boot subiu, a fumaça deu 200 em tudo, e a seção estava morta
  em produção. → **SQL novo se executa contra o banco antes de subir**, em transação com `ROLLBACK`.
- **`ALTER TABLE` "rodou" e não criou nada.** A tabela pertencia a outro papel do banco, o app
  conectava com um papel sem permissão, e o `catch` engoliu o erro de permissão imprimindo mensagem
  de outro assunto. → depois de mudar schema, **consultar o catálogo** (`information_schema`); e testar
  a escrita **com o usuário do app**, não com o do agente.
- **Bancada reprovou por fuso horário.** Rodou num contêiner cru em UTC e o teste de expediente deu 0
  dos dois lados. → **mesmo ambiente da produção** (fuso, locale, versão). *Quando os dois lados dão
  zero, o suspeito é o arreio, não o produto.*

**Regra:** depois de qualquer mudança, consultar o estado que deveria ter mudado. Exit 0 não é prova;
linha nova é.

## Âncora estrutural, nunca posicional

A mesma armadilha pegou cinco vezes num dia, já documentada:

- `src.slice(i, i+1800)` quebra quando alguém escreve um comentário no meio.
- Uma bancada que troca comentário por espaço do mesmo comprimento faz âncora em texto de comentário
  devolver `-1`, e a asserção julga o trecho errado, em silêncio.

→ Ancorar em **código que tem de existir**: a chamada seguinte, o fecho da consulta, o nome de uma
função. Nunca em número de posição, nunca em comentário.

## Regra escrita ≠ regra testada

Um teste de apelido foi escrito como prefixo com limite de palavra e não casou o nome completo que o
motivou — zero marcados, e quase passou. → **toda regra nova roda contra o caso concreto que a motivou,
antes de dizer que funciona.** Controle positivo + os negativos mais parecidos com ele.

## Não contorne o defeito

O dono cortou, com razão: *"qual o sentido de fazer por fora se toda a integração visa unificar as ações
pelo sistema?"*. A proposta roteava em volta de um defeito — desfazia o produto para poupar trabalho.

→ Quando a saída for "faça por fora", parar e perguntar: **isso desfaz o motivo pelo qual a coisa
existe?** Se sim, o conserto é no caminho principal.

## Dizer "não sei" e "não medido"

**Consulta que não enxerga a população não devolve zero, devolve NÃO MEDIDO.** Uma contagem de cadastro
duplicado feita num espelho deu zero — mas o espelho marcava com um valor nulo justamente os cadastros
que o sistema novo cria. Medido na fonte certa, havia pessoas com quatro cadastros.

→ Antes de relatar zero: **essa consulta conseguiria ver o caso se ele existisse?** Se não sabe, é não
medido, e diz isso.

## Corrigir rápido e sem drama

Quando o agente errar e o erro mudar a conclusão do dono, retira em uma frase, diz o que a prova mostra,
e segue. Sem penitência, sem recontar a lista de erros. **Acusação sobre pessoa real se retrata na hora e
com o registro na mão.**

## Roteiro curto (o que rodar antes de falar)

1. Vou **afirmar** ou **perguntar**? Se afirmar, tem linha de registro? Qual?
2. A consulta que usei **enxergaria o caso** se ele existisse? (envio por modelo = nota privada!)
3. Mudei algo? Consultei **o efeito**, não o retorno?
4. A regra nova rodou contra **o caso concreto** que a motivou?
5. Estou propondo contornar em vez de consertar?

Relacionadas: [`auditar-dados-de-producao`](../auditar-dados-de-producao/SKILL.md) (afirmação sobre dado:
chaves, cardinalidade, níveis de evidência) · [`auditoria-de-software`](../auditoria-de-software/SKILL.md).

Fontes: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) ·
[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
