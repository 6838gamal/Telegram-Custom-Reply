import os
import asyncio
import json
from datetime import datetime, timedelta
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

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
EXPIRE_MINUTES = 120
MAX_ITEMS = 10
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="telegram-control-center")


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


def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


config = load_config()
api_id_value = os.getenv("API_ID") or config.get("api_id")
API_ID = int(api_id_value) if api_id_value else None
API_HASH = os.getenv("API_HASH") or config.get("api_hash")
TELEGRAM_READY = bool(API_ID and API_HASH)

keywords = []
chat_settings = {"groups": [], "private": []}
broadcast_message = "Hello"
auth_data = {}
telegram = None
telegram_lock = asyncio.Lock()

if TELEGRAM_READY:
    telegram = Client(
        "my_account",
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True
    )


def telegram_required():
    if telegram is None:
        raise HTTPException(
            status_code=503,
            detail="Telegram API credentials are not configured."
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


def format_error(error):
    message = str(error).strip()
    return message or "The request could not be completed. Please try again."


def with_notice(path, status, message):
    return f"{path}?{urlencode({'status': status, 'message': message})}"


def redirect_with_notice(status, message):
    return RedirectResponse(with_notice("/", status, message), status_code=303)


def login_response(request: Request, step: str, error: str | None = None, success: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "step": step,
            "telegram_ready": TELEGRAM_READY,
            "error": error,
            "success": success
        },
        status_code=status_code
    )


def dashboard_redirect():
    token = create_token()
    response = RedirectResponse(with_notice("/", "success", "You are signed in successfully."), status_code=303)
    response.set_cookie(
        "token",
        token,
        httponly=True,
        samesite="lax",
        max_age=EXPIRE_MINUTES * 60
    )
    return response


def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)


if telegram is not None:
    @telegram.on_message(filters.text)
    async def handler(_, message):
        try:
            if not message.text:
                return

            if not match_keyword(message.text.lower()):
                return

            chat_id = message.chat.id
            reply_type = "default"

            for group in chat_settings["groups"]:
                if group["id"] == chat_id:
                    reply_type = "group"

            for private_chat in chat_settings["private"]:
                if private_chat["id"] == chat_id:
                    reply_type = "private"

            if reply_type == "group":
                await message.reply("Group auto reply is active for this chat.")
            elif reply_type == "private":
                await message.reply("Private auto reply is active for this chat.")
            else:
                await message.reply("Default auto reply is active.")
        except Exception:
            return


@app.get("/login")
async def login(request: Request):
    return login_response(request, "phone")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    if telegram is None:
        return login_response(
            request,
            "phone",
            "Telegram API credentials are not configured. Add API_ID and API_HASH before signing in.",
            status_code=503
        )

    try:
        clean_phone = phone.strip()
        if not clean_phone:
            return login_response(request, "phone", "Enter a phone number with the country code.")

        await ensure_telegram_connected()
        sent = await telegram.send_code(clean_phone)
        auth_data["phone"] = clean_phone
        auth_data["hash"] = sent.phone_code_hash
        return login_response(request, "code", success="Verification code sent successfully.")
    except PhoneNumberInvalid:
        return login_response(request, "phone", "Invalid phone number. Use the international format, for example +966...")
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
            return login_response(request, "phone", "Start by sending the verification code to your phone number.")

        await telegram.sign_in(
            auth_data["phone"],
            auth_data["hash"],
            clean_code
        )

        await ensure_telegram_initialized()
        return dashboard_redirect()
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
            return login_response(request, "password", "Enter your two-step verification password.")

        await ensure_telegram_connected()
        await telegram.check_password(clean_password)
        await ensure_telegram_initialized()
        return dashboard_redirect()
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

    selected_chats = chat_settings["groups"] + chat_settings["private"]
    status = request.query_params.get("status")
    message = request.query_params.get("message")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "keywords": keywords,
            "chat_settings": chat_settings,
            "broadcast_message": broadcast_message,
            "selected_chats": selected_chats,
            "telegram_ready": TELEGRAM_READY,
            "stats": {
                "keywords": len(keywords),
                "groups": len(chat_settings["groups"]),
                "private": len(chat_settings["private"]),
                "total_chats": len(selected_chats)
            },
            "notice": {
                "status": status,
                "message": message
            } if status and message else None
        }
    )


