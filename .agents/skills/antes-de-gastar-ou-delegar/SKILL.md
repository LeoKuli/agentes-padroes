---
name: antes-de-gastar-ou-delegar
description: Obrigatória antes de (1) afirmar ao dono qualquer coisa sobre custo, crédito, cobrança, saldo, assinatura ou limite; (2) iniciar, sugerir ou manter qualquer sessão, chave ou recurso cobrado por uso; (3) entregar trabalho a outro agente ou sessão que possa gerar gasto. Existe porque, em outubro de 2026, um agente afirmou que sessões de API usavam crédito promocional e elas foram cobradas no cartão, com recarga automática e sem teto.
---

# Antes de gastar ou delegar

Em outubro de 2026, um agente afirmou ao dono que as sessões de API que estavam rodando consumiam um
crédito promocional. Era falso: o crédito não cobria aquele produto, e a recarga automática cobrou no
cartão dezenas de vezes em quatro dias, sem teto configurado. O pedido de reembolso foi negado na
primeira resposta.

A causa não foi técnica: **o agente afirmou e agiu sem conferir na fonte**, tratando uma anotação antiga
("o crédito está guardado") como fato.

## Parte 1. Antes de afirmar qualquer coisa sobre custo

1. **Nenhuma frase sobre dinheiro sem fonte lida AGORA.** "Está coberto", "não custa", "usa o crédito",
   "dentro do plano", "sobrou saldo": só com a tela de cobrança ou a resposta da API que prova, lida
   nesta volta e citada na resposta. Sem fonte, a frase é: "não sei se custa; vou conferir em <onde>".
2. **Assinatura, API paga por uso e crédito promocional são três coisas diferentes.** Assinatura não
   cobra por uso. API cobra por token no cartão ligado à conta. Crédito promocional tem regras próprias
   e pode não cobrir o produto que você está usando — **ler a quais produtos ele se aplica**. Nunca
   trate um como o outro.
3. **De quem é o cartão?** Antes de qualquer coisa que possa cobrar, conferir qual forma de pagamento
   está ligada e de quem é. O cartão pode ser de uma empresa, não do dono.
4. **Recarga automática ligada = risco aberto.** Se houver recarga automática em qualquer serviço em
   uso, avisar o dono e pedir para desligar antes de seguir.

## Parte 2. Antes de iniciar ou manter algo que cobra por uso

- **Proibido abrir sessão ou chave de API paga por uso** sem teto de gasto configurado **e** o sim
  explícito do dono, dado no chat, com o valor máximo conhecido por ele.
- Para desenvolvimento, o padrão do dono (decisão de 03/11/2026) é trabalhar na **assinatura**, nunca por
  API paga por uso, e **não criar nem pedir chave de roteadores de modelos (OpenRouter e similares)**.
  Roteador de modelo pode existir como parte de um produto (a IA dentro de um app), não como motor do
  desenvolvimento. Na dúvida, perguntar.
- Qualquer serviço pago por uso (GPU em nuvem, anúncios, nuvem, servidor extra) só com teto de gasto
  configurado e o dono ciente do valor máximo.
- Se perceber que algo está cobrando sem o dono saber: **parar primeiro, avisar depois**, com o valor
  medido e a fonte.
- Dado de paciente ou de cliente nunca vai a API externa sem decisão expressa do dono.

## Parte 3. Antes de entregar trabalho a outro agente ou sessão

- Conferir **onde o trabalho vai rodar e quem paga**: na assinatura, num serviço pago por uso, numa
  máquina alugada. Se pode cobrar, vale a Parte 2.
- Respeitar a cota: medir o uso antes e depois de cada pacote grande, e parar antes de esgotar o limite
  combinado com o dono.
- Paralelizar com moderação: vários agentes ao mesmo tempo esgotam a janela de uso muito mais rápido do
  que parece. Ondas pequenas, com medição entre elas.
- **Quem decide gasto é o dono.** O agente propõe com o valor e a fonte; não decide.

## Parte 4. Como o dono confere

- Gasto de cada serviço pago por uso na semana, lido no painel do próprio serviço.
- Gasto de API paga por uso para desenvolvimento: tem de ser zero.
- Lista de afirmações de custo feitas na semana, cada uma com a fonte.

## Checagem rápida (responda antes de agir)

1. Vou afirmar algo sobre custo? Tenho a fonte desta volta? Mostrei de onde veio?
2. Isto pode cobrar em algum cartão? De quem é o cartão? Há teto? O dono disse sim a este valor?
3. Vou entregar trabalho a outro agente? Onde roda, quem paga, e quanto da cota isso consome?
