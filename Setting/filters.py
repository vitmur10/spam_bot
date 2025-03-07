import asyncio
from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram import types
from aiogram.types import Message
from aiogram.types import ChatPermissions
from aiogram.filters import Filter, Command
from django.db.models import Exists, OuterRef
from const import *
from django.utils.timezone import now

router = Router()
ChatPermissions(can_send_messages=False)

banned_users = []
muted_users = []

async def add_user(chat_id, user_id):
    user, created = await sync_to_async(User.objects.get_or_create)(
        user_id=user_id,
        chat_id=chat_id
    )
    return user, created

async def mute_user(user_id, chat_id):
    user = await sync_to_async(User.objects.get)(user_id=user_id)
    user.is_muted = True
    user.mute_until = timezone.now() + timedelta(hours=24)  # Наприклад, на 24 години
    await sync_to_async(user.save)()

    # Мутити користувача в Telegram
    await bot.restrict_chat_member(chat_id, user_id, permissions={'can_send_messages': False})
    return user

async def unmute_user(user_id, chat_id):
    user = await sync_to_async(User.objects.get)(user_id=user_id)
    user.is_muted = False
    user.mute_until = None
    await sync_to_async(user.save)()

    # Розмутити користувача в Telegram
    await bot.restrict_chat_member(chat_id, user_id, permissions={'can_send_messages': True})
    return user

async def ban_user(user_id, chat_id):
    user = await sync_to_async(User.objects.get)(user_id=user_id)
    user.is_banned = True
    user.banned_at = timezone.now()
    await sync_to_async(user.save)()

    # Банити користувача в Telegram
    await bot.ban_chat_member(chat_id, user_id)
    return user

async def unban_user(user_id, chat_id):
    user = await sync_to_async(User.objects.get)(user_id=user_id)
    user.is_banned = False
    user.banned_at = None
    await sync_to_async(user.save)()

    # Розбанити користувача в Telegram
    await bot.unban_chat_member(chat_id, user_id)
    return user


async def log_action(chat_id, user_id, username, action_type, message_text=None):
    await sync_to_async(ActionLog.objects.create)(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        action_type=action_type,
        message_text=message_text
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


"""async def auto_unban_unmute(bot: Bot):
    while True:
        now_time = datetime.now()

        # Отримуємо всіх користувачів, яким вже можна зняти мут або бан
        muted_users = await MutedUser.filter(end_time__lte=now_time)

        for user in muted_users:
            try:
                # Знімаємо обмеження в чаті (розмут/розбан)
                await bot.restrict_chat_member(
                    chat_id=CHAT_ID,
                    user_id=user.user_id,
                    permissions=types.ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True
                    ),
                )
                print(f"Розмучено/розбанено користувача {user.user_id}")

                # Видаляємо запис з бази після зняття обмежень
                await user.delete()
            except Exception as e:
                print(f"Помилка при знятті мута/бану для {user.user_id}: {e}")

        # Чекаємо 60 секунд перед наступною перевіркою
        await asyncio.sleep(60)
"""
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


@router.message(IsChatAllowed(), F.text.startswith('/ban'))
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
    #await message.answer(f'Покинув нас: {user_first_name}')


# Обробник для команди /unban
"""@router.message(F.text == '/unban')
async def unban_user(message: types.Message):
    user_id = message.reply_to_message.from_user.id

    try:
        banned_user = BannedUser.objects.get(user_id=user_id)
        await bot.unban_chat_member(message.chat.id, user_id)
        banned_user.delete()  # Remove from the database
        #await message.answer(f"Користувач {user_id} розблокований.")
    except BannedUser.DoesNotExist:
        await message.answer(f"Користувач {user_id} не був забанений.")"""


# Обробник для команди /mute
@router.message(IsChatAllowed(),F.text.startswith('/mute'))
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
    )

    # Send confirmation
"""    await message.answer(
        f' | <b>Рішення було прийняте:</b> {message.from_user.get_mention(as_html=True)}\n'
        f' | <b>Порушник:</b> <a href="tg://user?id={message.reply_to_message.from_user.id}">{message.reply_to_message.from_user.first_name}</a>\n'
        f'⏰ | <b>Термін покарання:</b> {muteint} {mutetype}\n'
        f' | <b>Причина:</b> {comment}',
        parse_mode='html'
    )"""


# Обробник для команди /unmute
"""@router.message(IsChatAllowed(),F.text == '/unmute')
async def unmute_user(message: types.Message):
    user_id = message.reply_to_message.from_user.id

    try:
        muted_user = MutedUser.objects.get(user_id=user_id)
        await bot.restrict_chat_member(message.chat.id, user_id, can_send_messages=True)
        muted_user.delete()  # Remove from the database
        await message.answer(f"Користувач {user_id} розмучений.")
    except MutedUser.DoesNotExist:
        await message.answer(f"Користувач {user_id} не був замучений.")"""


