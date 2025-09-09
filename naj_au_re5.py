import json
import asyncio
from threading import Thread
from flask import Flask, request, render_template_string
from pyrogram import Client, filters

# 📌 تحميل وحفظ الإعدادات
CONFIG_FILE = "config.json"
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()

# 📌 إعداد البوت
app_telegram = Client(
    "my_account",
    api_id=config["api_id"],
    api_hash=config["api_hash"]
)

# 📌 وظيفة البوت
@app_telegram.on_message(filters.group)
async def auto_reply(client, message):
    cfg = load_config()
    text = message.text.lower() if message.text else ""
    user = message.from_user.first_name if message.from_user else "صديق"

    # تحقق من الكلمات المفتاحية
    if any(kw.lower() in text for kw in cfg["keywords"]):
        for group in cfg["allowed_groups"]:
            if message.chat.id == group["id"]:
                if group["reply_type"] == "group":
                    await message.reply_text(cfg["group_reply_template_ar"].format(user=user))
                elif group["reply_type"] == "private":
                    await client.send_message(message.from_user.id,
                                              cfg["group_reply_template_en"].format(user=user))
                break

print("🚀 البوت جاهز للعمل...")

# 📌 لوحة التحكم Flask
flask_app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <title>لوحة تحكم البوت</title>
    <style>
        body {
            font-family: 'Tahoma', sans-serif;
            background: #f4f6f9;
            margin: 0; padding: 0;
        }
        .container {
            width: 80%%; max-width: 800px;
            margin: 30px auto;
            background: #fff;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h2 {
            text-align: center;
            color: #333;
        }
        label {
            font-weight: bold;
            display: block;
            margin: 15px 0 5px;
        }
        textarea, input[type="text"] {
            width: 100%%;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        button {
            background: #007BFF;
            color: white;
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #0056b3;
        }
        .footer {
            text-align: center;
            font-size: 12px;
            color: #777;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>⚙️ لوحة تحكم البوت</h2>
        <form method="POST">
            <label>الكلمات المفتاحية (مفصولة بفواصل):</label>
            <textarea name="keywords" rows="4">{{ keywords }}</textarea>

            <label>المجموعات المسموحة (id:reply_type):</label>
            <textarea name="groups" rows="4">{{ groups }}</textarea>

            <label>رسالة الرد (عربي):</label>
            <input type="text" name="reply_ar" value="{{ reply_ar }}">

            <label>رسالة الرد (English):</label>
            <input type="text" name="reply_en" value="{{ reply_en }}">

            <button type="submit">💾 حفظ التعديلات</button>
        </form>
        <div class="footer">تم التطوير بواسطة Gamal Almaqtary 🚀</div>
    </div>
</body>
</html>
"""

@flask_app.route("/", methods=["GET", "POST"])
def panel():
    cfg = load_config()
    if request.method == "POST":
        cfg["keywords"] = [w.strip() for w in request.form["keywords"].split(",")]
        groups_text = request.form["groups"].splitlines()
        cfg["allowed_groups"] = []
        for g in groups_text:
            if ":" in g:
                gid, rtype = g.split(":")
                cfg["allowed_groups"].append({"id": int(gid.strip()), "reply_type": rtype.strip()})
        cfg["group_reply_template_ar"] = request.form["reply_ar"]
        cfg["group_reply_template_en"] = request.form["reply_en"]
        save_config(cfg)
    return render_template_string(HTML_TEMPLATE,
                                  keywords=",".join(cfg["keywords"]),
                                  groups="\\n".join([f"{g['id']}:{g['reply_type']}" for g in cfg["allowed_groups"]]),
                                  reply_ar=cfg["group_reply_template_ar"],
                                  reply_en=cfg["group_reply_template_en"])

# 📌 تشغيل البوت في Thread
def run_bot():
    asyncio.run(app_telegram.run())

Thread(target=run_bot, daemon=True).start()

# 📌 تشغيل Flask
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000)
