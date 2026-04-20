import os
import asyncio
import json
import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
)

# =========================
# APP
# =========================
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# =========================
# JWT
# =========================
SECRET_KEY = "super-secret-key"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 120

def create_token():
    payload = {
        "auth": True,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(request: Request):
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401)

    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        raise HTTPException(status_code=401)

# =========================
# ENV
# =========================
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

# =========================
# DATA
# =========================
keywords = []
chat_settings = {"groups": [], "private": []}
broadcast_message = "Hello"

auth_data = {}

MAX_ITEMS = 10

# =========================
# TELEGRAM
# =========================
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
    if getattr(telegram, "is_initialized", False):
        return

    try:
        await telegram.initialize()
    except ConnectionError as error:
        if "already initialized" not in str(error).lower():
            raise

def login_response(request: Request, step: str, error: str | None = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "step": step,
            "telegram_ready": TELEGRAM_READY,
            "error": error
        },
        status_code=status_code
    )

def dashboard_redirect():
    token = create_token()
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "token",
        token,
        httponly=True,
        samesite="lax",
        max_age=EXPIRE_MINUTES * 60
    )
    return response

# =========================
# KEYWORD MATCH
# =========================
def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)

# =========================
# AUTO REPLY ENGINE
# =========================
if telegram is not None:
    @telegram.on_message(filters.text)
    async def handler(_, message):
        if not message.text:
            return

        if not match_keyword(message.text.lower()):
            return

        chat_id = message.chat.id

        reply_type = "default"

        for g in chat_settings["groups"]:
            if g["id"] == chat_id:
                reply_type = "group"

        for p in chat_settings["private"]:
            if p["id"] == chat_id:
                reply_type = "private"

        if reply_type == "group":
            await message.reply("📢 Group Auto Reply")

        elif reply_type == "private":
            await message.reply("💬 Private Auto Reply")

        else:
            await message.reply("✅ Default Reply")

# =========================
# LOGIN
# =========================
@app.get("/login")
async def login(request: Request):
    return login_response(request, "phone")

@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    if telegram is None:
        return login_response(
            request,
            "phone",
            "Telegram API credentials are not configured.",
            503
        )

    try:
        await ensure_telegram_connected()

        sent = await telegram.send_code(phone.strip())

        auth_data["phone"] = phone.strip()
        auth_data["hash"] = sent.phone_code_hash

        return login_response(request, "code")
    except PhoneNumberInvalid:
        return login_response(request, "phone", "رقم الجوال غير صحيح. اكتب الرقم مع رمز الدولة مثل +966...")
    except FloodWait as error:
        return login_response(request, "phone", f"تيليجرام طلب الانتظار {error.value} ثانية قبل المحاولة مرة أخرى.")
    except Exception as error:
        return login_response(request, "phone", str(error), 500)

@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    try:
        await ensure_telegram_connected()

        if not auth_data.get("phone") or not auth_data.get("hash"):
            return login_response(request, "phone", "ابدأ بإرسال رقم الجوال أولاً.")

        await telegram.sign_in(
            auth_data["phone"],
            auth_data["hash"],
            code.strip()
        )

        await ensure_telegram_initialized()
        return dashboard_redirect()
    except SessionPasswordNeeded:
        return login_response(request, "password", "الحساب يحتاج كلمة مرور التحقق بخطوتين.")
    except PhoneCodeInvalid:
        return login_response(request, "code", "كود التحقق غير صحيح.")
    except PhoneCodeExpired:
        auth_data.clear()
        return login_response(request, "phone", "انتهت صلاحية كود التحقق. أرسل الكود من جديد.")
    except FloodWait as error:
        return login_response(request, "code", f"تيليجرام طلب الانتظار {error.value} ثانية قبل المحاولة مرة أخرى.")
    except Exception as e:
        return login_response(request, "code", str(e), 500)

@app.post("/password")
async def verify_password(request: Request, password: str = Form(...)):
    try:
        await ensure_telegram_connected()
        await telegram.check_password(password.strip())
        await ensure_telegram_initialized()
        return dashboard_redirect()
    except FloodWait as error:
        return login_response(request, "password", f"تيليجرام طلب الانتظار {error.value} ثانية قبل المحاولة مرة أخرى.")
    except Exception as error:
        return login_response(request, "password", str(error), 500)

# =========================
# DASHBOARD (INGEST)
# =========================
@app.get("/")
async def dashboard(request: Request):
    try:
        verify_token(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "keywords": keywords,
            "chat_settings": chat_settings,
            "broadcast_message": broadcast_message
        }
    )

# =========================
# LOAD CHATS
# =========================
@app.get("/load_chats")
async def load_chats():
    telegram_required()

    chats = []

    async for d in telegram.get_dialogs():
        c = d.chat

        chats.append({
            "id": c.id,
            "name": c.title or c.first_name or "Private",
            "type": str(c.type)
        })

        if len(chats) >= 50:
            break

    return {"chats": chats}

# =========================
# KEYWORDS CRUD
# =========================
@app.post("/keywords")
async def save_keywords(keywords_form: list[str] = Form(default=[], alias="keywords")):
    global keywords

    keywords = [k.strip() for k in keywords_form if k.strip()][:MAX_ITEMS]

    return RedirectResponse("/", status_code=303)

# =========================
# SAVE CHATS
# =========================
@app.post("/save_chats")
async def save_chats(
    selected: list[str] = Form(...),
    types: list[str] = Form(...)
):

    groups = []
    privates = []

    for i in range(min(len(selected), MAX_ITEMS)):
        cid = int(selected[i])

        item = {"id": cid}

        if i < len(types) and types[i] == "group":
            groups.append(item)
        else:
            privates.append(item)

    chat_settings["groups"] = groups
    chat_settings["private"] = privates

    return RedirectResponse("/", status_code=303)

# =========================
# BROADCAST
# =========================
@app.post("/broadcast")
async def broadcast(message: str = Form(...)):
    telegram_required()

    global broadcast_message

    broadcast_message = message

    targets = chat_settings["groups"] + chat_settings["private"]

    for t in targets[:MAX_ITEMS]:
        try:
            await telegram.send_message(t["id"], message)
        except:
            pass

    return RedirectResponse("/", status_code=303)
