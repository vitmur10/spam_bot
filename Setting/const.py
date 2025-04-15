import os
import re
from datetime import datetime, timezone
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from asgiref.sync import sync_to_async
from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('TOKEN_BOT')
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
# Створюємо екземпляр DefaultBotProperties з parse_mode
default_properties = DefaultBotProperties(parse_mode="HTML")

# Створюємо екземпляр бота та диспетчера
bot = Bot(token=API_TOKEN)  # Використовуємо default для налаштувань
dp = Dispatcher(storage=MemoryStorage())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Setting.settings")
application = get_wsgi_application()
from setting_bot.models import ModerationSettings,Chats, ChatUser, Message, ActionLog, ChatMembership

WHITE_LIST_THRESHOLD = 15  # Мінімальна кількість повідомлень

# Налаштування логера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

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
    settings = ModerationSettings.objects.all()

    if settings.exists():
        # Створюємо єдиний словник для всіх налаштувань
        combined_settings = {
            "BAD_WORDS_MUTE": [],
            "BAD_WORDS_KICK": [],
            "BAD_WORDS_BAN": [],

            "MAX_MENTIONS": [],
            "MAX_EMOJIS": [],
            "MIN_CAPS_LENGTH": [],
            "MUTE_TIME": [],
            "DELETE_LINKS": [],
            "DELETE_AUDIO": [],
            "DELETE_VIDEO": [],
            "DELETE_VIDEO_NOTES": [],
            "DELETE_STICKERS": [],
            "DELETE_EMOJIS": [],
            "DELETE_CHINESE": [],
            "DELETE_RTL": [],
            "DELETE_EMAILS": [],
            "DELETE_REFERRAL_LINKS": [],
            "EMOJI_LIST": [],
            "MORPHOLOGY_UK": [],
            "MORPHOLOGY_RU": [],
        }

        # Перебираємо всі налаштування і додаємо їх до відповідних списків
        for setting in settings:
            combined_settings["BAD_WORDS_MUTE"].append(setting.mute_words.split(", "))
            combined_settings["BAD_WORDS_KICK"].append(setting.kick_words.split(", "))
            combined_settings["BAD_WORDS_BAN"].append(setting.ban_words.split(", "))
            combined_settings["MAX_MENTIONS"].append(setting.max_mentions)
            combined_settings["MAX_EMOJIS"].append(setting.max_emojis)
            combined_settings["MIN_CAPS_LENGTH"].append(setting.min_caps_length)
            combined_settings["MUTE_TIME"].append(setting.mute_time)
            combined_settings["DELETE_LINKS"].append(setting.delete_links)
            combined_settings["DELETE_AUDIO"].append(setting.delete_audio)
            combined_settings["DELETE_VIDEO"].append(setting.delete_video)
            combined_settings["DELETE_VIDEO_NOTES"].append(setting.delete_video_notes)
            combined_settings["DELETE_STICKERS"].append(setting.delete_stickers)
            combined_settings["DELETE_EMOJIS"].append(setting.delete_emojis)
            combined_settings["DELETE_CHINESE"].append(setting.delete_chinese)
            combined_settings["DELETE_RTL"].append(setting.delete_rtl)
            combined_settings["DELETE_EMAILS"].append(setting.delete_emails)
            combined_settings["DELETE_REFERRAL_LINKS"].append(setting.delete_referral_links)
            combined_settings["EMOJI_LIST"].append(setting.emoji_list.split(", "))
            combined_settings["MORPHOLOGY_UK"].append(setting.morphology_worlds_lang_uk.split(","))
            combined_settings["MORPHOLOGY_RU"].append(setting.morphology_worlds_lang_ru.split(","))

        return combined_settings

    return {}


# Регулярний вираз для пошуку посилань
URL_PATTERN = re.compile(r"https?://\S+|www\.\S+")


@sync_to_async
def get_whitelisted_users(chat_id):
    """Отримуємо список користувачів, які досягли порогу повідомлень для білого списку"""
    chat = Chats.objects.get(chat_id=chat_id)

    # Фільтруємо участі в чаті з message_count >= порогу
    whitelisted_memberships = ChatMembership.objects.filter(
        chat=chat,
        message_count__gte=WHITE_LIST_THRESHOLD
    ).select_related('user')

    # Отримуємо user_id користувачів
    whitelisted_user_ids = whitelisted_memberships.values_list('user__user_id', flat=True)

    return set(whitelisted_user_ids)


@sync_to_async
def increment_message_count(user_id: int, chat_id: int, name: str):
    """Збільшує лічильник повідомлень користувача у чаті."""
    # Отримуємо або створюємо об'єкт чату
    chat = Chats.objects.get(chat_id=chat_id)

    # Отримуємо або створюємо користувача
    user, _ = ChatUser.objects.get_or_create(
        user_id=user_id,
        defaults={'first_name': name}
    )

    # Отримуємо або створюємо зв’язок користувача з чатом
    membership, _ = ChatMembership.objects.get_or_create(
        user=user,
        chat=chat,
        defaults={
            'message_count': 0,
            'last_message_date': datetime.now(timezone.utc),
            'status': 'Активний'
        }
    )

    # Збільшуємо лічильник на 1
    membership.message_count += 1

    # Оновлюємо час останнього повідомлення
    membership.last_message_date = datetime.now(timezone.utc)

    # Зберігаємо зміни
    membership.save()