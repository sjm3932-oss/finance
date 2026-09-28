# Deprecated. Production is Next.js on Vercel (web/).
# Do not deploy this image for mobile/OAuth use.
FROM busybox:1.36
CMD ["sh", "-c", "echo 'Use https://richddoong.vercel.app (Vercel web/). Streamlit Docker deploy is removed.' >&2; exit 1"]
