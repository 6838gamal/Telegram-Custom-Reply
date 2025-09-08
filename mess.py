import json
from datetime import datetime
from pyrogram import Client, filters

# === إعدادات الحساب الشخصي ===
api_id = 20200731        # ضع api_id هنا
api_hash = "debec87745352ef7c5fdcae9622930a1"  # ضع api_hash هنا

# === إعدادات البوت ===
keywords = ["أريد مساعدة", "مساعدة", "أحتاج مساعدة", "help", "need help"]
group_reply_template = "✅ {user} طلب المساعدة! للتواصل: 0774440982"
log_file = "help_requests.json"

# قائمة المعرفات (IDs) للمجموعات التي يعمل فيها الرد الآلي
allowed_groups = [-1001234567890, -1009876543210]  # ضع هنا معرفات المجموعات المسموح لها

# دالة لتسجيل الطلب في JSON
def log_request(user, message_text, chat_id):
    request_data = {
        "user": user,
        "message": message_text,
        "chat_id": chat_id,
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

# إنشاء عميل Pyrogram
app = Client("my_account", api_id=api_id, api_hash=api_hash)

# مراقبة الرسائل
@app.on_message(filters.text)
def handle_message(client, message):
    # التحقق إذا كانت الرسالة في مجموعة مسموح بها فقط
    if message.chat.id not in allowed_groups:
        return

    text = message.text.lower()
    if any(keyword.lower() in text for keyword in keywords):
        user = message.from_user.first_name or message.from_user.username or "مستخدم"
        reply_text = group_reply_template.format(user=user)
        
        # إرسال الرسالة في المجموعة (من رقمك الشخصي)
        message.reply(reply_text)
        
        # تسجيل الطلب
        log_request(user, message.text, message.chat.id)

# تشغيل العميل
app.run()
