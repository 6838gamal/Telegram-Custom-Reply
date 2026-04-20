import os
import secrets
import asyncio
import json
from datetime import datetime
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(32)
EXPIRE_MINUTES = 120
MAX_ITEMS = 10
STATE_FILE = "app_state.json"
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="telegram-control-center")


def default_state():
    return {
        "api_id": None,
        "api_hash": "",
        "auto_reply_rules": [],
        "broadcast_presets": []
    }


def load_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_state():
    state = default_state()
    saved = load_json_file(STATE_FILE)
    state.update({key: saved.get(key, value) for key, value in state.items()})
    return state


def save_state():
    temp_path = f"{STATE_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, STATE_FILE)


def load_config():
    return load_json_file("config.json")


state = load_state()
config = load_config()
api_id_value = os.getenv("API_ID") or state.get("api_id") or config.get("api_id")
API_ID = int(api_id_value) if api_id_value else None
API_HASH = os.getenv("API_HASH") or state.get("api_hash") or config.get("api_hash") or ""
TELEGRAM_READY = bool(API_ID and API_HASH)
auth_data = {}
telegram = None
telegram_lock = asyncio.Lock()


def create_token():
    return serializer.dumps({"auth": True, "created_at": datetime.utcnow().isoformat()})


def verify_token(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401)

    try:
        payload = serializer.loads(token, max_age=EXPIRE_MINUTES * 60)
        if not payload.get("auth"):
            raise HTTPException(status_code=401)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401)


def format_error(error):
    message = str(error).strip()
    return message or "The request could not be completed. Please try again."


def with_notice(path, status, message):
    return f"{path}?{urlencode({'status': status, 'message': message})}"


def redirect_with_notice(status, message):
    return RedirectResponse(with_notice("/", status, message), status_code=303)


def login_notice_redirect(status, message):
    return RedirectResponse(with_notice("/login", status, message), status_code=303)


def is_https_request(request: Request):
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def dashboard_redirect(request: Request):
    token = create_token()
    response = RedirectResponse(with_notice("/", "success", "Signed in successfully."), status_code=303)
    response.set_cookie(
        "token",
        token,
        httponly=True,
        samesite="lax",
        secure=is_https_request(request),
        max_age=EXPIRE_MINUTES * 60
    )
    return response


def parse_chat_value(value):
    chat_id, chat_type, chat_name = value.split("|", 2)
    return {"id": int(chat_id), "type": chat_type or "private", "name": chat_name or "Unnamed chat"}


def unique_chats(chats):
    seen = set()
    result = []
    for chat in chats:
        try:
            chat_id = int(chat.get("id"))
        except Exception:
            continue
        if chat_id in seen:
            continue
        seen.add(chat_id)
        result.append({
            "id": chat_id,
            "type": chat.get("type") or "private",
            "name": chat.get("name") or "Unnamed chat"
        })
    return result[:100]


def collect_saved_chats():
    chats = []
    for rule in state.get("auto_reply_rules", []):
        chats.extend(rule.get("chats", []))
    for preset in state.get("broadcast_presets", []):
        chats.extend(preset.get("chats", []))
    return unique_chats(chats)


def selected_chat_ids(chats):
    ids = []
    for chat in chats:
        try:
            ids.append(int(chat.get("id")))
        except Exception:
            continue
    return ids


def find_auto_reply(text, chat_id):
    lowered = text.lower()
    for rule in state.get("auto_reply_rules", []):
        keyword = (rule.get("keyword") or "").strip().lower()
        reply = (rule.get("reply") or "").strip()
        target_ids = selected_chat_ids(rule.get("chats", []))
        if keyword and reply and keyword in lowered and (not target_ids or chat_id in target_ids):
            return reply
    return None


def attach_telegram_handlers(client):
    @client.on_message(filters.text)
    async def handler(_, message):
        try:
            if not message.text:
                return
            reply = find_auto_reply(message.text, message.chat.id)
            if reply:
                await message.reply(reply)
        except Exception:
            return


def build_telegram_client(api_id, api_hash):
    if not api_id or not api_hash:
        return None
    client = Client("my_account", api_id=int(api_id), api_hash=api_hash, in_memory=True)
    attach_telegram_handlers(client)
    return client


telegram = build_telegram_client(API_ID, API_HASH)


async def configure_telegram_client(api_id, api_hash):
    global API_ID, API_HASH, TELEGRAM_READY, telegram

    async with telegram_lock:
        if telegram is not None and getattr(telegram, "is_connected", False):
            try:
                await telegram.disconnect()
            except Exception:
                pass

        API_ID = int(api_id)
        API_HASH = api_hash
        TELEGRAM_READY = bool(API_ID and API_HASH)
        telegram = build_telegram_client(API_ID, API_HASH)
        auth_data.clear()


def telegram_required():
    if telegram is None:
        raise HTTPException(
            status_code=503,
            detail="Telegram API credentials are not saved yet. Enter API ID and API Hash first."
        )


