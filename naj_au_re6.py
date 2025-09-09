import json
import os
from threading import Thread
from flask import Flask, request, render_template_string
from pyrogram import Client, filters

# ---------------------------
# 📌 تحميل وحفظ الإعدادات
# ---------------------------
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        # إنشاء إعدادات افتراضية إذا الملف غير موجود
        default_config = {
            "api_id": 0,
            "api_hash": "",
            "keywords": [],
            "allowed_groups": [],
            "group_reply_template_ar": "تفضل خاص، أبشر {user}!",
            "group_reply_template_en": "Here you go, {user}! I'm ready to help you!"
        }
        save_config(default_config)
        return default_config
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()

# ---------------------------
# 📌 إعداد البوت
# ---------------------------
app_telegram = Client(
    "my_account",
    api_id=config["api_id"],
    api_hash=config["api_hash"]
)

# ---------------------------
# 📌 وظيفة البوت
# ---------------------------
@app_telegram.on_message(filters.group)
async def auto_reply(client, message):
    cfg = load_config()
    text = message.text.lower() if message.text else ""
    user = message.from_user.first_name if message.from_user else "صديق"

    if any(kw.lower() in text for kw in cfg["keywords"]):
        for group in cfg["allowed_groups"]:
            if message.chat.id == group["id"]:
                if group["reply_type"] == "group":
                    await message.reply_text(cfg.get("group_reply_template_ar", f"تفضل خاص، أبشر {user}!"))
                elif group["reply_type"] == "private":
                    await client.send_message(
                        message.from_user.id,
                        cfg.get("group_reply_template_en", f"Here you go, {user}! I'm ready to help you!")
                    )
                break

print("🚀 البوت جاهز للعمل!")

# ---------------------------
# 📌 لوحة التحكم Flask
# ---------------------------
flask_app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar">
<head>
    <meta charset="UTF-8">
    <title>لوحة تحكم البوت</title>
    <style>
        body { font-family: 'Tahoma', sans-serif; background: #f4f6f9; margin: 0; padding: 0; }
        .container { width: 90%%; max-width: 900px; margin: 30px auto; background: #fff; padding: 25px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);}
        h2 { text-align: center; color: #333; }
        label { font-weight: bold; display: block; margin: 15px 0 5px; }
        textarea, input[type="text"] { width: 100%%; padding: 10px; border: 1px solid #ccc; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }
        button { background: #007BFF; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 16px; transition: 0.2s; }
        button:hover { background: #0056b3; }
        .section { border: 1px solid #ddd; padding: 15px; border-radius: 10px; margin-bottom: 20px; background: #f9f9f9; }
        .section h3 { margin-top: 0; color: #444; }
        .footer { text-align: center; font-size: 12px; color: #777; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>⚙️ لوحة تحكم البوت</h2>
        <form method="POST">
            <div class="section">
                <h3>🔑 الكلمات المفتاحية</h3>
                <textarea name="keywords" rows="4">{{ keywords }}</textarea>
                <small>افصل بين الكلمات بفاصلة</small>
            </div>

            <div class="section">
                <h3>📌 المجموعات المسموحة</h3>
                <textarea name="groups" rows="4">{{ groups }}</textarea>
                <small>اكتب كل مجموعة في سطر بالشكل: id:reply_type (group أو private)</small>
            </div>

            <div class="section">
                <h3>💬 رسائل الرد</h3>
                <label>الرد بالعربي:</label>
                <input type="text" name="reply_ar" value="{{ reply_ar }}">
                <label>الرد بالإنجليزي:</label>
                <input type="text" name="reply_en" value="{{ reply_en }}">
            </div>

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
    return render_template_string(
        HTML_TEMPLATE,
        keywords=",".join(cfg["keywords"]),
        groups="\n".join([f"{g['id']}:{g['reply_type']}" for g in cfg["allowed_groups"]]),
        reply_ar=cfg.get("group_reply_template_ar", "تفضل خاص، أبشر {user}!"),
        reply_en=cfg.get("group_reply_template_en", "Here you go, {user}! I'm ready to help you!")
    )

# ---------------------------
# 📌 تشغيل البوت في Thread
# ---------------------------
def run_bot():
    app_telegram.start()
    print("🚀 البوت يعمل الآن!")
    app_telegram.idle()

Thread(target=run_bot, daemon=True).start()

# ---------------------------
# 📌 تشغيل Flask
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
