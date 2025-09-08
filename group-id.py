from pyrogram import Client, filters

api_id = 20200731
api_hash = "debec87745352ef7c5fdcae9622930a1"

app = Client("my_account", api_id=api_id, api_hash=api_hash)

@app.on_message(filters.group)
def get_group_id(client, message):
    print(f"اسم المجموعة: {message.chat.title}")
    print(f"معرف المجموعة: {message.chat.id}")

app.run()
