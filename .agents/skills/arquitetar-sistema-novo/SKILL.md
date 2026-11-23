---
name: arquitetar-sistema-novo
description: Disciplina de arquitetura para qualquer trabalho num sistema que nasce para substituir um legado — escrever ou alterar código, desenhar uma feature, portar algo do velho, decidir uma abordagem. Cada família de defeito do velho tem de ficar impossível por construção, não vigiada por asserção; princípio sem trava automática é só intenção.
---

# Arquitetar um sistema novo

Em setembro de 2026 o dono desistiu de um sistema legado: *"todo dia tapando buraco, nunca acaba. A
refatoração não adiantou de absolutamente nada."* Ele estava certo no diagnóstico: refatorar mata **uma
família** de defeito (a mesma regra em duas casas), não o defeito.

O sucessor só vale a pena se **cada família de defeito ficar impossível por construção**, e não vigiada por
asserção. É isso que esta skill protege.

## A lei já existe — leia antes de decidir

O sistema novo tem uma **constituição** (`.specify/memory/constitution.md` ou equivalente) com princípios
inegociáveis. Esta skill não os repete; diz como aplicá-los. Princípios que costumam decidir o desenho:

1. **O compilador e o verificador de tipos são o primeiro auditor** — erro que o tipo pega não precisa de
   teste.
2. **Engolir erro é decisão escrita, nunca o padrão.**
3. **Trabalho com prazo é job persistente, jamais timer em memória.**
4. **Uma regra, uma casa.**
5. **Estado que importa mora no banco.**

E a doutrina que evita reimportar o passado: **"melhor, não igual"**.

## Antes de portar qualquer coisa do velho: triar

O velho tem centenas de cicatrizes. Cada uma responde a uma pergunta antes de atravessar:

- **É regra?** O comportamento certo, que qualquer versão do sistema deveria ter — *"envio por modelo é
  nota privada"*, *"família dividindo um telefone não é duplicata"*, *"áudio chega com texto vazio e quem
  julga por texto libera"*. → **porta**, e vira teste.
- **É remendo?** Existe só porque a arquitetura de lá obrigava — *"o guarda conta balões porque o webhook
  dispara em rajada"*, *"o teto de paginação existe porque a fonte é uma API de terceiro"*. → **não porta.**
  Portá-lo importa a doença junto com a cura.

Regra prática: se a cicatriz cita um **arquivo** do velho, é remendo. Se cita uma **pessoa atendida**, é
regra.

## Ao portar uma MEDIÇÃO: prove que os dois lados contam a mesma gente

Quando o que atravessa é um número, existe uma terceira categoria de erro: **a definição plausível que conta
outra população**.

Medido montando uma sombra de estado: três perguntas, três SQL que qualquer um escreveria, três populações
erradas. **Nenhuma dá erro.**

| pergunta | o SQL plausível | o certo | por quê |
|---|---:|---:|---|
| a empresa falou com o cliente (24 h) | 187 ou 127 | **143** | "saída" infla 32% com anotação interna; "só públicas" perde quase todos os envios por modelo |
| conversas "esperando" | 816 | **21** | 795 já tinham sido respondidas depois daquela fala |
| conversas abertas | 1125 | **891** | coluna de status e etapa discordam em 234 — e o novo **não tem** coluna de status |

**A regra: prove pela partição que fecha.** Não "o número parece razoável", e sim `universo = a + b + c`
batendo exato, com os lados não-vazios. É essa igualdade que prova que o instrumento enxerga os dois lados.

**Corolários típicos de schema herdado:**

- Uma flag de "privado" raramente separa "falamos com o cliente" de "o sistema anotou algo".
- O que prova que uma mensagem saiu é o **identificador devolvido pelo provedor** — mais o log de envios
  para os que não gravam esse identificador.
- Cancelamento pode ser **a linha sumir**, sem status próprio. Quem espelha precisa escrever isso, senão
  parece esquecimento.
- Filtro de tipo é **denylist, nunca whitelist**: whitelist esconde o tipo novo em silêncio.

## Corrigir ao encostar

Uma auditoria inicial do repositório (medida, não suposta) gera uma lista de dívida: funções públicas sem
contrato de tipo, tarefas assíncronas sem supervisor, chamadas HTTP fora da porta única, tratamentos de
exceção sem motivo escrito, avisos de segurança em dependências, a mesma lista copiada em várias casas.

**Regra:** ao tocar um arquivo da lista, conserte o item dele. Não abra frente própria para isso.

E o que **confere** não se mexe sem motivo forte: porta única de HTTP com disjuntor e classificação de
falha; fila persistente de jobs; isolamento garantido pelo **banco** (papéis e RLS), não pelo código.

## A catraca — por que os princípios não eram seguidos, e o que mudou

Em setembro de 2026 o dono perguntou por que o sistema novo não seguia todos os princípios que a própria
constituição declarava. A resposta foi **mecânica**:

> O CI cobrava tudo que a linguagem dá de graça (formato, avisos como erro, lint estrito, testes, tipos,
> dependências não usadas) e **nada** específico do projeto. Escrever contrato de tipo era opcional.
> Escrever o motivo de um tratamento de exceção era opcional. Não copiar uma lista era opcional.

