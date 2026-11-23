---
name: auditoria-de-software
description: Método de auditoria e verificação de software ancorado em literatura validada (mutation testing do Google, taxonomia de flaky tests de Luo et al., IEEE 1028, ODC, chaos engineering, teste metamórfico) e em defeitos medidos nos projetos do dono. Use ao auditar código, avaliar se uma suíte protege de verdade, escrever ou consertar cicatrizes de regressão, caçar flake, montar sabotagem/mutação, julgar uma medição, e antes de afirmar que algo está verificado — verificação que não pode reprovar não é verificação.
---

# Auditoria de software — o método

> **A regra que gera todas as outras:** uma verificação que **não pode reprovar** não é verificação.
> Antes de confiar em qualquer detector — teste, varredor, portão, script de sabotagem, consulta SQL —,
> prove que ele **acusa quando deve** e **cala quando não deve**.
>
> Custo de ignorar isto, medido: o arreio de sabotagem de um dos projetos aprovou **todas** as
> sabotagens que rodou durante uma semana — 207 na varredura final — sem medir uma sequer. Ambiente
> mínimo → o banco não subia → a suíte devolvia `rc=1` **sempre** → o arreio lia isso como *"a cicatriz
> reprovou"*. A frase "sabotagem verificada" foi para cerca de 20 commits e dois documentos de
> arquitetura sem lastro. Consertado o arreio, **24 cicatrizes** não reprovavam.

---

## 1. Controle positivo e controle negativo (o alicerce)

Emprestado do desenho experimental das ciências naturais; é o que separa auditoria de cerimônia:

| Controle | Pergunta | Sem ele |
|---|---|---|
| **Positivo** | o detector acusa um caso que sabidamente deveria acusar? | detector cego devolve lista vazia, e vazio **se parece com saúde** |
| **Negativo** | o detector cala num caso que sabidamente não deveria acusar? | detector que acusa tudo faz o próximo dev apagar o teste |

**Todo varredor precisa dos DOIS, e de um terceiro piso:**

1. **Há o que varrer** — `assert length(arquivos()) > 200`. Sem isto, o varredor passa por não ter
   olhado nada.
2. **A varredura enxerga** — alimente um trecho sintético com o defeito e exija que ele apareça.
   *Três varredores medidos tinham o piso 1 e nenhum tinha o piso 2.*
3. **A varredura não acusa o legítimo** — alimente o padrão permitido e exija silêncio.

```
# ERRADO: piso 1 sozinho
assert length(arquivos()) > 50
assert infratores == []

# CERTO: os três
assert length(arquivos()) > 50
assert [{_, 2, _}] = detectar(trecho_com_o_defeito)   # positivo
assert detectar(trecho_legitimo) == []                # negativo
assert infratores == []
```

**Ausência de queixa não é aprovação.** Um script que estoura antes da primeira verificação não imprime
falha nenhuma e passa por verde. Todo arreio deve exigir que o processo **chegue ao fim e diga que
chegou** — não basta olhar o código de saída.

---

## 2. Mutação / sabotagem — como fazer certo

Sabotar o código e exigir que o teste reprove é **mutation testing**, e a literatura já mapeou as
armadilhas. Vale ler o que o Google aprendeu rodando isso em escala.

### 2.1 O mutante equivalente (a "sabotagem inócua")

Um mutante é **equivalente** quando é sintaticamente diferente mas semanticamente idêntico: não existe
teste capaz de matá-lo. A taxa em código real vai de **4% a 39%**, e detectá-los é formalmente
indecidível.

Quando uma cicatriz não reprova sob sabotagem, **a primeira hipótese não é "o teste é fraco"** — é *"a
mutação não mudou comportamento"*. Formas medidas:

