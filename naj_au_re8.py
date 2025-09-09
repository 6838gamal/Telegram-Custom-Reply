import json
import os
import time
from threading import Thread
from flask import Flask, request, render_template_string
from pyrogram import Client, filters

# ---------------------------
# 📌 تحميل وحفظ الإعدادات
# ---------------------------
CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
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
bot_status = "❌ متوقف"

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
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body { background-color: #f8f9fa; padding: 20px; font-family: 'Tahoma', sans-serif; }
.status { font-size: 1.2rem; font-weight: bold; margin-bottom: 20px; }
.table input { width: 100%%; }
</style>
</head>
<body>
<div class="container">
    <h2 class="text-center mb-4">⚙️ لوحة تحكم البوت</h2>
    <div class="status">
        حالة البوت:
        {% if bot_status.startswith('✅') %}
            <span class="text-success">{{ bot_status }}</span>
        {% elif bot_status.startswith('❌') %}
            <span class="text-danger">{{ bot_status }}</span>
        {% else %}
            <span class="text-warning">{{ bot_status }}</span>
        {% endif %}
    </div>
    <form method="POST">
        <table class="table table-bordered">
            <thead>
                <tr class="table-primary text-center">
                    <th>الخاصية</th>
                    <th>القيمة</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>الكلمات المفتاحية</td>
                    <td><input type="text" name="keywords" value="{{ keywords }}"></td>
                </tr>
                <tr>
                    <td>المجموعات المسموحة</td>
                    <td><textarea name="groups" rows="4">{{ groups }}</textarea>
                    <small>id:reply_type (group أو private)</small></td>
                </tr>
                <tr>
                    <td>الرد بالعربي</td>
                    <td><input type="text" name="reply_ar" value="{{ reply_ar }}"></td>
                </tr>
                <tr>
                    <td>الرد بالإنجليزي</td>
                    <td><input type="text" name="reply_en" value="{{ reply_en }}"></td>
                </tr>
            </tbody>
        </table>
        <button class="btn btn-primary">💾 حفظ التعديلات</button>
    </form>
    <div class="text-center mt-3 text-muted">تم التطوير بواسطة Gamal Almaqtary 🚀</div>
</div>
</body>
</html>
"""

@flask_app.route("/", methods=["GET", "POST"])
def panel():
    cfg = load_config()
    global bot_status
    if request.method == "POST":
        try:
            cfg["keywords"] = [w.strip() for w in request.form["keywords"].split(",") if w.strip()]
            groups_text = request.form["groups"].splitlines()
            cfg["allowed_groups"] = []
            for g in groups_text:
                if ":" in g:
                    gid, rtype = g.split(":")
                    if rtype.strip() in ["group","private"]:
                        cfg["allowed_groups"].append({"id": int(gid.strip()), "reply_type": rtype.strip()})
            cfg["group_reply_template_ar"] = request.form["reply_ar"].strip()
            cfg["group_reply_template_en"] = request.form["reply_en"].strip()
            save_config(cfg)
        except Exception as e:
            bot_status = f"⚠️ خطأ أثناء الحفظ: {str(e)}"
    return render_template_string(
        HTML_TEMPLATE,
        keywords=",".join(cfg["keywords"]),
        groups="\n".join([f"{g['id']}:{g['reply_type']}" for g in cfg["allowed_groups"]]),
        reply_ar=cfg.get("group_reply_template_ar", "تفضل خاص، أبشر {user}!"),
        reply_en=cfg.get("group_reply_template_en", "Here you go, {user}! I'm ready to help you!"),
        bot_status=bot_status
    )

# ---------------------------
# 📌 تشغيل البوت في Thread
# ---------------------------
def run_bot():
    global bot_status
    try:
        app_telegram.start()
        bot_status = "✅ شغال"
        while True:
            time.sleep(60)
    except Exception as e:
        bot_status = f"⚠️ خطأ: {str(e)}"

Thread(target=run_bot, daemon=True).start()

# ---------------------------
# 📌 تشغيل Flask
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)