**Regra que ninguém automatiza degrada em silêncio.** A única regra que virou check reprovou o próprio
autor **duas horas** depois de ser escrita. As que não viraram continuaram sendo violadas.

Um teste de arquitetura é a casa dessas travas. Cada uma tem:

1. **Piso congelado que SÓ ENCOLHE.** Passar do piso reprova.
2. **Reprovação nos dois sentidos.** Ficar muito abaixo do piso também reprova — piso que não acompanha a
   melhora vira enfeite. Ao consertar, **abaixe o piso junto**.
3. **Controle positivo.** Varredura que não enxerga o que vigia reprova, e a mensagem diz que o suspeito é a
   varredura. Glob quebrado devolve lista vazia, e lista vazia se parece com saúde.

**Ao acrescentar um princípio à constituição, acrescente a trava no mesmo commit.**

## Técnicas que a plataforma nova permite e a velha não permitia

Não reimplemente no novo o que o velho obrigava:

- **Deixe quebrar, supervisione** (quando a plataforma tem supervisão). Processo que falha e reinicia limpo
  é mais seguro que tratamento que continua com estado meio-escrito.
- **Durabilidade é do banco, não da memória.** Trabalho com prazo → fila persistente. Marca de "já fiz" →
  linha com índice único, não flag em memória.
- **O tipo é a primeira asserção.** Tipo distinto para id de tenant impede a chave errada de compilar.
- **A fronteira valida.** Dado externo entra por validação declarada, não por leitura de campo espalhada.
- **Isolamento é garantia do banco, não promessa do código.**
- **Telemetria antes de otimizar.**

## Padrões em vigor

- **Ports & adapters.** Toda saída ao mundo passa por uma porta. Integração existente que já é serviço HTTP
  **não se porta; se adapta** — passando pela porta, herda disjuntor de graça.
- **Fitness function.** Regra de arquitetura nova → teste que reprova, no CI, com piso e exceção
  **nomeada**.
- **Strangler Fig + Parallel Run** para a migração — ver [`migracao-de-sistema`](../migracao-de-sistema/SKILL.md).
- **Uma casa por regra.** Antes de escrever uma função, procure a pergunta que ela responde. Duas cópias
  divergem — causa-raiz nº 1 do velho.

## Rotina antes de escrever código

1. **Isto tem nome?** Ver [`embasar-antes-de-mudar`](../embasar-antes-de-mudar/SKILL.md).
2. **A constituição já decide isso?** Se sim, siga; se o código não segue, o achado é esse.
3. **É regra ou remendo?** Só regra atravessa.
4. **Qual casa?** Se a resposta é "uma nova", prove que nenhuma existente responde à mesma pergunta.
5. **Como isso falha?** Escreva o teste da falha antes do caminho feliz. Teste de propriedade quando o espaço
   de entrada é maior que a imaginação.
6. **O que prova que ficou?** Teste que **reprova** sem o conserto.
7. **CI verde é o piso.**

## O que NÃO fazer

- Não portar remendo.
- Não criar a segunda casa de uma regra que já existe.
- Não usar timer para trabalho com prazo.
- Não engolir erro sem o motivo escrito na linha de cima.
- Não compilar no servidor que atende ao vivo em horário de uso; build tem janela e teto de CPU.
- Não rodar teste contra o banco de produção. Contêiner descartável, com os mesmos papéis de banco da
  produção — e quem **cria** o banco de teste é o papel da aplicação (dono errado quebra o RLS forçado).
- Não anunciar paridade sem inventário item a item contra as funções e rotas do velho.

## O que a suíte NÃO pega — confira à mão depois de tocar empacotamento

Medido no primeiro build e deploy reais: **centenas de testes passavam com quatro defeitos vivos.** Depois de
mexer em `Dockerfile`, scripts de release, ordem de boot ou configuração de runtime, **suba o contêiner e
leia o log**:

| defeito | sintoma |
|---|---|
| passo de assets antes da compilação | arquivo gerado pelo compilador não encontrado |
| script de release sem bit de execução | `permission denied` antes de qualquer log (repositório editado no Windows) |
| comando de avaliação não sobe o repositório de dados | "could not lookup repo" — usar a chamada no nó vivo |
| ordem de boot errada | disjuntor sobe antes do banco e nasce sem o estado persistido |

## Verificação barata enquanto a janela de build não abre

- **Parse** de cada arquivo mudado — com controle negativo (mande código torto e confira que reprova).
- **Formato** comparado com o formatador — atenção a falso positivo de configuração; confira numa linha
  pré-existente com a mesma forma antes de "consertar" a sua.
- **Módulo isolado** sem dependência externa, compilado num contêiner: dá para executar o módulo real e
  matar mutações sem subir o projeto.

## Limite honesto

Esta skill não substitui medir. A constituição diz o que deve ser verdade; só o teste e o registro dizem o
que **é**. Quando discordarem, o registro ganha e a discordância vira o achado.

Relacionadas: [`migrar-sistema-legado`](../migrar-sistema-legado/SKILL.md) · [`embasar-antes-de-mudar`](../embasar-antes-de-mudar/SKILL.md) ·
[`auditoria-de-software`](../auditoria-de-software/SKILL.md) · [`migracao-de-sistema`](../migracao-de-sistema/SKILL.md) ·
[`refatorar-sem-quebrar`](../refatorar-sem-quebrar/SKILL.md) · [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md)
