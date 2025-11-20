import logging
from telethon import TelegramClient, events
from const import api_id, api_hash, Chats

# ----- Налаштовуємо логування -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

client = TelegramClient('userbot_session', api_id, api_hash)

# Слухаємо повідомлення в групі
chat_ids = list(Chats.objects.values_list('chat_id', flat=True))

@client.on(events.NewMessage(chats=chat_ids))
async def delete_bot_message(event):
    chat = await event.get_chat()

    try:
        sender = await event.get_sender()
    except Exception:
        sender = None

    chat_title = getattr(chat, "title", chat.id)
    sender_id = getattr(sender, "id", None)
    sender_is_bot = getattr(sender, "bot", False)

    logger.info(
        f"Incoming message | Chat={chat_title} ({event.chat_id}) | Sender={sender_id} | Bot={sender_is_bot}"
    )

    if sender_is_bot:
        try:
            await event.delete()
            logger.info(f"Deleted bot message from {sender_id} in chat {chat_title}")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
    else:
        logger.debug("Message is not from a bot — skipped")


client.start()
logger.info("Userbot started")
client.run_until_disconnected()
