---
status: aceito
date: 2026-11-23
decision-makers: dono
---

# Usar o AGENTS.md como fonte única de instruções, com ponteiros finos por ferramenta

## Contexto e problema

As regras e decisões dos projetos moravam na memória de um único assistente (arquivos locais do Claude Code), num
`CLAUDE.md` do monorepo e em skills locais. Outro modelo, ou o mesmo numa máquina nova, não conseguia retomar o
trabalho só com o repositório. Em 2026-11-23, 9 de 22 repositórios tinham AGENTS.md e nenhum tinha arquivo de
retomada.

## Fatores da decisão

- Qualquer modelo (Claude, GPT/Codex, Gemini, Cursor, Copilot, local) tem de conseguir colaborar, assumir ou retomar.
- Uma casa por regra: duas cópias de instrução divergem.
- O AGENTS.md é o padrão aberto da Agentic AI Foundation (Linux Foundation, dez/2025), lido por Codex, Cursor,
  Gemini CLI, Copilot, Devin, Jules e VS Code; Agent Skills e MCP foram doados à mesma fundação.

## Opções consideradas

- Um arquivo por ferramenta (CLAUDE.md, GEMINI.md, .cursorrules…) com o conteúdo inteiro.
- AGENTS.md como fonte única e arquivos de ferramenta que só apontam para ele.

## Decisão

Escolhida: AGENTS.md como fonte única. `CLAUDE.md` contém só `@AGENTS.md`; `GEMINI.md` importa `@./AGENTS.md`;
`.github/copilot-instructions.md` aponta para ele. Skills vão para `.agents/skills/` no formato Agent Skills;
regras transversais do dono, para `docs/REGRAS-DO-DONO.md` deste repositório.

### Consequências

- Bom: trocar de modelo não perde contexto; a conformidade confere os ponteiros.
- Ruim: ferramentas que não leem AGENTS.md dependem do ponteiro; o kit precisa acompanhar as ferramentas novas.

## Mais informações

`scripts/conformidade.py` (checagem dos ponteiros) e `templates/AGENTS.md`.