| Forma | Exemplo real |
|---|---|
| **Código morto naquele caminho** | mutar o tratamento de exceção externo quando o interno já converteu a exceção |
| **Chave a mais num mapa** | acrescentar a um mapa uma chave que ele já tinha, com o mesmo valor |
| **Predicado já implicado** | `WHERE estado = 'reservado'` implica `WHERE estado <> 'falhou'`; o banco escolhe o mesmo índice |
| **Alvo por número de linha** | `mix test arquivo:99` não roda nada e **sai 0** |
| **Alvo no guarda errado** | pedir a um teste de runtime que reproduza defeito de ordem de carregamento |

### 2.2 Regra que mora em N lugares — mutar uma camada mede a REDUNDÂNCIA

Num código com defesa em profundidade, apagar **um** ponto não mede a cicatriz: a camada vizinha segura
o comportamento e o teste passa com razão.

> Medido: "exceção vira degradado" morava em **três** tratamentos de exceção empilhados, em três
> funções encadeadas. Foram precisas três tentativas para entender. Defesa em profundidade é o
> comportamento desejado; o errado era a medição.

**A sabotagem honesta apaga a regra INTEIRA** — todos os lugares onde ela está escrita. Ferramenta de
sabotagem deve aceitar lista de edições, não uma só.

### 2.3 A sabotagem tem de produzir o defeito que ela NOMEIA

Trocar só a escrita por uma chave fixa vira "nunca acusa" — outro defeito, não o que a cicatriz guarda.
Se a mutação produz um estrago diferente do nome dela, o resultado não diz nada sobre a cicatriz.

### 2.4 O que o Google mede (e o que ele recusa medir)

- **Mutante produtivo** = aquele para o qual *escrever um teste melhoraria a suíte*. **Improdutivo** =
  trivialmente equivalente, ou detectável mas inútil (mutar capacidade de coleção, valor de timeout).
  A produtividade subiu de **15% para 89%** com heurísticas.
- **Nós áridos** (*arid nodes*): posições da AST onde mutar só gera lixo, marcadas **antes** da
  mutagênese. Eles mantêm **mais de cem regras** disso.
- **Mutation score é rejeitado como métrica**: *"nem concreto nem acionável, e não guia o teste"*. O
  sinal deles é feedback humano — **82%** dos mutantes apresentados foram marcados como produtivos.
- **No máximo um mutante por linha coberta**, e no máximo 7× o número de arquivos do changelist.
  Mediana de **7 mutantes por changelist**, contra 820 na mutagênese tradicional.

**Tradução:** não persiga cobertura de mutação. Persiga *"esta regra específica, se apagada, faz alguém
reprovar?"* — uma sabotagem por regra de negócio nomeada.

---

## 3. Caçar flake — comece pela taxonomia, não pelo palpite

Luo et al. (FSE 2014) classificaram 201 correções de flaky test em 51 projetos. **Rodar a suíte muitas
vezes do mesmo jeito não encontra a maioria delas.** As dez causas:

| # | Causa | Peso | Como provocar de propósito |
|---|---|---|---|
| 1 | **Async wait** | 45% | reduzir timeouts, injetar latência |
| 2 | **Concorrência** | 20% | rodar com paralelismo máximo |
| 3 | **Ordem dos testes** | 12% | variar a semente; rodar arquivos isolados vs em lote |
| 4 | Vazamento de recurso | | rodar a suíte duas vezes no mesmo processo |
| 5 | Rede | | cortar a rede; apontar para host morto |
| 6 | **Tempo** | | mudar a HORA em que a suíte roda (ver §4) |
| 7 | IO | | disco cheio, permissão negada |
| 8 | Aleatoriedade | | fixar e variar a semente |
| 9 | Ponto flutuante | | comparar com tolerância explícita |
| 10 | Coleção não ordenada | | ordenar antes de comparar; ou embaralhar de propósito |

> Medido: três flakes e **três cicatrizes decorativas** eram categoria 6. Fora do expediente a régua
> não manda nada de ninguém — então *"cliente inativo não recebe"* era verdade para todo mundo, e a
> asserção não separava nada. Dez rodadas limpas não acharam, porque foram todas de dia.

