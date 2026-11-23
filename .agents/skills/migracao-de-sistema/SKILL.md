---
name: migracao-de-sistema
description: Método para substituir um sistema em produção por outro sem perder cliente no caminho — estrangulamento, execução paralela, calibração do comparador, virada reversível e migração de dados — ancorado em Strangler Fig (Fowler), Parallel Run e Tracer Write (Sam Newman), Scientist (GitHub), problema do dual-write e migração sem downtime (Mercari). Use ao planejar ou executar troca de sistema, ligar modo sombra, comparar velho contra novo, migrar dados, virar tráfego, desligar o legado, e antes de afirmar que a paridade está provada.
---

# Migração de sistema — o método

> **A regra que gera todas as outras:** um comparador que nunca foi calibrado **não mede nada**, e o
> resultado dele se parece exatamente com sucesso. Antes de confiar em qualquer paridade, rode a
> comparação com **os dois lados sendo o sistema velho** e exija zero divergência.
>
> Custo de ignorar isto, medido: uma sombra aprovou uma virada por dias — e era **cega**. Um índice único
> valia também em modo sombra, então a reserva bloqueada não gravava linha nenhuma, e silêncio foi lido
> como aprovação. A virada foi revertida depois de feita.
>
> A mesma família apareceu duas vezes mais: uma relação metamórfica `f(a) == f(b)` que **colapsava os
> dois lados juntos** sob sabotagem, e um comparador de produção com **28 rodadas em que os dois lados
> leram zero** e o painel escreveu "sem divergência".

---

## 1. Estrangular, não substituir (Strangler Fig)

Nunca troque o sistema inteiro num evento. Ponha uma **fachada** na frente e mova uma capacidade por vez,
com o velho de pé o tempo todo.

**O alerta que vem junto:** a fachada vira **ponto único de falha**. Isso não impede o uso — obriga a:

- a fachada **responder e só depois processar** (ACK imediato, trabalho em segundo plano);
- ter **kill-switch** que a desliga sem deploy;
- medir a latência que ela acrescenta **antes** de ligar.

> Detalhe que vale ouro em webhooks assinados: a fachada valida a assinatura, responde 200 na hora,
> deduplica pelo id da mensagem e repassa o **corpo cru com a assinatura original** ao destino. Repassar
> o corpo cru faz o destino validar a assinatura sem adaptação nenhuma.

## 2. Conte as PORTAS antes de desenhar a fachada

Um sistema em produção quase nunca tem uma entrada só. Fachada que cobre uma porta e ignora as outras dá
sensação de estrangulamento sem estrangular nada.

**Levante a lista antes:** webhooks de terceiros, cron, filas, uploads, integrações internas, botões
administrativos, e **canais alternativos** (um segundo número, um segundo provedor).

**E levante por AST, nunca por `grep`** — ver [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md):
uma contagem por regex errou 25% da amostra conferida.

> Medido: o plano de virada inteiro foi desenhado em cima de UMA porta, e o dono corrigiu — um segundo
> canal entrava por outro webhook, fora da fachada, com mais de mil mensagens em dezenas de conversas.
> Duas portas, não uma.

## 3. Execução paralela: o velho é a FONTE DE VERDADE

Chame os dois, compare, e **devolva sempre o resultado do velho**. O novo não tem voz enquanto a paridade
não fecha.

| Papel | Quem | O que pode fazer |
|---|---|---|
| Controle | sistema velho | decide, responde, escreve |
| Candidato | sistema novo | calcula, registra, **não fala com ninguém** |

- **Ordem aleatória entre os dois.** Se um sempre roda primeiro, ele vê um estado que o outro não vê.
  Quando os dois são processos separados lendo bancos diferentes, declare a **tolerância de instante** e
  justifique-a.
- **Comparação por campo, não por igualdade de objeto.** `==` em estrutura rica compara coisas que não
  interessam (id, timestamp) e esconde as que interessam.

## 4. Calibrar o comparador ANTES de usá-lo

Primeiro experimento: **controle contra controle** — os dois lados sendo o sistema velho.

- **zero divergência** → o comparador serve;
- divergência → o comparador está quebrado, e qualquer número depois seria ficção.

É o controle positivo da [`auditoria-de-software`](../auditoria-de-software/SKILL.md) aplicado à migração.
**Nenhum número de paridade vale antes desta calibração.**

## 5. Divergência tolerada é DÍVIDA, não zero

Toda diferença conhecida-e-aceita vai para um **catálogo**, com motivo e dono. O critério de virada não é
"sem divergência nova": é **catálogo vazio**.

