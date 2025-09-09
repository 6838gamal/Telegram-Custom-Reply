# naj_au_re10.py
import os
import json
import threading
import time
from flask import Flask, render_template_string, request, redirect, url_for
from pyrogram import Client, filters

# ---------------------------
# ملفات / إعدادات
# ---------------------------
CONFIG_FILE = "config.json"

def ensure_config():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "api_id": 0,
            "api_hash": "",
            "keywords": [],
            "allowed_groups": [],
            "group_reply_template_ar": "تفضل {user}، سيتم التواصل معك.",
            "group_reply_template_en": "Hi {user}, we will contact you shortly."
        }
        save_config(default)
        return default
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Normalize structure: ensure keys exist and types right
    cfg["keywords"] = [k.strip() for k in cfg.get("keywords", []) if k and k.strip()]
    ag = []
    for g in cfg.get("allowed_groups", []):
        try:
            gid = int(g.get("id")) if not isinstance(g.get("id"), int) else g.get("id")
            name = str(g.get("name","")).strip()
            rtype = str(g.get("reply_type","group")).strip().lower()
            if rtype not in ("group","private"):
                rtype = "group"
            template = str(g.get("template","ar"))
            custom = str(g.get("custom_reply","")).strip()
            ag.append({"id": gid, "name": name, "reply_type": rtype, "template": template, "custom_reply": custom})
        except Exception:
            continue
    cfg["allowed_groups"] = ag
    cfg.setdefault("group_reply_template_ar", "تفضل {user}، سيتم التواصل معك.")
    cfg.setdefault("group_reply_template_en", "Hi {user}, we will contact you shortly.")
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

config = ensure_config()

# ---------------------------
# إعداد Pyrogram client
# ---------------------------
API_ID = config.get("api_id", 0)
API_HASH = config.get("api_hash", "")

if not API_ID or not API_HASH:
    print("⚠️ الرجاء تعبئة api_id و api_hash في config.json ثم إعادة التشغيل.")
# Client session file will be created (my_account.session) on first login
app_telegram = Client("my_account", api_id=API_ID, api_hash=API_HASH)

# حالة البوت للواجهة
bot_status = "⏳ جاري التشغيل"

# طباعة ملخّص عند البدء
def print_summary():
    cfg = ensure_config()
    print("=== Bot config summary ===")
    print("API ID:", cfg.get("api_id"))
    print("Groups (id:name:type:template):")
    for g in cfg.get("allowed_groups", []):
        print("  -", g["id"], ":", g.get("name",""), ":", g["reply_type"], ":", g.get("template","ar"))
    print("Keywords:", cfg.get("keywords"))
    print("==========================")

print_summary()

# ---------------------------
# Handlers
# ---------------------------

# ping test
@app_telegram.on_message(filters.command("ping") & filters.group)
async def cmd_ping(client, message):
    await message.reply_text("pong")

# auto-reply handler
@app_telegram.on_message(filters.group & ~filters.me)
async def auto_reply(client, message):
    try:
        cfg = ensure_config()  # read fresh config for live updates
        text = (message.text or message.caption or "").strip()
        if not text:
            return
        text_l = text.lower()

        # debug print (visible in logs)
        print(f"[MSG] chat_id={message.chat.id} user={getattr(message.from_user, 'id', None)} text={text}")

        # check keywords
        matched = None
        for kw in cfg.get("keywords", []):
            if kw and kw.strip() and kw.lower() in text_l:
                matched = kw
                break
        if not matched:
            return

        # find group config
        gid = int(message.chat.id)
        grp = next((g for g in cfg.get("allowed_groups", []) if int(g["id"]) == gid), None)
        if not grp:
            print(f"[SKIP] chat {gid} not in allowed_groups")
            return

        # choose template
        tpl_kind = grp.get("template","ar")
        if tpl_kind == "custom" and grp.get("custom_reply"):
            tpl = grp.get("custom_reply")
        elif tpl_kind == "en":
            tpl = cfg.get("group_reply_template_en")
        else:
            tpl = cfg.get("group_reply_template_ar")

        # format username
        user_display = getattr(message.from_user, "first_name", None) or getattr(message.from_user, "username", "User")
        reply_text = tpl.replace("{user}", user_display)

        # send according to reply_type
        if grp.get("reply_type") == "private":
            # send private message to user
            uid = getattr(message.from_user, "id", None)
            if uid:
                await client.send_message(uid, reply_text)
                print(f"[SENT] private to {uid}")
            else:
                print("[WARN] sender id unknown, cannot send private message")
        else:
            await message.reply_text(reply_text)
            print(f"[SENT] group reply in {gid}")

    except Exception as e:
        print("Error in auto_reply:", e)

