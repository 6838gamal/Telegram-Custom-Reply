import json
import streamlit as st
from pyrogram import Client, filters
import asyncio
from threading import Thread
from datetime import datetime
import os

CONFIG_FILE = "config.json"

# ================= تحميل/حفظ الإعدادات =================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "api_id": "",
            "api_hash": "",
            "keywords": [],
            "allowed_groups": [],
            "group_reply_template_ar": "تفضل خاص، أبشر {user}!",
            "group_reply_template_en": "Here you go, {user}! I'm ready to help you!",
            "log_file": "help_requests.json"
        }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

config = load_config()
if "logs" not in st.session_state:
    st.session_state["logs"] = []

# ================= وظيفة تشغيل البوت =================
async def run_bot_async():
    async with Client("my_account", api_id=int(config["api_id"]), api_hash=config["api_hash"]) as app:

        @app.on_message(filters.group)
        async def auto_reply(client, message):
            gid = str(message.chat.id)
            for group in config["allowed_groups"]:
                if gid == str(group["id"]):
                    text = message.text.lower()
                    if any(kw.lower() in text for kw in config["keywords"]):
                        user_name = message.from_user.first_name if message.from_user else "User"
                        if group["reply_type"] == "private":
                            reply_msg = config["group_reply_template_ar"].replace("{user}", user_name) + "\n" + \
                                        config["group_reply_template_en"].replace("{user}", user_name)
                        else:
                            reply_msg = config["group_reply_template_ar"].replace("{user}", user_name)
                        await message.reply(reply_msg)

                        # حفظ السجل
                        log_entry = {
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "group_id": gid,
                            "group_type": group["reply_type"],
                            "user": user_name,
                            "message": message.text
                        }
                        st.session_state["logs"].append(f"[{log_entry['time']}] {log_entry['user']} في {gid}: {message.text}")
                        if config.get("log_file"):
                            if os.path.exists(config["log_file"]):
                                with open(config["log_file"], "r", encoding="utf-8") as f:
                                    logs_data = json.load(f)
                            else:
                                logs_data = []
                            logs_data.append(log_entry)
                            with open(config["log_file"], "w", encoding="utf-8") as f:
                                json.dump(logs_data, f, ensure_ascii=False, indent=4)

        print("🚀 البوت يعمل الآن من رقمك الشخصي...")
        await app.idle()

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
        config["api_id"] = st.session_state["api_id_input"]
        config["api_hash"] = st.session_state["api_hash_input"]
        save_config(config)
        thread = Thread(target=lambda: asyncio.run(run_bot_async()), daemon=True)
        thread.start()
        st.info("⏳ البوت يعمل في الخلفية... تحقق من الكونسول.")

# ===== Tab 2: إدارة الكلمات المفتاحية =====
with tab2:
    st.subheader("الكلمات المفتاحية")
    st.write("القائمة الحالية:", config.get("keywords", []))

    new_kw = st.text_input("➕ كلمة جديدة")
    if st.button("إضافة كلمة"):
        if new_kw and new_kw not in config["keywords"]:
            config["keywords"].append(new_kw)
            save_config(config)
            st.success(f"تمت إضافة الكلمة: {new_kw}")

    remove_kw = st.selectbox("🗑 حذف كلمة", [""] + config.get("keywords", []))
    if st.button("حذف كلمة"):
        if remove_kw in config.get("keywords", []):
            config["keywords"].remove(remove_kw)
            save_config(config)
            st.warning(f"تم حذف الكلمة: {remove_kw}")

# ===== Tab 3: إدارة المجموعات =====
with tab3:
    st.subheader("المجموعات")
    for i, group in enumerate(config.get("allowed_groups", [])):
        st.text_input(f"📛 معرف المجموعة {i+1}", value=str(group.get("id","")), key=f"group_id_{i}")
        st.selectbox(f"🌍 نوع الرد {i+1}", ["private", "group"], index=0 if group.get("reply_type","private")=="private" else 1, key=f"group_type_{i}")

    if st.button("➕ إضافة مجموعة"):
        config["allowed_groups"].append({"id": 0, "reply_type": "private"})
        save_config(config)

    if st.button("💾 حفظ جميع التعديلات"):
        new_groups = []
        for i in range(len(config["allowed_groups"])):
            new_groups.append({
                "id": st.session_state[f"group_id_{i}"],
                "reply_type": st.session_state[f"group_type_{i}"]
            })
        config["allowed_groups"] = new_groups
        save_config(config)
        st.success("✅ تم حفظ جميع التعديلات على المجموعات")

# ===== Tab 4: نص الرد =====
with tab4:
    st.subheader("تخصيص نص الرد")
    reply_ar = st.text_area("🇸🇦 الرد بالعربية", config.get("group_reply_template_ar",""))
    reply_en = st.text_area("🇬🇧 الرد بالإنجليزية", config.get("group_reply_template_en",""))

    if st.button("💾 حفظ نص الرد"):
        config["group_reply_template_ar"] = reply_ar
        config["group_reply_template_en"] = reply_en
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
