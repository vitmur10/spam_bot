import os
from django.core.management.base import BaseCommand
from const import UserMessageCount

# Шлях до файлу з ID юзерів і чатів
file_path = 'while.txt'

if not os.path.exists(file_path):
    print(f"Файл {file_path} не знайдено!")
    exit()

# Зчитуємо файл і обробляємо рядки
with open(file_path, 'r', encoding='utf-8') as file:
    lines = file.readlines()

for line in lines:
    try:
        user_id, chat_id = map(int, line.strip().split(','))
    except ValueError:
        print(f"Невірний формат рядка: {line.strip()}")
        continue

    user_message, created = UserMessageCount.objects.get_or_create(
        user_id=user_id,
        chat_id=chat_id,
    )

    if not created:
        print(f"Запис для user_id={user_id}, chat_id={chat_id} вже існує.")

    user_message.message_count = 15
    user_message.save()

    print(f"Запис для user_id={user_id}, chat_id={chat_id} імпортовано/оновлено.")

print("Імпорт завершено!")
