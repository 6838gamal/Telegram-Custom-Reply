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

# 🔥 مهم جداً لتخزين تسجيل الدخول
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

bot_status = "⏳ Starting..."
MAX_ITEMS = 10

# ------------------------------
# ENV CONFIG ONLY
# ------------------------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not API_ID or not API_HASH:
    raise Exception("API_ID and API_HASH are required")

API_ID = int(API_ID)

# ------------------------------
# MEMORY STORAGE
# ------------------------------
keywords = []
allowed_groups = []
private_chats = []
broadcast_message = "Hello"

# ------------------------------
# TELEGRAM CLIENT
# ------------------------------
telegram = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True
)

auth = {}

# ------------------------------
# KEYWORD MATCH
# ------------------------------
def match_keyword(text: str):
    return any(k.lower() in text for k in keywords)

# ------------------------------
# MESSAGE HANDLER
# ------------------------------
@telegram.on_message(filters.text)
async def handler(_, message):
    if not message.text:
        return

    if not match_keyword(message.text.lower()):
        return

    await message.reply("✅ Auto Reply Triggered")

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
# VERIFY CODE (FIXED)
# ------------------------------
@app.post("/verify")
async def verify(request: Request, code: str = Form(...)):
    try:
        await telegram.sign_in(
            auth["phone"],
            auth["hash"],
            code
        )

        # 🔥 SESSION FIX (IMPORTANT)
        request.session["auth"] = True

        async def run_bot():
            await telegram.idle()

        asyncio.create_task(run_bot())

        return RedirectResponse("/", status_code=303)

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"step": "code", "error": str(e)}
        )

# ------------------------------
# DASHBOARD (FIXED)
# ------------------------------
@app.get("/")
async def dashboard(request: Request):

    # 🔥 SESSION CHECK (FIX)
    if not request.session.get("auth"):
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "status": bot_status,
            "keywords": keywords,
            "groups": allowed_groups,
            "private_chats": private_chats,
            "broadcast_message": broadcast_message
        }
    )

# ------------------------------
# LOAD CHATS
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
async def save_chats(selected: list[str] = Form(...)):
    global allowed_groups, private_chats

    groups = []
    privates = []

    for cid in selected[:MAX_ITEMS]:
        cid = int(cid)

        if cid < 0:
            groups.append({"id": cid})
        else:
            privates.append(cid)

    allowed_groups = groups
    private_chats = privates

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

    targets = allowed_groups + [{"id": x} for x in private_chats]

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
