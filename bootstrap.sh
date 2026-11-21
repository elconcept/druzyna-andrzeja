#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v git >/dev/null 2>&1; then
  echo 'Brak Git.' >&2; exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Brak Python 3.11+.' >&2; exit 1
fi
if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo 'Uruchom w repozytorium Git.' >&2; exit 1
fi

# Domyślnie odtwarza przypięte SHA. GitHub Actions używa --refresh.
exec python3 "$ROOT/scripts/sync.py" "$@"
