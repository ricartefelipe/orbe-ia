#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' "Docker não está disponível. Instale Docker para subir o banco e a API." >&2
  exit 1
fi

printf '%s\n' "A interface fica em http://127.0.0.1:8000/"
exec docker compose up --build
