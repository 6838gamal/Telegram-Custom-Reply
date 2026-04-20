import os
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pyrogram import Client, filters

# ------------------------------
# APP
# ------------------------------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

MAX_ITEMS = 10
bot_status = "⏳ Starting..."

# ------------------------------
# ENV ONLY
# ------------------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# ------------------------------
# MEMORY STORAGE
# ------------------------------
keywords = []

chat_settings = {
    "groups": [],     # {"id": -100, "reply_type": "group"}
    "private": []     # {"id": 123, "reply_type": "private"}
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
# KEYWORD CHECK
# ------------------------------
def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)

# ------------------------------
# AUTO REPLY LOGIC
# ------------------------------
@telegram.on_message(filters.text)
async def handler(_, message):
    if not message.text:
        return

    if not match_keyword(message.text.lower()):
        return

    chat_id = message.chat.id

    # default reply
    reply_type = "default"

    for g in chat_settings["groups"]:
        if g["id"] == chat_id:
            reply_type = g.get("reply_type", "group")

    for p in chat_settings["private"]:
        if p["id"] == chat_id:
            reply_type = p.get("reply_type", "private")

    if reply_type == "group":
        await message.reply("📢 Group Auto Reply")

    elif reply_type == "private":
        await message.reply("💬 Private Auto Reply")

    else:
        await message.reply("✅ Default Reply")

# ------------------------------
# LOGIN
# ------------------------------
@app.get("/login")
async def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "step": "phone"}
    )

@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    await telegram.connect()

    sent = await telegram.send_code(phone)

    auth["phone"] = phone
    auth["hash"] = sent.phone_code_hash

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "step": "code"}
    )

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
            "login.html",
            {"request": request, "step": "code", "error": str(e)}
        )

# ------------------------------
# DASHBOARD
# ------------------------------
@app.get("/")
async def dashboard(request: Request):
    if not request.session.get("auth"):
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
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

# ------------------------------
# SAVE CHATS WITH TYPE + RULE
# ------------------------------
@app.post("/save_chats")
async def save_chats(
    selected: list[str] = Form(...),
    types: list[str] = Form(...),
    reply_types: list[str] = Form(...)
):

    groups = []
    privates = []

    for i in range(len(selected[:MAX_ITEMS])):
        cid = int(selected[i])

        item = {
            "id": cid,
            "reply_type": reply_types[i] if i < len(reply_types) else "default"
        }

        if types[i] == "group":
            groups.append(item)
        else:
            privates.append(item)

    chat_settings["groups"] = groups
    chat_settings["private"] = privates

    return RedirectResponse("/", status_code=303)

# ------------------------------
# KEYWORDS CRUD
# ------------------------------
@app.post("/keywords")
async def update_keywords(keywords_form: list[str] = Form(default=[])):
    global keywords

    keywords = [k.strip() for k in keywords_form if k.strip()][:MAX_ITEMS]

    return RedirectResponse("/", status_code=303)

# ------------------------------
# BROADCAST MESSAGE
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
