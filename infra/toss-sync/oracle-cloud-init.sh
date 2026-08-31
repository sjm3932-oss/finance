#!/usr/bin/env bash
# Oracle Cloud Always Free — paste as instance "Initialization script".
# Image must be Canonical Ubuntu. Default user is ubuntu.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip git ca-certificates curl
id ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu
install -d -o ubuntu -g ubuntu /opt/toss-sync
rm -rf /opt/toss-sync/repo
git clone --depth 1 --branch cursor/wealth-mvp-core-faae \
  https://github.com/sjm3932-oss/finance.git /opt/toss-sync/repo
chown -R ubuntu:ubuntu /opt/toss-sync/repo
cd /opt/toss-sync/repo
sudo -u ubuntu python3 -m venv /opt/toss-sync/repo/.venv
sudo -u ubuntu /opt/toss-sync/repo/.venv/bin/pip install --no-cache-dir \
  -r /opt/toss-sync/repo/infra/toss-sync/requirements-toss-worker.txt

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
TOSS_AUTO_SYNC_HOURS=6,16
TOSS_TRADE_LOOKBACK_DAYS=365
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_CANO=
KIS_ACNT_PRDT_CD=01
KIS_ACCOUNTS=
KIS_ENV=real
KIS_TRADE_LOOKBACK_DAYS=365
ENV
chmod 600 /opt/toss-sync/env.example
if [ ! -f /opt/toss-sync/env ]; then
  cp /opt/toss-sync/env.example /opt/toss-sync/env
  chmod 600 /opt/toss-sync/env
  chown ubuntu:ubuntu /opt/toss-sync/env
fi
echo "READY. Fill /opt/toss-sync/env then: systemctl enable --now toss-sync-worker"
curl -sS https://ifconfig.me || true
echo
