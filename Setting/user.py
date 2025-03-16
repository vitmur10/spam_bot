import asyncio
import os
from telegram import Bot, ChatMember
from telegram.ext import Updater
from dotenv import load_dotenv

load_dotenv()

# Токен вашого бота
API_TOKEN = os.getenv('TOKEN_BOT')
chat_id = '-1002273775768'  # Замініть на ваш Chat ID

# Створення об'єкта бота
bot = Bot(token=API_TOKEN)

# Створення асинхронного бота
async def collect_banned_and_muted_users(chat_id):
    banned_users = 0
    muted_users = 0
    all_users = []  # Список для збереження всіх користувачів

    try:
        # Отримуємо всіх адміністраторів чату
        members = await bot.get_chat_administrators(chat_id)

        # Перевіряємо кожного адміністратора
        for member in members:
            chat_member = await bot.get_chat_member(chat_id, member.user.id)

            # Додаємо всіх адміністраторів у список користувачів
            all_users.append(member.user.username if member.user.username else str(member.user.id))

            # Якщо користувач забанений
            if chat_member.status == ChatMember.BANNED:
                banned_users += 1
            # Якщо користувач замучений
            elif chat_member.status == ChatMember.RESTRICTED:
                muted_users += 1

        # Виведення всіх адміністраторів
        print(f"Усі адміністратори в чаті: {', '.join(all_users)}")
        print(f"Забанених користувачів: {banned_users}")
        print(f"Зам'ючених користувачів: {muted_users}")
        return {"banned": banned_users, "muted": muted_users}

    except Exception as e:
        print(f"Error: {e}")
        return {"banned": 0, "muted": 0}

# Запуск асинхронного виконання
async def main():
    result = await collect_banned_and_muted_users(chat_id)
    print(f"Результат: {result}")


# Виклик асинхронної функції
if __name__ == "__main__":
    asyncio.run(main())
