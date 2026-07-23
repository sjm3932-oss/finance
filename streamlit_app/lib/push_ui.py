"""Push subscription widget (embedded in 자산 챗)."""

from __future__ import annotations

import json
import os

import streamlit as st
import streamlit.components.v1 as components

from lib.supabase_client import SUPABASE_URL


def render_push_subscribe(*, user_id: str, access_token: str) -> None:
    vapid = os.getenv("VAPID_PUBLIC_KEY", "")
    if not vapid:
        st.caption("푸시 키가 없어 구독을 생략합니다. (VAPID_PUBLIC_KEY)")
        return

    sw_url = "/app/static/sw.js"
    html = f"""
<!DOCTYPE html>
<html><body style="font-family:Pretendard,sans-serif;padding:4px;margin:0;background:transparent;">
<button id="btn" style="width:100%;min-height:44px;font-size:15px;font-weight:700;border:none;border-radius:14px;color:#fff;background:linear-gradient(180deg,#03C75A,#02B350);cursor:pointer;">알림 구독</button>
<pre id="out" style="white-space:pre-wrap;font-size:12px;color:#6B7280;"></pre>
<script>
const vapidPublicKey = {json.dumps(vapid)};
const accessToken = {json.dumps(access_token)};
const supabaseUrl = {json.dumps(SUPABASE_URL)};
const userId = {json.dumps(user_id)};
const anonKey = {json.dumps(os.getenv("SUPABASE_ANON_KEY", ""))};
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
      throw new Error('이 브라우저는 웹 푸시를 지원하지 않습니다');
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
        'apikey': anonKey,
        'Authorization': 'Bearer ' + accessToken,
        'Prefer': 'resolution=merge-duplicates'
      }},
      body: JSON.stringify(row)
    }});
    out.textContent = '상태 ' + res.status + '\\n' + (await res.text());
  }} catch (e) {{
    out.textContent = String(e);
  }}
}}
document.getElementById('btn').onclick = subscribe;
</script>
</body></html>
"""
    components.html(html, height=140)
