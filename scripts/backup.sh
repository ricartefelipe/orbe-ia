#!/bin/sh
# Dump do banco do Compose em backups/. Não liga efeitos externos.
# Saída: 0 sucesso · 1 falha · 2 inconclusivo (sem Docker ou banco no ar).
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

service=db
db_user=orbe
db_name=orbe
timeout_seconds="${BACKUP_TIMEOUT:-120}"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' "Docker Compose não está disponível." >&2
  exit 2
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$service"; then
  printf '%s\n' "O serviço $service não está no ar. Suba o banco antes do backup." >&2
  exit 2
fi

out="${1:-backups/orbe-$(date -u +%Y%m%dT%H%M%SZ).dump}"
mkdir -p "$(dirname "$out")"

printf '%s\n' "Gerando dump de $db_name em $out…"
if ! timeout "$timeout_seconds" docker compose exec -T "$service" \
  pg_dump -U "$db_user" -d "$db_name" -Fc >"$out"; then
  printf '%s\n' "pg_dump falhou." >&2
  rm -f "$out"
  exit 1
fi

if [ ! -s "$out" ]; then
  printf '%s\n' "O dump ficou vazio." >&2
  rm -f "$out"
  exit 1
fi

printf '%s\n' "Backup concluído: $out ($(wc -c <"$out") bytes)."
