---
name: migrar-sistema-legado
description: Como manter o fio de uma migração longa de um sistema legado para o sucessor, que atravessa muitas sessões e agentes — documento de estado sempre atualizado, o que já está provado, a ordem e por quê, o que é proibido, e as armadilhas que já se repetiram. Use sempre que a sessão tocar a migração; o risco número um é perder o fio e transferir para o novo uma doença do velho.
---

# Migrar um sistema legado — o fio

**A regra do dono, e ela é absoluta (setembro de 2026):**

> *"O sistema novo está sendo criado para resolver os problemas que o velho não resolve, ser mais
> performático, escalável. Não podemos transferir problemas do velho para o novo em hipótese alguma."*

E o que dói: as dívidas medidas no novo **não vieram do código velho**. Eram as mesmas doenças reproduzidas
na linguagem nova por quem escreveu o sucessor. **Transferir a doença não exige copiar código — exige apenas
não ter uma trava.**

Disciplina de arquitetura: [`arquitetar-sistema-novo`](../arquitetar-sistema-novo/SKILL.md). Método de troca:
[`migracao-de-sistema`](../migracao-de-sistema/SKILL.md). Esta skill é sobre **estado** e **ordem**.

---

## 1. O documento de estado (atualizar a cada avanço)

A migração tem **um** documento de estado no repositório do sistema novo (por exemplo
`docs/ESTADO-DA-MIGRACAO.md`), com data no topo e uma tabela curta:

| | o que registrar |
|---|---|
| **No ar?** | sim/não, desde quando, e o motivo registrado se saiu do ar |
| Código | qual ramo é a ponta, quantos commits à frente da `main`, PR aberto |
| CI | verde/vermelho, desde quando, e a causa medida |
| Suíte | número de testes, falhas, cobertura — **com a data e o lugar da medição** |
| Sombra | quais indicadores estão em paridade e quais faltam, e o que fecha cada um |
| Migração de dados | cada passo: escrito? ensaiado? reconciliado? (contagem **e** amostra) |
| Resíduos | o que ficou ligado no servidor e pede limpeza (com o OK do dono) |

**Estado antigo nunca se apaga; vira "histórico — NÃO é o estado atual"**, com a data. Uma sessão nova lê o
estado atual primeiro e o histórico só para entender o caminho.

Número de estado e número histórico confundem: onde puder confundir, **dar a data**.

## 2. A ordem, e por que é esta

0. **Zerar as cópias** da mesma regra antes de qualquer outra coisa (a lista de etapas fechadas copiada à
   mão em seis lugares é o exemplo clássico). Toda mudança de comportamento que isso causar fica escrita,
   na direção conservadora com o cliente.
1. **Catraca dos princípios** (teste de arquitetura com pisos que só encolhem). Vem primeiro porque é o
   único item que muda a **probabilidade** de o novo repetir a história do velho. Tudo depois dela nasce sob
   trava; tudo antes nasceria solto.
2. **Armar a sombra de estado** lendo os dois lados. `novo: 0` em tudo é a **linha de base correta** antes de
   migrar dado, não defeito. A sombra vira o placar da migração.
3. **Adaptar as integrações** que já são serviço (não portar).
4. **Modelar o que o velho tinha e o novo não** antes de migrar dado — por exemplo, várias pessoas numa
   mesma conversa (família). Sem o modelo, a primeira trava de duplicata que alguém escrever **cala o
   segundo**. Quem recusa duplicata é o **índice único do banco**, não um `if`; e a deduplicação **nunca** é
   por telefone.
5. **Mapeamento e migração de dados**, passo a passo, com ensaio contra cópia da produção. Reconciliação por
   contagem **e** por amostra — a contagem sozinha não vê permutação.
6. **Virada** — por configuração, medida, reversível.

## 3. O que já está PROVADO (não refazer, não duvidar sem medir de novo)

Lista curta no documento de estado, cada item com **como foi provado** e **com controle negativo**: login
ponta a ponta (senha certa entra, errada não, sem sessão redireciona); isolamento garantido pelo banco
(papel da aplicação sem bypass, conferido no catálogo); os indicadores da sombra rodando contra a produção
do velho com o **SQL gerado pelo próprio módulo**, não escrito à parte; a suíte rodando num comando só; a
ordem de boot conferida pelo log.

Quando um item provado se revela errado, ele sai da lista com a errata ao lado (ex.: um indicador lia a
tabela errada — a agenda da empresa inteira em vez dos compromissos do sistema).

## 4. Os defeitos que a SUÍTE NÃO PEGA — sempre conferir à mão

Medidos no primeiro build/deploy real, com centenas de testes verdes:

