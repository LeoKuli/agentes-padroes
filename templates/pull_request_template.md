Ficha: #<número da Issue-ficha, ex.: 123>

## O que muda

<!-- 1–3 frases. -->

## Modelo e ferramenta usados

<!-- ex.: modelo X via ferramenta Y. Serve para medir a aceitação por modelo. -->

## Checklist da ficha (todos obrigatórios)

- [ ] Este PR cumpre UMA ficha, e `Ficha: #<n>` está na primeira linha acima (o `escopo` lê a Issue)
- [ ] O PR vem de um **fork**, e tenho no máximo 2 PRs abertos neste repositório
- [ ] Só toquei os **arquivos permitidos** da ficha; nenhum **arquivo proibido** nem protegido (`.github/`, CODEOWNERS, `AGENTS.md`, constituição)
- [ ] O diff está dentro do **tamanho máximo** da ficha
- [ ] O **comando de aceite** da ficha passa localmente: `<colar o comando e o resultado>`
- [ ] Criei o **teste da ficha**, que executa o código real, e o **controle positivo**
- [ ] A **mutação** da ficha morre, e na asserção indicada: `<qual asserção>`
- [ ] Não enfraqueci, pulei nem apaguei teste algum
- [ ] Não alterei CI, CODEOWNERS, constituição, testes de arquitetura, pisos nem limiares de mutação
- [ ] Sem credencial, telefone, CPF, e-mail ou dado de paciente em arquivo, teste, commit ou nesta descrição
- [ ] Commits em Conventional Commits

## O que ficou fora do escopo

<!-- Ideias e problemas vistos no caminho. Cada um vira ficha nova; não entra neste PR. -->

## Dúvidas ou riscos para o revisor

<!-- Onde a ficha estava ambígua e o que você decidiu. Se algo não foi medido, escreva "NÃO MEDIDO". -->
