import re
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage
from django.core.wsgi import get_wsgi_application

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

def get_moderation_settings():
    settings = ModerationSettings.objects.first()
    if not settings:
        return None
    return {
        "BAD_WORDS_MUTE": set(settings.mute_words.split(", ")),
        "BAD_WORDS_KICK": set(settings.kick_words.split(", ")),
        "BAD_WORDS_BAN": set(settings.ban_words.split(", ")),
        "MAX_MENTIONS": settings.max_mentions,
        "MAX_EMOJIS": settings.max_emojis,
        "MIN_CAPS_LENGTH": settings.min_caps_length,
        "MUTE_TIME": settings.mute_time
    }

settings = get_moderation_settings()
BAD_WORDS_MUTE = settings["BAD_WORDS_MUTE"]
BAD_WORDS_KICK = settings["BAD_WORDS_KICK"]
BAD_WORDS_BAN = settings["BAD_WORDS_BAN"]
MAX_MENTIONS = settings["MAX_MENTIONS"]
MAX_EMOJIS = settings["MAX_EMOJIS"]
MIN_CAPS_LENGTH = settings["MIN_CAPS_LENGTH"]
MUTE_TIME = settings["MUTE_TIME"]

# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