---

## 4. Desenhar o experimento: o controle que separa as hipóteses

Vem do chaos engineering — hipótese de estado estável, grupo de controle e grupo experimental — e é a
disciplina que impede uma auditoria de acusar inocentes.

**Antes de rodar, responda: "o que MAIS explicaria este resultado?"** Depois desenhe o regime que
distingue as duas coisas. Se não houver, o experimento não mede o que diz medir.

### O ciclo

1. **Estado estável** — o que é "normal", medido por um número, não por impressão.
2. **Perturbação MÍNIMA** — mude *uma* variável. Perturbação larga mede duas coisas ao mesmo tempo e
   produz vítimas que parecem defeitos.
3. **Controle** — mesma mudança de forma, sem a variável de interesse.
4. **Diferença** — só o que muda entre experimental e controle é achado.

> Medido: para descobrir se algum teste dependia da hora, mover a janela de expediente para o dia
> inteiro **mediu duas coisas**. A prova veio sozinha: **os acusados trocaram de lado entre duas rodadas
> seguidas.** A versão correta desloca a janela por uma faixa pequena e roda um **terceiro regime de
> controle** com a faixa longe de agora. De quatro "culpados" sobrou zero.

### Vítimas da perturbação precisam APARECER

Testes que afirmam justamente aquilo que você perturbou vão quebrar. Elas **não são defeito e não são
ruído** — são o custo do instrumento. Liste-as separadamente; um relatório que só mostra o diff parece
ter rodado uma suíte limpa quando não rodou.

### Ambiente de teste mais permissivo que a produção esconde a regra

Quando o arnês relaxa uma restrição que a produção impõe, **a cicatriz escrita dentro dele não pode
provar a regra** — e escrever mais casos lá dentro não adianta. A cicatriz precisa **sair** do ambiente
de teste.

> Medido: uma função fixava o tenant com `SET LOCAL`, cujo escopo é a **transação**. No sandbox de teste
> do ORM, a "transação" interna é um savepoint dentro da transação única do teste, e savepoint liberado
> não desfaz `SET`. Duas consequências:
>
> 1. Consultar "fora de tenant" num teste está, na verdade, **dentro do último tenant fixado**.
> 2. A regra *"o ajuste é LOCAL, e por isso nunca vaza entre conexões do pool"* fica **invisível**: com
>    tudo numa transação só, `LOCAL` e `GLOBAL` se comportam igual, e trocar um pelo outro passa na
>    suíte inteira. O defeito liberado é o pior num sistema multi-cliente — tenant grudado na conexão,
>    requisição seguinte lendo dados de outro cliente, silencioso e dependente de carga.
>
> A saída foi rodar essa cicatriz com transações de verdade (modo sem sandbox). É o único lugar onde a
> diferença existe, logo é o único lugar onde a cicatriz vale.

**Como procurar:** liste o que o arnês faz de diferente da produção — transação única, relógio
congelado, adapter falso, fila síncrona, cache desligado, um processo só — e pergunte de cada item: *que
regra esta facilidade torna impossível de reprovar?* Cada resposta é uma cicatriz que precisa morar fora.

### Todo instrumento tem teto — escreva o teto na saída

Quando o método tem limite conhecido, o relatório diz **"suspeitos, não condenados"** e explica o que
ainda pode explicá-los.

---

## 5. Cheiros de teste que fazem a suíte mentir

Além do catálogo clássico (*Assertion Roulette*, *Mystery Guest*, *Eager Test*, *Sensitive Equality*,
*Conditional Logic*), estes foram medidos e merecem busca ativa:

