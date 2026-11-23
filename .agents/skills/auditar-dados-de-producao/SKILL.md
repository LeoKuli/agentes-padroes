---
name: auditar-dados-de-producao
description: Método obrigatório antes de afirmar qualquer fato sobre os dados de um sistema em produção — quantos registros, quem está parado, se alguém recebeu mensagem, se a agenda bate, "está tudo certo", e também "não achei nada". Exige chave de junção provada, cardinalidade conferida, nível de evidência declarado e NÃO MEDIDO em vez de zero. Existe porque, em agosto de 2026, duas afirmações ditas com confiança estavam erradas e uma quase virou uma chave em produção que calaria dois clientes.
---

# Auditar dados de produção sem errar feio

Em agosto de 2026 um agente disse ao dono duas coisas graves e falsas no mesmo dia:

1. **"0 mensagens teriam sido bloqueadas"** — contou linhas numa tabela onde o evento bloqueado **não deixa
   linha**. Com esse número, uma chave foi virada em produção. Ela teria calado dois clientes que dividem o
   mesmo número de telefone com um parente.
2. **"17 cadastros nesta etapa sem compromisso marcado"**, com nomes e história — juntou duas tabelas pela
   chave errada (uma usa o id interno, a outra o id de exibição). O número real era **zero**. Os nomes eram
   de outras pessoas.

As duas têm a mesma forma: **uma medição foi inventada em vez de usar as que já existem, e nada foi provado
antes de falar.** O dono respondeu *"eu já não sei mais no que acreditar"*. Este método existe para isso não
repetir.

## Quando esta skill manda

Sempre que o agente for **afirmar um fato** sobre os dados de produção. Vale também para "não achei nada" —
ausência é afirmação, e é a mais fácil de errar.

## A cadeia. Cada elo derruba o próximo.

O projeto deve ter, versionado e com prova:

1. **Mapa de chaves** — para cada tabela, qual chave de junção ela usa e qual a cardinalidade.
2. **Bateria de controles sintéticos** sobre os detectores (positivos e negativos), que roda **antes** dos
   detectores contra produção.
3. **Detectores** — o SQL que mede, **o mesmo** que a bateria exercita.
4. **Alarme** — que abre e **fecha sozinho**, provado num banco descartável.

**Se um controle reprovar, a cadeia aborta e não imprime número nenhum** — nem escreve alarme. Rodando
sozinha, a cadeia tem horário e log próprios, e o log é lido.

Onde moram as ferramentas e o método completo fica no `docs/ESTADO.md` do projeto.

## As recusas — é isto que impede de errar

- **`INDETERMINADO` não é "provavelmente X".** É proibição de concluir sobre aquela tabela.
- **Consulta que estoura NÃO vira zero.** Vira `NÃO MEDIDO`, aparece no relatório e nunca some.
- **Ausência exige prova de rastro.** Antes de dizer "ninguém foi bloqueado" / "nenhuma repetida", rodar o
  mesmo detector sobre uma janela onde o evento **comprovadamente ocorreu**. Se ele não achar o caso
  conhecido, o zero de hoje é cegueira.
- **Nenhum alarme sem a bateria em 100%.** Alarme falso destrói o canal mais rápido que alarme nenhum.
- **`docker exec` sem `-i` não recebe stdin** — heredoc morre em silêncio. Conferir o EFEITO, nunca o
  código de saída.

## Chaves — medidas, nunca lembradas

Uma mesma coluna `*_id` pode apontar para lugares diferentes conforme a tabela (id interno × id de
exibição). Errar **não dá erro**: as duas sequências de id se sobrepõem na maior parte, então a junção
errada devolve dados plausíveis **de outras pessoas**.

- Classificar cada tabela em: **chave interna**, **chave de exibição**, **INDETERMINADO**.
- Anotar quando a coluna é texto e não número (junção crua estoura).
- Cruzar duas tabelas de famílias diferentes exige as **duas** chaves na mesma consulta.
- **Taxa de casamento não prova chave em espaço de id denso:** uma chave deslocada de UMA casa casou 372 de
  373. Prova é uma **relação** que a chave errada não satisfaz (por exemplo, um evento que precede o outro
  em segundos).

**E a cardinalidade, não só a chave.** Poucas tabelas são 1:1; a maioria é 1:N, com centenas de linhas por
entidade. Contar depois de juntar, sem agregar antes, dá número inflado plausível. Reconferir o mapa quando
surgir tabela nova ou quando o número parecer alto demais.

## Nível da evidência em toda afirmação

- **N1 — o artefato:** a conversa com horário, o texto da mensagem, o código rodando com entrada fixada.
- **N2 — fonte única, sem junção:** uma tabela, uma contagem; ou número que o próprio sistema calcula.
- **N3 — derivado:** junção ou consulta do agente. **Não vira afirmação sem bater com N1 ou N2.**

