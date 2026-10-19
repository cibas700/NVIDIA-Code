#!/bin/zsh

set -u
resources_dir="${0:A:h}"
app_dir="${resources_dir:h:h}"
root_dir="${app_dir:h}"
config_path="$root_dir/Dati/nim-router.json"
default_project_dir="$root_dir/Progetti"
project_dir="${1:-$default_project_dir}"

export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export PYTHONPATH="$resources_dir/programma"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

fail() {
    print -r -- "$1"
    if [[ -t 0 ]]; then
        print -r -- "Premi Invio per chiudere."
        read -r reply
    fi
    exit 1
}

# Prefer a user-selected interpreter, otherwise use the first compatible one.
python_bin=""
python_candidates=()
if [[ -n "${NVIDIA_CODE_PYTHON:-}" ]]; then
    python_candidates=("$NVIDIA_CODE_PYTHON")
else
    path_python="$(command -v python3 2>/dev/null || true)"
    [[ -z "$path_python" ]] || python_candidates+=("$path_python")
    python_candidates+=(/usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3)
fi
for candidate in "${python_candidates[@]}"; do
    if [[ -x "$candidate" ]] && "$candidate" -c 'import sys; assert sys.version_info >= (3,9); import httpx; from nim_task_router.policy import validate' >/dev/null 2>&1; then
        python_bin="$candidate"
        break
    fi
done
[[ -n "$python_bin" ]] || fail "Serve Python 3.9 o successivo compatibile con le librerie incluse. Installa Python oppure imposta NVIDIA_CODE_PYTHON sul percorso completo dell'interprete."
[[ -f "$config_path" ]] || fail "Manca Dati/nim-router.json. Mantieni NVIDIA Code.app e Dati nella stessa cartella."

if [[ "$project_dir" == "--verifica" ]]; then
    "$python_bin" - "$config_path" <<'PY'
import json
import sys
from pathlib import Path
from nim_task_router.policy import validate, Policy
config = validate(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
Policy(config)
print("NVIDIA_CODE_CONFIG_OK")
print("Verifica locale completata: Python, librerie e configurazione. Nessuna chiamata NVIDIA.")
PY
    exit $?
fi

# Recreate the default folder when an archive or a repository omits empty folders.
if [[ "$project_dir" == "$default_project_dir" ]]; then
    mkdir -p -- "$default_project_dir" || fail "Non riesco a creare la cartella Progetti. Sposta l'intero pacchetto in una posizione scrivibile."
fi
[[ -d "$project_dir" ]] || fail "La cartella del progetto non esiste: $project_dir"
command -v claude >/dev/null 2>&1 || fail "Claude Code non è installato o non è nel PATH. Installa la CLI di Claude Code e riapri NVIDIA Code."

cd -- "$project_dir" || fail "Non riesco ad aprire la cartella del progetto."
print -r -- "NVIDIA Code"
print -r -- "Progetto: $project_dir"
print -r -- "Avvio del gateway locale e della CLI di Claude Code…"
print
"$python_bin" -m nim_task_router --config "$config_path" run
router_exit_code=$?
if (( router_exit_code != 0 )); then
    print
    print -r -- "Avvio terminato con un errore (codice $router_exit_code)."
    print -r -- "Controlla il messaggio sopra. Inserisci la tua chiave NVIDIA in Dati/nvidia-api-key.txt."
    if [[ -t 0 ]]; then
        print -r -- "Premi Invio per chiudere."
        read -r reply
    fi
fi
exit "$router_exit_code"
