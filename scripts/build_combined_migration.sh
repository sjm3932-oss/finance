#!/usr/bin/env bash
# Concatenate migrations for paste into Supabase SQL Editor (fallback when CLI link is unavailable).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/supabase/combined_migration.sql}"
{
  echo "-- Auto-generated combined migration for Couples Wealth Master"
  echo "-- Project: https://lsqkixysysfhywipmrky.supabase.co"
  echo "-- Apply in Supabase Dashboard → SQL → New query"
  echo
  for f in "$ROOT"/supabase/migrations/*.sql; do
    echo "-- >>> $(basename "$f")"
    cat "$f"
    echo
    echo
  done
} > "$OUT"
echo "Wrote $OUT"
