# Skills portáveis (formato aberto Agent Skills)

Esta pasta guarda o **método de trabalho** do dono em forma de skills: instruções empacotadas que qualquer
agente, de qualquer modelo, carrega quando a tarefa pede. Nada aqui depende de um fornecedor específico.

As regras de comportamento que valem sempre (como falar com o dono, o que nunca fazer, dinheiro, dados) estão
em [`docs/REGRAS-DO-DONO.md`](../../docs/REGRAS-DO-DONO.md). As skills são o **como fazer** de cada tipo de
trabalho.

## O formato

Cada skill é uma pasta com um arquivo `SKILL.md`:

```
.agents/skills/
└── nome-da-skill/
    └── SKILL.md
```

O `SKILL.md` começa com um cabeçalho YAML e depois traz o corpo em Markdown:

```markdown
---
name: nome-da-skill          # kebab-case, igual ao nome da pasta
description: Quando usar, em 1 a 3 frases.
---

# Título

O método, com o caso que o motivou, a regra, o roteiro e as fontes.
```

- `name` identifica a skill e tem de ser igual ao nome da pasta.
- `description` é o que o agente lê para decidir se a skill vale para a tarefa. Por isso diz **quando** usar.
- O corpo só é lido quando a skill é escolhida (carregamento progressivo): o agente não precisa ler todas
  antes de começar.

Convenções desta pasta: pt-BR, UTF-8 sem BOM, LF. Nenhum nome de pessoa, telefone, e-mail, valor em
dinheiro, domínio, IP, caminho de servidor ou nome de tabela de sistema real — este repositório é público.
As versões com os detalhes de cada projeto moram nos repositórios privados de cada um.

## Como cada ferramenta lê

- **Ferramentas que leem pasta de skills:** `.agents/skills/` é o caminho neutro do formato aberto. Várias
  ferramentas de agente (CLIs e editores) já procuram skills em pastas do projeto, conforme o suporte de
  cada uma. Se a sua ferramenta procurar em outra pasta, aponte-a para cá (configuração, link simbólico ou
  cópia gerada no CI) em vez de manter uma segunda cópia à mão — duas cópias divergem.
- **Ferramentas que não leem pasta de skills:** leem o `AGENTS.md` do repositório, que aponta para esta
  pasta e para `docs/REGRAS-DO-DONO.md`. O agente abre o `SKILL.md` indicado quando a tarefa casa com a
  `description`.
- **Modelo local ou chat sem ferramenta de arquivos:** cole o `SKILL.md` da tarefa no início da conversa.

## As skills

| skill | quando usar |
|---|---|
| [`antes-de-afirmar`](antes-de-afirmar/SKILL.md) | antes de dizer ao dono **por que** o sistema fez algo, **quem** fez, ou **se** uma mudança funcionou |
| [`antes-de-gastar-ou-delegar`](antes-de-gastar-ou-delegar/SKILL.md) | antes de afirmar algo sobre custo, abrir qualquer recurso cobrado por uso, ou entregar trabalho a outro agente |
| [`auditar-dados-de-producao`](auditar-dados-de-producao/SKILL.md) | antes de afirmar qualquer fato sobre dados de produção, inclusive "não achei nada" |
| [`auditoria-de-software`](auditoria-de-software/SKILL.md) | ao auditar código, julgar se uma suíte protege, montar mutação, caçar flake, ou dizer que algo está verificado |
| [`embasar-antes-de-mudar`](embasar-antes-de-mudar/SKILL.md) | antes de escrever ou alterar código, consertar defeito ou propor abordagem: nomear a classe e citar a prática validada |
| [`refatorar-sem-quebrar`](refatorar-sem-quebrar/SKILL.md) | antes de extrair módulo, mover SQL, unificar cópias ou renomear em massa |
| [`inventario-e-codemod`](inventario-e-codemod/SKILL.md) | ao contar chamadas, levantar o contrato de uma fachada ou aplicar a mesma mudança em muitos arquivos |
| [`migracao-de-sistema`](migracao-de-sistema/SKILL.md) | ao planejar ou executar troca de sistema: sombra, comparador, dados, virada |
| [`migrar-sistema-legado`](migrar-sistema-legado/SKILL.md) | sempre que a sessão tocar uma migração longa: estado, o que está provado, ordem, proibido |
| [`arquitetar-sistema-novo`](arquitetar-sistema-novo/SKILL.md) | em qualquer trabalho num sistema que nasce para substituir um legado |

## Como acrescentar uma skill

1. Criar `.agents/skills/<nome>/SKILL.md` com `name` igual à pasta e `description` dizendo quando usar.
2. Abrir com o caso que motivou a skill (sem nome, valor ou dado pessoal), depois a regra, o roteiro e as
   fontes.
3. Acrescentar a linha na tabela acima.
4. Rodar a varredura de segredo (`gitleaks`) antes do commit.
