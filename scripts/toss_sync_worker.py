#!/usr/bin/env python3
"""Cloud worker: claim queued Toss sync jobs and run Open API from this host.

This process must run on a cloud VM with a *static* public IP. Register that
IP once in Toss WTS → Open API → 허용 IP. Do not run this on a laptop.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sync_toss import public_ip, run_sync, supabase  # noqa: E402
from toss_client import INSTITUTION  # noqa: E402

# 0 disables automatic enqueue. The in-app 지금 동기화 button still works.
AUTO_EVERY = int(os.getenv("TOSS_AUTO_SYNC_SECONDS", str(6 * 3600)))
_last_auto_check = 0.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def users_for_autosync(c) -> list[str]:
    rows = (
        c.table("accounts")
        .select("user_id")
        .eq("institution", INSTITUTION)
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


def maybe_enqueue_auto(c) -> None:
    global _last_auto_check
    if AUTO_EVERY <= 0:
        return
    now = time.time()
    if now - _last_auto_check < 60:
        return
    _last_auto_check = now
    last = (
        c.table("toss_sync_jobs")
        .select("finished_at")
        .eq("status", "ok")
        .order("finished_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    ts = _parse_ts(last[0].get("finished_at") if last else None)
    if ts is not None and now - ts < AUTO_EVERY:
        return
    for uid in users_for_autosync(c):
        pending = (
            c.table("toss_sync_jobs")
            .select("id")
            .eq("user_id", uid)
            .in_("status", ["queued", "running"])
            .limit(1)
            .execute()
            .data
            or []
        )
        if pending:
            continue
        c.table("toss_sync_jobs").insert({"user_id": uid, "status": "queued"}).execute()
        print(f"auto-queued toss sync for {uid}", flush=True)


def heartbeat(c) -> str:
    ip = public_ip()
    c.rpc("touch_toss_sync_worker", {"p_ip": ip}).execute()
    return ip


def claim(c):
    res = c.rpc("claim_toss_sync_job").execute()
    data = res.data
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


def finish(c, job_id: str, *, status: str, error: str | None, result: dict | None) -> None:
    c.table("toss_sync_jobs").update(
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
    print(f"toss-sync worker up. public IP={ip} (register this in Toss WTS)", flush=True)
    while True:
        try:
            heartbeat(c)
            maybe_enqueue_auto(c)
            job = claim(c)
            if not job or not job.get("id"):
                time.sleep(5)
                continue
            job_id = job["id"]
            user_id = job["user_id"]
            print(f"claimed {job_id} user={user_id}", flush=True)
            try:
                result = run_sync(user_id=user_id)
                finish(c, job_id, status="ok", error=None, result=result)
                print(f"ok {job_id} {result}", flush=True)
            except Exception as exc:
                finish(
                    c,
                    job_id,
                    status="error",
                    error=str(exc)[:800],
                    result=None,
                )
                print(f"error {job_id}: {exc}", flush=True)
                traceback.print_exc()
        except Exception as exc:
            print(f"worker loop: {exc}", flush=True)
            traceback.print_exc()
            time.sleep(8)


if __name__ == "__main__":
    loop()
