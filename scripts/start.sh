#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' "Docker Compose não está disponível. Instale Docker para subir o banco e a API." >&2
  exit 1
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  printf '%s\n' "OPENAI_API_KEY não está no ambiente. A página abre; indexar ou perguntar avisa a falta da chave."
fi

printf '%s\n' "A interface fica em http://127.0.0.1:8000/"
exec docker compose up --build
