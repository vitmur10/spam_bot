import os
import django
from const import *
# Отримуємо всі моделі, які містять поле 'chats_names'
models_to_update = [
    "BannedUser",
    "MutedUser",
    "UserMessageCount",
    "ActionLog",
    "User",
    "Message",
]

# Завантажуємо всі чати у словник {chat_id: chat_instance}
chats_map = {chat.chat_id: chat for chat in Chats.objects.all()}

total_updated = 0

# Проходимо по всіх моделях
for model_name in models_to_update:
    model = apps.get_model("setting_bot", model_name)  # Отримуємо модель
    incorrect_objects = model.objects.exclude(
        chats_names_id__in=chats_map.keys())  # Обираємо записи без коректного chats_names

    updated_count = 0
    for obj in incorrect_objects:
        if obj.chat_id in chats_map:  # Якщо є відповідний чат
            obj.chats_names = chats_map[obj.chat_id]
            obj.save()
            updated_count += 1

    total_updated += updated_count
    print(f"Оновлено {updated_count} записів у {model_name}")

print(f"Загалом оновлено {total_updated} записів.")
