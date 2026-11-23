# Estado do projeto — agentes-padroes

Atualizado em: 2026-11-23
Por: Claude Opus 5.5 no Claude Code (app desktop)
Situação: ativo

## Onde parou

Kit v2 (agnóstico a modelo e a ferramenta): modelos de `docs/ESTADO.md`, ADR (MADR), glossário, ponteiros
`CLAUDE.md`/`GEMINI.md`/`copilot-instructions.md`, `.agents/skills/`, `.mcp.json`, `.env.example`,
`scripts/verificar` e `.devcontainer`; `scripts/adotar_padrao.py`, `scripts/conformidade.py`,
`scripts/iniciar_projeto.py` e o workflow reutilizável `conformidade.yml`. O próprio repositório adota o kit.

## Em curso

- Regras do dono (`docs/REGRAS-DO-DONO.md`, 44 regras) e 10 skills de método em `.agents/skills/` (7 de método puro e 3 genéricas tiradas das skills do CRM; as versões com detalhe de projeto vão para os repositórios privados crm-oralunic e crm-clinica).
- Adoção do kit nos 22 repositórios ativos, um PR por repositório, com conteúdo real de cada projeto.

## Próximo passo

Depois de mesclar a v2: marcar o repositório como template (`gh repo edit LeoKuli/agentes-padroes --template`) e
seguir a adoção nos repositórios.

## Bloqueios

Nenhum.

## Últimas decisões

- [ADR 0001](decisoes/0001-agents-md-fonte-unica.md): AGENTS.md como fonte única; os outros arquivos só apontam.
- [ADR 0002](decisoes/0002-fluxo-openrouter-encerrado.md): fichas executadas pelo OpenRouter, encerrado em 2026-11-03.
- [ADR 0003](decisoes/0003-estado-md-e-conformidade.md): ESTADO.md com data e conformidade que reprova acima de 30 dias.

## Como retomar em 5 minutos

1. `bash scripts/verificar`
2. Ler `scripts/adotar_padrao.py` (o manifesto `KIT`) e `scripts/conformidade.py`.
