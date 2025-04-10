import asyncio
from datetime import timedelta

from aiogram import Router, F
from aiogram import types
from aiogram.filters import Filter
from aiogram.types import ChatPermissions, ChatMemberUpdated
from django.utils.timezone import now

from const import *

router = Router()
ChatPermissions(can_send_messages=False)

banned_users = []
muted_users = []


async def add_user(chat_id, user_id, first_name, username):
    # Отримуємо чат
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)

    # Отримуємо або створюємо користувача
    user, created = await sync_to_async(ChatUser.objects.get_or_create)(
        user_id=user_id,
        defaults={'username': username, 'first_name': first_name}
    )

    # Якщо не створено і first_name відрізняється — оновлюємо
    if not created and (not user.first_name or user.first_name != first_name):
        user.first_name = first_name
        await sync_to_async(user.save)()

    # Створюємо або отримуємо зв'язок з чатом (ChatMembership)
    membership, membership_created = await sync_to_async(ChatMembership.objects.get_or_create)(
        user=user,
        chat=chat,
        defaults={'status': 'Активний'}
    )

    # Якщо зв’язок уже був, але статус не "Активний", оновлюємо
    if not membership_created and membership.status != 'Активний':
        membership.status = 'Активний'
        await membership.save_async()

    return user, membership

def flatten_and_join(data):
    return [word for sublist in data for word in (sublist if isinstance(sublist, list) else [sublist])]

async def log_action(chat_id, user_id, username, first_name, action_type, info, message=None):
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)

    await sync_to_async(ActionLog.objects.create)(
        chat=chat,
        user_id=user_id,
        username=username,
        first_name = first_name,
        action_type=action_type,
        message=message,
        info=info
    )

async def clean_old_logs(days=30):
    delete_before = now() - timedelta(days=days)
    await sync_to_async(ActionLog.objects.filter(created_at__lt=delete_before).delete)()

async def is_chat_allowed(chat_id: int) -> bool:
    return await Chats.objects.filter(chat_id=chat_id).aexists()
