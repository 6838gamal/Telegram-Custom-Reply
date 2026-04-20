# Telegram Custom Reply

## Overview
Python FastAPI web dashboard for Telegram custom auto-replies. The main app is served from `main.py` with Arabic Jinja templates in `templates/` and responsive styles in `static/`.

## Runtime
- Development workflow runs `uvicorn main:app --host 0.0.0.0 --port 5000`.
- Production deployment is configured to run the same FastAPI app with Uvicorn.
- Telegram functionality uses Pyrogram.
- Users can enter `API_ID` and `API_HASH` from the login screen before signing in, or update them later from the dashboard.
- Runtime settings are saved in `app_state.json`, which is ignored by Git. Environment variables `API_ID` and `API_HASH` still take priority when present.

## Current Features
- Arabic right-to-left login and dashboard UI.
- API setup screen for first-time Telegram configuration.
- Dashboard API settings section.
- Auto-reply rules: up to 10 saved rules, each with a keyword/phrase, custom reply message, and selected chats.
- Broadcast presets: up to 10 saved broadcast configurations, each with a title, message, and selected chats, with a send action for saved presets.
- Telegram chat loading populates reusable chat choices for auto-replies and broadcast presets.
- Layout is responsive for small mobile screens.

## Security Notes
- Dashboard actions that read Telegram chats, save rules, save broadcast presets, update API settings, or send broadcasts require the signed-in cookie.
- Session cookies are HTTP-only, same-site, and marked secure when served over HTTPS.
- `SECRET_KEY` should be provided as an environment variable for stable login sessions across restarts; otherwise the app generates a process-local key.
- Python virtual-package folders, Telegram session files, bytecode caches, `.env` files, and `app_state.json` are ignored by Git.

## Notes
- The root route redirects unauthenticated users to `/login`.
- The app starts even when Telegram credentials are missing, showing an API setup form instead of crashing.
- Telegram login safely reuses an existing Pyrogram connection, handles invalid/expired codes, rate-limit waits, and two-step password verification before redirecting to the dashboard.
- Telegram-dependent actions catch failures and report them to the user instead of returning server errors when possible.
