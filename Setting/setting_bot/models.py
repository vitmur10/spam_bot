from django.db import models
from django.contrib.auth.models import User

class Chats(models.Model):
    chat_id = models.IntegerField("ІД чату")
    name = models.CharField("Назва чату", max_length=70)

    def __str__(self):
        return "Чат: {} ID {}".format(self.name, self.chat_id)

    class Meta:
        verbose_name = "Чати"
        verbose_name_plural = "Чати"


class ModerationSettings(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Модератор",
                             related_name="moderation_settings")

    mute_words = models.TextField("Слова для мута", help_text="Перераховуйте через кому",
                                  default="спам, флуд, лох, реклама, лохотрон")
    kick_words = models.TextField("Слова для кіку", help_text="Перераховуйте через кому",
                                  default="тролінг, деструктив, образа")
    ban_words = models.TextField("Слова для бану", help_text="Перераховуйте через кому",
                                 default="нацизм, расизм, тероризм, дитяче порно")

    max_mentions = models.IntegerField("Макс. теги", default=5)
    max_emojis = models.IntegerField("Макс. емодзі", default=10)
    min_caps_length = models.IntegerField("Мін. капс", default=10)
    mute_time = models.IntegerField("Час мута (секунди)", default=3600)

    delete_links = models.BooleanField("Видаляти повідомлення з посиланнями", default=True)
    delete_audio = models.BooleanField("Видаляти аудіозаписи", default=False)
    delete_video = models.BooleanField("Видаляти відео", default=False)
    delete_video_notes = models.BooleanField("Видаляти відеоповідомлення", default=False)
    delete_stickers = models.BooleanField("Видаляти стикери", default=False)
    delete_emojis = models.BooleanField("Видаляти занадто багато емодзі", default=True)
    delete_chinese = models.BooleanField("Видаляти китайські ієрогліфи", default=False)
    delete_rtl = models.BooleanField("Видаляти повідомлення з RTL символами", default=False)
    delete_emails = models.BooleanField("Видаляти email адреси", default=True)
    delete_referral_links = models.BooleanField("Видаляти реферальні посилання Telegram", default=True)

    emoji_list = models.TextField("Список емодзі", help_text="Перерахуйте емодзі без пробілів",
                                  default="😀😁😂🤣😃😄😅😆😉😊😋😎😜😝😛🤪🤩🤯🥳😇🥰😍😘")

    def __str__(self):
        return f"Налаштування {self.user.username}"

    class Meta:
        verbose_name = "Налаштування модерації"
        verbose_name_plural = "Налаштування модерації"



class BannedUser(models.Model):
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    banned_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        verbose_name = "Забанений користувач"
        verbose_name_plural = "Забанені користувачі"
        ordering = ["-banned_at"]

    def __str__(self):
        return f"{self.first_name} ({self.user_id})"

    def chat_name(self):  # Додаємо метод
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

class MutedUser(models.Model):
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = "Замучений користувач"
        verbose_name_plural = "Замучені користувачі"
        ordering = ["-end_time"]

    def __str__(self):
        return f"{self.first_name} ({self.user_id}) - Muted until {self.end_time}"


    def chat_name(self):  # Додаємо метод
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"



class UserMessageCount(models.Model):
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField()
    message_count = models.IntegerField(default=0)
    name = models.CharField(max_length=255, null=True, blank=True)
    last_message_date = models.DateTimeField(null=True, blank=True)  # Дата останнього повідомлення, тепер не обов'язкова

    class Meta:
        unique_together = ('user_id', 'chats_names')
        ordering = ['-last_message_date']
        verbose_name = "Кількість повідомлень користувача"
        verbose_name_plural = "Кількість повідомлень користувачів"

    def __str__(self):
        return f"User {self.user_id} ({self.name or 'No Name'}) in Chat {self.chats_names.name}: {self.message_count} messages, Last message: {self.last_message_date}"

    def chat_name(self):  # Додаємо метод
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

class Message(models.Model):
    message_id = models.BigIntegerField(unique=True, null=True, blank=True)
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField(null=True, blank=True)  # ID відправника
    username = models.CharField(max_length=255, null=True, blank=True)  # Юзернейм відправника
    first_name = models.CharField(max_length=255, null=True, blank=True)  # Ім'я відправника
    timestamp = models.DateTimeField()  # Час повідомлення
    message_text = models.TextField()  # Текст повідомлення
    action = models.CharField(max_length=50, null=True, blank=True)  # Дія з повідомленням (наприклад, "deleted", "muted", "banned")

    class Meta:
        verbose_name = "Повідомлення"
        verbose_name_plural = "Повідомлення"

    def __str__(self):
        return f"Chat {self.chats_names.name} | User {self.user_id} | {self.message_text[:30]} | Action: {self.action}"


    def chat_name(self):  # Додаємо метод
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

class ActionLog(models.Model):
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField()
    username = models.CharField(max_length=255, null=True, blank=True)
    action_type = models.CharField(max_length=50)  # Наприклад: 'spam_deleted', 'user_muted'
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='action_logs',
        null=True,
        blank=True )
    info = models.TextField(null=True, blank=True)  # Додане поле для зберігання деталей дії
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.username or self.user_id} ({self.created_at})"

    class Meta:
        verbose_name = "Журнал дій"
        verbose_name_plural = "Журнали дій"



class User(models.Model):
    chats_names = models.ForeignKey(Chats, on_delete=models.CASCADE)
    user_id = models.BigIntegerField(unique=True)
    is_banned = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    mute_until = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"

    def __str__(self):
        return f"User: {self.user_id} in Chat: {self.chats_names.name}"


    def chat_name(self):  # Додаємо метод
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"


