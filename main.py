import os
import asyncio
import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters

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
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

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
telegram = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# =========================
# KEYWORD MATCH
# =========================
def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)

# =========================
# AUTO REPLY ENGINE
# =========================
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
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "phone"}
    )

@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    await telegram.connect()

    sent = await telegram.send_code(phone)

    auth_data["phone"] = phone
    auth_data["hash"] = sent.phone_code_hash

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "code"}
    )

@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    try:
        await telegram.sign_in(
            auth_data["phone"],
            auth_data["hash"],
            code
        )

        token = create_token()

        response = RedirectResponse("/", status_code=303)
        response.set_cookie("token", token, httponly=True)

        asyncio.create_task(telegram.idle())

        return response

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"step": "code", "error": str(e)}
        )

# =========================
# DASHBOARD (INGEST)
# =========================
@app.get("/")
async def dashboard(request: Request):
    verify_token(request)

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
async def save_keywords(keywords_form: list[str] = Form(default=[])):
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
    global broadcast_message

    broadcast_message = message

    targets = chat_settings["groups"] + chat_settings["private"]

    for t in targets[:MAX_ITEMS]:
        try:
            await telegram.send_message(t["id"], message)
        except:
            pass

    return RedirectResponse("/", status_code=303)
