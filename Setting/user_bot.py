from telethon import TelegramClient, events
from const import api_id, api_hash, Chats


client = TelegramClient('userbot_session', api_id, api_hash)

# Слухаємо повідомлення в групі
chat_ids = list(Chats.objects.values_list('chat_id', flat=True))  # приклад: [-1001234567890, -1009876543210]

# ----- Реєструємо один обробник для всіх чатів -----
@client.on(events.NewMessage(chats=chat_ids))
async def delete_bot_message(event):
    sender = await event.get_sender()  # отримуємо повний об'єкт
    if sender.bot:
        await event.delete()

client.start()
client.run_until_disconnected()