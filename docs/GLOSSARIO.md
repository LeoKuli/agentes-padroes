# Glossário — agentes-padroes

| Termo | Significado | Onde aparece |
|---|---|---|
| ADR | Registro de decisão de arquitetura, formato MADR, em `docs/decisoes/NNNN-*.md` | todo repositório com o kit |
| Agent Skills | Formato aberto de skill: pasta com `SKILL.md` (frontmatter `name` e `description`) | `.agents/skills/` |
| AGENTS.md | Padrão aberto de instruções para agentes de código; aqui, a fonte única | raiz de cada repositório |
| cicatriz | Teste de regressão que executa o código real e prova um defeito que já aconteceu | regras do dono |
| comando único | `bash scripts/verificar` (ou `make verificar`): prepara, testa e valida; o mesmo no CI | AGENTS.md |
| conformidade | Workflow reutilizável que confere o kit (AGENTS.md, ESTADO.md em dia, ADR, ponteiros) | `.github/workflows/conformidade.yml` |
| controle positivo | Caso que prova que a verificação consegue reprovar | testes |
| dono | O dono dos repositórios, quem decide prioridade, gasto e arquitetura | regras do dono |
| ESTADO.md | Arquivo de retomada: onde parou, em curso, próximo passo, bloqueios, decisões, data | `docs/ESTADO.md` |
| ficha | Tarefa autocontida numa Issue, para um agente executar por PR (fluxo antigo, ver ADR 0002) | `templates/FICHA-DE-TAREFA.md` |
| kit | O conjunto de arquivos que o `adotar-padrao` monta num repositório | `scripts/adotar_padrao.py` |
| mutação | Defeito plantado de propósito; a cicatriz tem de reprovar na trava certa | regras do dono |
| NÃO MEDIDO | O que uma medição devolve quando falha; nunca zero | regras do dono |
| PREENCHER | Marca dos modelos; a conformidade reprova enquanto sobrar alguma | `templates/` |
| portão | O único caminho de pôr código no ar de cada projeto (deploy controlado) | AGENTS.md de cada projeto |
