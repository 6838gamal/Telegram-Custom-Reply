import json
from datetime import datetime
from pyrogram import Client, filters
import threading
import time
import os
import re

CONFIG_FILE = "config1.json"

# === دالة لقراءة الإعدادات من JSON ===
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

config = load_config()
last_modified = os.path.getmtime(CONFIG_FILE)

# إعدادات البوت من JSON
api_id = config["api_id"]
api_hash = config["api_hash"]
keywords = config["keywords"]
allowed_groups_dict = {g["id"]: g["reply_type"] for g in config["allowed_groups"]}
group_reply_template_ar = config["group_reply_template_ar"]
group_reply_template_en = config["group_reply_template_en"]
log_file = config["log_file"]

# === دالة لتسجيل الطلبات في JSON ===
def log_request(user, message_text, chat_id, message_id):
    request_data = {
        "user": user,
        "message": message_text,
        "chat_id": chat_id,
        "message_id": message_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    data.append(request_data)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# === دالة لتوحيد النص العربي ===
def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[ًٌٍَُِّْ]", "", text)  # إزالة التشكيل
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    text = re.sub(r"\s+", " ", text).strip()  # إزالة المسافات الزائدة
    return text

# === وظيفة لمراقبة تغييرات ملف JSON ===
def watch_config():
    global config, keywords, allowed_groups_dict, group_reply_template_ar, group_reply_template_en, last_modified
    while True:
        try:
            current_modified = os.path.getmtime(CONFIG_FILE)
            if current_modified != last_modified:
                print("🔄 تم تحديث config.json، إعادة تحميل الإعدادات...")
                config = load_config()
                keywords = config["keywords"]
                allowed_groups_dict = {g["id"]: g["reply_type"] for g in config["allowed_groups"]}
                group_reply_template_ar = config["group_reply_template_ar"]
                group_reply_template_en = config["group_reply_template_en"]
                last_modified = current_modified
        except Exception as e:
            print(f"⚠️ خطأ أثناء مراقبة config.json: {e}")
        time.sleep(2)  # تحقق كل ثانيتين

# === إنشاء عميل Pyrogram ===
# لتجنب مشكلة database locked يمكن تغيير اسم الجلسة إذا لزم الأمر
app = Client("my_account", api_id=api_id, api_hash=api_hash)

# === رسالة بدء التشغيل ===
@app.on_message(filters.me & filters.command("start"))
def start_message(client, message):
    print("🚀 البوت بدأ العمل وينتظر الرسائل...")

# === مراقبة الرسائل في المجموعات ===
@app.on_message(filters.text & filters.group)
def handle_message(client, message):
    if message.chat.id not in allowed_groups_dict:
        return

    # تجاهل رسائل الحساب الشخصي
    me_id = app.get_me().id
    if message.from_user and message.from_user.id == me_id:
        return

    text_normalized = normalize_text(message.text)
    for keyword in keywords:
        keyword_normalized = normalize_text(keyword)
        if keyword_normalized in text_normalized:
            user = message.from_user.first_name or message.from_user.username or "User"

            # اختر القالب حسب وجود حروف عربية أو لا
            if re.search(r"[اأإآء-ي]", message.text):
                reply_text = group_reply_template_ar.format(user=user)
            else:
                reply_text = group_reply_template_en.format(user=user)

            reply_type = allowed_groups_dict[message.chat.id]

            if reply_type == "group":
                message.reply(reply_text)
            elif reply_type == "private":
                client.send_message(message.from_user.id, reply_text)

            log_request(user, message.text, message.chat.id, message.id)
            break  # لا حاجة للاستمرار بعد العثور على أول كلمة

# === تشغيل مراقب التحديثات في الخلفية ===
threading.Thread(target=watch_config, daemon=True).start()

# === تشغيل البوت ===
print("✅ جاري تشغيل البوت...")
app.run()
