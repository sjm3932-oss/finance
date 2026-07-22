"""Page: Web Push subscription + manual briefing/backup triggers."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.auth import ensure_profile, require_auth  # noqa: E402
from lib.supabase_client import PUBLIC_APP_URL, SUPABASE_URL, get_service_client  # noqa: E402
from lib.ui_ko import rename_columns  # noqa: E402

st.set_page_config(page_title="알림·작업", layout="wide")

VAPID_PUBLIC = os.getenv("VAPID_PUBLIC_KEY", "")


def _invoke(name: str, token: str) -> dict:
    url = f"{SUPABASE_URL}/functions/v1/{name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": os.getenv("SUPABASE_ANON_KEY", ""),
        "Content-Type": "application/json",
    }
    # Prefer service role for cron-equivalent manual runs
    try:
        svc = get_service_client()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        headers["Authorization"] = f"Bearer {key}"
        headers["apikey"] = key
    except Exception:
        pass
    r = httpx.post(url, headers=headers, json={}, timeout=120.0)
    try:
        return {"status": r.status_code, "body": r.json()}
    except Exception:
        return {"status": r.status_code, "body": r.text}


def main() -> None:
    st.title("알림·작업")
    st.caption("Web Push 구독 · 아침 브리핑/시세/백업 수동 실행")

    user, client = require_auth()
    ensure_profile(user, client)
    access = st.session_state.get("access_token") or ""

    st.subheader("푸시 구독")
    if not VAPID_PUBLIC:
        st.error("VAPID_PUBLIC_KEY가 없습니다. `.env`를 확인하세요.")
    else:
        st.write("모바일 브라우저에서 알림을 허용한 뒤 아래 버튼으로 구독하세요.")
        # Static SW is served when enableStaticServing=true → /app/static/sw.js
        sw_url = "/app/static/sw.js"
        html = f"""
<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:8px;">
<button id="btn" style="width:100%;min-height:48px;font-size:16px;">알림 구독</button>
<pre id="out" style="white-space:pre-wrap;font-size:12px;"></pre>
<script>
const vapidPublicKey = {json.dumps(VAPID_PUBLIC)};
const accessToken = {json.dumps(access)};
const supabaseUrl = {json.dumps(SUPABASE_URL)};
const userId = {json.dumps(str(user.id))};
function urlBase64ToUint8Array(base64String) {{
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}}
async function subscribe() {{
  const out = document.getElementById('out');
  try {{
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {{
      throw new Error('이 브라우저는 Web Push를 지원하지 않습니다');
    }}
    const reg = await navigator.serviceWorker.register('{sw_url}', {{ scope: '/app/' }});
    await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {{
      sub = await reg.pushManager.subscribe({{
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
      }});
    }}
    const json = sub.toJSON();
    const row = {{
      user_id: userId,
      endpoint: json.endpoint,
      p256dh_key: json.keys.p256dh,
      auth_key: json.keys.auth
    }};
    const res = await fetch(supabaseUrl + '/rest/v1/push_subscriptions', {{
      method: 'POST',
      headers: {{
        'Content-Type': 'application/json',
        'apikey': {json.dumps(os.getenv("SUPABASE_ANON_KEY", ""))},
        'Authorization': 'Bearer ' + accessToken,
        'Prefer': 'resolution=merge-duplicates'
      }},
      body: JSON.stringify(row)
    }});
    const text = await res.text();
    out.textContent = '상태 ' + res.status + '\\n' + text;
  }} catch (e) {{
    out.textContent = String(e);
  }}
}}
document.getElementById('btn').onclick = subscribe;
</script>
</body></html>
"""
        components.html(html, height=160)

    subs = (
        client.table("push_subscriptions")
        .select("id,endpoint,created_at,user_id")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    st.write(f"등록된 구독: **{len(subs)}**")
    if subs:
        st.dataframe(
            rename_columns(
                pd.DataFrame(
                    [
                        {
                            "id": s["id"][:8],
                            "endpoint": s["endpoint"][:48] + "…",
                            "created_at": s["created_at"],
                        }
                        for s in subs
                    ]
                )
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("수동 실행 (cron 대체 테스트)")
    c1, c2, c3 = st.columns(3)
    if c1.button("시세 갱신"):
        st.json(_invoke("refresh-prices", access))
    if c2.button("아침 브리핑 + 푸시", type="primary"):
        st.json(_invoke("morning-briefing", access))
    if c3.button("야간 백업"):
        st.json(_invoke("nightly-backup", access))

    # Snapshot now
    if st.button("오늘 스냅샷 계산"):
        try:
            row = client.rpc("compute_daily_snapshot").execute().data
            st.success(row)
        except Exception as exc:
            # fallback service
            try:
                row = get_service_client().rpc("compute_daily_snapshot").execute().data
                st.success(row)
            except Exception as exc2:
                st.error(f"{exc} / {exc2}")

    snaps = (
        client.table("daily_snapshots")
        .select("*")
        .order("snapshot_date", desc=True)
        .limit(14)
        .execute()
        .data
        or []
    )
    st.subheader("최근 스냅샷")
    st.dataframe(rename_columns(pd.DataFrame(snaps)), use_container_width=True, hide_index=True)

    st.caption(f"PUBLIC_APP_URL={PUBLIC_APP_URL}")


main()
