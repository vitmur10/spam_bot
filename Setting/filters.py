import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram import types
from aiogram.types import Message
from aiogram.types import ChatPermissions

from const import *

router = Router()
ChatPermissions(can_send_messages=False)

banned_users = []
muted_users = []


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

@router.message(F.text.startswith('/ban'))
async def ban_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return

    user_id = message.reply_to_message.from_user.id
    user_first_name = message.reply_to_message.from_user.first_name

    # Ban the user
    await bot.ban_chat_member(message.chat.id, user_id)

    # Add user to the banned users database
    BannedUser.objects.create(user_id=user_id, first_name=user_first_name)

    # Send confirmation message
    await message.answer(f'Покинув нас: {user_first_name}')


# Обробник для команди /unban
@router.message(F.text == '/unban')
async def unban_user(message: types.Message):
    user_id = message.reply_to_message.from_user.id

    try:
        banned_user = BannedUser.objects.get(user_id=user_id)
        await bot.unban_chat_member(message.chat.id, user_id)
        banned_user.delete()  # Remove from the database
        await message.answer(f"Користувач {user_id} розблокований.")
    except BannedUser.DoesNotExist:
        await message.answer(f"Користувач {user_id} не був забанений.")


# Обробник для команди /mute
@router.message(F.text.startswith('/mute'))
async def mute_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return

    try:
        muteint = int(message.text.split()[1])  # Мute duration
        mutetype = message.text.split()[2]  # Time unit (hour, minute, day)
        comment = " ".join(message.text.split()[3:])  # Reason for mute
    except IndexError:
        await message.answer('Бракує аргументів! Приклад: `/mute 1 хвилина причина`')
        return

    # Calculate mute end time
    if mutetype in ["г", "годин", "година"]:
        dt = datetime.now() + timedelta(hours=muteint)
    elif mutetype in ["х", "хвилин", "хвилини"]:
        dt = datetime.now() + timedelta(minutes=muteint)
    elif mutetype in ["д", "днів", "день"]:
        dt = datetime.now() + timedelta(days=muteint)
    else:
        await message.answer("Невідомий тип часу. Використовуйте 'г', 'х' або 'д'.")
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
    await message.answer(
        f' | <b>Рішення було прийняте:</b> {message.from_user.get_mention(as_html=True)}\n'
        f' | <b>Порушник:</b> <a href="tg://user?id={message.reply_to_message.from_user.id}">{message.reply_to_message.from_user.first_name}</a>\n'
        f'⏰ | <b>Термін покарання:</b> {muteint} {mutetype}\n'
        f' | <b>Причина:</b> {comment}',
        parse_mode='html'
    )


# Обробник для команди /unmute
@router.message(F.text == '/unmute')
async def unmute_user(message: types.Message):
    user_id = message.reply_to_message.from_user.id

    try:
        muted_user = MutedUser.objects.get(user_id=user_id)
        await bot.restrict_chat_member(message.chat.id, user_id, can_send_messages=True)
        muted_user.delete()  # Remove from the database
        await message.answer(f"Користувач {user_id} розмучений.")
    except MutedUser.DoesNotExist:
        await message.answer(f"Користувач {user_id} не був замучений.")


# Обробник для команди /banned_list
@router.message(F.text == '/banned_list')
async def banned_list(message: types.Message):
    banned_users = BannedUser.objects.all()
    if banned_users:
        banned_list_str = ""
        for user in banned_users:
            banned_list_str += f"🚫 Name: {user.first_name}, Забанений: {user.banned_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        await message.answer(f"Забанені користувачі:\n{banned_list_str}")
    else:
        await message.answer("Немає забанених користувачів.")


# Обробник для команди /muted_list
@router.message(F.text == '/muted_list')
async def muted_list(message: types.Message):
    muted_users = MutedUser.objects.all()
    if muted_users:
        muted_list_str = ""
        for user in muted_users:
            muted_list_str += f"🧑‍🦰 Name: {user.first_name}, Мут до: {user.end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        await message.answer(f"Замучені користувачі:\n{muted_list_str}")
    else:
        await message.answer("Немає замучених користувачів.")


