# Estado do projeto — agentes-padroes

Atualizado em: 2026-11-23
Por: Claude Opus 5.5 no Claude Code (app desktop)
Situação: ativo

## Onde parou

- Kit v2 no ar (#14) e marcado como **template repository**; regras do dono (44) e 10 skills de método (#15); as
  lições da retomada sem contexto aplicadas aos modelos (o PR que traz esta atualização).
- Adoção feita em 21 dos 22 repositórios ativos, um PR por repositório, todos mesclados com a conformidade verde. O
  `setfisio-conteudo` ficou de fora de propósito: o importador do site recusa qualquer caminho fora de `src/`.
- Teste sem contexto: Sonnet retomou o `rastro-estudo-pwa` e Haiku o `notas-imoveis` só com o repositório, os dois
  com o comando único verde. As lacunas que acharam foram corrigidas nos repositórios e, as que eram do kit, nos
  modelos.

## Em curso

Nada aberto neste repositório.

## Próximo passo

- Acompanhar a primeira semana: repositório que reprovar na conformidade por ESTADO.md vencido é sinal de sessão
  que não atualizou o estado. Ajustar `dias-maximos` só por ADR.
- Avaliar se o `scripts/verificar` modelo deve ganhar uma varredura completa do histórico (`gitleaks git .`), hoje só
  feita no CI.

## Bloqueios

Nenhum.

## Últimas decisões

- [ADR 0001](decisoes/0001-agents-md-fonte-unica.md): AGENTS.md como fonte única; os outros arquivos só apontam.
- [ADR 0002](decisoes/0002-fluxo-openrouter-encerrado.md): fichas executadas pelo OpenRouter, encerrado em 2026-11-03.
- [ADR 0003](decisoes/0003-estado-md-e-conformidade.md): ESTADO.md com data e conformidade que reprova acima de 30 dias.

## Como retomar em 5 minutos

1. `bash scripts/verificar`
2. Ler `scripts/adotar_padrao.py` (o manifesto `KIT`) e `scripts/conformidade.py`.
