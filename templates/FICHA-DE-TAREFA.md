# Ficha de tarefa <ID>

> Uma ficha por pull request. Autocontida: quem pega a ficha não precisa de outro contexto além
> dos links abaixo. Escrita por um modelo forte; executada por qualquer modelo.

| Campo | Valor |
|---|---|
| **ID** | `<SIGLA>-<NNN>` (ex.: `MKT-012`) |
| **Spec** | `specs/NNN-nome/spec.md` (e a seção/FR que esta ficha cumpre) |
| **Nível** | 1 simples · 2 média · 3 difícil · 4 arquitetura |
| **Modelo mínimo** | ex.: Haiku / Sonnet / Opus ou equivalente de outro fornecedor |

## Objetivo

<!-- 1 a 3 frases. O que muda no comportamento do sistema quando esta ficha estiver pronta. -->

## Contexto

<!-- Links (caminhos de arquivo e seções de spec/ADR/lição). Só o que é necessário. -->

- Spec:
- Código relacionado:
- Lição/ADR:

## Arquivos permitidos

<!-- Lista exata. Tudo que não está aqui é proibido. -->

-

## Arquivos proibidos

<!-- Sempre inclua: .github/, CI, CODEOWNERS, constitution, testes de arquitetura, limiares de mutação,
     arquivos de segredo/ambiente. Acrescente o que for específico desta tarefa. -->

- `.github/**`
- `**/CODEOWNERS`
- constituição e testes de arquitetura
- limiares de mutação e pisos
- `.env*`

## Passos sugeridos

1.
2.
3.

## Teste que deve nascer

<!-- Nome do arquivo e do caso. Tem de EXECUTAR o código real. -->

- Teste:
- **Controle positivo** (o caso que prova que o teste enxerga o defeito):

## Mutação que tem de morrer

<!-- A alteração no código que o teste precisa detectar, e QUAL asserção deve reprová-la. -->

- Mutação:
- Asserção que a mata:

## Comando de aceite

```bash
<comando exato, o mesmo "pronto" do AGENTS.md>
```

## Critério de pronto

- [ ] O comando de aceite passa (local e no CI)
- [ ] O teste novo existe, executa código real e tem controle positivo
- [ ] A mutação indicada morre na asserção indicada
- [ ] Só arquivos permitidos foram tocados
- [ ] Diff dentro do tamanho máximo
- [ ] Nenhum teste existente foi enfraquecido, pulado ou apagado
- [ ] Sem segredo, telefone, CPF, e-mail ou dado de paciente em nenhum arquivo
- [ ] PR traz `Ficha: <ID>` e o template preenchido

## Tamanho máximo do diff

<!-- ex.: 150 linhas alteradas, 3 arquivos. Estourou? Pare e relate no PR em vez de continuar. -->

## Fora do escopo

<!-- O que NÃO fazer, mesmo que pareça melhorar. Ideias novas viram nova ficha, não entram aqui. -->

-
