#!/usr/bin/env bash
# Keep Cloudflare quick tunnel alive, publish live URL to app_runtime,
# and sync OAuth allow-list. Users should open the stable gateway URL, not the tunnel hostname.
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
STABLE_GATEWAY="${STABLE_APP_URL:-https://lsqkixysysfhywipmrky.supabase.co/functions/v1/app-gateway}"

publish_runtime() {
  local url="$1"
  python3 - "$url" "$STABLE_GATEWAY" "$REF" <<'PY'
import os, sys, httpx
from pathlib import Path
from dotenv import dotenv_values

url = sys.argv[1].rstrip("/")
stable = sys.argv[2].rstrip("/")
ref = sys.argv[3]
env_path = Path("/workspace/.env") if Path("/workspace/.env").exists() else Path(".env")
vals = dotenv_values(str(env_path))
token = vals.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_ACCESS_TOKEN")
svc = vals.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
sb_url = (vals.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL") or "").rstrip("/")

# Persist tunnel URL for the Streamlit process / local tooling.
lines, found = [], False
for line in env_path.read_text().splitlines():
    if line.startswith("PUBLIC_APP_URL="):
        lines.append(f"PUBLIC_APP_URL={url}")
        found = True
    elif line.startswith("STABLE_APP_URL="):
        lines.append(f"STABLE_APP_URL={stable}")
    else:
        lines.append(line)
if not found:
    lines.append(f"PUBLIC_APP_URL={url}")
if not any(l.startswith("STABLE_APP_URL=") for l in lines):
    lines.append(f"STABLE_APP_URL={stable}")
env_path.write_text("\n".join(lines) + "\n")

# Publish live URL for the stable gateway to resolve.
if sb_url and svc:
    r = httpx.patch(
        f"{sb_url}/rest/v1/app_runtime?id=eq.1",
        headers={
            "Authorization": f"Bearer {svc}",
            "apikey": svc,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={"public_url": url},
        timeout=30,
    )
    if r.status_code >= 400:
        # insert if missing
        httpx.post(
            f"{sb_url}/rest/v1/app_runtime",
            headers={
                "Authorization": f"Bearer {svc}",
                "apikey": svc,
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            json={"id": 1, "public_url": url},
            timeout=30,
        )
    print(f"runtime publish {r.status_code} -> {url}", flush=True)

# Keep both the stable gateway and current tunnel in Auth allow-list.
if token:
    allow = ",".join([
        "http://localhost:8501",
        "http://localhost:8501/**",
        stable,
        stable + "/**",
        url,
        url + "/**",
    ])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = httpx.patch(
        f"https://api.supabase.com/v1/projects/{ref}/config/auth",
        headers=headers,
        json={"site_url": stable, "uri_allow_list": allow},
        timeout=60,
    )
    print(f"auth sync {r.status_code} site_url={stable}", flush=True)
PY
}

dns_ok() {
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
    data = r.json()
    # Status 0 + Answer => resolvable
    ok = data.get("Status") == 0 and bool(data.get("Answer"))
    print("1" if ok else "0")
except Exception:
    print("0")
PY
}

probe_http() {
  local url="$1"
  local host="${url#https://}"; host="${host%%/*}"
  local ip
  ip=$(python3 - "$host" <<'PY'
import sys, httpx
host=sys.argv[1]
try:
  r=httpx.get('https://cloudflare-dns.com/dns-query', params={'name':host,'type':'A'}, headers={'accept':'application/dns-json'}, timeout=15)
  ans=r.json().get('Answer') or []
  print(ans[0]['data'] if ans else '')
except Exception:
  print('')
PY
)
  if [[ -n "$ip" ]]; then
    curl -fsS -o /dev/null --max-time 15 --resolve "${host}:443:${ip}" "${url}/_stcore/health"
  else
    return 1
  fi
}

echo "Waiting for Streamlit on :$PORT …"
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null --max-time 2 "http://127.0.0.1:${PORT}/_stcore/health" 2>/dev/null; then
    break
  fi
  sleep 1
done

echo "Stable gateway: $STABLE_GATEWAY"

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
  echo "$URL" >"$STATE"
  echo "TUNNEL URL: $URL" | tee -a "$LOG"
  publish_runtime "$URL" || true

  # Wait until public DNS exists (DoH). NXDOMAIN means the hostname is useless.
  dns_ready=0
  for _ in $(seq 1 30); do
    if [[ "$(dns_ok "$HOST")" == "1" ]]; then
      dns_ready=1
      break
    fi
    sleep 2
  done
  if [[ "$dns_ready" != "1" ]]; then
    echo "DNS never became ready for $HOST; rotating" | tee -a "$LOG"
    kill "$CF_PID" 2>/dev/null || true
    wait "$CF_PID" 2>/dev/null || true
    sleep 2
    continue
  fi

  if probe_http "$URL"; then
    echo "tunnel healthy (+ DNS)" | tee -a "$LOG"
  else
    echo "HTTP probe failed after DNS ok; continuing watch" | tee -a "$LOG"
  fi

  fails=0
  while kill -0 "$CF_PID" 2>/dev/null; do
    if [[ "$(dns_ok "$HOST")" != "1" ]]; then
      echo "DNS NXDOMAIN for $HOST; rotating" | tee -a "$LOG"
      break
    fi
    if probe_http "$URL"; then
      fails=0
    else
      fails=$((fails + 1))
      echo "health fail #$fails for $URL" | tee -a "$LOG"
      if [[ "$fails" -ge 4 ]]; then
        echo "sustained health failures; rotating" | tee -a "$LOG"
        break
      fi
    fi
    sleep 20
  done

  kill "$CF_PID" 2>/dev/null || true
  wait "$CF_PID" 2>/dev/null || true
  sleep 2
done
