import re
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

API_TOKEN = os.getenv('TOKEN_BOT')

# Налаштування логування
# Створюємо екземпляр DefaultBotProperties з parse_mode
# Створюємо екземпляр DefaultBotProperties з parse_mode
default_properties = DefaultBotProperties(parse_mode="HTML")

# Створюємо екземпляр бота та диспетчера
bot = Bot(token=API_TOKEN)  # Використовуємо default для налаштувань
dp = Dispatcher(storage=MemoryStorage())
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
