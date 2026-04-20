# Telegram Custom Reply

## Overview
Python FastAPI web dashboard for Telegram custom auto-replies. The main app is served from `main.py` with Jinja templates in `templates/` and static styles in `static/`.

## Runtime
- Development workflow runs `uvicorn main:app --host 0.0.0.0 --port 5000`.
- Production deployment is configured to run the same FastAPI app with Uvicorn.
- Telegram functionality uses Pyrogram and requires `API_ID` and `API_HASH` environment variables. `config.json` remains only as a legacy fallback and no longer stores credential values.

## Security Notes
- Dashboard actions that read Telegram chats, save rules, save chat targets, or broadcast messages require the signed-in cookie.
- Session cookies are HTTP-only, same-site, and marked secure when served over HTTPS.
- `SECRET_KEY` should be provided as an environment variable for stable login sessions across restarts; otherwise the app generates a process-local key.
- Python virtual-package folders, Telegram session files, bytecode caches, and `.env` files are ignored by Git.

## Notes
- The root route redirects unauthenticated users to `/login`.
- The app starts even when Telegram credentials are missing, showing a setup message instead of crashing.
- Telegram login safely reuses an existing Pyrogram connection, handles invalid/expired codes, rate-limit waits, and two-step password verification before redirecting to the dashboard.
- The UI is English-only and includes a professional dashboard with success, warning, and error feedback for keyword saves, chat loading, chat target saves, and broadcasts.
- Telegram-dependent actions catch failures and report them to the user instead of returning server errors when possible.
