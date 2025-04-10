import json
from django.utils.timezone import make_aware
from datetime import datetime

from const import *

def import_chats():
    with open("chats_backup.json", "r", encoding="utf-8") as f:
        old_chats = json.load(f)

    for entry in old_chats:
        fields = entry["fields"]
        chat_id = fields["chat_id"]
        name = fields["name"]

        # створюємо Chat або отримуємо існуючий
        chat, created = Chats.objects.get_or_create(
            chat_id=chat_id,
            defaults={"name": name}
        )

        if created:
            print(f"Чат {name} з ID {chat_id} був створений.")
        else:
            print(f"Чат {name} з ID {chat_id} вже існує.")
    print("✅ Chats imported successfully.")

def import_users():
    with open("user_backup.json", "r", encoding="utf-8") as f:
        old_users = json.load(f)

    for entry in old_users:
        fields = entry["fields"]
        user_id = fields["user_id"]
        username = fields.get("username")
        first_name = fields.get("first_name")
        is_banned = fields.get("is_banned", False)
        is_muted = fields.get("is_muted", False)
        mute_count = fields.get("mute_count", 0)
        mute_until = fields.get("mute_until")
        banned_at = fields.get("banned_at")
        status = fields.get("status")
        message_count = fields.get("message_count", 0)
        last_message_date = fields.get("last_message_date")
        chat_id = fields["chats_names"]

        chat = Chats.objects.get(pk=chat_id)

        # створюємо ChatUser або отримуємо існуючого
        chat_user, _ = ChatUser.objects.get_or_create(user_id=user_id, defaults={
            "username": username,
            "first_name": first_name
        })

        # створюємо ChatMembership
        ChatMembership.objects.update_or_create(
            user=chat_user,
            chat=chat,
            defaults={
                "is_banned": is_banned,
                "is_muted": is_muted,
                "mute_count": mute_count,
                "mute_until": parse_datetime(mute_until),
                "banned_at": parse_datetime(banned_at),
                "status": status,
                "message_count": message_count,
                "last_message_date": parse_datetime(last_message_date),
            }
        )
    print("✅ Users imported successfully.")


def import_messages():
    # Читання даних з файлу
    with open("message_backup.json", "r", encoding="utf-8") as f:
        old_messages = json.load(f)

    for entry in old_messages:
        fields = entry["fields"]
        chat_id = fields["chats_names"]  # Отримання ID чату
        user_id = fields["user_id"]  # ID користувача
        message_id = fields["message_id"]  # ID повідомлення
        username = fields.get("username")  # Юзернейм
        first_name = fields.get("first_name")  # Ім'я користувача
        timestamp = fields.get("timestamp")  # Час повідомлення
        message_text = fields.get("message_text")  # Текст повідомлення
        action = fields.get("action")  # Дія (наприклад, "deleted", "muted", "banned")

        if not timestamp:
            print(f"Пропущено повідомлення з ID {message_id} через відсутність timestamp.")
            continue  # Пропустити повідомлення, якщо timestamp відсутній

        # Логування для перевірки формату дати
        print(f"Час повідомлення для ID {message_id}: {timestamp}")

        # Парсинг дати
        timestamp = parse_datetime(timestamp)

        if not timestamp:
            print(f"Не вдалося обробити дату для повідомлення з ID {message_id}. Пропускаємо.")
            continue  # Пропустити, якщо не вдалося обробити дату

        # Отримання чату та членства
        try:
            chat = Chats.objects.get(pk=chat_id)
        except Chats.DoesNotExist:
            print(f"Чат з ID {chat_id} не знайдений.")
            continue

        # Знаходимо членство (ChatMembership) на основі user_id і chat_id
        membership = ChatMembership.objects.filter(user__user_id=user_id, chat=chat).first()

        # Створення запису в моделі Message
        try:
            Message.objects.create(
                chats_names=chat,
                membership=membership,
                message_id=message_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
                timestamp=timestamp,
                message_text=message_text,
                action=action
            )
            print(f"✅ Повідомлення з ID {message_id} додано.")
        except Exception as e:
            print(f"Помилка при додаванні повідомлення з ID {message_id}: {e}")

def import_action_logs():
    with open("actionlog_backup.json", "r", encoding="utf-8") as f:
        logs = json.load(f)

    for entry in logs:
        fields = entry["fields"]
        chat_id = fields.get("chat")
        user_id = fields["user_id"]
        username = fields.get("username")
        first_name = fields.get("first_name")
        action_type = fields["action_type"]
        message = fields.get("message")
        info = fields.get("info")
        created_at = parse_datetime(fields.get("created_at"))

        chat = Chats.objects.get(pk=chat_id) if chat_id else None
        chat_user = ChatUser.objects.filter(user_id=user_id).first()
        membership = ChatMembership.objects.filter(user=chat_user, chat=chat).first() if chat else None

        ActionLog.objects.create(
            chat=chat,
            membership=membership,
            user_id=user_id,
            username=username,
            first_name=first_name,
            action_type=action_type,
            message=message,
            info=info,
            created_at=created_at
        )
    print("✅ ActionLogs imported successfully.")


def parse_datetime(dt_str):
    """Функція для парсингу дати і часу з рядка"""
    if not dt_str:
        return None
    try:
        # Видаляємо 'Z' з кінця, якщо є, щоб працювати з ISO форматом
        dt_str = dt_str.rstrip("Z")
        return make_aware(datetime.fromisoformat(dt_str))
    except ValueError:
        print(f"Не вдалося парсити дату в ISO форматі: {dt_str}")
        try:
            # Пробуємо інший формат (наприклад, через strptime)
            return make_aware(datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            print(f"Не вдалося парсити дату з формату: {dt_str}")
            return None

def run():
    import_chats()
    import_users()
    import_messages()
    import_action_logs()

if __name__ == "__main__":
    run()