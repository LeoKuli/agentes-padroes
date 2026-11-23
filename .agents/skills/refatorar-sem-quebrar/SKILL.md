---
name: refatorar-sem-quebrar
description: Como mover código de casa (extrair para módulos, tirar SQL de dentro de regra, unificar cópias, renomear em massa) sem cegar a bancada de testes nem derrubar quem está usando o sistema. Use ANTES de qualquer extração, migração de SQL, unificação de cópias ou renomeação em massa; o método é Parallel Change, um chamador por vez, com caracterização antes.
---

# Refatorar sem quebrar

Em agosto de 2026 o dono perguntou: *"eu juro que não entendo o porquê de você estar tendo tanta
dificuldade de refatorar"*. Ele estava certo. Em dois dias foram 24 deploys, 4 defeitos reais consertados,
e **8% do SQL movido — que precisou ser revertido**, porque a extração cegou 8 cicatrizes de uma vez.

A dificuldade não era o código. Eram três erros de método, e os três têm nome na literatura.

## 1. Teste que lê o fonte é teste de ARQUITETURA, não de comportamento

Num dos projetos, 253 de 412 cicatrizes perguntavam *"a função X contém o texto Y?"*. Isso não é teste de
comportamento — é uma regra de arquitetura, no mesmo espírito do [ArchUnit](https://www.archunit.org/). E
a prática estabelecida ali é explícita: quando uma regra de arquitetura falha, ela **força uma decisão
consciente — ou você corrige a violação, ou atualiza a regra**, e os dois desfechos são legítimos.

"8 cicatrizes reprovaram" foi tratado como "8 proteções cegas" e tudo foi revertido. Metade delas só
pedia que se declarasse que a mudança era intencional.

**O que fazer:** quando mover código e uma cicatriz de texto reprovar, decidir entre:

- **a regra continua valendo** → o movimento está errado, desfaça;
- **a regra mudou de propósito** → atualize-a **com o motivo escrito junto**. Atualizar calado vira
  carimbo, pior que degrau nenhum.

Exemplo: a regra "todo módulo é desestruturado pelo arquivo principal" nasceu quando módulo exportava
funções soltas. Um **repositório de consultas** exporta dezenas de funções e é usado como namespace.
Desestruturar 57 nomes seria pior que o problema — então a pasta de repositórios virou exceção **declarada
dentro da própria cicatriz**, com o porquê.

## 2. Movimento seco quebra tudo junto — use Parallel Change

Criar o repositório e trocar **23 arquivos de uma vez** cegou oito cicatrizes no mesmo instante, e não
dava para saber quais eram dano e quais eram regra desatualizada.

O padrão certo é [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html) (expand → migrate →
contract), primo do
[Branch by Abstraction](https://continuousdelivery.com/2011/05/make-large-scale-changes-incrementally-with-branch-by-abstraction/):

| fase | o que faz | o que não pode quebrar |
|---|---|---|
| **expand** | o novo nasce ao lado do velho | nada — ninguém usa ainda |
| **migrate** | **um chamador por vez**, com a cicatriz dele atualizada no mesmo passo | bancada verde a cada passo |
| **contract** | o velho sai quando o último chamador migrou | nada |

**Regra prática:** se o passo pode quebrar mais de uma cicatriz, ele é grande demais. Divida. Vale dar ao
extrator modos `--expand` / `--migrate=<arquivo>`, para tornar impossível repetir o movimento seco.

## 3. Caracterização vem ANTES de mexer

Michael Feathers (*Working Effectively with Legacy Code*) descreve a ordem: achar o ponto de mudança,
achar o ponto de teste, quebrar dependências, **escrever os testes de caracterização** e só então
refatorar. Escrever a caracterização depois de mover é escrever o alarme depois do incêndio.

## O arreio: sem controle positivo, o teste não vale nada

Isto pegou **quatro vezes em um dia**, e uma delas quase virou um defeito reportado que não existia:

- um arreio concluiu *"manda mesmo desligada"* — mas tinha stubado justamente a função que consome a
  chave, anulando o guarda que dizia testar;
- um arreio de job em que **nenhum** dos dois lados disparou — dois zeros iguais não provam nada.

**Regras:**

1. **Todo arreio tem controle positivo.** Se o caso legítimo não age, a asserção acusa *o arreio*, não o
   produto: `ARREIO FURADO: ... — a asserção não mede o que diz medir`.
2. **Nunca stubar a função que consome a regra sob teste.** Ela tem de ser a real.
3. **Prove o dente por sabotagem**, numa cópia: desligue a regra e confirme que a cicatriz reprova. Monte
   a cópia **no mesmo caminho absoluto** que a bancada usa — senão você testa a produção achando que testa
   a cópia.
4. **Cópia de sabotagem sem sabotagem tem de PASSAR.** Se já falha, o arreio está sujo.

## O extrator: recusar é melhor que adivinhar

O que funcionou (141 rotas e 57 consultas extraídas sem defeito):

- **Prova por reversão byte a byte**: desfazer a troca tem de devolver o arquivo original. Se não devolver,
  o extrator não entendeu o arquivo — e não toca nele.
- **Recusas explícitas**: SQL concatenado com variável do call site, parâmetro que não é expressão simples,
  âncora não-única. Recusar 6 de 63 é melhor que estragar 1.
- **Preserve a forma**: não reordene nem reescreva listas. Insira antes do `]`, não reescreva a lista — o
  degrau que conta cópias por linha acusa deriva que não existe.

## Nome dentro de string engana todo scanner

`'/app/data/x.log'` fez `app` contar como identificador usado. Um caminho sumiu quando strings foram
apagadas, e a varredura achou 0 `require`.

**Use o texto certo para cada pergunta:**

| pergunta | texto |
|---|---|
| esse NOME é usado como código? | sem string **e** sem comentário |
| esse SQL/caminho existe? | sem comentário, **com** string |
| onde a rota está declarada? | cru (o caminho é string) |

O limpador de código tem de entender comentário, string, template com `${...}` **e regex literal** — o `'`
dentro de `/[\s'"]/` já desalinhou um arquivo inteiro e acusou uma linha correta.

## Instrumento de medição precisa de autoteste

Um medidor de progresso errou **quatro vezes, sempre para menos**, e números errados foram reportados ao
dono três vezes.

**Regra:** todo medidor tem modo `--controle` com casos de resposta conhecida **dos dois lados**. Se o
controle falha, o número não vale e o medidor diz isso. **Duas medidas discordantes já provam que uma está
errada.**

## Não reverta pelo `git checkout` um arquivo que a cadeia inteira compartilha

Uma única consulta foi revertida com `git checkout -- <arquivo principal>`. O arquivo era compartilhado
por todos os passos da migração — o checkout apagou junto as injeções de dependência de **14 módulos já
migrados**. A checagem de sintaxe passou. A bancada passou. Só o **boot** morreu, e o site ficou fora por
7 minutos.

**Regra:** desfaça cirurgicamente (a substituição específica) ou pelo backup do próprio passo. Nunca por
checkout do arquivo compartilhado.

## Portão que procura erro conhecido dá verde para o erro novo

Um degrau de boot procurava uma **lista** (`ReferenceError|SyntaxError|Cannot find module|...`). A morte
foi um `throw` do próprio módulo, fora da lista. Degrau **verde**, deploy seguiu, produção caiu.

**Regra:** degrau de vida prova o **sucesso**, não a ausência de fracassos conhecidos. Exija a linha que só
existe quando deu certo (`servidor ouvindo na porta N`). E ele também precisa de controle dos dois lados.

## Refatoração que atrapalha quem atende perdeu o propósito

Foram **30 deploys num dia**, com meta de **menos de 3**. Um atendente tentou mandar mensagem **14 vezes** e
levou 500 em todas — caiu na janela de reinício de um deploy.

- deploy em lote, em janela combinada — não a cada conserto;
- depois de todo deploy, ler a **classe** de erro do log e as falhas HTTP das últimas 24h;
- `catch` que devolve 500 **sem logar** faz a falha ser invisível.

## Roteiro (antes de mover qualquer código)

1. As cicatrizes que vigiam esta área **executam** ou leem texto? As de texto vão reprovar — decida antes
   se cada uma é regra viva ou desatualizada.
2. O passo cabe em **um chamador**? Se não, divida (expand → migrate → contract).
3. Existe **caracterização** do comportamento atual, com controle positivo? Se não, escreva primeiro.
4. O extrator **recusa** o que não entende e prova por **reversão byte a byte**?
5. Depois: bancada verde, portão, log varrido, e o motivo de cada regra atualizada **escrito junto**.

Relacionadas: [`antes-de-afirmar`](../antes-de-afirmar/SKILL.md) ·
[`auditar-dados-de-producao`](../auditar-dados-de-producao/SKILL.md) · [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md)

Fontes: [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html) ·
[Branch by Abstraction](https://continuousdelivery.com/2011/05/make-large-scale-changes-incrementally-with-branch-by-abstraction/) ·
[ArchUnit](https://www.archunit.org/) ·
[Characterization test](https://en.wikipedia.org/wiki/Characterization_test) ·
[Working Effectively with Legacy Code — workflow](https://github.com/testdouble/contributing-tests/wiki/Refactoring-Legacy-code-with-tests)
