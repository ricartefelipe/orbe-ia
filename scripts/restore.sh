#!/bin/sh
# Restaura um dump em um banco NOVO (padrão orbe_restore), sem tocar no banco de uso.
# Valide a aplicação contra o destino antes de promover.
# Saída: 0 sucesso · 1 falha · 2 inconclusivo (uso incorreto, sem Docker ou banco no ar).
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$root"

service=db
db_user=orbe
source_db=orbe
target_db="${2:-orbe_restore}"
timeout_seconds="${RESTORE_TIMEOUT:-180}"

dump="${1:-}"
if [ -z "$dump" ] || [ ! -f "$dump" ]; then
  printf '%s\n' "Uso: scripts/restore.sh <arquivo.dump> [banco_destino]" >&2
  exit 2
fi

if [ "$target_db" = "$source_db" ]; then
  printf '%s\n' "Recuse restaurar sobre o banco de uso ($source_db). Escolha outro destino." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  printf '%s\n' "Docker Compose não está disponível." >&2
  exit 2
fi

if ! docker compose ps --status running --services 2>/dev/null | grep -qx "$service"; then
  printf '%s\n' "O serviço $service não está no ar." >&2
  exit 2
fi

run_sql() {
  docker compose exec -T "$service" psql -v ON_ERROR_STOP=1 -U "$db_user" "$@"
}

printf '%s\n' "Recriando o banco destino $target_db…"
run_sql -d "$source_db" -c "DROP DATABASE IF EXISTS $target_db" >/dev/null
run_sql -d "$source_db" -c "CREATE DATABASE $target_db" >/dev/null
run_sql -d "$target_db" -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null

printf '%s\n' "Restaurando $dump em $target_db…"
if ! timeout "$timeout_seconds" docker compose exec -T "$service" \
  pg_restore -U "$db_user" -d "$target_db" --no-owner <"$dump"; then
  printf '%s\n' "pg_restore falhou." >&2
  exit 1
fi

files=$(run_sql -tA -d "$target_db" -c "SELECT count(*) FROM dossier_files" 2>/dev/null || echo erro)
chunks=$(run_sql -tA -d "$target_db" -c "SELECT count(*) FROM langchain_pg_embedding" 2>/dev/null || echo erro)
if [ "$files" = erro ] || [ "$chunks" = erro ]; then
  printf '%s\n' "As tabelas esperadas não foram restauradas." >&2
  exit 1
fi

printf '%s\n' "Restauração concluída em $target_db: $files documentos, $chunks trechos."
printf '%s\n' "Valide apontando DATABASE_URL para $target_db antes de promover."
