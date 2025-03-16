from django.utils import timezone
from const import *  # або будь-які потрібні імпорти

# Отримуємо всі записи з UserMessageCount
user_message_counts = UserMessageCount.objects.all()

# Проходимо по кожному запису в UserMessageCount
for user_message_count in user_message_counts:
    # Отримуємо всі повідомлення для конкретного користувача та чату, відсортовані за часом (остання перше)
    messages = Message.objects.filter(user_id=user_message_count.user_id, chats_names=user_message_count.chats_names).order_by('-timestamp')

    # Перевіряємо, чи є повідомлення
    if messages.exists():
        # Останнє повідомлення (відсортоване за часом у спадному порядку)
        last_message = messages.first()
        last_message_date = last_message.timestamp

        # Оновлюємо дані у UserMessageCount
        user_message_count.last_message_date = last_message_date
        user_message_count.message_count = messages.count()  # Оновлюємо кількість повідомлень
        user_message_count.save()  # Зберігаємо зміни в базі даних

        # Виводимо повідомлення про успішне оновлення
        print(f"Updated UserMessageCount for user {user_message_count.user_id} in chat {user_message_count.chats_names.name} - Last Message: {last_message_date}, Message Count: {user_message_count.message_count}")
    else:
        # Якщо повідомлень не знайдено для цього користувача та чату
        print(f"No messages found for user {user_message_count.user_id} in chat {user_message_count.chats_names.name}")
