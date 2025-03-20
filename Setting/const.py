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
from setting_bot.models import ModerationSettings,Chats, ActionLog, User, Message
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
    settings = ModerationSettings.objects.all()  # Отримуємо всі записи

    if settings.exists():  # Якщо є записи
        first_setting = settings.first()  # Беремо перший запис
        return {
            "MODERATOR": first_setting.user.username,
            "BAD_WORDS_MUTE": first_setting.mute_words.split(", "),  # Перетворюємо в список
            "BAD_WORDS_KICK": first_setting.kick_words.split(", "),
            "BAD_WORDS_BAN": first_setting.ban_words.split(", "),
            "MAX_MENTIONS": first_setting.max_mentions,
            "MAX_EMOJIS": first_setting.max_emojis,
            "MIN_CAPS_LENGTH": first_setting.min_caps_length,
            "MUTE_TIME": first_setting.mute_time,
            "DELETE_LINKS": first_setting.delete_links,
            "DELETE_AUDIO": first_setting.delete_audio,
            "DELETE_VIDEO": first_setting.delete_video,
            "DELETE_VIDEO_NOTES": first_setting.delete_video_notes,
            "DELETE_STICKERS": first_setting.delete_stickers,
            "DELETE_EMOJIS": first_setting.delete_emojis,
            "DELETE_CHINESE": first_setting.delete_chinese,
            "DELETE_RTL": first_setting.delete_rtl,
            "DELETE_EMAILS": first_setting.delete_emails,
            "DELETE_REFERRAL_LINKS": first_setting.delete_referral_links,
            "EMOJI_LIST": first_setting.emoji_list.split(", ")
        }
    return {}  # Якщо немає записів, повертаємо порожній словник

# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")


@sync_to_async
def get_whitelisted_users(chat_id):
    """Отримуємо список користувачів, які досягли порогу повідомлень для білого списку"""
    chat = Chats.objects.get(chat_id=chat_id)

    # Фільтруємо користувачів за лічильником повідомлень
    whitelisted_users = User.objects.filter(
        chats_names=chat,
        message_count__gte=WHITE_LIST_THRESHOLD
    ).values_list("user_id", flat=True)

    return set(whitelisted_users)


@sync_to_async
def increment_message_count(user_id: int, chat_id: int, name: str):
    """Збільшує лічильник повідомлень користувача у чаті."""
    # Отримуємо або створюємо об'єкт чату
    chat = Chats.objects.get(chat_id=chat_id)

    # Отримуємо або створюємо запис користувача у чаті
    user, created = User.objects.get_or_create(
        user_id=user_id,
        chats_names=chat,
        defaults={
            'first_name': name,
            'message_count': 0,
            'last_message_date': datetime.now(timezone.utc)
        }
    )

    # Збільшуємо лічильник на 1
    user.message_count += 1

    # Оновлюємо час останнього повідомлення
    user.last_message_date = datetime.now(timezone.utc)

    # Зберігаємо зміни
    user.save()


