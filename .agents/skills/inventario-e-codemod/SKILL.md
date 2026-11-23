---
name: inventario-e-codemod
description: Como levantar com precisão quem chama o quê num código grande (por AST, nunca por regex) e como mudar dezenas ou centenas de call sites de uma vez sem quebrar. Use ao contar chamadas, classificar call sites, levantar o contrato de uma fachada nova ou aplicar a mesma mudança mecânica em muitos arquivos.
---

# Inventário e codemod — parar de contar código com regex

Em agosto de 2026 foi preciso saber quantas chamadas a um serviço externo existiam num sistema e o que
cada uma fazia. Usou-se `grep` com uma janela de texto em volta. Resultado: **uma LEITURA foi classificada
como ENVIO porque a palavra `POST` aparecia por perto**. Dos 4 casos-limite conferidos à mão, 1 estava
errado. **25% de erro na amostra — e a migração inteira ia ser planejada em cima daquilo.**

Refeito por AST, os números mudaram: 111 → **107 chamadas**, e apareceu uma categoria inteira que o regex
não tinha contado (24 escritas que não eram envio de mensagem).

É a mesma família de uma cicatriz antiga: **âncora estrutural, nunca vizinhança de texto**.

---

## 1. A pergunta certa é estrutural, não textual

| pergunta textual (erra) | pergunta estrutural (não erra) |
|---|---|
| "aparece `POST` perto de `/messages`?" | "este nó é `CallExpression` com callee `cliente` e o 2º argumento tem `method: 'POST'`?" |
| "tem `private: true` nesta janela de 500 chars?" | "o objeto do corpo tem a propriedade `private`, e qual é o valor dela?" |
| "quantas vezes o nome X aparece?" | "quantas dessas ocorrências são chamada, e quantas são comentário, string ou nome parecido?" |

O parser da linguagem já sabe responder isso. Escrever regex para adivinhar é reimplementar o parser mal.

**Sintoma de ferramenta errada:** precisar de uma janela de N caracteres, precisar excluir comentários à
mão, ou precisar de uma lista de exceções que só cresce.

## 2. Ferramenta mínima, sem instalar nada em produção

Para JavaScript: `acorn` + `acorn-walk` num contêiner efêmero, com o código montado só para leitura. Não
toca o servidor, não entra no `package.json` do projeto, não exige TypeScript.

```bash
docker run --rm -v "$PWD":/w:ro -v "$PWD/_ast":/ast -w /ast node:20-alpine node /ast/inventario.js
```

Dois scripts úteis em qualquer projeto:

- **inventário** — classifica todas as chamadas a um cliente: leitura, envio, outras escritas; e para os
  envios diz se é nota interna ou se fala com uma pessoa.
- **contrato** — levanta as **formas de corpo** que os chamadores usam. É o contrato que uma fachada nova
  precisa aceitar.

Para transformar (não só ler): **jscodeshift** (usa `recast`, preserva a formatação) ou **ts-morph**
quando há tipos para consultar. Em outras linguagens, a ferramenta de AST da própria linguagem.

## 3. O inventário tem de declarar o que NÃO cobriu

O primeiro inventário engoliu 28 arquivos em silêncio: arquivos ESM (`import`/`export`) e scripts que
começam com shebang — o parser recusou os dois e quase ninguém viu, porque o resultado saía bonito no fim.

**Regra:** todo inventário imprime a lista de arquivos que não parsearam. Arquivo não lido é **NÃO
MEDIDO**, nunca "não tem nada lá".

E o inverso: quando o AST não resolve (corpo montado numa variável, argumento vindo de outro módulo), ele
**diz** que não resolveu e a pessoa lê à mão. Está certo em não fingir que seguiu.

## 4. Duas medidas independentes, e o que fazer quando discordam

Depois do AST, conferir à mão os casos marcados como duvidosos. **As duas medidas bateram** nos 11 call
sites críticos — é isso que autoriza a confiar no número.