| defeito | como aparece | por que a suíte é cega |
|---|---|---|
| passo de assets antes da compilação | arquivo gerado pelo compilador não encontrado | teste não monta assets |
| script de release sem bit de execução | `permission denied` antes de qualquer log | repositório editado no Windows |
| comando de avaliação × chamada no nó vivo | o repositório de dados não sobe | processo novo ≠ nó vivo |
| ordem de boot | componente nasce antes da dependência | supervisor de teste não é o de produção |

**Regra:** depois de mexer em empacotamento, release, boot ou configuração de runtime, **suba o contêiner e
leia o log**.

## 5. Armadilhas que se repetiram mesmo catalogadas

- **Violação de índice único dentro de transação aborta a transação inteira** se a inserção não usar
  savepoint. A recusa deixa de ser **informação** ("esta pessoa já está cadastrada") e vira **erro de
  infraestrutura** — uma família legítima parece defeito do sistema.
- **Restrição de índice composto pendura o erro no PRIMEIRO campo**, não no que carrega o sentido. Nomear o
  campo explicitamente.
- **Antes de assumir a forma do retorno, leia a função.** Lista ≠ tupla; três cicatrizes reprovaram por
  isso com a produção certa o tempo todo.
- **A chave de cada tabela é medida, não deduzida.** Uma junção pela chave errada não dá erro — junta
  pessoas com a conversa de outro cliente. Guardar a chave de origem numa coluna própria torna a junção
  **verificável**.
- **Nome de coluna é palpite até perguntar ao banco.** Rodar o SQL real com `LIMIT 0`: o banco resolve os
  nomes no planejamento e reprova antes de ler linha, sem trazer dado pessoal.
- **Funções de "mesclar" listas podem não preservar posição.** Num arreio posicional isso entrega cada valor
  na coluna errada — e a asserção "tem tantas colunas quanto o esperado" passa: contagem não vê permutação.
- **Inserção em lote pode não gerar a chave primária** nem converter tipos como a inserção unitária faz.
- **Escape em heredoc morde:** contrabarra dupla colapsa, e `\b` vira **byte de backspace literal** dentro
  do regex — a guarda fica verde por não procurar nada. Quem acha é o controle positivo. Preferir `[.]` a
  contrabarra-ponto; varrer por `0x08` depois de escrever regex por heredoc.
- **Booleano impresso pelo cliente do banco** muda conforme o cast. Mensagem de erro mostra o valor **real**,
  não só o esperado.
- **Prontidão se mede pelo EFEITO.** Durante a inicialização, o banco pode subir um servidor temporário só no
  socket local: a checagem de prontidão responde "pronto" e o servidor some. Pergunte **por TCP, de fora**.
- **Predicado de busca importa:** "começa com" não casa uma chamada qualificada; "contém" casa.
- **Escreveu o literal no comentário? A varredura conta.**
- **Em template, `@nome` pode ser variável do template, não constante do módulo.** Lista vira **função**
  antes de encostar no template.
- **Dois critérios que somam mais que o total estão se sobrepondo.** Faça a matriz 2×2 — não escolha um.
- **Duas tabelas com nome parecido são duas POPULAÇÕES.** Antes de mapear uma tabela, **pergunte de quem ela
  é** e quantas linhas ela tem.
- **`grep -c <palavra>` não conta construções.** Contar ocorrência de string infla e desinforma; contar por
  AST (ver [`inventario-e-codemod`](../inventario-e-codemod/SKILL.md)).
- **Decisão que mora em arquivo de configuração não atravessa a migração** de tabelas e não dá erro. Listar
  as decisões junto com os dados.

## 6. Antes de dizer que algo está pronto

1. **Rodou a suíte?** (o comando único)
2. **Subiu e leu o log do contêiner?** (os defeitos da seção 4)
3. **A catraca aceitou?** Piso que subiu = dívida que cresceu = "transferir problema do velho".
4. **Tem controle negativo?**
5. **O número que vou dizer foi MEDIDO ou lembrado?** Se lembrado, meça.

## 7. Proibido

- Compilar no servidor que atende ao vivo, em horário de uso, sem teto de CPU.
- Rodar a suíte contra o banco de produção — ela cria e derruba banco.
- Mexer no compose de produção do velho para subir o novo. Compose separado, sempre.
- Copiar arquivo para dentro de contêiner de produção.
- Mensagem de teste a cliente. Segredo em argv, em log ou no chat.
- **Baixar um piso da catraca sem ter consertado a dívida.**

## Limite honesto

Nenhuma trava torna o sistema livre de erro, e prometer isso já custou caro. O que elas fazem é a coisa
certa: **cada classe de defeito que aparece uma vez fica impossível de repetir em silêncio.** O erro que
ainda vai acontecer aparece na bancada ou no portão — não no cliente.
