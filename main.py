import os
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pyrogram import Client, filters

# ------------------------------
# APP SETUP
# ------------------------------
app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MAX_ITEMS = 10

bot_status = "⏳ Starting..."

# ------------------------------
# ENV CONFIG
# ------------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# ------------------------------
# MEMORY STORAGE
# ------------------------------
keywords = []

chat_settings = {
    "groups": [],
    "private": []
}

broadcast_message = "Hello from bot"

auth = {}

# ------------------------------
# TELEGRAM CLIENT
# ------------------------------
telegram = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

# ------------------------------
# KEYWORD MATCH
# ------------------------------
def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)

# ------------------------------
# AUTO REPLY
# ------------------------------
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
            reply_type = g.get("reply_type", "group")

    for p in chat_settings["private"]:
        if p["id"] == chat_id:
            reply_type = p.get("reply_type", "private")

    if reply_type == "group":
        await message.reply("📢 Group Reply")

    elif reply_type == "private":
        await message.reply("💬 Private Reply")

    else:
        await message.reply("✅ Default Reply")

# ------------------------------
# LOGIN PAGE
# ------------------------------
@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "phone"}
    )

# ------------------------------
# SEND CODE
# ------------------------------
@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    await telegram.connect()

    sent = await telegram.send_code(phone)

    auth["phone"] = phone
    auth["hash"] = sent.phone_code_hash

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "code"}
    )

# ------------------------------
# VERIFY CODE
# ------------------------------
@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    try:
        await telegram.sign_in(
            auth["phone"],
            auth["hash"],
            code
        )

        request.session["auth"] = True
        asyncio.create_task(telegram.idle())

        return RedirectResponse("/", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"step": "code", "error": str(e)}
        )

# ------------------------------
# DASHBOARD (ingest.html)
# ------------------------------
@app.get("/")
async def dashboard(request: Request):
    if not request.session.get("auth"):
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "status": bot_status,
            "keywords": keywords,
            "chat_settings": chat_settings,
            "broadcast_message": broadcast_message
        }
    )

# ------------------------------
# LOAD TELEGRAM CHATS
# ------------------------------
@app.get("/load_chats")
async def load_chats():
    chats = []

    async for dialog in telegram.get_dialogs():
        chat = dialog.chat

        chats.append({
            "id": chat.id,
            "name": chat.title or chat.first_name or "Private",
            "type": str(chat.type)
        })

        if len(chats) >= 50:
            break

    return {"chats": chats}

# ------------------------------
# SAVE CHATS
# ------------------------------
@app.post("/save_chats")
async def save_chats(
    selected: list[str] = Form(...),
    types: list[str] = Form(...),
    reply_types: list[str] = Form(...)
):

    groups = []
    privates = []

    for i in range(min(len(selected), MAX_ITEMS)):
        cid = int(selected[i])
        t = types[i] if i < len(types) else "private"
        r = reply_types[i] if i < len(reply_types) else "default"

        item = {
            "id": cid,
            "reply_type": r
        }

        if t == "group":
            groups.append(item)
        else:
            privates.append(item)

    chat_settings["groups"] = groups
    chat_settings["private"] = privates

    return RedirectResponse("/", status_code=303)

# ------------------------------
# KEYWORDS
# ------------------------------
@app.post("/keywords")
async def update_keywords(keywords_form: list[str] = Form(default=[])):
    global keywords

    keywords = [k.strip() for k in keywords_form if k.strip()][:MAX_ITEMS]

    return RedirectResponse("/", status_code=303)

# ------------------------------
# BROADCAST
# ------------------------------
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

# ------------------------------
# STARTUP
# ------------------------------
@app.on_event("startup")
async def startup():
    pass