async def ensure_telegram_connected():
    telegram_required()

    async with telegram_lock:
        if getattr(telegram, "is_connected", False):
            return

        try:
            await telegram.connect()
        except ConnectionError as error:
            if "already connected" not in str(error).lower():
                raise


async def ensure_telegram_initialized():
    await ensure_telegram_connected()

    if getattr(telegram, "is_initialized", False):
        return

    try:
        await telegram.initialize()
    except ConnectionError as error:
        if "already initialized" not in str(error).lower():
            raise


def login_response(request: Request, step: str, error: str | None = None, success: str | None = None, status_code: int = 200):
    status = request.query_params.get("status")
    message = request.query_params.get("message")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "step": step,
            "telegram_ready": TELEGRAM_READY,
            "api_id": API_ID,
            "error": error,
            "success": success,
            "notice": {
                "status": status,
                "message": message
            } if status and message else None
        },
        status_code=status_code
    )


@app.get("/login")
async def login(request: Request):
    return login_response(request, "phone")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/setup_api")
async def setup_api(request: Request, api_id: str = Form(...), api_hash: str = Form(...)):
    if TELEGRAM_READY:
        verify_token(request)

    clean_id = api_id.strip()
    clean_hash = api_hash.strip()

    if not clean_id.isdigit() or not clean_hash:
        return login_response(request, "phone", "Enter a numeric API ID and a valid API Hash.", status_code=200)

    state["api_id"] = int(clean_id)
    state["api_hash"] = clean_hash
    save_state()
    await configure_telegram_client(state["api_id"], state["api_hash"])
    return login_notice_redirect("success", "Telegram API credentials were saved. You can now sign in with your phone number.")


@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    if telegram is None:
        return login_response(
            request,
            "phone",
            "Enter API ID and API Hash before signing in.",
            status_code=503
        )

    try:
        clean_phone = phone.strip()
        if not clean_phone:
            return login_response(request, "phone", "Enter the phone number with the country code.")

        await ensure_telegram_connected()
        sent = await telegram.send_code(clean_phone)
        auth_data["phone"] = clean_phone
        auth_data["hash"] = sent.phone_code_hash
        return login_response(request, "code", success="Verification code sent successfully.")
    except PhoneNumberInvalid:
        return login_response(request, "phone", "Invalid phone number. Use international format, for example +966...")
    except FloodWait as error:
        return login_response(request, "phone", f"Telegram rate limit reached. Try again in {error.value} seconds.")
    except Exception as error:
        return login_response(request, "phone", format_error(error), status_code=200)


@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    try:
        clean_code = code.strip()
        if not clean_code:
            return login_response(request, "code", "Enter the verification code.")

        await ensure_telegram_connected()

        if not auth_data.get("phone") or not auth_data.get("hash"):
            return login_response(request, "phone", "Start by sending the verification code to the phone number.")

        await telegram.sign_in(
            auth_data["phone"],
            auth_data["hash"],
            clean_code
        )

        await ensure_telegram_initialized()
        return dashboard_redirect(request)
    except SessionPasswordNeeded:
        return login_response(request, "password", "This account requires a two-step verification password.")
    except PhoneCodeInvalid:
        return login_response(request, "code", "The verification code is incorrect.")
    except PhoneCodeExpired:
        auth_data.clear()
        return login_response(request, "phone", "The verification code expired. Send a new code.")
    except FloodWait as error:
        return login_response(request, "code", f"Telegram rate limit reached. Try again in {error.value} seconds.")
    except Exception as error:
        return login_response(request, "code", format_error(error), status_code=200)


@app.post("/password")
async def verify_password(request: Request, password: str = Form(...)):
    try:
        clean_password = password.strip()
        if not clean_password:
            return login_response(request, "password", "Enter the two-step verification password.")

        await ensure_telegram_connected()
        await telegram.check_password(clean_password)
        await ensure_telegram_initialized()
        return dashboard_redirect(request)
    except FloodWait as error:
        return login_response(request, "password", f"Telegram rate limit reached. Try again in {error.value} seconds.")
    except Exception as error:
        return login_response(request, "password", format_error(error), status_code=200)


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("token")
    return response


@app.get("/")
async def dashboard(request: Request):
    try:
        verify_token(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    auto_reply_rules = state.get("auto_reply_rules", [])[:MAX_ITEMS]
    broadcast_presets = state.get("broadcast_presets", [])[:MAX_ITEMS]
    saved_chats = collect_saved_chats()
    status = request.query_params.get("status")
    message = request.query_params.get("message")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "api_id": API_ID,
            "telegram_ready": TELEGRAM_READY,
            "auto_reply_rules": auto_reply_rules,
            "broadcast_presets": broadcast_presets,
            "available_chats": saved_chats,
            "stats": {
                "rules": len(auto_reply_rules),
                "presets": len(broadcast_presets),
                "saved_chats": len(saved_chats),
                "telegram": "Ready" if TELEGRAM_READY else "Incomplete"
            },
            "notice": {
                "status": status,
                "message": message
            } if status and message else None
        }
    )


