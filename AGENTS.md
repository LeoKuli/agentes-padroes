# AGENTS.md — agentes-padroes

> Fonte única de instruções para qualquer agente, de qualquer modelo (Claude, GPT/Codex, Gemini, Cursor, Copilot,
> modelo local). `CLAUDE.md`, `GEMINI.md` e `.github/copilot-instructions.md` só apontam para cá.

## Antes de tudo: retomar o trabalho

1. Leia este arquivo, depois [`docs/ESTADO.md`](docs/ESTADO.md).
2. Leia os ADRs aceitos em [`docs/decisoes/`](docs/decisoes/) e o [`docs/GLOSSARIO.md`](docs/GLOSSARIO.md).
3. `git log --oneline -20`, PRs e Issues abertos.
4. `bash scripts/verificar` antes de mudar qualquer coisa.

**Conflito com ADR aceito: pare e pergunte ao dono.** Não escolha sozinho e não "obedeça o mais recente".
**No fim de toda sessão, atualize `docs/ESTADO.md`.**

## Objetivo do projeto

O contrato compartilhado que deixa os repositórios do dono (conta GitHub `LeoKuli`) agnósticos a modelo e a
ferramenta: o kit de agentes (AGENTS.md, ESTADO.md, ADR, glossário, ponteiros, skills, comando único), o
`adotar-padrao` que o monta sem sobrescrever, o workflow reutilizável de conformidade, o gitleaks reutilizável, as
regras transversais do dono e as skills de método no formato aberto Agent Skills. Também é template repository para
projetos novos. NÃO é lugar de código de produto, nem de dado de projeto: o repositório é **público**.

## Como rodar e o comando único de "pronto"

```bash
bash scripts/verificar        # pip install pytest pyyaml, pytest, bash -n, conformidade, gitleaks (se houver)
```

Pré-requisitos: Python 3.12+ e bash (no Windows, o Git Bash). Tempo: menos de 1 minuto.

## Mapa de pastas

- `templates/` — os modelos do kit, copiados pelo `adotar-padrao` (manifesto em `scripts/adotar_padrao.py`, `KIT`).
  Os modelos trazem a marca de preenchimento de propósito: o repositório que adota troca por conteúdo real.
- `scripts/` — `adotar_padrao.py`, `conformidade.py`, `iniciar_projeto.py` e os scripts do fluxo antigo de fichas.
- `.github/workflows/` — workflows reutilizáveis (`conformidade`, `segredos`, `ficha`, `escopo`, `mutacao-ficha`,
  `juntar-so-teste`, `agente-openhands`) e o CI deste repositório (`teste-padroes`, `conformidade-propria`).
- `.agents/skills/` — skills de método compartilhadas, no formato Agent Skills (genéricas; repositório público).
- `docs/REGRAS-DO-DONO.md` — regras transversais do dono, que valem em todo projeto.
- `docs/decisoes/` — ADRs deste repositório. `docs/COMUNICACAO.md`, `docs/REVISAO.md`, `docs/OPENHANDS.md` —
  fluxo de fichas por agente externo (ver ADR 0002: o caminho pelo OpenRouter está encerrado).
- `tests/` — testes de tudo acima; cada verificador tem controle positivo.

## Regras inegociáveis

- As regras de [`docs/REGRAS-DO-DONO.md`](docs/REGRAS-DO-DONO.md) valem aqui.
- **Repositório público**: nenhum segredo, dado de paciente, nome de pessoa, telefone, e-mail, valor em dinheiro,
  domínio, IP ou caminho de servidor. O que é de um projeto vai para o repositório (privado) dele.
- Mudar o kit muda os 22 repositórios que o adotaram: mudança de regra da conformidade só com teste que reprova
  o caso novo e aprova o controle positivo, e com nota no `docs/ESTADO.md`.
- `adotar-padrao` nunca sobrescreve arquivo existente. Quem quiser trocar, troca à mão.
- Verificação que não reprova não é verificação; falha de medição devolve `NÃO MEDIDO`, nunca zero.
- pt-BR na documentação; código em inglês ou pt-BR como já está; UTF-8 sem BOM, LF; Conventional Commits.

## O que o agente NUNCA faz

- Commitar segredo ou dado pessoal (o gitleaks roda em todo PR).
- Enfraquecer um teste para ele passar; apagar o controle positivo.
- Criar chave de API paga, ligar agente por OpenRouter ou qualquer recurso cobrado por uso (ADR 0002).
- `push --force` ou reescrever histórico.

## Como é um PR aceitável

- Um assunto por PR, `bash scripts/verificar` verde, `docs/ESTADO.md` atualizado.
- Merge: o CI (`teste-padroes` e `conformidade-propria`) verde, depois `gh pr merge --squash`. A `main` não tem
  proteção de branch; o CI é o portão.

## Onde está o conhecimento

| O quê | Onde |
|---|---|
| Estado e próximo passo | [`docs/ESTADO.md`](docs/ESTADO.md) |
| Decisões | [`docs/decisoes/`](docs/decisoes/) |
| Termos | [`docs/GLOSSARIO.md`](docs/GLOSSARIO.md) |
| Regras do dono | [`docs/REGRAS-DO-DONO.md`](docs/REGRAS-DO-DONO.md) |
| Skills de método | [`.agents/skills/`](.agents/skills/) |
| Como adotar o kit | [`README.md`](README.md) |