# Обробник для команди /banned_list
"""@router.message(IsChatAllowed(),F.text == '/banned_list')
async def banned_list(message: types.Message):
    banned_users = BannedUser.objects.all()
    if banned_users:
        banned_list_str = ""
        for user in banned_users:
            banned_list_str += f"🚫 Name: {user.first_name}, Забанений: {user.banned_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        await message.answer(f"Забанені користувачі:\n{banned_list_str}")
    else:
        await message.answer("Немає забанених користувачів.")"""


# Обробник для команди /muted_list
"""@router.message(IsChatAllowed(),F.text == '/muted_list')
async def muted_list(message: types.Message):
    muted_users = MutedUser.objects.all()
    if muted_users:
        muted_list_str = ""
        for user in muted_users:
            muted_list_str += f"🧑‍🦰 Name: {user.first_name}, Мут до: {user.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        await message.answer(f"Замучені користувачі:\n{muted_list_str}")
    else:
        await message.answer("Немає замучених користувачів.")"""


@router.message(IsChatAllowed(),F.text.startswith('/kik'))
async def unban_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        #await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        #await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return


@router.message(IsChatAllowed())
async def filter_spam(message: Message, bot: Bot):
    user_id = message.from_user.id
    first_name = message.from_user.full_name
    username = message.from_user.username
    chat_id = message.chat.id
    await add_user(chat_id, user_id)

    whitelisted_users = await get_whitelisted_users()

    if user_id in whitelisted_users:
        return  # Якщо юзер у білому списку – не перевіряємо його

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

    # Перевірка на заборонені слова для MUTE
    if any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_MUTE):
        await bot.delete_message(chat_id, message.message_id)
        await bot.restrict_chat_member(chat_id, user_id, ChatPermissions(can_send_messages=False))

        mute_end_time = now() + timedelta(minutes=MUTE_TIME / 60)

        # Додаємо користувача до MutedUser
        await sync_to_async(MutedUser.objects.update_or_create)(
            user_id=user_id,
            defaults={"first_name": first_name, "end_time": mute_end_time}
        )

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на заборонені слова для KICK
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_KICK):
        await bot.delete_message(chat_id, message.message_id)
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на заборонені слова для BAN
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_BAN):
        await bot.delete_message(chat_id, message.message_id)
        await bot.ban_chat_member(chat_id, user_id)

        # Додаємо користувача до BannedUser
        await sync_to_async(BannedUser.objects.get_or_create)(user_id=user_id, defaults={"first_name": first_name})

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на посилання
    if URL_PATTERN.search(message.text) and DELETE_LINKS:
        await bot.delete_message(message.chat.id, message.message_id)

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на велику кількість @
    if text.count("@") >= MAX_MENTIONS:
        await bot.delete_message(message.chat.id, message.message_id)

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на велику кількість емодзі
    emoji_count = sum(1 for char in text if char in EMOJI_LIST)
    if emoji_count >= MAX_EMOJIS and DELETE_EMOJIS:
        await bot.delete_message(message.chat.id, message.message_id)

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на капс
    caps_text = sum(1 for char in text if char.isupper())
    if caps_text >= MIN_CAPS_LENGTH and caps_text > len(text) * 0.7:
        await bot.delete_message(message.chat.id, message.message_id)

        # Логуємо дію
        await log_action(chat_id, user_id, username, "spam_deleted", message.text)

        return  # Завершуємо функцію

    # Перевірка на видалення аудіо
    if message.audio and DELETE_AUDIO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Audio message")
        return

    # Перевірка на видалення відео
    if message.video and DELETE_VIDEO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video message")
        return

    # Перевірка на видалення відеосообщень
    if message.video_note and DELETE_VIDEO_NOTES:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Video note")
        return

    # Перевірка на видалення стикерів
    if message.sticker and DELETE_STICKERS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Sticker")
        return

    # Перевірка на китайські ієрогліфи
    if DELETE_CHINESE and any("\u4e00" <= char <= "\u9fff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Chinese characters")
        return

    # Перевірка на RTL символи
    if DELETE_RTL and any("\u0590" <= char <= "\u08ff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "RTL characters")
        return

    # Перевірка на email адреси
    if DELETE_EMAILS and re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Email address")
        return

    # Перевірка на реферальні посилання
    if DELETE_REFERRAL_LINKS and re.search(r"referral_link_pattern", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, "spam_deleted", "Referral link")
        return

    # Якщо повідомлення пройшло всі перевірки, збільшуємо лічильник повідомлень
    await increment_message_count(user_id=user_id, chat_id=chat_id)