@app.get("/load_chats")
async def load_chats(request: Request):
    verify_token(request)

    try:
        await ensure_telegram_initialized()
        chats = []

        async for dialog in telegram.get_dialogs():
            chat = dialog.chat
            raw_type = str(chat.type).lower()
            chat_type = "group" if "group" in raw_type or "channel" in raw_type else "private"

            chats.append({
                "id": chat.id,
                "name": chat.title or chat.first_name or "Private chat",
                "type": chat_type
            })

            if len(chats) >= 100:
                break

        return {"ok": True, "chats": unique_chats(chats + collect_saved_chats()), "message": f"Loaded {len(chats)} chats successfully."}
    except HTTPException as error:
        return JSONResponse({"ok": False, "chats": [], "message": error.detail}, status_code=200)
    except FloodWait as error:
        return JSONResponse({"ok": False, "chats": [], "message": f"Telegram rate limit reached. Try again in {error.value} seconds."}, status_code=200)
    except Exception as error:
        return JSONResponse({"ok": False, "chats": [], "message": format_error(error)}, status_code=200)


@app.post("/dashboard_api")
async def dashboard_api(request: Request, api_id: str = Form(...), api_hash: str = Form(...)):
    verify_token(request)
    clean_id = api_id.strip()
    clean_hash = api_hash.strip()

    if not clean_id.isdigit() or not clean_hash:
        return redirect_with_notice("error", "Enter a numeric API ID and a valid API Hash.")

    state["api_id"] = int(clean_id)
    state["api_hash"] = clean_hash
    save_state()
    await configure_telegram_client(state["api_id"], state["api_hash"])
    return redirect_with_notice("success", "Telegram API credentials were updated.")


@app.post("/auto_replies")
async def save_auto_replies(request: Request):
    verify_token(request)
    form = await request.form()
    keywords = form.getlist("rule_keyword")
    replies = form.getlist("rule_reply")
    rules = []

    for index, keyword in enumerate(keywords[:MAX_ITEMS]):
        clean_keyword = keyword.strip()
        clean_reply = replies[index].strip() if index < len(replies) else ""
        chats = []
        for raw_chat in form.getlist(f"rule_chats_{index}"):
            try:
                chats.append(parse_chat_value(raw_chat))
            except Exception:
                continue

        if clean_keyword and clean_reply:
            rules.append({
                "keyword": clean_keyword,
                "reply": clean_reply,
                "chats": unique_chats(chats)[:MAX_ITEMS]
            })

    state["auto_reply_rules"] = rules[:MAX_ITEMS]
    save_state()
    return redirect_with_notice("success", f"Saved {len(state['auto_reply_rules'])} auto-reply rules.")


@app.post("/broadcast_presets")
async def save_broadcast_presets(request: Request):
    verify_token(request)
    form = await request.form()
    titles = form.getlist("preset_title")
    messages = form.getlist("preset_message")
    presets = []

    for index, title in enumerate(titles[:MAX_ITEMS]):
        clean_title = title.strip() or f"Broadcast {index + 1}"
        clean_message = messages[index].strip() if index < len(messages) else ""
        chats = []
        for raw_chat in form.getlist(f"preset_chats_{index}"):
            try:
                chats.append(parse_chat_value(raw_chat))
            except Exception:
                continue

        if clean_message:
            presets.append({
                "title": clean_title,
                "message": clean_message,
                "chats": unique_chats(chats)[:MAX_ITEMS]
            })

    state["broadcast_presets"] = presets[:MAX_ITEMS]
    save_state()
    return redirect_with_notice("success", f"Saved {len(state['broadcast_presets'])} broadcast presets.")


@app.post("/broadcast_preset/{preset_index}")
async def broadcast_preset(request: Request, preset_index: int):
    verify_token(request)
    presets = state.get("broadcast_presets", [])

    if preset_index < 0 or preset_index >= len(presets):
        return redirect_with_notice("error", "Broadcast preset was not found.")

    preset = presets[preset_index]
    message = (preset.get("message") or "").strip()
    targets = unique_chats(preset.get("chats", []))[:MAX_ITEMS]

    if not message:
        return redirect_with_notice("error", "Broadcast message is empty.")

    if not targets:
        return redirect_with_notice("warning", "Select at least one chat for this broadcast before sending.")

    try:
        await ensure_telegram_initialized()
    except Exception as error:
        return redirect_with_notice("error", f"Broadcast was not sent because Telegram is not ready: {format_error(error)}")

    sent = 0
    failed = []

    for target in targets:
        try:
            await telegram.send_message(target["id"], message)
            sent += 1
        except FloodWait as error:
            failed.append(f"{target.get('name', target['id'])}: wait {error.value} seconds")
        except Exception as error:
            failed.append(f"{target.get('name', target['id'])}: {format_error(error)}")

    if failed and sent:
        return redirect_with_notice("warning", f"Sent to {sent} chats, failed for {len(failed)}: {'; '.join(failed[:3])}")

    if failed:
        return redirect_with_notice("error", f"Broadcast failed: {'; '.join(failed[:3])}")

    return redirect_with_notice("success", f"Broadcast sent successfully to {sent} chats.")
