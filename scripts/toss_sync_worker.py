#!/usr/bin/env python3
"""Cloud worker: claim queued Toss/KIS sync jobs and run Open API from this host.

This process must run on a cloud VM with a *static* public IP for Toss.
KIS keys are stored in kis_api_settings (in-app). The worker reads them from
the DB when env is empty. Do not run Toss sync on a laptop.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def maybe_self_update() -> None:
    """Pull WORKER_GIT_REF so a static-IP VM eventually picks up merged sync fixes."""
    if os.getenv("WORKER_SELF_UPDATE", "1").strip().lower() in {"0", "false", "no"}:
        return
    if not (ROOT / ".git").exists():
        return
    ref = os.getenv("WORKER_GIT_REF", "cursor/wealth-mvp-core-faae").strip()
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "fetch", "--depth", "1", "origin", ref],
            check=True,
            timeout=90,
            capture_output=True,
        )
        local = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True, timeout=10
        ).strip()
        remote = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "FETCH_HEAD"], text=True, timeout=10
        ).strip()
        if local == remote:
            return
        subprocess.run(
            ["git", "-C", str(ROOT), "checkout", "--force", "FETCH_HEAD"],
            check=True,
            timeout=30,
            capture_output=True,
        )
        print(f"worker updated {local[:8]} -> {remote[:8]} ({ref}), restarting", flush=True)
        os.execv(sys.executable, [sys.executable, *sys.argv])
    except Exception as exc:
        print(f"worker self-update skip: {exc}", flush=True)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from kis_client import INSTITUTION as KIS_INSTITUTION  # noqa: E402
from sync_kis import kis_credentials, run_sync as run_kis_sync  # noqa: E402
from sync_toss import public_ip, run_sync, supabase  # noqa: E402
from toss_client import INSTITUTION, KST, kst_auto_sync_due, parse_auto_sync_hours  # noqa: E402

# TOSS_AUTO_SYNC_SECONDS=0 disables auto enqueue. The in-app button still works.
# Default clock: 06:00 and 16:00 KST.
AUTO_DISABLED = int(os.getenv("TOSS_AUTO_SYNC_SECONDS", "1")) <= 0
AUTO_HOURS = parse_auto_sync_hours(os.getenv("TOSS_AUTO_SYNC_HOURS", "6,16"))
KIS_AUTO_DISABLED = int(os.getenv("KIS_AUTO_SYNC_SECONDS", "1")) <= 0
_last_auto_check = 0.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def users_for_autosync(c, institution: str) -> list[str]:
    rows = (
        c.table("accounts")
        .select("user_id")
        .eq("institution", institution)
        .execute()
        .data
        or []
    )
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        uid = row.get("user_id")
        if uid and uid not in seen:
            seen.add(uid)
            ids.append(uid)
    if ids:
        return ids
    users = (
        c.table("users").select("id").order("created_at").limit(1).execute().data or []
    )
    return [u["id"] for u in users if u.get("id")]


def _last_ok(c, table: str) -> datetime | None:
    last = (
        c.table(table)
        .select("finished_at")
        .eq("status", "ok")
        .order("finished_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return _parse_dt(last[0].get("finished_at") if last else None)


def maybe_enqueue_auto(c) -> None:
    global _last_auto_check
    if not AUTO_HOURS:
        return
    now = time.time()
    if now - _last_auto_check < 60:
        return
    _last_auto_check = now
    now_kst = datetime.now(KST)
    if not AUTO_DISABLED and kst_auto_sync_due(now_kst, _last_ok(c, "toss_sync_jobs"), AUTO_HOURS):
        for uid in users_for_autosync(c, INSTITUTION):
            _enqueue_if_idle(
                c,
                "toss_sync_jobs",
                uid,
                f"auto-queued toss sync for {uid} (KST {AUTO_HOURS})",
            )
    if KIS_AUTO_DISABLED:
        return
    appkey, appsecret, _env, accounts = kis_credentials()
    if not (appkey and appsecret and accounts):
        return
    if not kst_auto_sync_due(now_kst, _last_ok(c, "kis_sync_jobs"), AUTO_HOURS):
        return
    for uid in users_for_autosync(c, KIS_INSTITUTION):
        _enqueue_if_idle(
            c,
            "kis_sync_jobs",
            uid,
            f"auto-queued kis sync for {uid} (KST {AUTO_HOURS})",
        )


def _enqueue_if_idle(c, table: str, uid: str, log: str) -> None:
    pending = (
        c.table(table)
        .select("id")
        .eq("user_id", uid)
        .in_("status", ["queued", "running"])
        .limit(1)
        .execute()
        .data
        or []
    )
    if pending:
        return
    c.table(table).insert({"user_id": uid, "status": "queued"}).execute()
    print(log, flush=True)


def heartbeat(c) -> str:
    ip = public_ip()
    c.rpc("touch_toss_sync_worker", {"p_ip": ip}).execute()
    return ip


def claim(c, rpc: str):
    res = c.rpc(rpc).execute()
    data = res.data
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


def finish(c, table: str, job_id: str, *, status: str, error: str | None, result: dict | None) -> None:
    c.table(table).update(
        {
            "status": status,
            "error": error,
            "result": result,
            "finished_at": utcnow(),
        }
    ).eq("id", job_id).execute()


def loop() -> None:
    c = supabase()
    ip = heartbeat(c)
    print(
        f"broker-sync worker up. public IP={ip} (Toss WTS + KIS Developers allow-list)",
        flush=True,
    )
    while True:
        try:
            heartbeat(c)
            maybe_enqueue_auto(c)
            job = claim(c, "claim_toss_sync_job")
            kind = "toss"
            table = "toss_sync_jobs"
            runner = run_sync
            if not job or not job.get("id"):
                try:
                    job = claim(c, "claim_kis_sync_job")
                except Exception as exc:
                    print(f"kis claim skip: {exc}", flush=True)
                    job = None
                kind = "kis"
                table = "kis_sync_jobs"
                runner = run_kis_sync
            if not job or not job.get("id"):
                time.sleep(5)
                continue
            job_id = job["id"]
            user_id = job["user_id"]
            print(f"claimed {kind} {job_id} user={user_id}", flush=True)
            try:
                result = runner(user_id=user_id)
                finish(c, table, job_id, status="ok", error=None, result=result)
                print(f"ok {kind} {job_id} {result}", flush=True)
            except Exception as exc:
                finish(
                    c,
                    table,
                    job_id,
                    status="error",
                    error=str(exc)[:800],
                    result=None,
                )
                print(f"error {kind} {job_id}: {exc}", flush=True)
                traceback.print_exc()
        except Exception as exc:
            print(f"worker loop: {exc}", flush=True)
            traceback.print_exc()
            time.sleep(8)


if __name__ == "__main__":
    maybe_self_update()
    loop()
