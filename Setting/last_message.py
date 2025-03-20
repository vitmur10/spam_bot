from django.utils.timezone import now
from const import *

def update_user_message_counts():
    users = User.objects.select_related('chats_names').all()

    for user in users:
        messages = Message.objects.filter(user_id=user.user_id, chats_names=user.chats_names).order_by('-timestamp')

        if messages.exists():
            last_message = messages.first()
            user.last_message_date = last_message.timestamp
            user.message_count = messages.count()
            user.save()

            print(f"Updated User for {user.user_id} in chat {user.chats_names.name} - Last Message: {last_message.timestamp}, Message Count: {user.message_count}")
        else:
            print(f"No messages found for user {user.user_id} in chat {user.chats_names.name}")

if __name__ == "__main__":
    update_user_message_counts()
