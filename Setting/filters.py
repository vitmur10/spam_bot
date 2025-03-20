import asyncio
from datetime import timedelta
from aiogram import Router
from aiogram import types
from aiogram.filters import Filter
from aiogram.types import Message, ChatPermissions, ChatMemberUpdated, InlineKeyboardButton
from django.utils.timezone import now

from const import *

router = Router()
ChatPermissions(can_send_messages=False)

banned_users = []
muted_users = []


async def add_user(chat_id, user_id,first_name):
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)
    user, created = await sync_to_async(User.objects.get_or_create)(
        user_id=user_id,
        chats_names=chat,
        first_name=first_name,
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

    # Отримуємо користувачів, у яких статус "muted" і час мута завершився
    muted_users = await sync_to_async(list)(User.objects.filter(is_muted=True, mute_until__lte=now_plus_3))

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
            if user.status == "muted" and user.end_time <= datetime.now(timezone.utc):  # Перевіряємо, чи статус "muted"
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

                # Оновлюємо статус на "unmuted"
                await sync_to_async(user.update)(  # Оновлюємо запис у базі
                    {"status": "unmuted"},
                    where={"user_id": user.user_id}  # Шукаємо за user_id
                )

                # Оскільки ви коментуєте код для скасування обмежень, додайте лише оновлення статусу:
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

    await add_user(chat_id, user_id, first_name)
    whitelisted_users = await get_whitelisted_users(chat_id)

    if user_id in whitelisted_users:
        await save_message(message.message_id, chat_id, user_id, username, first_name, text)
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

    # Коли користувач отримує мут
    if any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_MUTE):
        await bot.delete_message(chat_id, message.message_id)
        mute_end_time = datetime.now() + timedelta(minutes=MUTE_TIME)

        # Отримуємо користувача з БД або створюємо нового, якщо його немає
        user, created = await sync_to_async(User.objects.get_or_create)(user_id=user_id, chats_names=chat)

        # Різниця між поточним часом та часом завершення муту
        time_diff = mute_end_time - datetime.now()

        # Мутимо користувача, передаємо тривалість муту (timedelta)
        await user.mute(mute_duration=time_diff)
        await bot.restrict_chat_member(
            chat_id, user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=mute_end_time
        )
        # Зберігаємо лог дії
        matched_words = [word for word in BAD_WORDS_MUTE if re.sub(r"[^\w\s]", "", word).lower() in text]
        await save_message(
            message.message_id, chat_id, user_id, username, first_name, text,
            action="muted by bot"
        )
        await log_action(
            chat_id, user_id, username, "spam_deleted",
            f"Muted by bot for bad words: {', '.join(matched_words)}",
            message.message_id
        )
        return

    # Коли користувач отримує кік
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_KICK):
        await bot.delete_message(chat_id, message.message_id)
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)

        # Отримуємо користувача з БД або створюємо нового, якщо його немає
        user, created = await sync_to_async(User.objects.get_or_create)(user_id=user_id, chats_names=chat)

        # Зберігаємо лог дії
        matched_words = [word for word in BAD_WORDS_KICK if re.sub(r"[^\w\s]", "", word).lower() in text]
        await save_message(
            message.message_id, chat_id, user_id, username, first_name, text,
            action="kicked by bot"
        )
        await log_action(
            chat_id, user_id, username, "spam_deleted",
            f"Kicked by bot for bad words: {', '.join(matched_words)}",
            message.message_id
        )
        return

    # Коли користувач отримує бан
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_BAN):
        await bot.delete_message(chat_id, message.message_id)

        # Встановлюємо час для бану (наприклад, на 10 хвилин)
        ban_end_time = now() + timedelta(minutes=10)

        # Отримуємо користувача з БД або створюємо нового, якщо його немає
        user, created = await sync_to_async(User.objects.get_or_create)(user_id=user_id, chats_names=chat)
        await bot.ban_chat_member(chat_id, user_id, until_date=ban_end_time)

        # Банимо користувача
        user.ban()

        # Зберігаємо лог дії
        matched_words = [word for word in BAD_WORDS_BAN if re.sub(r"[^\w\s]", "", word).lower() in text]
        await save_message(
            message.message_id, chat_id, user_id, username, first_name, text,
            action="banned by bot"
        )
        await log_action(
            chat_id, user_id, username, "spam_deleted",
            f"Banned by bot for bad words: {', '.join(matched_words)}",
            message.message_id
        )
        return
    if message.reply_markup:
        # Якщо в повідомленні є кнопки, видаляти його
        await bot.delete_message(chat_id, message.message_id)
        await save_message(message.message_id, chat_id, user_id, username, first_name, text,
                           action="message_with_button_deleted")
        await log_action(chat_id, user_id, username, "spam_deleted", "Deleted message with button",
                         message.message_id)
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

    elif message.audio and DELETE_AUDIO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Audio message deleted", message.message_id)
        return

    elif message.video and DELETE_VIDEO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video message deleted", message.message_id)
        return

    elif message.video_note and DELETE_VIDEO_NOTES:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video note deleted", message.message_id)
        return

    elif message.sticker and DELETE_STICKERS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Sticker deleted", message.message_id)
        return

    elif DELETE_CHINESE and any("\u4e00" <= char <= "\u9fff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Chinese characters deleted", message.message_id)
        return

    elif DELETE_RTL and any("\u0590" <= char <= "\u08ff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "RTL characters deleted", message.message_id)
        return

    elif DELETE_EMAILS and re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Email address deleted", message.message_id)
        return

    elif DELETE_REFERRAL_LINKS and re.search(r"referral_link_pattern", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Referral link deleted", message.message_id)
        return

    elif message.forward_from:
        await bot.delete_message(chat_id, message.message_id)
        await save_message(message.message_id, chat_id, user_id, username, first_name, text,
                           action="forwarded_message_deleted")
        await log_action(chat_id, user_id, username, "spam_deleted", "Deleted forwarded message", message.message_id)
        return

    await save_message(message.message_id,chat_id, user_id, username, first_name, text)
    await increment_message_count(user_id=user_id, chat_id=chat_id, name=first_name)


@router.chat_member()
async def track_admin_actions(update: ChatMemberUpdated):
    initiator = update.from_user  # Користувач, який здійснив дію (адміністратор)
    target = update.new_chat_member  # Користувач, над яким була виконана дія (забанений/зам'ючений)

    action = None
    info = ""
    chat = await sync_to_async(Chats.objects.get)(chat_id=update.chat.id)  # Отримуємо чат, де відбулась дія

    # Визначаємо тип дії та збираємо інформацію про неї
    if target.status == "kicked":
        action = "ban"
        info = f"Забанив користувача @{target.user.username} ({target.user.id})"

        # Додаємо або оновлюємо запис в базі даних для забороненого користувача, використовуючи нову модель User
        await sync_to_async(User.objects.update_or_create)(
            user_id=target.user.id,
            chats_names=chat,
            defaults={
                "first_name": target.user.first_name,
                "is_banned": True,
                "banned_at": now(),
                "status": "ban"
            }
        )

    elif target.status == "restricted":
        action = "mute"
        info = f"Зам'ютив користувача @{target.user.username} ({target.user.id})"

        mute_end_time = None  # Тут ви можете додати час завершення, якщо він заданий

        # Додаємо або оновлюємо запис в базі даних для зам'юченого користувача
        await sync_to_async(User.objects.update_or_create)(
            user_id=target.user.id,
            chats_names=chat,
            defaults={
                "first_name": target.user.first_name,
                "is_muted": True,
                "mute_until": mute_end_time
            }
        )

    elif target.status == "member" and update.old_chat_member.status == "kicked":
        action = "unban"
        info = f"Розбанив користувача @{target.user.username} ({target.user.id})"

        # Оновлюємо статус користувача в базі даних (розбанюємо)
        await sync_to_async(User.objects.update_or_create)(
            user_id=target.user.id,
            chats_names=chat,
            defaults={
                "is_banned": False,
                "banned_at": None,
                "status": "active"
            }
        )

    elif target.status == "member" and update.old_chat_member.status == "restricted":
        action = "unmute"
        info = f"Розмутив користувача @{target.user.username} ({target.user.id})"

        # Оновлюємо статус користувача в базі даних (розмутуємо)
        await sync_to_async(User.objects.update_or_create)(
            user_id=target.user.id,
            chats_names=chat,
            defaults={
                "is_muted": False,
                "mute_until": None
            }
        )

    # Записуємо дію адміністратора в лог
    if action:
        await log_action(
            chat_id=update.chat.id,
            user_id=initiator.id,  # Ідентифікатор адміністратора
            username=initiator.username,  # Ім'я користувача адміністратора
            action_type=action,  # Тип дії (ban, mute, unban, unmute)
            info=info,  # Деталі про дію
            message_id=None  # Оскільки в цьому випадку message_id не використовується
        )