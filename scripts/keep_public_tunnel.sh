#!/usr/bin/env bash
# DEPRECATED — do not use for production access.
# Streamlit Community Cloud (*.streamlit.app) is the canonical host.
# This script previously published Pinggy/Cloudflare tunnels into
# app_runtime + Supabase Auth site_url and broke Google login.
echo "keep_public_tunnel.sh is disabled. Use https://richddoong.streamlit.app" >&2
exit 1