# ---------------------------
# Flask dashboard (Thread)
# ---------------------------
flask_app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>لوحة تحكم البوت</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
body{background:#f4f6f9;font-family:tahoma;padding:20px}
.card{border-radius:12px;padding:18px}
.table-scroll{max-height:300px;overflow:auto;background:#fff;border-radius:6px}
th.sticky{position:sticky;top:0;background:#0d6efd;color:#fff}
.small-input{width:95%}
</style>
</head>
<body>
<div class="container">
  <h3 class="text-center mb-3">⚙️ لوحة تحكم البوت</h3>
  <div class="card mb-3">
    <div>حالة البوت: 
      {% if status.startswith('✅') %}
        <span class="text-success">{{ status }}</span>
      {% elif status.startswith('⚠️') %}
        <span class="text-warning">{{ status }}</span>
      {% else %}
        <span class="text-danger">{{ status }}</span>
      {% endif %}
      &nbsp;&nbsp; | &nbsp;&nbsp; <small>أرسل <code>/ping</code> في أي مجموعة لاختبار الاستجابة</small>
    </div>
  </div>

  <form method="POST" action="/save_all">
  <div class="card mb-3">
    <h5>🔑 الكلمات المفتاحية</h5>
    <div class="table-scroll mt-2">
      <table class="table">
        <thead><tr class="sticky"><th>الكلمة</th><th>إجراء</th></tr></thead>
        <tbody>
        {% for kw in keywords %}
          <tr>
            <td><input class="form-control small-input" name="kw_{{ loop.index0 }}" value="{{ kw }}"></td>
            <td><button class="btn btn-sm btn-danger" name="del_kw" value="{{ kw }}">حذف</button></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    <div class="mt-2">
      <button class="btn btn-info" name="add_kw" value="1">➕ إضافة كلمة</button>
    </div>
  </div>

  <div class="card mb-3">
    <h5>📌 المجموعات المسموحة</h5>
    <div class="table-scroll mt-2">
      <table class="table">
        <thead><tr class="sticky"><th>الاسم</th><th>ID</th><th>نوع</th><th>قالب</th><th>رد مخصص (لو اخترت مخصص)</th><th>إجراء</th></tr></thead>
        <tbody>
        {% for g in groups %}
          <tr>
            <td><input class="form-control small-input" name="g_name_{{ loop.index0 }}" value="{{ g.get('name','') }}"></td>
            <td><input class="form-control small-input" name="g_id_{{ loop.index0 }}" value="{{ g['id'] }}"></td>
            <td>
              <select class="form-select" name="g_type_{{ loop.index0 }}">
                <option value="group" {% if g['reply_type']=='group' %}selected{% endif %}>Group</option>
                <option value="private" {% if g['reply_type']=='private' %}selected{% endif %}>Private</option>
              </select>
            </td>
            <td>
              <select class="form-select" name="g_tpl_{{ loop.index0 }}">
                <option value="ar" {% if g.get('template','ar')=='ar' %}selected{% endif %}>عربي</option>
                <option value="en" {% if g.get('template')=='en' %}selected{% endif %}>English</option>
                <option value="custom" {% if g.get('template')=='custom' %}selected{% endif %}>مخصص</option>
              </select>
            </td>
            <td><input class="form-control small-input" name="g_custom_{{ loop.index0 }}" value="{{ g.get('custom_reply','') }}"></td>
            <td><button class="btn btn-sm btn-danger" name="del_group" value="{{ g['id'] }}">حذف</button></td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    <div class="mt-2">
      <button class="btn btn-info" name="add_group" value="1">➕ إضافة مجموعة</button>
    </div>
  </div>

  <div class="card mb-3">
    <h5>💬 قوالب الرد العامة</h5>
    <div class="mb-2">
      <label>الرد بالعربي</label>
      <textarea class="form-control" name="reply_ar" rows="3">{{ reply_ar }}</textarea>
    </div>
    <div>
      <label>الرد بالإنجليزي</label>
      <textarea class="form-control" name="reply_en" rows="3">{{ reply_en }}</textarea>
    </div>
  </div>

  <div class="text-end mb-5">
    <button class="btn btn-success" type="submit">💾 حفظ التعديلات</button>
  </div>
  </form>

  <div class="text-center text-muted"><small>تم التطوير بواسطة Gamal Almaqtary</small></div>
</div>
</body>
</html>
"""

@flask_app.route("/", methods=["GET", "POST"])
def dashboard():
    global config, bot_status
    cfg = ensure_config()
    # POST from save_all
    if request.method == "POST":
        # handle keywords add/delete and edits
        if 'add_kw' in request.form:
            cfg.setdefault("keywords", []).append("كلمة جديدة")
        if 'del_kw' in request.form:
            val = request.form.get('del_kw')
            cfg["keywords"] = [k for k in cfg.get("keywords", []) if k != val]
        # update edited keywords
        new_keywords = []
        for i in range(len(cfg.get("keywords", []))):
            v = request.form.get(f"kw_{i}")
            if v and v.strip():
                new_keywords.append(v.strip())
        cfg["keywords"] = new_keywords

        # handle groups add/delete and edits
        if 'add_group' in request.form:
            cfg.setdefault("allowed_groups", []).append({"id": 0, "name": "New Group", "reply_type": "group", "template": "ar", "custom_reply": ""})
        if 'del_group' in request.form:
            try:
                gid_del = int(request.form.get('del_group'))
                cfg["allowed_groups"] = [g for g in cfg.get("allowed_groups", []) if int(g["id"]) != gid_del]
            except:
                pass
        # collect groups edited
        new_groups = []
        group_count = len(cfg.get("allowed_groups", []))
        for i in range(group_count):
            gid_raw = request.form.get(f"g_id_{i}","").strip()
            name = request.form.get(f"g_name_{i}","").strip()
            rtype = request.form.get(f"g_type_{i}","group")
            tpl = request.form.get(f"g_tpl_{i}","ar")
            custom = request.form.get(f"g_custom_{i}","").strip()
            try:
                gid_val = int(gid_raw)
            except:
                gid_val = 0
            new_groups.append({"id": gid_val, "name": name, "reply_type": rtype, "template": tpl, "custom_reply": custom})
        cfg["allowed_groups"] = new_groups

        # replies
        cfg["group_reply_template_ar"] = request.form.get("reply_ar","").strip()
        cfg["group_reply_template_en"] = request.form.get("reply_en","").strip()

        # save and reload config variable
        save_config(cfg)
        config = ensure_config()
        bot_status = "✅ شغال"
        return redirect(url_for("dashboard"))

    # GET -> render
    return render_template_string(HTML,
        status=bot_status,
        keywords=config.get("keywords", []),
        groups=config.get("allowed_groups", []),
        reply_ar=config.get("group_reply_template_ar",""),
        reply_en=config.get("group_reply_template_en","")
    )

def run_flask():
    port = int(os.environ.get("PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=port)

# ---------------------------
# Main: run Flask in background thread, run Pyrogram in main thread
# ---------------------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    try:
        with app_telegram:
            bot_status = "✅ شغال"
            print("🚀 Bot started (main thread).")
            # keep running (pyrogram keeps handlers active)
            import asyncio
            asyncio.get_event_loop().run_forever()
    except Exception as e:
        bot_status = f"⚠️ خطأ: {e}"
        print("Bot error:", e)
