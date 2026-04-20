# Telegram Custom Reply

## Overview
Python FastAPI web dashboard for Telegram custom auto-replies. The main app is served from `main.py` with Jinja templates in `templates/` and static styles in `static/`.

## Runtime
- Development workflow runs `uvicorn main:app --host 0.0.0.0 --port 5000`.
- Production deployment is configured to run the same FastAPI app with Uvicorn.
- Telegram functionality uses Pyrogram and requires `API_ID` and `API_HASH` environment variables, with `config.json` as a legacy fallback.

## Notes
- The root route redirects unauthenticated users to `/login`.
- The app starts even when Telegram credentials are missing, showing a setup message instead of crashing.