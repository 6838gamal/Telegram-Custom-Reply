import json
import streamlit as st
from pyrogram import Client, filters
from threading import Thread
from datetime import datetime
import os

# ================= ملف الإعدادات =================
CONFIG_FILE = "config.json"
SESSION_FILE = "my_account"  # ملف الجلسة

# ================= تحميل/حفظ الإعدادات =================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # إعداد افتراضي
        return {
            "api_id": "",
            "api_hash": "",
            "groups": [],
            "reply_text_ar": "📞 للتواصل مع الدعم يرجى الاتصال على: +967774440982",
            "reply_text_en": "📞 For support, please contact: +967774440982"
        }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()
if "logs" not in st.session_state:
    st.session_state["logs"] = []

# ================= وظيفة تشغيل البوت =================
def run_bot():
    if not config.get("api_id") or not config.get("api_hash"):
        print("⚠️ الرجاء إدخال API ID و API Hash أولاً.")
        return

    app = Client(SESSION_FILE, api_id=int(config["api_id"]), api_hash=config["api_hash"])

    @app.on_message(filters.group)
    def auto_reply(client, message):
        gid = str(message.chat.id)
        for group in config["groups"]:
            if gid == group["id"]:
                for kw in group["keywords"]:
                    if kw.lower() in message.text.lower():
                        reply_msg = f"{config['reply_text_ar']}\n\n{config['reply_text_en']}"
                        message.reply(reply_msg)
                        log_entry = f"[{datetime.now().strftime('%H:%M:%S')}] رد على {group['name']} ({gid}) بالكلمة: {kw}"
                        print(log_entry)
                        st.session_state["logs"].append(log_entry)
                        break

    print("🚀 البوت يعمل الآن من رقمك الشخصي...")
    app.run()

# ================= واجهة Streamlit =================
st.set_page_config(page_title="Telegram UserBot", page_icon="📱", layout="wide")
st.title("📱 Telegram UserBot Dashboard")
st.write("لوحة تحكم لإدارة الردود التلقائية من حسابك الشخصي")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "تشغيل البوت", "الكلمات المفتاحية", "المجموعات", "نص الرد", "سجل الرسائل"
])

# ===== Tab 1: تشغيل البوت =====
with tab1:
    st.subheader("تشغيل الحساب الشخصي")
    st.text_input("API ID", value=config.get("api_id", ""), key="api_id_input")
    st.text_input("API Hash", value=config.get("api_hash", ""), key="api_hash_input", type="password")

    if st.button("▶️ تشغيل البوت"):
        # حفظ API قبل التشغيل
        config["api_id"] = st.session_state["api_id_input"]
        config["api_hash"] = st.session_state["api_hash_input"]
        save_config(config)
        thread = Thread(target=run_bot, daemon=True)
        thread.start()
        st.info("⏳ البوت يعمل في الخلفية... تحقق من الكونسول.")

# ===== Tab 2: إدارة الكلمات المفتاحية =====
with tab2:
    st.subheader("الكلمات المفتاحية العامة")
    st.write("القائمة الحالية:", config.get("keywords_global", []))

    new_kw = st.text_input("➕ كلمة جديدة")
    if st.button("إضافة كلمة عامة"):
        if "keywords_global" not in config:
            config["keywords_global"] = []
        if new_kw and new_kw not in config["keywords_global"]:
            config["keywords_global"].append(new_kw)
            save_config(config)
            st.success(f"تمت إضافة الكلمة: {new_kw}")

    remove_kw = st.selectbox("🗑 حذف كلمة", [""] + config.get("keywords_global", []))
    if st.button("حذف كلمة عامة"):
        if remove_kw in config.get("keywords_global", []):
            config["keywords_global"].remove(remove_kw)
            save_config(config)
            st.warning(f"تم حذف الكلمة: {remove_kw}")

# ===== Tab 3: إدارة المجموعات =====
with tab3:
    st.subheader("المجموعات")
    for i, group in enumerate(config.get("groups", [])):
        st.text_input(f"📛 اسم المجموعة {i+1}", value=group["name"], key=f"name_{i}")
        st.text_input(f"🆔 معرف المجموعة {i+1}", value=group["id"], key=f"id_{i}")
        st.text_area(f"🔑 الكلمات المفتاحية {i+1} (مفصولة بفاصلة)", 
                     value=",".join(group["keywords"]), key=f"keywords_{i}")
        st.selectbox(f"🌍 نوع المجموعة {i+1}", ["عامة", "خاصة"], 
                     index=0 if group["type"] == "public" else 1, key=f"type_{i}")

    if st.button("➕ إضافة مجموعة"):
        config["groups"].append({"name":"New Group","id":"","keywords":[],"type":"public"})
        save_config(config)

    if st.button("💾 حفظ جميع التعديلات"):
        new_groups = []
        for i in range(len(config["groups"])):
            new_groups.append({
                "name": st.session_state[f"name_{i}"],
                "id": st.session_state[f"id_{i}"],
                "keywords": [kw.strip() for kw in st.session_state[f"keywords_{i}"].split(",") if kw.strip()],
                "type": "public" if st.session_state[f"type_{i}"]=="عامة" else "private"
            })
        config["groups"] = new_groups
        save_config(config)
        st.success("✅ تم حفظ جميع التعديلات على المجموعات")

# ===== Tab 4: نص الرد =====
with tab4:
    st.subheader("تخصيص نص الرد")
    reply_ar = st.text_area("🇸🇦 الرد بالعربية", config["reply_text_ar"])
    reply_en = st.text_area("🇬🇧 الرد بالإنجليزية", config["reply_text_en"])

    if st.button("💾 حفظ نص الرد"):
        config["reply_text_ar"] = reply_ar
        config["reply_text_en"] = reply_en
        save_config(config)
        st.success("✅ تم حفظ نصوص الرد")

# ===== Tab 5: سجل الرسائل =====
with tab5:
    st.subheader("📜 سجل الرسائل التي تم الرد عليها")
    if st.session_state["logs"]:
        for log in st.session_state["logs"]:
            st.text(log)
    else:
        st.info("لم يتم الرد على أي رسالة بعد.")
