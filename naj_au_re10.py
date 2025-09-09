import os
import json
import threading
from flask import Flask, render_template_string, request, redirect, url_for
from pyrogram import Client, filters

# ------------------------------
# تحميل الإعدادات
# ------------------------------
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError("⚠️ ملف config.json غير موجود!")

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

api_id = config["api_id"]
api_hash = config["api_hash"]

# Pyrogram Client
app_telegram = Client("my_account", api_id=api_id, api_hash=api_hash)

# Flask app
flask_app = Flask(__name__)

bot_status = "⏳ جاري التشغيل"

# ------------------------------
# Telegram Handlers
# ------------------------------
@app_telegram.on_message(filters.text & filters.group)
async def handler(client, message):
    text = message.text.lower()
    for kw in config.get("keywords", []):
        if kw.lower() in text:
            reply_template = config.get("group_reply_template_ar", "✅ تم التقاط الرسالة من {user}")
            reply = reply_template.format(user=message.from_user.mention if message.from_user else "مستخدم")
            await message.reply(reply)
            break

# ------------------------------
# Flask لوحة التحكم
# ------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة تحكم البوت</title>
    <style>
        body { font-family: Tahoma, sans-serif; margin: 30px; background: #f8f9fa; color: #333; }
        h1 { text-align: center; color: #007BFF; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; background: #fff; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: center; }
        th { background: #007BFF; color: white; }
        tr:nth-child(even) { background: #f2f2f2; }
        .btn { padding: 5px 10px; border: none; cursor: pointer; border-radius: 4px; }
        .save { background: #28a745; color: white; }
        .delete { background: #dc3545; color: white; }
        .add { background: #17a2b8; color: white; margin: 10px 0; }
        .status { font-weight: bold; color: green; }
    </style>
</head>
<body>
    <h1>لوحة تحكم البوت</h1>
    <p>حالة البوت: <span class="status">{{ status }}</span></p>

    <h2>الكلمات المفتاحية</h2>
    <form method="POST" action="/update_keywords">
        <table>
            <tr><th>الكلمة</th><th>إجراء</th></tr>
            {% for kw in keywords %}
            <tr>
                <td><input type="text" name="keywords" value="{{ kw }}" style="width:90%"></td>
                <td><button type="submit" name="delete" value="{{ kw }}" class="btn delete">حذف</button></td>
            </tr>
            {% endfor %}
        </table>
        <button type="submit" name="add" value="1" class="btn add">➕ إضافة كلمة</button>
        <button type="submit" class="btn save">💾 حفظ</button>
    </form>

    <h2>المجموعات المسموح بها</h2>
    <form method="POST" action="/update_groups">
        <table>
            <tr><th>ID المجموعة</th><th>النوع</th><th>إجراء</th></tr>
            {% for g in groups %}
            <tr>
                <td><input type="text" name="group_ids" value="{{ g['id'] }}" style="width:90%"></td>
                <td>
                    <select name="group_types">
                        <option value="group" {% if g['reply_type']=="group" %}selected{% endif %}>Group</option>
                        <option value="private" {% if g['reply_type']=="private" %}selected{% endif %}>Private</option>
                    </select>
                </td>
                <td><button type="submit" name="delete" value="{{ g['id'] }}" class="btn delete">حذف</button></td>
            </tr>
            {% endfor %}
        </table>
        <button type="submit" name="add" value="1" class="btn add">➕ إضافة مجموعة</button>
        <button type="submit" class="btn save">💾 حفظ</button>
    </form>
</body>
</html>
"""

def save_config():
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

@flask_app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE,
        status=bot_status,
        keywords=config.get("keywords", []),
        groups=config.get("allowed_groups", [])
    )

@flask_app.route("/update_keywords", methods=["POST"])
def update_keywords():
    if "delete" in request.form:
        word = request.form["delete"]
        config["keywords"] = [w for w in config.get("keywords", []) if w != word]
    elif "add" in request.form:
        config.setdefault("keywords", []).append("كلمة جديدة")
    else:
        config["keywords"] = request.form.getlist("keywords")
    save_config()
    return redirect(url_for("index"))

@flask_app.route("/update_groups", methods=["POST"])
def update_groups():
    if "delete" in request.form:
        gid = int(request.form["delete"])
        config["allowed_groups"] = [g for g in config.get("allowed_groups", []) if g["id"] != gid]
    elif "add" in request.form:
        config.setdefault("allowed_groups", []).append({"id": 0, "reply_type": "group"})
    else:
        ids = request.form.getlist("group_ids")
        types = request.form.getlist("group_types")
        config["allowed_groups"] = [{"id": int(ids[i]), "reply_type": types[i]} for i in range(len(ids))]
    save_config()
    return redirect(url_for("index"))

# ------------------------------
# Main
# ------------------------------
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot_status = "✅ شغال"
    app_telegram.run()
