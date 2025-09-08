from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8317337195:AAEKG5koGvaYJYyxZK_zglRY_pNadazLhoY"

# ✅ قوائم الكلمات المفتاحية لكل نوع طلب
keywords_dict = {
    "مساعدة": ["أريد مساعدة", "مساعدة", "أحتاج مساعدة", "help", "need help"],
    "استفسار": ["هل من يعرف", "استفسار", "سؤال", "أريد معرفة", "question"],
    "تقنية": ["مشاكل تقنية", "تطبيق", "برنامج", "software issue"]
}

# الرسائل الخاصة لكل نوع
private_messages = {
    "مساعدة": "مرحبًا! لاحظت أنك طلبت مساعدة. كيف يمكنني مساعدتك؟",
    "استفسار": "لقد استلمت استفسارك! سأرد عليك في أقرب وقت ممكن.",
    "تقنية": "شكراً لسؤالك التقني! دعنا نساعدك بحل المشكلة."
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! اكتب رسالتك وسأقوم بالرد عليك بشكل خاص إذا احتوت على كلمات مفتاحية."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()  # تحويل النص كله إلى أحرف صغيرة
    user_id = update.message.from_user.id

    sent = False  # علامة لتجنب إرسال أكثر من رسالة واحدة لكل رسالة

    # البحث عن أي كلمة مفتاحية في أي قائمة
    for category, keywords in keywords_dict.items():
        if any(keyword.lower() in text for keyword in keywords):
            try:
                # إرسال رسالة خاصة للمستخدم
                await context.bot.send_message(chat_id=user_id, text=private_messages[category])
                sent = True
            except Exception as e:
                print("Error:", e)

    if sent:
        # تأكيد في الشات الأصلي بأن رسالة خاصة أرسلت
        await update.message.reply_text("✅ تم إرسال رسالة خاصة لك.")
        
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is running...")
    app.run_polling()