# Фільтр для перевірки чату
class IsChatAllowed(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return await is_chat_allowed(message.chat.id)




async def get_muted_users():
    """Отримуємо список ChatMembership-ів замучених користувачів з повною інформацією про ChatUser"""
    now_plus_3 = datetime.now(timezone(timedelta(hours=3)))  # Київський час

    muted_users = await sync_to_async(list)(
        ChatMembership.objects
        .select_related('user')  # отримуємо ChatUser одразу
        .filter(is_muted=True, mute_until__lte=now_plus_3)
    )

    return muted_users

# Функція для отримання chats_names асинхронно
@sync_to_async
def get_chats_names(user):
    return user.chat

@sync_to_async
def get_chat_by_name(name):
    return Chats.objects.get(name=name)


async def auto_unban_unmute(bot: Bot):
    while True:
        # Отримуємо користувачів, яких потрібно розбанити або розмутити
        muted_users = await get_muted_users()  # Наприклад, User.objects.filter(is_muted=True)

        for membership in muted_users:
            # Перевіряємо, чи користувач мутований і чи настав час для розмутування
            if membership.is_muted and membership .mute_until <= datetime.now(timezone.utc):
                chats_names = await get_chats_names(membership )  # Отримуємо чат користувача
                chat = await get_chat_by_name(chats_names.name)  # Отримуємо сам чат
                username = membership.user.username
                first_name = membership.user.first_name
                user_id = membership.user.user_id
                # Логуємо дію в ActionLog
                await sync_to_async(ActionLog.objects.create)(  # Створюємо запис у базі
                    chat=chats_names,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    action_type='unmute_unban',
                    info=f"User {user_id} was unmuted and unbanned.",
                    created_at=datetime.now()
                )

                # Оновлюємо статус користувача на "unmuted"
                await membership.unmute()  # Викликаємо метод для зняття мутації

                # Оновлення статусу користувача в чаті (розмутування, розбанення)
                # Важливо використовувати методи ботів для обмежень, якщо потрібно
                print(chat.chat_id)
                chat_member = await bot.get_chat_member(chat.chat_id, user_id)
                print(chat_member.status)
                if chat_member.status != "creator":
                    await bot.restrict_chat_member(
                        chat_id=chat.chat_id,
                        user_id=user_id,
                        permissions=types.ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True
                        ),
                    )

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

    await add_user(chat_id, user_id,first_name, username)
    whitelisted_users = await get_whitelisted_users(chat_id)

    if user_id in whitelisted_users:
        await save_message(message.message_id, chat_id, user_id, username, first_name, text)
        return

    settings = await get_moderation_settings()
    if settings:
        BAD_WORDS_MUTE = settings.get("BAD_WORDS_MUTE", [])
        BAD_WORDS_MUTE = flatten_and_join(BAD_WORDS_MUTE)

        BAD_WORDS_KICK = settings.get("BAD_WORDS_KICK", [])
        BAD_WORDS_KICK = flatten_and_join(BAD_WORDS_KICK)

        BAD_WORDS_BAN = settings.get("BAD_WORDS_BAN", [])
        BAD_WORDS_BAN = flatten_and_join(BAD_WORDS_BAN)

        MAX_MENTIONS = settings.get("MAX_MENTIONS", [0])[0]
        MAX_EMOJIS = settings.get("MAX_EMOJIS", [0])[0]
        MIN_CAPS_LENGTH = settings.get("MIN_CAPS_LENGTH", [0])[0]
        MUTE_TIME = settings.get("MUTE_TIME", [0])[0]
        DELETE_LINKS = settings.get("DELETE_LINKS", [False])[0]
        DELETE_AUDIO = settings.get("DELETE_AUDIO", [False])[0]
        DELETE_VIDEO = settings.get("DELETE_VIDEO", [False])[0]
        DELETE_VIDEO_NOTES = settings.get("DELETE_VIDEO_NOTES", [False])[0]
        DELETE_STICKERS = settings.get("DELETE_STICKERS", [False])[0]
        DELETE_EMOJIS = settings.get("DELETE_EMOJIS", [False])[0]
        DELETE_CHINESE = settings.get("DELETE_CHINESE", [False])[0]
        DELETE_RTL = settings.get("DELETE_RTL", [False])[0]
        DELETE_EMAILS = settings.get("DELETE_EMAILS", [False])[0]
        DELETE_REFERRAL_LINKS = settings.get("DELETE_REFERRAL_LINKS", [False])[0]

        EMOJI_LIST = settings.get("EMOJI_LIST", [])
        EMOJI_LIST = flatten_and_join(EMOJI_LIST)
        flattened_emoji_list = [emoji for emojis in EMOJI_LIST for emoji in emojis]
    text = re.sub(r"[^\w\s]", "", (message.text or message.caption or "").lower())
    chat = await sync_to_async(Chats.objects.get)(chat_id=chat_id)
    # Коли користувач отримує мут
    if any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_MUTE):
        await bot.delete_message(chat_id, message.message_id)
        mute_end_time = datetime.now() + timedelta(minutes=MUTE_TIME)
        time_diff = mute_end_time - datetime.now()

        user, created = await sync_to_async(ChatUser.objects.get_or_create)(user_id=user_id, defaults={
            "username": username,
            "first_name": first_name,
        })

        # Всі чати, в яких є цей користувач
        memberships = await sync_to_async(list)(
            ChatMembership.objects.select_related("chat").filter(user=user)
        )

        # Замучити користувача у кожному чаті
        for membership in memberships:
            await membership.mute(mute_duration=time_diff)

            try:
                await bot.restrict_chat_member(
                    membership.chat.chat_id,
                    user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_end_time,
                )
            except Exception as e:
                print(f"Не вдалося замутити в чаті {membership.chat.chat_id}: {e}")

        matched_word = next((word for word in BAD_WORDS_MUTE if word.lower() in text), None)

        await log_action(
            chat_id,
            user_id,
            username,
            first_name,
            "spam_deleted",
            f"Користувач був замучений БОТОМ у всіх чатах за слово '{matched_word}' до {mute_end_time.strftime('%Y-%m-%d %H:%M:%S')}.",
            text,
        )
        return
    # Коли користувач отримує кік
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_KICK):
        await bot.delete_message(chat_id, message.message_id)
        await bot.ban_chat_member(chat_id, user_id)
        await bot.unban_chat_member(chat_id, user_id)

        user, created = await sync_to_async(ChatUser.objects.get_or_create)(user_id=user_id, chats_names=chat)

        matched_word = next((word for word in BAD_WORDS_KICK if re.sub(r"[^\w\s]", "", word).lower() in text), None)

        await log_action(
            chat_id, user_id, username,first_name, "spam_deleted",
            f"Kicked by bot for bad word: '{matched_word}'",
            text
        )
        return

    # Коли користувач отримує бан
    elif any(re.sub(r"[^\w\s]", "", word).lower() in text for word in BAD_WORDS_BAN):
        await bot.delete_message(chat_id, message.message_id)
        ban_end_time = now() + timedelta(minutes=10)

        user, _ = await sync_to_async(ChatUser.objects.get_or_create)(user_id=user_id, defaults={
            "username": username,
            "first_name": first_name,
        })

        memberships = await sync_to_async(list)(
            ChatMembership.objects.select_related("chat").filter(user=user)
        )

        for membership in memberships:
            await membership.ban()
            try:
                await bot.ban_chat_member(
                    membership.chat.chat_id,
                    user_id,
                    until_date=ban_end_time
                )
            except Exception as e:
                print(f"❌ Не вдалося забанити в чаті {membership.chat.chat_id}: {e}")

        matched_word = next((word for word in BAD_WORDS_BAN if re.sub(r"[^\w\s]", "", word).lower() in text), None)

        await log_action(
            chat_id,
            user_id,
            username,
            first_name,
            "spam_deleted",
            f"Користувач був забанений БОТОМ у всіх чатах за слово: '{matched_word}'",
            text
        )
        return
    if message.reply_markup:
        # Якщо в повідомленні є кнопки, видаляти його
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Deleted message with button",
                         text)
        return
    if message.text:
        if URL_PATTERN.search(message.text) and DELETE_LINKS:
            await bot.delete_message(chat_id, message.message_id)
            await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Deleted link", text)
            return

    if text.count("@") >= MAX_MENTIONS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Too many mentions", text)
        return
    try:
        emoji_count = sum(1 for char in message.text if char in flattened_emoji_list)
    except TypeError:
        return
    # Перевірка на кількість емодзі
    if emoji_count >= MAX_EMOJIS and DELETE_EMOJIS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username, first_name, "spam_deleted", "Too many emojis", text)
        return

    caps_text = sum(1 for char in text if char.isupper())
    if caps_text >= MIN_CAPS_LENGTH and caps_text > len(text) * 0.7:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Excessive capitalization", text)
        return

    elif message.audio and DELETE_AUDIO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Audio message deleted", text)
        return

    elif message.video and DELETE_VIDEO:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Video message deleted", text)
        return

    elif message.video_note and DELETE_VIDEO_NOTES:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Video note deleted", text)
        return

    elif message.sticker and DELETE_STICKERS:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Sticker deleted", text)
        return

    elif DELETE_CHINESE and any("\u4e00" <= char <= "\u9fff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Chinese characters deleted", text)
        return

    elif DELETE_RTL and any("\u0590" <= char <= "\u08ff" for char in message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "RTL characters deleted", text)
        return

    elif DELETE_EMAILS and re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Email address deleted", text)
        return

    elif DELETE_REFERRAL_LINKS and re.search(r"referral_link_pattern", message.text):
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Referral link deleted", text)
        return

    elif message.forward_from:
        await bot.delete_message(chat_id, message.message_id)
        await log_action(chat_id, user_id, username,first_name, "spam_deleted", "Deleted forwarded message", text)
        return
    elif message.from_user.username == "combot":
        await bot.delete_message(chat_id, message.message_id)
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
        user = await sync_to_async(ChatUser.objects.get)(user_id=target.user.id)
        membership, _ = await sync_to_async(ChatMembership.objects.update_or_create)(
            user=user,
            chat=chat,
            defaults={
                "is_banned": True,
                "banned_at": now(),
                "status": "ban"
            }
        )

    elif target.status == "restricted":
        action = "mute"
        info = f"Зам'ютив користувача @{target.user.username} ({target.user.id})"

        mute_end_time = None  # Тут ви можете додати час завершення, якщо він заданий
        user = await sync_to_async(ChatUser.objects.get)(user_id=target.user.id)
        membership, _ = await sync_to_async(ChatMembership.objects.update_or_create)(
            user=user,
            chat=chat,
            defaults={
                "is_muted": True,
                "mute_until": mute_end_time,
                "status": "Замучено"
            }
        )
        # Додаємо або оновлюємо запис в базі даних для зам'юченого користувача

    elif target.status == "member" and update.old_chat_member.status == "kicked":
        action = "unban"
        info = f"Розбанив користувача @{target.user.username} ({target.user.id})"

        # Оновлюємо статус користувача в базі даних (розбанюємо)
        user = await sync_to_async(ChatUser.objects.get)(user_id=target.user.id)
        membership, _ = await sync_to_async(ChatMembership.objects.update_or_create)(
            user_id=user,
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
        user = await sync_to_async(ChatUser.objects.get)(user_id=target.user.id)
        membership, _ = await sync_to_async(ChatMembership.objects.update_or_create)(
            user_id=user,
            chat=chat,
            defaults={
                "is_muted": False,
                "mute_until": None
            }
        )

    # Записуємо дію адміністратора в лог
    if action:
        await log_action(
            first_name=initiator.first_name,
            chat_id=update.chat.id,
            user_id=initiator.id,  # Ідентифікатор адміністратора
            username=initiator.username,  # Ім'я користувача адміністратора
            action_type=action,  # Тип дії (ban, mute, unban, unmute, delete_message)
            info=info)
