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
allowed_groups = [-1001234567890, -1009876543210 ,    -1002718581472]  # ضع هنا معرفات المجموعات المسموح لها

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

# إظهار رسالة عند بدء التشغيل
@app.on_message(filters.me & filters.command("start"))
def start_message(client, message):
    print("🚀 البوت بدأ العمل وينتظر الرسائل...")

# مراقبة الرسائل في المجموعات
@app.on_message(filters.text & filters.group)
def handle_message(client, message):
    # التحقق أن الرسالة من مجموعة مسموح بها
    if message.chat.id not in allowed_groups:
        return

    # تجاهل رسائلك أنت (صاحب الرقم)
    if message.from_user and message.from_user.is_self:
        return

    text = message.text.lower()
    if any(keyword.lower() in text for keyword in keywords):
        user = message.from_user.first_name or message.from_user.username or "مستخدم"
        reply_text = group_reply_template.format(user=user)
        
        # إرسال الرد في نفس المجموعة
        message.reply(reply_text)
        
        # تسجيل الطلب في JSON
        log_request(user, message.text, message.chat.id)

# تشغيل العميل
print("✅ جاري تشغيل البوت...")
app.run()
