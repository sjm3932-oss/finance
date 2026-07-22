#!/usr/bin/env bash
# Start Streamlit + Cloudflare quick tunnel for mobile HTTPS access.
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
export PUBLIC_APP_URL="${PUBLIC_APP_URL:-}"

echo "Starting Streamlit on :$PORT …"
. .venv/bin/activate
streamlit run streamlit_app/app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT

sleep 3
echo "Starting Cloudflare quick tunnel …"
echo "When the trycloudflare.com URL appears:"
echo "  1) Set PUBLIC_APP_URL to that URL and restart, OR export it before this script"
echo "  2) Add the URL to Supabase Auth → Redirect URLs"
cloudflared tunnel --url "http://127.0.0.1:$PORT" --no-autoupdate
