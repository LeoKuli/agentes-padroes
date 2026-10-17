#!/usr/bin/env bash
# Cria ou atualiza os rótulos padrão (templates/labels.json) em um repositório.
#
# Uso:   scripts/aplicar-labels.sh LeoKuli/<repo> [agente:<modelo> ...]
# Ex.:   scripts/aplicar-labels.sh LeoKuli/marketing agente:sonnet agente:deepseek
# Teste: DRY_RUN=1 scripts/aplicar-labels.sh LeoKuli/marketing   (só mostra, não chama o gh)
#
# Idempotente: `gh label create --force` cria o rótulo ou atualiza cor e descrição.
# Só mexe em rótulos; não toca em nenhuma outra configuração do repositório.
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "uso: $0 LeoKuli/<repo> [agente:<modelo> ...]" >&2
  exit 2
fi

repo="$1"
shift
if ! [[ "$repo" =~ ^LeoKuli/[A-Za-z0-9_.-]+$ ]]; then
  echo "repositório inválido: use o formato LeoKuli/<nome>" >&2
  exit 2
fi

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
arquivo="$aqui/../templates/labels.json"
[ -f "$arquivo" ] || { echo "não achei $arquivo" >&2; exit 1; }

py=python3
command -v "$py" >/dev/null 2>&1 || py=python
command -v "$py" >/dev/null 2>&1 || { echo "preciso de python3" >&2; exit 1; }

aplicar() {
  local nome="$1" cor="$2" desc="$3"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf 'DRY_RUN: %s | %s | %s\n' "$nome" "$cor" "$desc"
  else
    gh label create "$nome" --repo "$repo" --color "$cor" --description "$desc" --force </dev/null
  fi
}

# Lê o JSON com Python (sem depender de jq) e emite "nome<TAB>cor<TAB>descrição".
"$py" - "$arquivo" <<'PY' | while IFS=$'\t' read -r nome cor desc; do aplicar "$nome" "$cor" "$desc"; done
import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline=chr(10))
with open(sys.argv[1], encoding="utf-8") as f:
    dados = json.load(f)
for r in dados["labels"]:
    print("\t".join([r["name"], r["color"], r["description"]]))
PY

# Rótulos por modelo, sob demanda (cor e descrição vêm do molde "agente:<modelo>").
for nome in "$@"; do
  if ! [[ "$nome" =~ ^agente:[a-z0-9][a-z0-9._-]*$ ]]; then
    echo "rótulo de agente inválido: '$nome' (use agente:<modelo>, minúsculas)" >&2
    exit 2
  fi
  molde="$("$py" - "$arquivo" <<'PY'
import json, sys
sys.stdout.reconfigure(encoding="utf-8", newline=chr(10))
with open(sys.argv[1], encoding="utf-8") as f:
    m = json.load(f)["sob_demanda"]["agente:<modelo>"]
print(m["color"] + "\t" + m["description"])
PY
)"
  aplicar "$nome" "${molde%%$'\t'*}" "${molde#*$'\t'}"
done
