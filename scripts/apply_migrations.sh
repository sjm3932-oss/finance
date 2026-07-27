#!/usr/bin/env bash
# Apply migrations to the linked Supabase project.
# Requires one of:
#   - SUPABASE_ACCESS_TOKEN + linked project (npx supabase db push)
#   - DATABASE_URL / SUPABASE_DB_URL (psql -f combined)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/build_combined_migration.sh"

if [[ -n "${SUPABASE_DB_URL:-${DATABASE_URL:-}}" ]]; then
  DB_URL="${SUPABASE_DB_URL:-$DATABASE_URL}"
  echo "Applying via psql…"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$ROOT/supabase/combined_migration.sql"
  echo "Done."
  exit 0
fi

if [[ -n "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "Applying via supabase db push…"
  npx --yes supabase link --project-ref lsqkixysysfhywipmrky
  npx --yes supabase db push
  echo "Done."
  exit 0
fi

cat <<EOF
No credentials found.

Set one of:
  export SUPABASE_ACCESS_TOKEN=...   # then re-run this script
  export SUPABASE_DB_URL=postgresql://postgres.[ref]:[password]@db.[ref].supabase.co:5432/postgres

Or paste supabase/combined_migration.sql into:
  https://supabase.com/dashboard/project/lsqkixysysfhywipmrky/sql/new
EOF
exit 1
