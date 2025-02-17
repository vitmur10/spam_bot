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
from Setting.setting_bot.models import ModerationSettings

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

# ❌ Слова, за які бот МУТИТЬ (тимчасова заборона на відправку повідомлень)
BAD_WORDS_MUTE = {"спам", "флуд", "лох", "реклама", "лохотрон"}

# ❌ Слова, за які бот КІКАЄ (видаляє з чату)
BAD_WORDS_KICK = {"тролінг", "деструктив", "образа"}

# ❌ Слова, за які бот БАНИТЬ (перманентний бан)
BAD_WORDS_BAN = {"нацизм", "расизм", "тероризм", "дитяче порно"}

# Максимальна кількість тегів @ перед видаленням
MAX_MENTIONS = 5

# Максимальна кількість емодзі перед видаленням
MAX_EMOJIS = 10

# Мінімальна довжина капс-лока для виявлення "крику"
MIN_CAPS_LENGTH = 10

# Час мута в секундах (наприклад, 1 година = 3600 секунд)
MUTE_TIME = 3600

# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")