| Cheiro | Como se parece | Por que engana |
|---|---|---|
| **Asserção tautológica** | `assert html =~ acao(motivo)` | `html =~ ""` é sempre verdade. Exija que a resposta signifique algo |
| **Testar a ponta, não a primitiva** | `refute armado?()` para medir o interruptor | `armado?` é `a() and b()`; o `and` curto-circuita e a ponta só vê a primeira perna que falha |
| **Replicar o default** | `get_env(:app, :chave, 30)` no teste | o teste vira cópia do código; mudar o default não reprova nada. **Pergunte ao código**, com piso |
| **Olhar só o estado final quando a regra é de ORDEM** | conferir o banco depois da ação | "registrou e mandou" e "mandou e registrou" terminam iguais. Use um **espião** que observa *durante* |
| **Cenário que não separa** | entrada 9:00, saída 9:20 | 20 minutos no relógio de parede **e** no de expediente. O cenário tem de dar respostas diferentes sob as duas hipóteses |
| **Promessa no `describe` sem caso** | "um cliente que cai não cala os outros" | nenhum teste fazia cliente nenhum cair |
| **Um exemplo cobrindo várias alternativas** | regex `(já falei\|acabei de dizer\|você não leu)` testado com *"eu já falei isso, você não leu?"* | a frase casa em **duas** alternativas; apagar uma deixa a outra segurando. **Um regex com N alternativas é N regras** |
| **Cenário barrado por uma regra ANTERIOR à que o teste nomeia** | "endereços parecidos não são a mesma mensagem" com `120` × `125` | quem separa ali é a regra dos **dígitos**, não o limiar de semelhança. Para medir uma regra, o cenário precisa **falhar em todas as outras** |
| **Limiar numérico torna o TAMANHO do exemplo parte do teste** | `jaro >= 0.95` com duas letras trocadas numa frase curta | dá **0,896** — abaixo do limiar. O teste passava pelo limiar, não pela regra. **Meça o número em vez de supô-lo** |

---

## 6. Quando não há oráculo: teste metamórfico

Quando você não sabe a resposta certa, ainda sabe **relações** que ela tem de obedecer. Transforme a
entrada de um jeito conhecido e exija que a saída se relacione conforme.

- Reordenar as mensagens de uma conversa **não pode** mudar quantas duplicatas são contadas.
- Somar um dia inteiro de expediente à espera **tem de** somar exatamente a jornada em minutos.
- Rodar a varredura duas vezes seguidas **tem de** dar o mesmo conjunto de achados (idempotência), e a
  segunda **não pode** duplicar linha.
- Renomear um cadastro **não pode** mudar nenhum outro campo.

Instrumento certo para métrica, relatório e agregação. **E toda relação `f(a) == f(b)` precisa de piso:**
se os dois lados colapsam juntos (os dois dão zero), a igualdade passa sem provar nada.

---

## 7. Classificar o que você achou (ODC)

A **Orthogonal Defect Classification** (IBM, Chillarege) organiza cada defeito por, no mínimo:

- **Tipo** — o que mudou no código para corrigir (atribuição, checagem, algoritmo, interface, função,
  sincronização, build).
- **Gatilho** — a condição que fez o defeito aparecer (carga, ordem, momento, dado de borda,
  recuperação de erro).

A distribuição dos tipos mede o **produto**; a dos gatilhos mede o **processo de teste**. É o que
transforma "achei 24 problemas" em "6 vieram de alvo por número de linha, e isso é defeito da
ferramenta, não do código".

**Regra prática:** ao fechar uma auditoria, publique a tabela causa × quantidade. Se uma causa concentra
≥25%, ela é um defeito de processo — conserte a ferramenta, não os sintomas.

---

## 8. Auditoria é EXAME INDEPENDENTE (IEEE 1028)

| Processo | O que é |
|---|---|
| **Revisão de gerência** | avalia progresso, plano, adequação |
| **Revisão técnica** | avalia se o produto técnico serve ao propósito |
| **Inspeção** | exame **visual** conduzido por facilitador imparcial, para achar anomalias |
| **Walkthrough** | o autor explica; serve para colher opinião, **não** para atestar |
| **Auditoria** | exame **independente**, por terceiro, contra especificação/padrão/contrato |

