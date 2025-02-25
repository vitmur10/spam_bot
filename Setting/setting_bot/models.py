from django.db import models

class Chats(models.Model):
    chat_id = models.IntegerField("ІД чату")
    name = models.CharField("Назва чату", max_length=70)

    def __str__(self):
        return "Чат: {}".format(self.name)

    class Meta:
        verbose_name = "Чати"
        verbose_name_plural = "Чати"

class ModerationSettings(models.Model):
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

    emoji_list = models.TextField("Список емодзі", help_text="Перерахуйте емодзі без пробілів",
                                  default="😀😁😂🤣😃😄😅😆😉😊😋😎😜😝😛🤪🤩🤯🥳😇🥰😍😘")

    def __str__(self):
        return "Налаштування модерації"

    class Meta:
        verbose_name = "Налаштування модерації"
        verbose_name_plural = "Налаштування модерації"


class BannedUser(models.Model):
    user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    banned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Banned User"
        verbose_name_plural = "Banned Users"
        ordering = ["-banned_at"]

    def __str__(self):
        return f"{self.first_name} ({self.user_id})"

class MutedUser(models.Model):
    user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)
    end_time = models.DateTimeField()

    class Meta:
        verbose_name = "Muted User"
        verbose_name_plural = "Muted Users"
        ordering = ["-end_time"]

    def __str__(self):
        return f"{self.first_name} ({self.user_id}) - Muted until {self.end_time}"


class UserMessageCount(models.Model):
    user_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField()
    message_count = models.IntegerField(default=0)

    def __str__(self):
        return f"User {self.user_id} in Chat {self.chat_id}: {self.message_count} messages"


class ActionLog(models.Model):
    chat_id = models.BigIntegerField()
    user_id = models.BigIntegerField()
    username = models.CharField(max_length=255, null=True, blank=True)
    action_type = models.CharField(max_length=50)  # Наприклад: 'spam_deleted', 'user_muted'
    message_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.username or self.user_id} ({self.created_at})"