# agentes-padroes

O contrato compartilhado que deixa os repositórios do dono **agnósticos a modelo de IA e a ferramenta**: qualquer
modelo (Claude, GPT/Codex, Gemini, Cursor, Copilot, um modelo local), em qualquer momento do projeto, consegue
colaborar, assumir ou retomar o trabalho **só com o que está no repositório**.

Instruções para agentes que trabalham **neste** repositório: [`AGENTS.md`](AGENTS.md).

## O kit (v2)

| No repositório que adota | Para quê |
|---|---|
| `AGENTS.md` | Fonte única de instruções (padrão aberto AGENTS.md): retomar, rodar, regras, o que nunca fazer, PR aceitável |
| `CLAUDE.md` (`@AGENTS.md`), `GEMINI.md` (`@./AGENTS.md`), `.github/copilot-instructions.md` | Ponteiros finos: cada ferramenta cai no AGENTS.md |
| `docs/ESTADO.md` | Arquivo de retomada: onde parou, em curso, próximo passo, bloqueios, últimas decisões, data. Atualizado no fim de toda sessão, por qualquer modelo |
| `docs/decisoes/NNNN-*.md` | ADRs no formato MADR. Tarefa que conflita com ADR aceito: o agente para e pergunta |
| `docs/GLOSSARIO.md` | Termos do domínio e apelidos internos |
| `.agents/skills/` | Skills próprias do projeto no formato aberto Agent Skills (`SKILL.md`); as de método ficam [aqui](.agents/skills/) |
| `.mcp.json` | Servidores MCP do projeto, sem segredo (só `${VAR}`) |
| `.env.example` | Nomes das variáveis de ambiente, nunca valores |
| `scripts/verificar` (ou `make verificar`) | Comando único: prepara, testa e valida; o mesmo no CI |
| `.devcontainer/devcontainer.json` | Ambiente reproduzível, onde fizer sentido (`--devcontainer`) |
| `.github/workflows/conformidade.yml` | Chama a conformidade e o gitleaks reutilizáveis |
| `.gitleaks.toml` | Regras de segredo e de dado pessoal |

Regras transversais do dono: [`docs/REGRAS-DO-DONO.md`](docs/REGRAS-DO-DONO.md).

## Adotar num repositório existente

```bash
git clone https://github.com/LeoKuli/agentes-padroes.git
python agentes-padroes/scripts/adotar_padrao.py <pasta-do-repositorio> [--nome NOME] [--devcontainer] [--simular]
```

O `adotar-padrao` **nunca sobrescreve**: o que existe fica ("mantido"), o que falta é criado. Depois:

1. Trocar todo `PREENCHER` por conteúdo **real** do projeto (a conformidade reprova enquanto sobrar algum).
2. Escrever ao menos o ADR `0001` com uma decisão real e o `docs/ESTADO.md` com a data de hoje.
3. Se já havia um `CLAUDE.md` com conteúdo, movê-lo para o `AGENTS.md` e deixar só `@AGENTS.md`.
4. Se o repositório já roda o gitleaks noutro workflow, apagar o job `segredos` do `conformidade.yml`.
5. `python agentes-padroes/scripts/conformidade.py --raiz <pasta>` até dar APROVADO; depois `bash scripts/verificar`.

## Projeto novo (template repository)

```bash
gh repo create LeoKuli/<novo> --private --template LeoKuli/agentes-padroes --clone
cd <novo> && python scripts/iniciar_projeto.py --nome <novo>
```

O `iniciar-projeto` apaga tudo o que veio do agentes-padroes (menos `.git`) e monta só o kit. Skills de método e
regras do dono continuam num lugar só (aqui) e são citadas por link.

## Conformidade

Workflow reutilizável [`conformidade.yml`](.github/workflows/conformidade.yml) com o verificador
[`scripts/conformidade.py`](scripts/conformidade.py) (só biblioteca padrão). Reprova:

- sem `AGENTS.md`, ou com `PREENCHER` sobrando nele, no `docs/ESTADO.md` ou no `scripts/verificar`;
- `docs/ESTADO.md` sem `Atualizado em: AAAA-MM-DD`, com data no futuro ou vencida além de `dias-maximos` (padrão 30);
- sem ADR em `docs/decisoes/NNNN-*.md`, ou ADR sem `status` válido no frontmatter;
- `CLAUDE.md` sem `@AGENTS.md`; `GEMINI.md`/`copilot-instructions.md` que não citam o AGENTS.md;
- sem comando único; `.mcp.json` inválido ou com valor literal em `env`.

Roda em PR e em push na branch padrão, não por agenda (ADR 0003).

## Os outros workflows reutilizáveis

| Caminho | Para quê |
|---|---|
| `.github/workflows/segredos.yml` | gitleaks no diff do PR (binário com sha256 conferido) |
| `.github/workflows/ficha.yml`, `escopo.yml`, `mutacao-ficha.yml`, `juntar-so-teste.yml` | Fluxo de fichas: PR cita a ficha, escopo contra a ficha, mutação que tem de morrer |
| `.github/workflows/agente-openhands.yml` | Agente dentro do Actions por rótulo. **Não ligar**: o caminho pelo OpenRouter foi encerrado em 03/11/2026 ([ADR 0002](docs/decisoes/0002-fluxo-openrouter-encerrado.md)) |

Modelos do fluxo de fichas: `templates/FICHA-DE-TAREFA.md`, `templates/ISSUE_TEMPLATE/`, `templates/labels.json`,
`templates/pull_request_template.md`, `templates/CODEOWNERS.example`. Como funcionava: [`docs/COMUNICACAO.md`](docs/COMUNICACAO.md),
[`docs/REVISAO.md`](docs/REVISAO.md), [`docs/OPENHANDS.md`](docs/OPENHANDS.md).

## Regra de ouro

Nenhum agente commita segredo ou dado de paciente, enfraquece teste para passar, gasta dinheiro sem o sim do dono,
ou faz `push --force`. Este repositório é **público**: nada de dado de projeto aqui.