Ciclo: **planejar → apresentar procedimentos → preparar → examinar e avaliar → corrigir e acompanhar.**

**A parte que dói:** *independente*. Quando o mesmo agente escreve o código, o teste, o sabotador e lê o
resultado, há um laço fechado. Compense com **artefatos que sobrevivem à própria confiança**: controles
positivos e negativos executáveis, arreio que recusa o próprio resultado quando não pode medir, e placar
publicado com o número honesto — inclusive quando ele desmente o que foi escrito antes. Quando possível,
peça a outro agente ou sessão, sem acesso à sua conclusão, que tente achar o que falta.

---

## 9. Protocolo de auditoria — a ordem que funciona

1. **Fechar o universo.** Listar todos os tipos de peça e contar cada um: é o denominador. Cobertura se
   declara em número (N de N).
2. **Medir antes de opinar.** Número medido vence impressão, sempre.
3. **Provar a chave antes de cruzar tabela.** Junção com a chave errada produz zero, e zero se parece
   com saúde.
4. **Auditar o instrumento antes do objeto.** Rode o detector contra um caso que ele *tem* de pegar.
   Se não pegar, pare.
5. **Desenhar o controle** que separa a sua hipótese da alternativa mais óbvia.
6. **Sabotar cada regra nomeada**, uma por vez, e exigir reprovação. Quando não reprovar, decidir entre
   *cicatriz fraca* (escreva o caso) e *mutação inócua* (troque a mutação e escreva por que a antiga não
   servia).
7. **Classificar** os achados por causa (§7) e olhar a concentração.
8. **Caçador independente** até duas rodadas seguidas sem achado novo.
9. **Publicar o placar honesto**, incluindo errata do que se afirmou antes. Documento confiante e errado
   é pior que ignorância: ele fecha a pergunta.

---

## 10. Sinais de que a auditoria está mentindo

- Um verificador que **nunca** acusou nada desde que foi escrito.
- Saída sem a linha de resumo, ou script que termina "em silêncio".
- Todos os itens passando na **primeira** rodada de um arreio novo.
- Resultado que **muda de lado entre duas rodadas** sem o código ter mudado.
- Consulta que devolve **zero** onde você esperava poucos — antes de comemorar, prove o rastro.
- Número redondo, uniforme ou igual ao limite de alguma consulta (teto de paginação, `LIMIT`).
- Um teste que você não consegue **fazer reprovar de propósito** em 30 segundos.
- Cobertura alta num arquivo cujo **chamador** nunca foi exercitado.
- Veredito verde **sem número**: "0 de 5 divergentes" é igual com cinco indicadores reais ou cinco
  zeros dos dois lados. Todo veredito leva o denominador e os valores.

---

## Fontes

- [Practical Mutation Testing at Scale: A view from Google](https://arxiv.org/pdf/2102.11378)
- [State of Mutation Testing at Google](https://research.google/pubs/state-of-mutation-testing-at-google/)
- [Large Language Models for Equivalent Mutant Detection](https://arxiv.org/html/2408.01760v1) — 4%–39% de mutantes equivalentes
- [An Empirical Analysis of Flaky Tests (Luo et al., FSE 2014)](https://mir.cs.illinois.edu/lamyaa/publications/fse14.pdf)
- [Test flakiness' causes, detection, impact and responses: a multivocal review](https://www.sciencedirect.com/science/article/pii/S0164121223002327)
- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [IEEE Std 1028-2008 — Software Reviews and Audits](https://standards.ieee.org/standard/1028-2008.html)
- [Orthogonal Defect Classification](https://en.wikipedia.org/wiki/Orthogonal_defect_classification)
- [Refactoring Assertion Roulette and Duplicate Assert test smells](https://arxiv.org/pdf/2207.05539)
