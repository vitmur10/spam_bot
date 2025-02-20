import re
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage
from django.core.wsgi import get_wsgi_application
from asgiref.sync import sync_to_async

load_dotenv()

API_TOKEN = os.getenv('TOKEN_BOT')

# Створюємо екземпляр DefaultBotProperties з parse_mode
default_properties = DefaultBotProperties(parse_mode="HTML")

# Створюємо екземпляр бота та диспетчера
bot = Bot(token=API_TOKEN)  # Використовуємо default для налаштувань
dp = Dispatcher(storage=MemoryStorage())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Setting.settings")
application = get_wsgi_application()
from setting_bot.models import ModerationSettings, BannedUser, MutedUser
@sync_to_async

def get_moderation_settings():
    settings = ModerationSettings.objects.first()
    if not settings:
        return None
    return {
        "BAD_WORDS_MUTE": settings.mute_words.split(", "),
        "BAD_WORDS_KICK": settings.kick_words.split(", "),
        "BAD_WORDS_BAN": settings.ban_words.split(", "),
        "MAX_MENTIONS": settings.max_mentions,
        "MAX_EMOJIS": settings.max_emojis,
        "MIN_CAPS_LENGTH": settings.min_caps_length,
        "MUTE_TIME": settings.mute_time,
        "DELETE_LINKS": settings.delete_links,
        "EMOJI_LIST": settings.emoji_list  # Дістаємо як рядок
    }


  # Тепер це рядок

# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")

