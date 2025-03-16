import os
import django
from const import *
from datetime import datetime, timedelta
from django.utils import timezone

# Файл з повідомленнями
FILE_PATH = "messages.txt"

# Підключення до Django
django.setup()

# Імпортуємо необхідні моделі
from setting_bot.models import Message, Chats

def parse_message(line, message_counter):
    """Функція парсингу рядка з файлу"""
    try:
        parts = line.split(", ")
        chat_id = int(parts[0].split(": ")[1])
        user_id = int(parts[1].split(": ")[1]) if "Unknown" not in parts[1] else None
        username = parts[2].split(": ")[1] if parts[2].split(": ")[1] != "NoUsername" else None
        first_name = parts[3].split(": ")[1] if parts[3].split(": ")[1] != "NoFirstName" else None
        timestamp = datetime.strptime(parts[4].split(": ")[1], "%Y-%m-%d %H:%M:%S")

        # ✅ Додаємо часовий пояс до timestamp
        timestamp = timezone.make_aware(timestamp, timezone.get_default_timezone())

        # Оновлюємо timestamp, щоб кожне повідомлення мало унікальний час
        # Зсув часу для кожного повідомлення
        timestamp += timedelta(seconds=message_counter)

        message_text = parts[5].split(": ", 1)[1]
        return chat_id, user_id, username, first_name, timestamp, message_text
    except Exception as e:
        print(f"❌ Помилка парсингу рядка: {line} | {e}")
        return None

def import_messages():
    """Функція імпорту повідомлень у базу"""
    if not os.path.exists(FILE_PATH):
        print(f"❌ Файл {FILE_PATH} не знайдено!")
        return

    with open(FILE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    messages_to_create = []
    message_counter = 0  # Лічильник для зсуву часу

    for line in lines:
        parsed = parse_message(line.strip(), message_counter)
        if parsed:
            chat_id, user_id, username, first_name, timestamp, message_text = parsed

            # Отримуємо відповідний об'єкт Chats за chat_id
            try:
                chat = Chats.objects.get(chat_id=chat_id)
            except Chats.DoesNotExist:
                print(f"❌ Чат з chat_id {chat_id} не знайдений. Пропускаємо повідомлення.")
                continue

            # Створюємо нове повідомлення і додаємо в список для збереження
            messages_to_create.append(
                Message(
                    chats_names=chat,  # заміняємо chat_id на chat_name, що є ForeignKey
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    timestamp=timestamp,
                    message_text=message_text,
                )
            )

            # Збільшуємо лічильник, щоб наступне повідомлення мало зсув на 1 секунду більше
            message_counter += 1

    # Масове збереження у базу
    Message.objects.bulk_create(messages_to_create)
    print(f"✅ Імпортовано {len(messages_to_create)} повідомлень у базу!")

if __name__ == "__main__":
    import_messages()
