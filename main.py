import os
import json
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters

# ------------------------------
# APP SETUP
# ------------------------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CONFIG_FILE = "config.json"
bot_status = "⏳ Starting..."

MAX_ITEMS = 10

# ------------------------------
# ENV + CONFIG
# ------------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError("config.json not found")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

config = load_config()

# 🔥 ENV overrides (if exists)
API_ID = int(os.getenv("API_ID", config["api_id"]))
API_HASH = os.getenv("API_HASH", config["api_hash"])

# ------------------------------
# DEFAULT STRUCTURE SAFETY
# ------------------------------
config.setdefault("keywords", [])
config.setdefault("allowed_groups", [])
config.setdefault("private_chats", [])
config.setdefault("broadcast_message", "Hello!")

# ------------------------------
# TELEGRAM CLIENT
# ------------------------------
telegram = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

auth_data = {}
is_authenticated = False

# ------------------------------
# KEYWORD MATCHER
# ------------------------------
def match_keyword(text: str):
    for kw in config["keywords"]:
        if kw.lower() in text:
            return kw
    return None

# ------------------------------
# MESSAGE HANDLER
# ------------------------------
@telegram.on_message(filters.text)
async def handler(_, message):
    if not message.text:
        return

    if not match_keyword(message.text.lower()):
        return

    await message.reply("✅ Auto Response Triggered")

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

    auth_data["phone"] = phone
    auth_data["phone_code_hash"] = sent.phone_code_hash

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
    global is_authenticated, bot_status

    await telegram.sign_in(
        auth_data["phone"],
        auth_data["phone_code_hash"],
        code
    )

    is_authenticated = True
    bot_status = "✅ Running"

    asyncio.create_task(telegram.idle())

    return RedirectResponse("/", status_code=303)

# ------------------------------
# DASHBOARD PROTECTION
# ------------------------------
@app.get("/")
async def dashboard(request: Request):
    if not is_authenticated:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "status": bot_status,
            "keywords": config["keywords"],
            "groups": config["allowed_groups"],
            "private_chats": config["private_chats"],
            "broadcast_message": config["broadcast_message"]
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
            "name": chat.title or chat.first_name or "Private Chat",
            "type": str(chat.type)
        })

        if len(chats) >= 50:
            break

    return {"chats": chats}

# ------------------------------
# SAVE SELECTED CHATS
# ------------------------------
@app.post("/save_chats")
async def save_chats(selected: list[str] = Form(...)):
    groups = []
    privates = []

    for cid in selected[:MAX_ITEMS]:
        cid = int(cid)

        if cid < 0:
            groups.append({"id": cid})
        else:
            privates.append(cid)

    config["allowed_groups"] = groups
    config["private_chats"] = privates

    save_config()

    return RedirectResponse("/", status_code=303)

# ------------------------------
# KEYWORDS UPDATE
# ------------------------------
@app.post("/keywords")
async def keywords(keywords: list[str] = Form(default=[])):
    config["keywords"] = [
        k.strip() for k in keywords if k.strip()
    ][:MAX_ITEMS]

    save_config()

    return RedirectResponse("/", status_code=303)

# ------------------------------
# BROADCAST
# ------------------------------
@app.post("/broadcast")
async def broadcast():
    message = config["broadcast_message"]

    targets = config["allowed_groups"] + [
        {"id": x} for x in config["private_chats"]
    ]

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