> Vem do Scientist: se existe bloco de `ignore`, o candidato **garantidamente** difere. Tolerância
> numérica é a mesma coisa com outro nome — "2% de tolerância" é um `ignore` em ponto flutuante.

Cada linha responde: **o que difere · por quê · some sozinho na virada ou alguém precisa consertar?**

## 6. "Não consegui comparar" nunca é "está igual"

O comparador precisa de **três** desfechos: `igual`, `diferente`, `não consegui`. Comparador que devolve
lista vazia quando falhou ao ler é o auditor cego.

E do outro lado: **divergência que ninguém lê não existe**. Um comparador acusou 85 divergências reais a
cada 2 minutos por 3 dias — cerca de 3.195 rodadas — e ninguém viu. Ligue a divergência a uma
**pendência com dono e prazo**, não a um painel.

## 7. O candidato registra o que FARIA, sem fazer (Spy)

Comparar contagem é raso. Compare **decisão**: o novo grava "eu teria respondido isto / movido para esta
etapa / disparado este modelo", e a comparação é contra o que o velho de fato fez.

## 8. Escrita NUNCA entra em execução paralela

O Scientist é taxativo: só é seguro embrulhar o que **não muda dado**. Para escrita: duplicar no momento
da escrita e **verificar na leitura**.

A garantia de que o candidato não escreve **não pode ser promessa do código**. Promessa some numa
refatoração. A garantia é externa:

- **papel de banco sem `INSERT`/`UPDATE`/`DELETE`** para o candidato;
- adaptador de envio trocado por um que só registra;
- kill-switch consultado a cada operação, não no boot.

### O ENVELOPE também é contrato — e a cicatriz tem de ler como o consumidor lê

Em agosto de 2026 a caixa de entrada de um sistema ficou **vazia por 4 horas** com um atendente no meio de
uma conversa. Os dados estavam certos: mesmas mensagens, mesma contagem, mesmo checksum. O que diferia era
a **casca**: a fonte antiga devolvia `{ payload: [...] }`, a nova devolvia o array cru, e o consumidor
fazia `(data && data.payload) || []`. Array não tem `.payload` — **zero mensagens em toda conversa**.

Três redes falharam juntas:

- o **comparador** olhava contagem e checksum — os dados *eram* iguais;
- a tabela de falhas HTTP **só guarda falhas**: rota que devolve 200 com o formato errado não deixa
  rastro;
- **a cicatriz escrita naquela mesma manhã** chamava o montador e lia `r.length` **direto**. Passou
  inteira enquanto o formato esvaziava a produção.

> **Cicatriz que lê o retorno de um jeito que nenhum consumidor usa não mede o contrato — mede a
> expectativa de quem a escreveu.** A primeira pergunta dela deve ser *"o consumidor leria zero?"*.

E cuidado com a cicatriz que **fossiliza o defeito**: cicatriz que reprova um conserto é suspeita de estar
protegendo o erro.

**Ao trocar a fonte de um serviço, compare:** quantos itens por vez · a casca do retorno · quais campos ·
com que tipo · e o que o consumidor **deriva** disso (`has_more` calculado do tamanho da página é a
armadilha clássica).

### Quando o efeito é EXTERNO e irreversível, compare a intenção

Quando o efeito sai do sistema — mandar mensagem, cobrar cartão, disparar e-mail — **duplicar é o dano**.
Compare **o que o candidato mandaria**: o novo monta o payload completo, grava, e **não entrega**.

E agrupe os call sites por **quem sofre o erro**: dos 38 envios medidos, 27 eram nota interna e 11 falavam
com o cliente. Os 27 vão juntos; os 11, um por vez.

## 9. Dual-write é o defeito, não a solução

Escrever "nos dois" sem transação única é o **problema do dual-write**: um lado grava, o outro falha, e a
inconsistência nasce silenciosa e permanente.

| Saída | Como funciona | Quando usar |
|---|---|---|
| **Outbox transacional** | o evento é gravado na MESMA transação do dado; um processo lê a outbox e publica | você controla o código que escreve |
| **CDC** | um leitor acompanha o log do banco e deriva os eventos | você não controla todos os escritores |

Estado que vive em duas casas (no banco **e** em atributos de um serviço terceiro) é dual-write herdado.
A migração não deve reproduzir isso; deve **acabar com a segunda casa**.

## 10. Migrar os dados: backfill, throttle, reconciliação

- **Backfill com freio.** Lotes, com throttle, e **pausa sozinho** se o atraso de replicação passar do
  limite.
