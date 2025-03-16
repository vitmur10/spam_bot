import re
import os
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage
from django.core.wsgi import get_wsgi_application
from asgiref.sync import sync_to_async
from datetime import datetime, timezone

load_dotenv()

API_TOKEN = os.getenv('TOKEN_BOT')

# Створюємо екземпляр DefaultBotProperties з parse_mode
default_properties = DefaultBotProperties(parse_mode="HTML")

# Створюємо екземпляр бота та диспетчера
bot = Bot(token=API_TOKEN)  # Використовуємо default для налаштувань
dp = Dispatcher(storage=MemoryStorage())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Setting.settings")
application = get_wsgi_application()
from setting_bot.models import ModerationSettings, BannedUser, MutedUser, Chats, UserMessageCount, ActionLog, User, Message
from django.apps import apps

WHITE_LIST_THRESHOLD = 15  # Мінімальна кількість повідомлень

@sync_to_async
def get_existing_message(message_id):
    return Message.objects.filter(message_id=message_id).first()


@sync_to_async
def update_message(existing_message, new_text):
    existing_message.message_text = new_text
    existing_message.timestamp = datetime.now(timezone.utc)
    existing_message.action = 'edited'
    existing_message.save()
async def save_message(message_id,chat_id, user_id, username, first_name, message_text, action=None):
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)
    await sync_to_async(Message.objects.create)(
        message_id=message_id,
        chats_names=chat,
        user_id=user_id,
        username=username,
        first_name=first_name,
        timestamp=datetime.now(timezone.utc),
        message_text=message_text,
        action=action
    )


@sync_to_async
def get_moderation_settings():
    all_settings = ModerationSettings.objects.all()  # Отримуємо всі записи

    moderation_data = []
    for settings in all_settings:
        moderation_data.append({
            "MODERATOR": settings.user.username,
            "BAD_WORDS_MUTE": settings.mute_words.split(", "),
            "BAD_WORDS_KICK": settings.kick_words.split(", "),
            "BAD_WORDS_BAN": settings.ban_words.split(", "),
            "MAX_MENTIONS": settings.max_mentions,
            "MAX_EMOJIS": settings.max_emojis,
            "MIN_CAPS_LENGTH": settings.min_caps_length,
            "MUTE_TIME": settings.mute_time,
            "DELETE_LINKS": settings.delete_links,
            "DELETE_AUDIO": settings.delete_audio,
            "DELETE_VIDEO": settings.delete_video,
            "DELETE_VIDEO_NOTES": settings.delete_video_notes,
            "DELETE_STICKERS": settings.delete_stickers,
            "DELETE_EMOJIS": settings.delete_emojis,
            "DELETE_CHINESE": settings.delete_chinese,
            "DELETE_RTL": settings.delete_rtl,
            "DELETE_EMAILS": settings.delete_emails,
            "DELETE_REFERRAL_LINKS": settings.delete_referral_links,
            "EMOJI_LIST": settings.emoji_list.split(",")
        })

    return moderation_data

# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

@sync_to_async
def get_whitelisted_users(chat_id):
    chat = Chats.objects.get(chat_id=chat_id)
    return set(
        UserMessageCount.objects
        .filter(chats_names=chat,
 message_count__gte=WHITE_LIST_THRESHOLD)
        .values_list("user_id", flat=True)
    )
@sync_to_async
def increment_message_count(user_id: int, chat_id: int, name):
    """Збільшує лічильник повідомлень користувача у чаті."""
    # Отримуємо або створюємо об'єкт
    chat = Chats.objects.get(chat_id=chat_id)
    user_message_count, created = UserMessageCount.objects.get_or_create(
        user_id=user_id,
        chats_names=chat,
        defaults={'message_count': 0, 'name': name, 'last_message_date': datetime.now(timezone.utc)}
    )
    # Збільшуємо лічильник на 1
    user_message_count.message_count += 1

    # Якщо значення змінилося, зберігаємо
    if user_message_count.message_count != (created and 0 or user_message_count.message_count - 1):
        user_message_count.save()


