import asyncio
from datetime import datetime, timedelta, timezone

import pytz
from aiogram import Router, F
from aiogram import types
from aiogram.types import Message, ChatPermissions, ContentType
from aiogram.filters import Filter, Command
from django.db.models import Exists, OuterRef
from const import *
from django.utils.timezone import now

router = Router()
ChatPermissions(can_send_messages=False)

banned_users = []
muted_users = []


async def add_user(chat_id, user_id):
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)
    user, created = await sync_to_async(User.objects.get_or_create)(
        user_id=user_id,
        chats_names=chat,
    )
    return user, created





async def log_action(chat_id, user_id, username, action_type, info, message_id=None):
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)
    message = await sync_to_async(Message.objects.get)(message_id=message_id) if message_id else None

    await sync_to_async(ActionLog.objects.create)(
        chats_names=chat,
        user_id=user_id,
        username=username,
        action_type=action_type,
        message=message,
        info=info
    )

async def clean_old_logs(days=30):
    delete_before = now() - timedelta(days=days)
    await sync_to_async(ActionLog.objects.filter(created_at__lt=delete_before).delete)()

# Фільтр для перевірки чату
class IsChatAllowed(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return await is_chat_allowed(message.chat.id)

async def is_chat_allowed(chat_id: int) -> bool:
    return await Chats.objects.filter(chat_id=chat_id).aexists()


async def get_muted_users():
    """Отримуємо список користувачів, яких потрібно розмутити"""
    now_plus_3 = datetime.now(timezone(timedelta(hours=3)))  # Київський часовий пояс (UTC+3)
    muted_users = await sync_to_async(list)(MutedUser.objects.filter(end_time__lte=now_plus_3))
    return muted_users

# Функція для отримання chats_names асинхронно
@sync_to_async
def get_chats_names(user):
    return user.chats_names

@sync_to_async
def get_chat_by_name(name):
    return Chats.objects.get(name=name)

async def auto_unban_unmute(bot: Bot):
    while True:
        muted_users = await get_muted_users()  # Отримуємо користувачів, яких потрібно розбанити
        for user in muted_users:
            if user.end_time <= datetime.now():  # Перевіряємо, чи закінчився час мута
                chats_names = await get_chats_names(user)  # Отримуємо чат
                chat = await get_chat_by_name(chats_names.name)  # Отримуємо сам чат

                # Логуємо дію в ActionLog
                await sync_to_async(ActionLog.objects.create)(
                    chats_names=chats_names,
                    user_id=user.user_id,
                    username=user.first_name,
                    action_type='unmute_unban',
                    info=f"User {user.user_id} was unmuted and unbanned.",
                    created_at=datetime.now()
                )

                # Закоментовано: Не знімаємо обмеження з користувачів
                # await bot.restrict_chat_member(
                #     chat_id=chat.chat_id,
                #     user_id=user.user_id,
                #     permissions=types.ChatPermissions(
                #         can_send_messages=True,
                #         can_send_media_messages=True,
                #         can_send_other_messages=True,
                #         can_add_web_page_previews=True
                #     ),
                # )

                # Закоментовано: Не видаляємо користувача з бази
                # await sync_to_async(user.delete)()

        # Чекаємо 60 секунд перед наступною перевіркою
        await asyncio.sleep(60)

@router.message(
    F.new_chat_members |  # Додавання нового учасника
    F.left_chat_member |  # Вихід/видалення учасника
    F.pinned_message |  # Закріплення повідомлення
    F.migrate_to_chat_id |  # Оновлення до супергрупи
    F.migrate_from_chat_id |  # Оновлення до супергрупи (зміна ID)
    F.group_chat_created |  # Створення групового чату
    F.supergroup_chat_created |  # Створення супергрупи
    F.channel_chat_created |  # Створення каналу
    F.message_auto_delete_timer_changed |  # Зміна таймера авто-видалення повідомлень
    F.chat_shared |  # Поділитися чатом
    F.chat_invite_link |  # Надіслано інвайт-посилання
    F.chat_photo |  # Додано/змінено фото чату
    F.chat_title  # Змінено назву чату
)
async def delete_service_messages(message: Message, bot: Bot):
    """Видаляє всі технічні повідомлення у групі/чаті."""
    await bot.delete_message(message.chat.id, message.message_id)


async def is_admin(chat_id, user_id):
    # Отримання інформації про учасника чату
    member = await bot.get_chat_member(chat_id, user_id)

    # Перевірка, чи є користувач адміністратором або власником чату
    if member.status in ['administrator', 'creator']:
        return True
    return False


# Обробник для команди /ban
@router.message(F.text.startswith("/chat_id"))
async def get_chat_id(message: types.Message):
    await message.answer(f"Chat ID: `{message.chat.id}`", parse_mode="Markdown")
    return


"""@router.message(IsChatAllowed(), F.text.startswith('/ban'))
async def ban_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        #await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        #await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return

    user_id = message.reply_to_message.from_user.id
    user_first_name = message.reply_to_message.from_user.first_name

    # Ban the user
    await bot.ban_chat_member(message.chat.id, user_id)

    # Add user to the banned users database
    BannedUser.objects.create(user_id=user_id, first_name=user_first_name)

    # Send confirmation message
    #await message.answer(f'Покинув нас: {user_first_name}')"""



"""@router.message(IsChatAllowed(),F.text.startswith('/mute'))
async def mute_user(message: Message, bot: Bot):

    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        #await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        #await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return

    try:
        muteint = int(message.text.split()[1])  # Мute duration
        mutetype = message.text.split()[2]  # Time unit (hour, minute, day)
        comment = " ".join(message.text.split()[3:])  # Reason for mute
    except IndexError:
        #await message.answer('Бракує аргументів! Приклад: `/mute 1 хвилина причина`')
        return

    # Calculate mute end time
    if mutetype in ["г", "годин", "година"]:
        dt = datetime.now() + timedelta(hours=muteint)
    elif mutetype in ["х", "хвилин", "хвилини"]:
        dt = datetime.now() + timedelta(minutes=muteint)
    elif mutetype in ["д", "днів", "день"]:
        dt = datetime.now() + timedelta(days=muteint)
    else:
        #await message.answer("Невідомий тип часу. Використовуйте 'г', 'х' або 'д'.")
        return

    # Mute the user
    timestamp = dt.timestamp()
    await bot.restrict_chat_member(
        message.chat.id,
        message.reply_to_message.from_user.id,
        types.ChatPermissions(can_send_messages=False),
        until_date=timestamp
    )

    # Add muted user to the database
    MutedUser.objects.create(
        user_id=message.reply_to_message.from_user.id,
        first_name=message.reply_to_message.from_user.first_name,
        end_time=dt
    )"""


"""@router.message(IsChatAllowed(),F.text.startswith('/kik'))
async def unban_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        #await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        #await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return"""


@router.edited_message(IsChatAllowed())
@router.message(IsChatAllowed())
async def filter_spam(message: Message, bot: Bot):
    user_id = message.from_user.id
    first_name = message.from_user.full_name
    username = message.from_user.username
    chat_id = message.chat.id
    text = message.text if message.text else ""

    existing_message = await get_existing_message(message.message_id)
    if existing_message:
        old_text = existing_message.message_text
        new_text = message.text
        if old_text != new_text:
            await update_message(existing_message, new_text)
            return

    await add_user(chat_id, user_id)
    whitelisted_users = await get_whitelisted_users(chat_id)

    if user_id in whitelisted_users:
        await save_message(chat_id, user_id, username, first_name, text)
        return

    settings = await get_moderation_settings()
    BAD_WORDS_MUTE = settings["BAD_WORDS_MUTE"]
    BAD_WORDS_KICK = settings["BAD_WORDS_KICK"]
    BAD_WORDS_BAN = settings["BAD_WORDS_BAN"]
    MAX_MENTIONS = settings["MAX_MENTIONS"]
    MAX_EMOJIS = settings["MAX_EMOJIS"]
    MIN_CAPS_LENGTH = settings["MIN_CAPS_LENGTH"]
    MUTE_TIME = settings["MUTE_TIME"]
    DELETE_LINKS = settings["DELETE_LINKS"]
    DELETE_AUDIO = settings["DELETE_AUDIO"]
    DELETE_VIDEO = settings["DELETE_VIDEO"]
    DELETE_VIDEO_NOTES = settings["DELETE_VIDEO_NOTES"]
    DELETE_STICKERS = settings["DELETE_STICKERS"]
    DELETE_EMOJIS = settings["DELETE_EMOJIS"]
    DELETE_CHINESE = settings["DELETE_CHINESE"]
    DELETE_RTL = settings["DELETE_RTL"]
    DELETE_EMAILS = settings["DELETE_EMAILS"]
    DELETE_REFERRAL_LINKS = settings["DELETE_REFERRAL_LINKS"]
    EMOJI_LIST = settings["EMOJI_LIST"]

    text = re.sub(r"[^\w\s]", "", message.text.lower()) if message.text else ""
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)

    if any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_MUTE):
        await bot.delete_message(chat_id, message.message_id)

        # Час закінчення мута
        mute_end_time = datetime.now(timezone.utc) + timedelta(minutes=MUTE_TIME)

        # Мутимо користувача з автоматичним розмучуванням
        await bot.restrict_chat_member(
            chat_id, user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=mute_end_time
        )

        # Збереження мута в БД
        await sync_to_async(MutedUser.objects.update_or_create)(
            user_id=user_id, chats_names=chat,
            defaults={"first_name": username, "end_time": mute_end_time}
        )

        # Логування
        await save_message(message.message_id, chat_id, user_id, username, first_name, text, action="muted")
        await log_action(chat_id, user_id, username, "spam_deleted", "Muted for bad words", message.message_id)

        return

    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_KICK):
        await bot.delete_message(chat_id, message.message_id)
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)
        await save_message(message.message_id,chat_id, user_id, username, first_name, text, action="kicked")
        await log_action(chat_id, user_id, username, "spam_deleted", "Kicked for bad words", message.message_id)
        return

    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_BAN):

        await bot.delete_message(chat_id, message.message_id)

        # Встановлюємо час для бану (наприклад, на 10 хвилин) з використанням timezone

        ban_end_time = datetime.now(timezone.utc) + timedelta(minutes=10)

        await bot.ban_chat_member(chat_id, user_id, until_date=ban_end_time)

        await save_message(message.message_id, chat_id, user_id, username, first_name, text, action="banned")

        # Додаємо користувача до бази даних як заблокованого

        await sync_to_async(BannedUser.objects.get_or_create)(user_id=user_id, defaults={"first_name": username})

        await log_action(chat_id, user_id, username, "spam_deleted", "Banned for bad words", message.message_id)

        return

    if URL_PATTERN.search(message.text) and DELETE_LINKS:
        await bot.delete_message(chat_id, message.message_id)
        await save_message(message.message_id,chat_id, user_id, username, first_name, text, action="deleted_link")
        await log_action(chat_id, user_id, username, "spam_deleted", "Deleted link", message.message_id)
        return

    if text.count("@") >= MAX_MENTIONS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Too many mentions", message.message_id)
        return

    emoji_count = sum(1 for char in text if char in EMOJI_LIST)
    if emoji_count >= MAX_EMOJIS and DELETE_EMOJIS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Too many emojis", message.message_id)
        return

    caps_text = sum(1 for char in text if char.isupper())
    if caps_text >= MIN_CAPS_LENGTH and caps_text > len(text) * 0.7:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Excessive capitalization", message.message_id)
        return

    if message.audio and DELETE_AUDIO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Audio message deleted", message.message_id)
        return

    if message.video and DELETE_VIDEO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video message deleted", message.message_id)
        return

    if message.video_note and DELETE_VIDEO_NOTES:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video note deleted", message.message_id)
        return

    if message.sticker and DELETE_STICKERS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Sticker deleted", message.message_id)
        return

    if DELETE_CHINESE and any("\u4e00" <= char <= "\u9fff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Chinese characters deleted", message.message_id)
        return

    if DELETE_RTL and any("\u0590" <= char <= "\u08ff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "RTL characters deleted", message.message_id)
        return

    if DELETE_EMAILS and re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Email address deleted", message.message_id)
        return

    if DELETE_REFERRAL_LINKS and re.search(r"referral_link_pattern", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Referral link deleted", message.message_id)
        return

    await save_message(message.message_id,chat_id, user_id, username, first_name, text)
    await increment_message_count(user_id=user_id, chat_id=chat_id, name=first_name)






