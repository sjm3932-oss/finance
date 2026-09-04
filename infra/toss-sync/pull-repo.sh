#!/usr/bin/env bash
# Refresh the worker checkout before systemd starts toss-sync-worker.
set -euo pipefail
REPO="${TOSS_SYNC_REPO:-/opt/toss-sync/repo}"
REF="${WORKER_GIT_REF:-cursor/wealth-mvp-core-faae}"
if [ ! -d "$REPO/.git" ]; then
  echo "pull-repo: $REPO is not a git checkout"
  exit 0
fi
git -C "$REPO" fetch --depth 1 origin "$REF"
git -C "$REPO" checkout --force FETCH_HEAD
echo "pull-repo: now at $(git -C "$REPO" rev-parse --short HEAD) ($REF)"
