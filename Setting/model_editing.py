from const import ActionLog, MutedUser

def update_muted_users_with_chat_id_from_action_log():
    # Отримуємо всі записи про замутених користувачів в ActionLog
    action_logs = ActionLog.objects.filter(action_type="spam_deleted")  # Можна змінити action_type на потрібний

    # Проходимо через кожен запис і оновлюємо MutedUser
    for action_log in action_logs:
        user_id = action_log.user_id
        chat_id = action_log.chat_id

        # Перевіряємо, чи існує вже цей користувач у MutedUser
        try:
            muted_user = MutedUser.objects.get(user_id=user_id)
            muted_user.chat_id = chat_id
            muted_user.save()
            print(f"User {user_id} updated with chat_id {chat_id}")
        except MutedUser.DoesNotExist:
            print(f"Muted user {user_id} not found.")

    print("Muted users update completed.")

update_muted_users_with_chat_id_from_action_log()