- **Reconciliação em três níveis:** contagem por tabela, **checksum** por faixa, e amostra inspecionada à
  mão. Contagem sozinha aprova duas bases igualmente erradas e não vê permutação.
- **A chave de identidade entra antes do backfill.** Decidir depois é caro: o dado já migrou com a chave
  errada.
- **Migração é fotografia, e ela envelhece**: copiar de sistema vivo diverge sozinho, por linhas novas
  **e** por linhas que mudaram de atributo. A segunda só a distribuição pega.

## 11. Virar e voltar

- **Ensaie o restore antes de tudo.** Backup que não foi restaurado não é backup.
- **Ensaie o rollback antes da virada**, não durante.
- **Mantenha a escrita dupla um tempo depois de virar**, como rede, com marcador para voltar o tráfego.
- **O velho fica de pé, desligado mas intacto**, por um período combinado.
- A virada deve ser **uma mudança de configuração**, reversível em minutos. Se exige deploy, não é
  reversível.
- **Virar a entrada sem a saída deixa o cliente mudo**: as duas pontas viram juntas ou nenhuma.

## 12. Sinais de que a migração está mentindo

| Sinal | O que costuma ser |
|---|---|
| paridade fechou rápido demais | o comparador não foi calibrado |
| divergência constante no mesmo número | teto de paginação, limite de lote, artefato do instrumento |
| número redondo ou uniforme demais | artefato do instrumento, não medição |
| os dois lados em zero | ninguém leu nada — é `não consegui`, não `igual` |
| catálogo de tolerâncias crescendo | você está normalizando defeito, não convergindo |
| ninguém abriu o painel esta semana | a divergência não virou pendência |
| a sombra "não achou nada" desde que subiu | ela provavelmente não está recebendo tráfego |

## Roteiro

0. **Ordem geral:** estrangular **leituras primeiro, depois escritas, depois o dado compartilhado**.
1. **Levantar as portas.** Todas, **por AST**. Escrever a lista, incluindo o que não foi possível ler.
2. **Fachada em uma porta**, com ACK imediato e kill-switch. Medir a latência acrescentada.
3. **Levantar o contrato dos consumidores** e tornar **explícito** todo default do sistema velho.
4. **Calibrar o comparador**: velho contra velho, exigir zero.
5. **Ligar a execução paralela** com o candidato mudo e papel de banco só-leitura.
6. **Catalogar cada divergência** com motivo e dono; trabalhar até o catálogo esvaziar.
7. **Comparar decisão, não só contagem** (spy).
8. **Resolver o dual-write** com outbox ou CDC — antes de migrar dado.
9. **Backfill com freio + reconciliação em três níveis.**
10. **Ensaiar restore e rollback.**
11. **Virar por configuração**, com escrita dupla ainda ligada e marcador de volta.
12. **Desligar o velho** só depois da janela de estabilização combinada.

## Fontes

- Martin Fowler, *Strangler Fig Application* (2004) — e as versões de [AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html), [Azure](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig) e [Thoughtworks](https://www.thoughtworks.com/en-us/insights/articles/embracing-strangler-fig-pattern-legacy-modernization-part-one)
- Sam Newman, *Monolith to Microservices* — Parallel Run, Tracer Write, Spy, Dark Launching ([site do autor](https://samnewman.io/books/monolith-to-microservices/))
- [github/scientist](https://github.com/github/scientist/blob/main/README.md)
- [Flexport Engineering](https://flexport.engineering/using-githubs-scientist-library-to-refactor-with-confidence-9d34600edd5e) — rodar nas duas ordens
- [Confluent, *The Dual-Write Problem*](https://www.confluent.io/blog/dual-write-problem/) e [AWS, *Transactional outbox*](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
- [Mercari Engineering, *Zero Downtime Migration with Strong Data Consistency*](https://engineering.mercari.com/en/blog/entry/20241113-designing-a-zero-downtime-migration-solution-with-strong-data-consistency-part-v/) e [LaunchDarkly](https://launchdarkly.com/blog/3-best-practices-for-zero-downtime-database-migrations/)

Relacionadas: [`migrar-sistema-legado`](../migrar-sistema-legado/SKILL.md) (o fio de uma migração longa) ·
[`inventario-e-codemod`](../inventario-e-codemod/SKILL.md) · [`auditoria-de-software`](../auditoria-de-software/SKILL.md) ·
[`refatorar-sem-quebrar`](../refatorar-sem-quebrar/SKILL.md) · [`antes-de-afirmar`](../antes-de-afirmar/SKILL.md)
