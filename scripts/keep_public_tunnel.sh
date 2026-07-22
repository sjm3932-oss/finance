#!/usr/bin/env bash
# Publish live Streamlit origins for the stable Supabase gateway.
# Primary: Pinggy (more reliable than Cloudflare quick tunnels here)
# Fallback: Cloudflare quick tunnel
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${PORT:-8501}"
STATE="${TUNNEL_STATE:-/tmp/cwm_tunnel_url.txt}"
CF_LOG="${TUNNEL_LOG:-/tmp/cloudflared.log}"
PINGGY_LOG="${PINGGY_LOG:-/tmp/pinggy.log}"
REF="${SUPABASE_PROJECT_REF:-lsqkixysysfhywipmrky}"
STABLE_GATEWAY="${STABLE_APP_URL:-https://lsqkixysysfhywipmrky.supabase.co/functions/v1/app-gateway}"

publish_runtime() {
  local primary="$1"
  local fallback="${2:-}"
  python3 - "$primary" "$fallback" "$STABLE_GATEWAY" "$REF" <<'PY'
import os, sys, httpx
from pathlib import Path
from dotenv import dotenv_values

primary = sys.argv[1].rstrip("/")
fallback = (sys.argv[2] or "").rstrip("/") or None
stable = sys.argv[3].rstrip("/")
ref = sys.argv[4]
env_path = Path("/workspace/.env") if Path("/workspace/.env").exists() else Path(".env")
vals = dotenv_values(str(env_path))
token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
svc = vals.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
sb_url = (vals.get("SUPABASE_URL") or "").rstrip("/")

lines, seen = [], set()
for line in env_path.read_text().splitlines():
    if line.startswith("PUBLIC_APP_URL="):
        lines.append(f"PUBLIC_APP_URL={primary}")
    elif line.startswith("STABLE_APP_URL="):
        lines.append(f"STABLE_APP_URL={stable}")
    else:
        lines.append(line)
    if "=" in line:
        seen.add(line.split("=", 1)[0])
if "PUBLIC_APP_URL" not in seen:
    lines.append(f"PUBLIC_APP_URL={primary}")
if "STABLE_APP_URL" not in seen:
    lines.append(f"STABLE_APP_URL={stable}")
env_path.write_text("\n".join(lines) + "\n")

if sb_url and svc:
    payload = {"public_url": primary, "fallback_url": fallback}
    r = httpx.patch(
        f"{sb_url}/rest/v1/app_runtime?id=eq.1",
        headers={
            "Authorization": f"Bearer {svc}",
            "apikey": svc,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=payload,
        timeout=30,
    )
    print(f"runtime {r.status_code} primary={primary} fallback={fallback}", flush=True)

if token:
    urls = ["http://localhost:8501", "http://localhost:8501/**", stable, stable + "/**", primary, primary + "/**"]
    if fallback:
        urls += [fallback, fallback + "/**"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.patch(
        f"https://api.supabase.com/v1/projects/{ref}/config/auth",
        headers=headers,
        json={"site_url": stable, "uri_allow_list": ",".join(urls)},
        timeout=60,
    )
    print(f"auth sync {r.status_code} site_url={stable}", flush=True)
PY
}

extract_pinggy() {
  grep -oE 'https://[a-z0-9.-]+\.(pinggy-free\.link|free\.pinggy\.net)' "$PINGGY_LOG" 2>/dev/null | tail -1 || true
}

extract_cf() {
  grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$CF_LOG" 2>/dev/null | tail -1 || true
}

probe() {
  local url="$1"
  curl -fsS -o /dev/null --max-time 12 "${url}/_stcore/health" 2>/dev/null
}

echo "Waiting for Streamlit on :$PORT …"
for _ in $(seq 1 60); do
  curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:${PORT}/_stcore/health" 2>/dev/null && break
  sleep 1
done
echo "Stable gateway: $STABLE_GATEWAY"

# Child: Cloudflare fallback
(
  while true; do
    : >"$CF_LOG"
    cloudflared tunnel --url "http://127.0.0.1:${PORT}" --protocol http2 --no-autoupdate >>"$CF_LOG" 2>&1 || true
    sleep 3
  done
) &
CF_LOOP_PID=$!

# Child: Pinggy primary
(
  while true; do
    : >"$PINGGY_LOG"
    ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=20 -o ServerAliveCountMax=3 \
      -p 443 -R0:localhost:${PORT} a.pinggy.io >>"$PINGGY_LOG" 2>&1 || true
    sleep 3
  done
) &
PINGGY_LOOP_PID=$!

trap 'kill $CF_LOOP_PID $PINGGY_LOOP_PID 2>/dev/null || true' EXIT

primary=""; fallback=""
while true; do
  p=$(extract_pinggy)
  c=$(extract_cf)

  # Prefer Cloudflare (no browser interstitial). Pinggy is fallback only
  # because free Pinggy shows an "Enter site" caution page in browsers.
  new_primary=""
  new_fallback=""
  if [[ -n "$c" ]] && probe "$c"; then
    new_primary="$c"
  fi
  if [[ -n "$p" ]] && probe "$p"; then
    if [[ -z "$new_primary" ]]; then
      new_primary="$p"
    else
      new_fallback="$p"
    fi
  fi

  if [[ -n "$new_primary" && ( "$new_primary" != "$primary" || "$new_fallback" != "$fallback" ) ]]; then
    primary="$new_primary"
    fallback="$new_fallback"
    echo "$primary" >"$STATE"
    echo "ACTIVE primary=$primary fallback=${fallback:-none}" 
    publish_runtime "$primary" "$fallback" || true
  elif [[ -z "$new_primary" ]]; then
    echo "no healthy tunnel yet (pinggy=$( [[ -n \"$p\" ]] && echo up || echo down ), cf=$( [[ -n \"$c\" ]] && echo up || echo down ))"
  fi
  sleep 15
done
