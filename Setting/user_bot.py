from telethon import TelegramClient, events
from const import api_id, api_hash, Chats, NAME_SESSION

client = TelegramClient("userbot_session", api_id, api_hash)

chat_ids = list(Chats.objects.values_list('chat_id', flat=True))


@client.on(events.NewMessage(chats=chat_ids))
async def delete_bot_message(event):
    sender = await event.get_sender()
    message = event.message

    sender_is_bot = getattr(sender, "bot", False)
    via_bot_id = getattr(message, "via_bot_id", None)

    if sender_is_bot or via_bot_id:
        try:
            await event.delete()
        except:
            pass


client.start()
client.run_until_disconnected()