@app.get("/load_chats")
async def load_chats():
    try:
        await ensure_telegram_initialized()
        chats = []

        async for dialog in telegram.get_dialogs():
            chat = dialog.chat
            raw_type = str(chat.type).lower()
            chat_type = "group" if "group" in raw_type or "channel" in raw_type else "private"

            chats.append({
                "id": chat.id,
                "name": chat.title or chat.first_name or "Private Chat",
                "type": chat_type
            })

            if len(chats) >= 50:
                break

        return {"ok": True, "chats": chats, "message": f"Loaded {len(chats)} chats successfully."}
    except HTTPException as error:
        return JSONResponse({"ok": False, "chats": [], "message": error.detail}, status_code=200)
    except FloodWait as error:
        return JSONResponse({"ok": False, "chats": [], "message": f"Telegram rate limit reached. Try again in {error.value} seconds."}, status_code=200)
    except Exception as error:
        return JSONResponse({"ok": False, "chats": [], "message": format_error(error)}, status_code=200)


@app.post("/keywords")
async def save_keywords(keywords_form: list[str] = Form(default=[], alias="keywords")):
    global keywords

    cleaned = []
    for keyword in keywords_form:
        value = keyword.strip()
        if value and value.lower() not in [item.lower() for item in cleaned]:
            cleaned.append(value)

    keywords = cleaned[:MAX_ITEMS]
    return redirect_with_notice("success", f"Saved {len(keywords)} keyword rules.")


@app.post("/save_chats")
async def save_chats(selected_chats: list[str] = Form(default=[])):
    groups = []
    privates = []
    skipped = 0

    for item in selected_chats[:MAX_ITEMS]:
        try:
            chat_id, chat_type, chat_name = item.split("|", 2)
            record = {"id": int(chat_id), "name": chat_name or "Unnamed chat", "type": chat_type}

            if chat_type == "group":
                groups.append(record)
            else:
                privates.append(record)
        except Exception:
            skipped += 1

    chat_settings["groups"] = groups
    chat_settings["private"] = privates

    if skipped:
        return redirect_with_notice("warning", f"Saved {len(groups) + len(privates)} chats. {skipped} invalid selections were skipped.")

    return redirect_with_notice("success", f"Saved {len(groups) + len(privates)} selected chats.")


@app.post("/broadcast")
async def broadcast(message: str = Form(...)):
    global broadcast_message

    broadcast_message = message.strip()
    if not broadcast_message:
        return redirect_with_notice("error", "Broadcast message cannot be empty.")

    targets = (chat_settings["groups"] + chat_settings["private"])[:MAX_ITEMS]
    if not targets:
        return redirect_with_notice("warning", "No chats are selected. Load chats and save at least one target before broadcasting.")

    try:
        await ensure_telegram_initialized()
    except Exception as error:
        return redirect_with_notice("error", f"Broadcast was not sent because Telegram is not ready: {format_error(error)}")

    sent = 0
    failed = []

    for target in targets:
        try:
            await telegram.send_message(target["id"], broadcast_message)
            sent += 1
        except FloodWait as error:
            failed.append(f"{target.get('name', target['id'])}: rate limited for {error.value} seconds")
        except Exception as error:
            failed.append(f"{target.get('name', target['id'])}: {format_error(error)}")

    if failed and sent:
        return redirect_with_notice("warning", f"Sent to {sent} chats. Failed for {len(failed)} chats: {'; '.join(failed[:3])}")

    if failed:
        return redirect_with_notice("error", f"Broadcast failed for all selected chats: {'; '.join(failed[:3])}")

    return redirect_with_notice("success", f"Broadcast sent successfully to {sent} chats.")
