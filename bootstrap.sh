#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v git >/dev/null 2>&1; then
    printf 'Błąd: git nie jest zainstalowany.\n' >&2
    exit 1
fi

if ! git -C "$ROOT" rev-parse --show-toplevel >/dev/null 2>&1; then
    printf 'Błąd: katalog nie jest repozytorium Git: %s\n' "$ROOT" >&2
    exit 1
fi

JOBS="${JOBS:-4}"
if ! [[ "$JOBS" =~ ^[1-9][0-9]*$ ]]; then
    printf 'Błąd: JOBS musi być dodatnią liczbą całkowitą.\n' >&2
    exit 1
fi

printf 'Synchronizacja submodułów…\n'
git -C "$ROOT" submodule sync --recursive
printf 'Inicjalizacja i aktualizacja submodułów…\n'
git -C "$ROOT" submodule update --init --recursive --jobs "$JOBS"
printf 'Gotowe.\n'
