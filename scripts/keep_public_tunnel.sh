#!/usr/bin/env bash
# Keep a public Cloudflare quick tunnel alive and sync OAuth redirect URLs.
# Usage: scripts/keep_public_tunnel.sh
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
LOG="${TUNNEL_LOG:-/tmp/cloudflared.log}"
STATE="${TUNNEL_STATE:-/tmp/cwm_tunnel_url.txt}"
REF="${SUPABASE_PROJECT_REF:-lsqkixysysfhywipmrky}"

resolve_ip() {
  local host="$1"
  python3 - "$host" <<'PY'
import sys, httpx
host = sys.argv[1]
try:
    r = httpx.get(
        "https://cloudflare-dns.com/dns-query",
        params={"name": host, "type": "A"},
        headers={"accept": "application/dns-json"},
        timeout=15,
    )
    ans = r.json().get("Answer") or []
    print(ans[0]["data"] if ans else "")
except Exception:
    print("")
PY
}

ensure_hosts() {
  local host="$1" ip="$2"
  [[ -z "$ip" ]] && return 0
  if ! grep -q "$host" /etc/hosts 2>/dev/null; then
    echo "$ip $host" | sudo tee -a /etc/hosts >/dev/null 2>&1 || true
  fi
}

sync_auth() {
  local url="$1"
  python3 - "$url" "$REF" <<'PY'
import os, sys, httpx
from dotenv import dotenv_values
from pathlib import Path

url = sys.argv[1].rstrip("/")
ref = sys.argv[2]
env_path = Path("/workspace/.env") if Path("/workspace/.env").exists() else Path(".env")
vals = dotenv_values(str(env_path))
token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
if not token:
    print("skip auth sync: no SUPABASE_ACCESS_TOKEN", flush=True)
    sys.exit(0)

lines, found = [], False
for line in env_path.read_text().splitlines():
    if line.startswith("PUBLIC_APP_URL="):
        lines.append(f"PUBLIC_APP_URL={url}")
        found = True
    else:
        lines.append(line)
if not found:
    lines.append(f"PUBLIC_APP_URL={url}")
env_path.write_text("\n".join(lines) + "\n")

allow = ",".join([
    "http://localhost:8501",
    "http://localhost:8501/**",
    url,
    url + "/**",
])
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
r = httpx.patch(
    f"https://api.supabase.com/v1/projects/{ref}/config/auth",
    headers=headers,
    json={"site_url": url, "uri_allow_list": allow},
    timeout=60,
)
print(f"auth sync {r.status_code} site_url={url}", flush=True)
PY
}

probe() {
  local url="$1"
  local host="${url#https://}"
  host="${host%%/*}"
  local ip
  ip=$(resolve_ip "$host")
  ensure_hosts "$host" "$ip"
  if [[ -n "$ip" ]]; then
    curl -fsS -o /dev/null --max-time 15 --resolve "${host}:443:${ip}" "${url}/_stcore/health" 2>/dev/null
  else
    curl -fsS -o /dev/null --max-time 15 "${url}/_stcore/health" 2>/dev/null
  fi
}

edge_alive() {
  # Prefer metrics gauge; fall back to recent register without terminate
  local metrics
  metrics=$(curl -fsS --max-time 2 http://127.0.0.1:20241/metrics 2>/dev/null || true)
  if [[ -n "$metrics" ]]; then
    echo "$metrics" | awk '/^cloudflared_tunnel_ha_connections / {print $2; found=1} END{if(!found) print 0}'
    return 0
  fi
  echo 0
}

echo "Waiting for Streamlit on :$PORT …"
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:${PORT}/_stcore/health" 2>/dev/null; then
    break
  fi
  sleep 1
done

while true; do
  : >"$LOG"
  echo "=== starting cloudflared $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  cloudflared tunnel --url "http://127.0.0.1:${PORT}" --protocol http2 --no-autoupdate \
    >>"$LOG" 2>&1 &
  CF_PID=$!

  URL=""
  for _ in $(seq 1 45); do
    URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | tail -1 || true)
    if [[ -n "$URL" ]] && grep -q 'Registered tunnel connection' "$LOG"; then
      break
    fi
    if ! kill -0 "$CF_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done

  if [[ -z "$URL" ]]; then
    echo "failed to obtain tunnel URL; retrying…" | tee -a "$LOG"
    kill "$CF_PID" 2>/dev/null || true
    wait "$CF_PID" 2>/dev/null || true
    sleep 3
    continue
  fi

  HOST="${URL#https://}"
  IP=$(resolve_ip "$HOST")
  ensure_hosts "$HOST" "$IP"
  echo "$URL" >"$STATE"
  echo "PUBLIC URL: $URL (ip=$IP)" | tee -a "$LOG"
  sync_auth "$URL" || true

  # Give DNS/edge a moment before probing
  sleep 3
  if probe "$URL"; then
    echo "tunnel healthy" | tee -a "$LOG"
  else
    echo "initial probe failed (may still work externally); continuing watch" | tee -a "$LOG"
  fi

  fails=0
  while kill -0 "$CF_PID" 2>/dev/null; do
    ha=$(edge_alive)
    if [[ "$ha" == "0" ]]; then
      echo "ha_connections=0; rotating" | tee -a "$LOG"
      break
    fi
    if probe "$URL"; then
      fails=0
    else
      fails=$((fails + 1))
      echo "health fail #$fails ha=$ha for $URL" | tee -a "$LOG"
      # Only rotate after sustained failures AND edge looks dead-ish
      if [[ "$fails" -ge 6 ]]; then
        echo "sustained health failures; rotating tunnel" | tee -a "$LOG"
        break
      fi
    fi
    sleep 20
  done

  kill "$CF_PID" 2>/dev/null || true
  wait "$CF_PID" 2>/dev/null || true
  sleep 2
done
