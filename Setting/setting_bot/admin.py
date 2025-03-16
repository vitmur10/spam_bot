from django.contrib import admin
from django.http import HttpResponse
import csv
import json
from django.utils.timezone import now
from datetime import timedelta
from .models import *


@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    # Додаємо поле `id` у `list_display`
    list_display = ("id", "user", "mute_time", "max_mentions", "max_emojis", "min_caps_length", "mute_words", "kick_words", "ban_words", "emoji_list")

    # Додаємо поле `id` у `fields_admin`, оскільки воно є в базі даних, але за замовчуванням приховане
    fields_admin = ['id'] + [field.name for field in ModerationSettings._meta.fields if field.name != 'id']

    readonly_fields = ('id',)  # `id` за замовчуванням readonly

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.fields_admin
        return []

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superuser:
            obj.user = request.user
        obj.save()


admin.site.register(BannedUser)
admin.site.register(MutedUser)
admin.site.register(Chats)


@admin.register(UserMessageCount)
class UserMessageCountAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'chat_name', 'name', 'message_count', 'last_message_date')
    search_fields = ('name', 'user_id')
    list_filter = ('chats_names', 'last_message_date')  # Було: chat_name
    ordering = ('-last_message_date',)
    readonly_fields = ('last_message_date',)

    def chat_name(self, obj):  # Додаємо метод для повернення назви чату
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"  # Опис для стовпця


from django.utils.html import format_html

@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username", "action_type", "chat_name", "user_id", "message_text", "info")  # Додано поле info
    list_filter = ("action_type", "created_at", "chats_names")
    search_fields = ("username", "user_id", "message_text", "info")  # Додано поле info для пошуку
    ordering = ("-created_at",)

    actions = ["export_as_csv", "export_as_json", "delete_old_logs"]

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="action_logs.csv"'

        writer = csv.writer(response, dialect="excel")
        writer.writerow(["created_at", "chat_name", "user_id", "username", "action_type", "message_text", "info"])

        for log in queryset.iterator():
            message_text = log.message.message_text if log.message else "Без тексту"
            info = log.info if log.info else "Без додаткової інформації"  # Додано info
            writer.writerow([log.created_at, log.chats_names, log.user_id, log.username, log.action_type, message_text, info])

        return response

    export_as_csv.short_description = "Експортувати у CSV"

    def export_as_json(self, request, queryset):
        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="action_logs.json"'

        logs = list(queryset.values("created_at", "chat_name", "user_id", "username", "action_type", "message", "info"))

        for log in logs:
            log["created_at"] = log["created_at"].isoformat()
            log["message_text"] = log["message"]["message_text"] if log["message"] else "Без тексту"
            log["info"] = log["info"] if log["info"] else "Без додаткової інформації"  # Додано info

        response.write(json.dumps(logs, ensure_ascii=False, indent=4))
        return response

    export_as_json.short_description = "Експортувати у JSON"

    def delete_old_logs(self, request, queryset):
        delete_before = now() - timedelta(days=30)
        old_logs = queryset.filter(created_at__lt=delete_before)
        deleted_count, _ = old_logs.delete()

        self.message_user(request, f"Видалено {deleted_count} старих логів.")

    delete_old_logs.short_description = "Видалити логи старші за 30 днів"

    def chat_name(self, obj):
        return obj.chats_names.name if obj.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

    def message_text(self, obj):
        # Зробити поле message_text клікабельним, щоб перейти на відповідне повідомлення
        return format_html('<a href="/admin/setting_bot/message/{}/change/">{}</a>', obj.message.id, obj.message.message_text) if obj.message else "Без тексту"

    message_text.short_description = "Текст повідомлення"

    # Додаємо метод для отримання info
    def info(self, obj):
        return obj.info if obj.info else "Без додаткової інформації"

    info.short_description = "Інформація"





@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'chat_name', 'is_banned', 'is_muted', 'mute_until', 'banned_at')
    list_filter = ('is_banned', 'is_muted', 'chats_names')  # Corrected: using chats_names as the filter
    search_fields = ('user_id',)

    def chat_name(self, obj):  # Method to return the chat name
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat_name", "user_id", "username", "first_name", "timestamp", "short_message", "action")  # Використовуємо chat_name замість chats_names
    search_fields = ("username", "first_name", "message_text")
    list_filter = ("chats_names", "timestamp")  # Це залишимо для фільтрації по chats_names
    ordering = ("-timestamp",)

    def short_message(self, obj):
        return obj.message_text[:50] + "..." if len(obj.message_text) > 50 else obj.message_text

    short_message.short_description = "Повідомлення"

    def chat_name(self, obj):  # Додаємо метод для повернення назви чату
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"  # Опис для стовпця