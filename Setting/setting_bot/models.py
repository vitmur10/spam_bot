from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from asgiref.sync import sync_to_async
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
    mute_time = models.IntegerField("Час мута (хвилини)", default=3600)

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
    chats_names = models.ForeignKey('Chats', on_delete=models.CASCADE)
    user_id = models.BigIntegerField(unique=True)
    first_name = models.CharField(max_length=255, blank=True, null=True)

    is_banned = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    mute_count = models.IntegerField(default=0)
    mute_until = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=50, null=True, blank=True)

    message_count = models.IntegerField(default=0)
    last_message_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user_id', 'chats_names')
        verbose_name = "Користувач"
        verbose_name_plural = "Користувачі"
        ordering = ['-last_message_date']

    def __str__(self):
        return f"User: {self.user_id} in Chat: {self.chats_names.name}"

    def chat_name(self):
        return self.chats_names.name if self.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

    @sync_to_async
    def save_async(self):
        self.save()

    async def ban(self):
        self.is_banned = True
        self.banned_at = now()
        await self.save_async()

    async def unban(self):
        self.is_banned = False
        self.banned_at = None
        await self.save_async()

    async def mute(self, mute_duration):
        self.is_muted = True
        self.mute_until = now() + mute_duration
        self.mute_count += 1
        await self.save_async()

    async def unmute(self):
        self.is_muted = False
        self.mute_until = None
        await self.save_async()

    async def update_message_count(self):
        self.message_count += 1
        self.last_message_date = now()
        await self.save_async()

    def get_status(self):
        if self.is_banned:
            return "Заблоковано"
        if self.is_muted and self.mute_until:
            return f"Замучено до {self.mute_until.strftime('%Y-%m-%d %H:%M:%S')}"
        return self.status or "Активний"