Quando discordam, uma está errada — e a resposta nunca é a média. Foi assim que o falso positivo do regex
apareceu.

## 5. Codemod: quando vale e quando não

Vale quando a transformação é **mecânica, repetitiva e testável** — o padrão velho mapeia direto no novo,
sem julgamento de regra de negócio, e são dezenas a centenas de call sites.

**Não vale** quando cada call site precisa de decisão. Aí é um por vez, com prova.

> Caso concreto: dos 38 envios, **27 eram nota interna com a mesma forma exata**. Isso é um codemod e
> **um** portão. Os outros **11 falavam com o cliente** — esses vão um por vez, porque errar ali manda
> (ou deixa de mandar) mensagem para uma pessoa real.

**A separação que decide isso não é técnica, é de quem sofre o efeito.** Antes de agrupar call sites,
classifique por consequência do erro, não por semelhança do código.

## 6. O contrato sai dos consumidores, antes da fachada nascer

Antes de escrever a porta única, levante por AST **todas as formas de payload que os chamadores usam
hoje**. Fachada que aceita menos do que os chamadores mandam **silencia campo** — e campo silenciado não
dá erro, dá comportamento errado.

> Medido: 38 emissores usavam só **3 formas de corpo**, e um campo de atributos tinha só 2 chaves em uso.
> O contrato cabia numa linha. A estimativa era de semanas — **medir encolheu o problema**.

## 7. Default herdado do sistema que está saindo é armadilha

Duas das 38 chamadas **omitiam** o campo de visibilidade. No sistema antigo, ausente significava "público",
ou seja **mensagem ao cliente por default do sistema**.

Se a porta nova nascer com outro default, o erro é silencioso **nos dois sentidos**: nota interna virando
mensagem ao cliente, ou mensagem ao cliente virando nota que ninguém recebe.

**Regra:** a fachada nova **exige explícito** o que o sistema velho deixava implícito, e **falha
ruidosamente** se faltar. Nunca reproduza o default de um sistema que você está removendo.

## 8. Roteiro

1. **Inventariar por AST**, nunca por regex. Imprimir o que não parseou.
2. **Classificar por consequência do erro**, não por forma do código.
3. **Conferir à mão** os casos duvidosos — e exigir que as duas medidas batam.
4. **Levantar o contrato** dos consumidores antes de escrever a fachada.
5. **Tornar explícito** todo default que vinha do sistema velho.
6. **Codemod** para o grupo mecânico (um portão), **um por vez** para o grupo que tem consequência.
7. Prototipar o transform no [AST Explorer](https://astexplorer.net/) antes de rodar no repositório.

## Fontes

- [Why Codemods Beat Search and Replace Every Time](https://typescript.tv/best-practices/why-codemods-beat-search-and-replace-every-time/)
- [Codemods at Scale — Steve Kinney](https://stevekinney.com/courses/enterprise-ui/codemods-at-scale)
- [Large-scale code changes using ASTs and jscodeshift](https://patricktree.me/blog/large-scale-code-changes-using-asts-and-jscodeshift)
- [ts-migrate: migrating to TypeScript at scale — Airbnb](https://medium.com/airbnb-engineering/ts-migrate-a-tool-for-migrating-to-typescript-at-scale-cd23bfeb5cc)
- [jscodeshift](https://github.com/facebook/jscodeshift) · [ts-morph](https://ts-morph.com/) · [acorn](https://github.com/acornjs/acorn) · [AST Explorer](https://astexplorer.net/)

Relacionadas: [`migracao-de-sistema`](../migracao-de-sistema/SKILL.md) ·
[`refatorar-sem-quebrar`](../refatorar-sem-quebrar/SKILL.md) ·
[`auditoria-de-software`](../auditoria-de-software/SKILL.md) · [`antes-de-afirmar`](../antes-de-afirmar/SKILL.md)