@router.message(F.text.startswith('/kik'))
async def unban_user(message: Message, bot: Bot):
    # Check if the user is an admin
    if not await is_admin(message.chat.id, message.from_user.id):
        await message.answer("Тільки адміністратори можуть використовувати цю команду.")
        return

    # Ensure the command is a reply to a message
    if not message.reply_to_message:
        await message.answer("Ця команда має бути відповіддю на повідомлення!")
        return

    # Unban the user
    await bot.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)

    # Send confirmation message
    await message.answer(f'Покинув нас: {message.reply_to_message.from_user.first_name}')




@router.message()
async def filter_spam(message: Message, bot: Bot):
    text = message.text or ""

    # Перевірка на заборонені слова для МУТА
    if any(word in text.lower() for word in BAD_WORDS_MUTE):
        print(f"[MUTE] {message.from_user.full_name}: {text}")

        user_id = message.from_user.id
        mute_time = 10  # Мут на 10 хвилин
        current_time = datetime.now()

        # Видаляємо повідомлення
        await bot.delete_message(message.chat.id, message.message_id)

        # Замучуємо користувача
        await bot.restrict_chat_member(message.chat.id, user_id, ChatPermissions(can_send_messages=False))
        # Зберігаємо час, коли користувач був замучений
        muted_users.append({
            "user_id": user_id,
            "first_name": message.from_user.full_name,
            "end_time": current_time + timedelta(minutes=mute_time)
        })

        await message.answer(f"Користувач {message.from_user.full_name} замучений на {mute_time} хвилин.")

        # Перевірка через кожну секунду, чи настав час для розмуту
        while True:
            # Знаходимо замученого користувача
            muted_user = next((user for user in muted_users if user['user_id'] == user_id), None)

            if muted_user and muted_user['end_time'] <= datetime.now():
                # Розмучуємо користувача
                await bot.restrict_chat_member(message.chat.id, user_id, ChatPermissions(can_send_messages=True))
                await message.answer(f"Користувач {message.from_user.full_name} розмучений.")

                # Видаляємо запис про замученого користувача
                muted_users.remove(muted_user)
                break

            await asyncio.sleep(1)

    # Перевірка на заборонені слова для КІКА
    if any(word in text.lower() for word in BAD_WORDS_KICK):
        print(f"[KICK] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        await bot.ban_chat_member(message.chat.id, message.from_user.id)
        await bot.unban_chat_member(message.chat.id, message.from_user.id)  # Кік без бана
        return

    # Перевірка на заборонені слова для БАНУ
    if any(word in text.lower() for word in BAD_WORDS_BAN):
        print(f"[BAN] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        await bot.ban_chat_member(message.chat.id, message.from_user.id)
        return

    # Перевірка на посилання
    if URL_PATTERN.search(text):
        print(f"[LINK DETECTED] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        return

    # Перевірка на велику кількість @
    if text.count("@") >= MAX_MENTIONS:
        print(f"[TOO MANY MENTIONS] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        return

    # Перевірка на велику кількість емодзі
    emoji_count = sum(1 for char in text if char in "😀😁😂🤣😃😄😅😆😉😊😋😎😜😝😛🤪🤩🤯🥳😇🥰😍😘")
    if emoji_count >= MAX_EMOJIS:
        print(f"[TOO MANY EMOJIS] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        return

    # Перевірка на капс
    caps_text = sum(1 for char in text if char.isupper())
    if caps_text >= MIN_CAPS_LENGTH and caps_text > len(text) * 0.7:
        print(f"[CAPS DETECTED] {message.from_user.full_name}: {text}")
        await bot.delete_message(message.chat.id, message.message_id)
        return
