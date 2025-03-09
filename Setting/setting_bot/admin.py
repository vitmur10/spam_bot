from django.contrib import admin
from django.http import HttpResponse
import csv
import json
from django.utils.timezone import now
from datetime import timedelta
from .models import *


@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "mute_time", "max_mentions", "max_emojis", "min_caps_length")


admin.site.register(BannedUser)
admin.site.register(MutedUser)
admin.site.register(Chats)

@admin.register(UserMessageCount)
class UserMessageCountAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'chat_id', 'name', 'message_count')  # Відображення колонок
    search_fields = ('name', 'user_id', 'chat_id')  # Додаємо пошук
    list_filter = ('chat_id',)  # Фільтр за чатом

@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username", "action_type", "chat_id", "user_id", "message_text")
    list_filter = ("action_type", "created_at")
    search_fields = ("username", "user_id", "message_text")
    ordering = ("-created_at",)

    actions = ["export_as_csv", "export_as_json", "delete_old_logs"]

    def export_as_csv(self, request, queryset):
        """Експорт логів у CSV"""
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="action_logs.csv"'

        writer = csv.writer(response, dialect="excel")
        writer.writerow(["created_at", "chat_id", "user_id", "username", "action_type", "message_text"])

        for log in queryset.iterator():
            writer.writerow([log.created_at, log.chat_id, log.user_id, log.username, log.action_type, log.message_text])

        return response

    export_as_csv.short_description = "Експортувати у CSV"

    def export_as_json(self, request, queryset):
        """Експорт логів у JSON"""
        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="action_logs.json"'

        logs = list(queryset.values("created_at", "chat_id", "user_id", "username", "action_type", "message_text"))

        # Перетворюємо `created_at` у строковий формат
        for log in logs:
            log["created_at"] = log["created_at"].isoformat()  # Перетворення в ISO-формат

        response.write(json.dumps(logs, ensure_ascii=False, indent=4))
        return response

    export_as_json.short_description = "Експортувати у JSON"

    def delete_old_logs(self, request, queryset):
        """Видалення старих логів (старших за 30 днів)"""
        delete_before = now() - timedelta(days=30)
        old_logs = queryset.filter(created_at__lt=delete_before)
        deleted_count, _ = old_logs.delete()

        self.message_user(request, f"Видалено {deleted_count} старих логів.")

    delete_old_logs.short_description = "Видалити логи старші за 30 днів"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'chat_id', 'is_banned', 'is_muted', 'mute_until', 'banned_at')
    list_filter = ('is_banned', 'is_muted')
    search_fields = ('user_id', 'chat_id')