Ao relatar, dizer a origem. Número sem origem: o dono deve parar o agente.

## O alarme chegou em alguém?

A doença mais comum é o canal ficar **mudo parecendo ligado**. Não basta o alarme existir — tem de chegar.
Um bom detector lê a marca de leitura das notificações e acusa **volume alto com ZERO leituras em 30 dias**.

**O critério é zero, não taxa baixa, e isso é deliberado:** quem lê 3% dos avisos LÊ — o canal chega nele.
Uma regra por taxa acusaria os dois juntos e a afirmação forte ("ninguém nunca viu") viraria ruído. O piso
de volume também é deliberado: três avisos sem leitura não provam nada.

## Quem já mede (olhar antes de inventar consulta)

Antes de escrever SQL novo, listar o que o sistema já mede: tabela de achados da auditoria, comparadores de
paridade, tabela de falhas HTTP, eventos de SLA, contadores internos, a bancada de regressão.

**Discordância não se resolve por autoridade.** A ISA 500 diz que evidência obtida pelo auditor é mais
confiável que a produzida pela entidade auditada — e já houve os dois casos no mesmo dia: o detector estava
certo e o agente errado, **mas** um contador que o próprio sistema calculava estava errado (truncado no teto
de paginação). Quando discordam, **descer ao artefato (N1)**, e a discordância vira o achado principal.

## Armadilhas que já pegaram (todas reais)

- **Pessoa ≠ conversa.** Uma conversa pode ter dois ou três clientes (família dividindo um telefone).
  Agrupar por conversa acusa família como duplicata — e, na porta de saída, **cala o segundo cliente**.
- **Janela.** Uma confirmação de outro compromisso, dias antes, entra na conta sem recorte de janela e vira
  falso "em dobro".
- **Comentário no código é alegação, não evidência.** O comentário dizia "aconteceu ZERO vezes em 30 dias";
  medido, foram 5 em 40 dias.
- **Número certo por acaso é o pior erro** — o total bate enquanto o conjunto está errado. Compare
  **conjunto** (quem), não só contagem (quanto).
- **Comparar com NULL não dá erro, dá FALSO.** Filtrar por uma coluna 97% nula devolve um número pequeno e
  tranquilizador. Medir a nulidade antes; preferir tabela de **eventos** a coluna de estado.
- **`psql` imprime booleano conforme o cast** (`true`/`false` × `t`/`f`) — conferir antes de comparar.
- **Tabela de log de uma ferramenta pode não gravar sucesso** — "0 execuções" sai sempre. Medir pelo log do
  contêiner ou do proxy.
- **"errors=0" no log de sucesso NÃO é erro** (cuidado no grep).
- **Ferramenta de rotina mora em volume persistente**, não na imagem efêmera: o próximo deploy apaga e o cron
  falha **em silêncio**.

## Acrescentar um detector novo

1. A lógica vai **uma vez**, na casa dos detectores, com as origens declaradas. A bateria roda o **mesmo**
   SQL da produção — controle que testa uma cópia passa enquanto o real quebra.
2. Na bateria, pelo menos **um positivo e dois negativos**, tirados de casos reais — inclusive o legítimo
   mais parecido com o defeito (família, janela, cancelado).
3. **Sabotar o detector** e confirmar que a bateria reprova com exit 1.
4. Só então ligar na cadeia, com alarme que abre e fecha sozinho.

Lições que valem para o próximo:

- **Quem já mede antes, inclusive a fila.** O detector novo pode acrescentar diagnóstico, não a primeira
  visibilidade.
- **Janela de tempo passa pela bateria:** relógio injetado, fixture com data FIXA, controles nas duas
  fronteiras. A janela sai de medição, não de gosto.
- **Evento novo não tem rastro histórico:** prova sintética sobre a casa REAL (caso plantado + consultas
  reais), entidades escolhidas NA HORA (id fixo vira bomba). Prova que não passa = `NÃO MEDIDO`, e o
  detector não abre nem fecha nada.
- **Status "resolvido" não prova que alguém resolveu.**
- **Subida da ferramenta** respeita a trava da árvore do servidor e o portão; nunca cópia solta.

## Segurança, que não muda

Auditoria é **somente leitura**. Conserto é outro ritual, pelo portão. **Nunca** mandar mensagem de teste a
cliente. Segredo nunca no argv nem impresso. Leitura com **lista branca de colunas**: coluna JSON sai só com
as chaves, nunca o valor. Servidor que atende ao vivo: toda consulta com filtro de data ou `LIMIT` — **mas
auditoria de "quantos?" nunca usa `LIMIT`**. Antes de tocar dado real: backup e reversão escrita.

Relacionadas: [`antes-de-afirmar`](../antes-de-afirmar/SKILL.md) (comportamento) ·
[`auditoria-de-software`](../auditoria-de-software/SKILL.md) (controle positivo, mutação)
