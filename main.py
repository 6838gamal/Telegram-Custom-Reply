import os
import json
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pyrogram import Client, filters

# ------------------------------
# إعداد التطبيق
# ------------------------------
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CONFIG_FILE = "config.json"
bot_status = "⏳ Starting..."

# ------------------------------
# تحميل الإعدادات
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

# ------------------------------
# Telegram Client
# ------------------------------
telegram = Client(
    "my_account",
    api_id=config["api_id"],
    api_hash=config["api_hash"],
    in_memory=True
)

auth_sessions = {}
is_authenticated = False

# ------------------------------
# Telegram Logic
# ------------------------------
def match_keyword(text: str):
    for kw in config.get("keywords", []):
        if kw.lower() in text:
            return kw
    return None


@telegram.on_message(filters.text & filters.group)
async def handler(client, message):
    if not message.text:
        return

    keyword = match_keyword(message.text.lower())

    if keyword:
        template = config.get(
            "group_reply_template_ar",
            "✅ Message captured from {user}"
        )

        reply = template.format(
            user=message.from_user.mention if message.from_user else "User"
        )

        await message.reply(reply)

# ------------------------------
# Login Routes
# ------------------------------
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "phone"}
    )


@app.post("/send_code")
async def send_code(request: Request, phone: str = Form(...)):
    await telegram.connect()
    sent = await telegram.send_code(phone)

    auth_sessions["phone"] = phone
    auth_sessions["phone_code_hash"] = sent.phone_code_hash

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"step": "code"}
    )


@app.post("/verify_code")
async def verify_code(request: Request, code: str = Form(...)):
    global is_authenticated, bot_status

    try:
        await telegram.sign_in(
            phone_number=auth_sessions["phone"],
            phone_code_hash=auth_sessions["phone_code_hash"],
            phone_code=code
        )

        is_authenticated = True
        bot_status = "✅ Running"

        async def run_bot():
            await telegram.idle()

        asyncio.create_task(run_bot())

        return RedirectResponse("/", status_code=303)

    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "step": "code",
                "error": "Invalid code, try again"
            }
        )

# ------------------------------
# Dashboard
# ------------------------------
@app.get("/")
async def index(request: Request):
    if not is_authenticated:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "status": bot_status,
            "keywords": config.get("keywords", []),
            "groups": config.get("allowed_groups", [])
        }
    )


@app.post("/update_keywords")
async def update_keywords(
    keywords: list[str] = Form(default=[]),
    delete: str = Form(default=None),
    add: str = Form(default=None)
):
    if delete:
        config["keywords"] = [w for w in config.get("keywords", []) if w != delete]

    elif add:
        config.setdefault("keywords", []).append("New keyword")

    else:
        config["keywords"] = [k.strip() for k in keywords if k.strip()]

    save_config()
    return RedirectResponse("/", status_code=303)


@app.post("/update_groups")
async def update_groups(
    group_ids: list[str] = Form(default=[]),
    group_types: list[str] = Form(default=[]),
    delete: str = Form(default=None),
    add: str = Form(default=None)
):
    if delete:
        gid = int(delete)
        config["allowed_groups"] = [
            g for g in config.get("allowed_groups", [])
            if g["id"] != gid
        ]

    elif add:
        config.setdefault("allowed_groups", []).append({
            "id": 0,
            "reply_type": "group"
        })

    else:
        cleaned = []
        for i in range(len(group_ids)):
            try:
                cleaned.append({
                    "id": int(group_ids[i]),
                    "reply_type": group_types[i]
                })
            except:
                continue

        config["allowed_groups"] = cleaned

    save_config()
    return RedirectResponse("/", status_code=303)
