#!/usr/bin/env bash
# Cloud-init for a *static-IP* Ubuntu VM (DigitalOcean / Lightsail / Oracle).
# Paste into the provider's web console. Do not run this on a laptop.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip git ca-certificates
install -d -o ubuntu -g ubuntu /opt/toss-sync
cd /opt/toss-sync
git clone --depth 1 --branch cursor/wealth-mvp-core-faae https://github.com/sjm3932-oss/finance.git repo || true
cd /opt/toss-sync/repo || cd /opt/toss-sync/finance
python3 -m venv .venv
.venv/bin/pip install -r infra/toss-sync/requirements-toss-worker.txt 2>/dev/null \
  || .venv/bin/pip install supabase python-dotenv

cat >/etc/systemd/system/toss-sync-worker.service <<'UNIT'
[Unit]
Description=Toss Open API sync worker (static IP)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/toss-sync/repo
EnvironmentFile=/opt/toss-sync/env
ExecStart=/opt/toss-sync/repo/.venv/bin/python3 scripts/toss_sync_worker.py
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
UNIT

cat >/opt/toss-sync/env.example <<'ENV'
SUPABASE_URL=https://lsqkixysysfhywipmrky.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
TOSS_CLIENT_ID=
TOSS_CLIENT_SECRET=
TOSS_AUTO_SYNC_SECONDS=21600
TOSS_TRADE_LOOKBACK_DAYS=365
ENV
chmod 600 /opt/toss-sync/env.example
if [ ! -f /opt/toss-sync/env ]; then
  cp /opt/toss-sync/env.example /opt/toss-sync/env
fi
echo "Fill /opt/toss-sync/env then: systemctl enable --now toss-sync-worker"
echo "Public IP: $(curl -s https://ifconfig.me || true)"
