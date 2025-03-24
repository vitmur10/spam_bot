import asyncio
import csv
import json
import os
from datetime import timedelta
from django.utils.html import format_html
from django.contrib import admin
from django.http import HttpResponse
from .views import *
from .models import *
from django import forms
from django.urls import reverse



@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "mute_time", "max_mentions", "max_emojis", "min_caps_length",
                     "mute_words", "kick_words", "ban_words", "emoji_list")

    fields_admin = ['id'] + [field.name for field in ModerationSettings._meta.fields if field.name != 'id']
    moderator_fields = ['mute_words', 'kick_words', 'ban_words']

    readonly_fields = ('id',)

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.fields_admin
        return self.moderator_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not request.user.is_superuser:
            obj.user = request.user
        obj.save()




admin.site.register(Chats)


class MuteUserInlineForm(forms.Form):
    mute_duration = forms.IntegerField(
        min_value=1,
        label="Тривалість мутації (в хвилинах)",
        help_text="Введіть кількість хвилин, на скільки мутити користувача."
    )


class ActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "username", "first_name", "action_type", "chat_name", "user_link", "message", "info",
        'mute_duration_field'
    )
    list_filter = ("action_type", "created_at", "chats_names")
    search_fields = ("username", "user_id", "message", "info")
    ordering = ("-created_at",)

    actions = ["export_as_csv", "export_as_json", "delete_old_logs", "ban_user", "unban_user", "mute_user", "unmute_user"]

    def user_link(self, obj):
        try:
            user = User.objects.get(user_id=obj.user_id)
            url = reverse("admin:setting_bot_user_change", args=[user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user_id)
        except User.DoesNotExist:
            return obj.user_id
    user_link.short_description = "User ID"

    # Поле для введення тривалості мутації
    def mute_duration_field(self, obj):
        form = MuteUserInlineForm(initial={'mute_duration': 5})  # Встановлюємо стандартне значення
        return form.as_p()

    mute_duration_field.short_description = 'Тривалість мутації'

    # Метод для блокування користувачів
    def ban_user(self, request, queryset):
        for log in queryset:
            try:
                user = User.objects.get(user_id=log.user_id)
            except User.DoesNotExist:
                continue  # Якщо користувача не знайдено, пропускаємо
            if user:
                asyncio.run(user.ban())
                ActionLog.objects.create(
                    chats_names=user.chats_names,
                    user_id=user.user_id,
                    action_type="user_banned",
                    info=f"Заблоковано користувача {user.first_name} ({user.user_id})",
                )
                ban_user_telegram(user.chats_names.chat_id, user.user_id)

    ban_user.short_description = "Заблокувати користувачів"

    # Метод для розблокування користувачів
    def unban_user(self, request, queryset):
        for log in queryset:
            try:
                user = User.objects.get(user_id=log.user_id)
            except User.DoesNotExist:
                continue  # Якщо користувача не знайдено, пропускаємо
            if user:
                asyncio.run(user.unban())
                ActionLog.objects.create(
                    chats_names=user.chats_names,
                    user_id=user.user_id,
                    action_type="user_unbanned",
                    info=f"Розблоковано користувача {user.first_name} ({user.user_id})",
                )
                unban_user_telegram(user.chats_names.chat_id, user.user_id)

    unban_user.short_description = "Розблокувати користувачів"

    # Метод для мутації користувачів
    def mute_user(self, request, queryset):
        mute_duration = request.POST.get('mute_duration', None)
        if mute_duration:
            mute_duration = timedelta(minutes=int(mute_duration))
            for log in queryset:
                try:
                    user = User.objects.get(user_id=log.user_id)
                except User.DoesNotExist:
                    continue  # Якщо користувача не знайдено, пропускаємо
            if user:
                asyncio.run(user.mute(mute_duration))
                ActionLog.objects.create(
                    chats_names=user.chats_names,
                    user_id=user.user_id,
                    action_type="user_muted",
                    info=f"Замучено користувача {user.first_name} ({user.user_id}) до {user.mute_until}",
                )
                mute_user_telegram(user.chats_names.chat_id, user.user_id, mute_duration)

    mute_user.short_description = "Замутити користувачів"

    # Метод для розмутації користувачів
    def unmute_user(self, request, queryset):
        for log in queryset:
            try:
                user = User.objects.get(user_id=log.user_id)
            except User.DoesNotExist:
                continue  # Якщо користувача не знайдено, пропускаємо
            if user:
                asyncio.run(user.unmute())
                ActionLog.objects.create(
                    chats_names=log.chats_names,
                    user_id=user.user_id,
                    action_type="user_unmuted",
                    info=f"Розмучено користувача {user.first_name} ({user.user_id})",
                )
                unmute_user_telegram(log.chats_names.chat_id, user.user_id)

    unmute_user.short_description = "Розмутити користувачів"

    # Експортуємо в CSV
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="action_logs.csv"'
        writer = csv.writer(response, dialect="excel")
        writer.writerow(["created_at", "chat_name", "user_id", "username", "action_type", "message_text", "info"])

        for log in queryset.iterator():
            message_text = log.message.message_text if log.message else "Без тексту"
            info = log.info if log.info else "Без додаткової інформації"
            writer.writerow(
                [log.created_at, log.chats_names, log.user_id, log.username, log.action_type, message_text, info])

        return response

    export_as_csv.short_description = "Експортувати у CSV"

    # Експортуємо в JSON
    def export_as_json(self, request, queryset):
        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="action_logs.json"'

        logs = list(queryset.values("created_at", "chat_name", "user_id", "username", "action_type", "message", "info"))

        for log in logs:
            log["created_at"] = log["created_at"].isoformat()
            log["message_text"] = log["message"]["message_text"] if log["message"] else "Без тексту"
            log["info"] = log["info"] if log["info"] else "Без додаткової інформації"

        response.write(json.dumps(logs, ensure_ascii=False, indent=4))
        return response

    export_as_json.short_description = "Експортувати у JSON"

    # Видалити старі логи
    def delete_old_logs(self, request, queryset):
        delete_before = now() - timedelta(days=30)
        old_logs = queryset.filter(created_at__lt=delete_before)
        deleted_count, _ = old_logs.delete()
        self.message_user(request, f"Видалено {deleted_count} старих логів.")

    delete_old_logs.short_description = "Видалити логи старші за 30 днів"

    def chat_name(self, obj):
        return obj.chats_names.name if obj.chats_names else "Без чату"

    chat_name.short_description = "Назва чату"

    def info(self, obj):
        return obj.info if obj.info else "Без додаткової інформації"

    info.short_description = "Інформація"


admin.site.register(ActionLog, ActionLogAdmin)




# Форма для введення тривалості мутації



class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username", 'first_name', "chat_name", 'get_status', 'mute_count', 'is_banned',
        'is_muted', 'mute_duration_field', 'message_count_link', 'action_log_link'
    )
    actions = ['ban_user', 'unban_user', 'mute_user', 'unmute_user']
    list_filter = ('is_banned', 'is_muted', 'chats_names')
    search_fields = ('first_name', 'user_id', 'chats_names__name')
    ordering = ('-last_message_date',)

    # Поле для введення тривалості мутації
    def mute_duration_field(self, obj):
        form = MuteUserInlineForm(initial={'mute_duration': 5})
        return form.as_p()

    mute_duration_field.short_description = 'Тривалість мутації'

    # Посилання на фільтровані повідомлення
    def message_count_link(self, obj):
        url = reverse('admin:setting_bot_message_changelist') + f'?user_id={obj.user_id}'
        return format_html('<a href="{}">{}</a>', url, obj.message_count)
    message_count_link.short_description = 'Кількість повідомлень'

    # Посилання на ActionLog
    def action_log_link(self, obj):
        url = reverse('admin:setting_bot_actionlog_changelist') + f'?user_id={obj.user_id}'
        return format_html('<a href="{}">Переглянути дії</a>', url)
    action_log_link.short_description = 'Логи дій'

    # Відображення статусу користувача
    def get_status(self, obj):
        return "Заблоковано" if obj.is_banned else "Активний"
    get_status.short_description = 'Статус'


    # Дії з користувачами
    def ban_user(self, request, queryset):
        for user in queryset:
            asyncio.run(user.ban())
            ActionLog.objects.create(
                chats_names=user.chats_names,
                user_id=user.user_id,
                action_type="user_banned",
                info=f"Заблоковано користувача {user.first_name} ({user.user_id})",
            )
            ban_user_telegram(user.chats_names.chat_id, user.user_id)
    ban_user.short_description = "Заблокувати користувачів"

    def unban_user(self, request, queryset):
        for user in queryset:
            asyncio.run(user.unban())
            ActionLog.objects.create(
                chats_names=user.chats_names,
                user_id=user.user_id,
                action_type="user_unbanned",
                info=f"Розблоковано користувача {user.first_name} ({user.user_id})",
            )
            unban_user_telegram(user.chats_names.chat_id, user.user_id)
    unban_user.short_description = "Розблокувати користувачів"

    def mute_user(self, request, queryset):
        mute_duration = request.POST.get('mute_duration', None)
        if mute_duration:
            mute_duration = timedelta(minutes=int(mute_duration))
            for user in queryset:
                asyncio.run(user.mute(mute_duration))
                ActionLog.objects.create(
                    chats_names=user.chats_names,
                    user_id=user.user_id,
                    action_type="user_muted",
                    info=f"Замучено користувача {user.first_name} ({user.user_id}) до {user.mute_until}",
                )
                mute_user_telegram(user.chats_names.chat_id, user.user_id, mute_duration)
    mute_user.short_description = "Замутити користувачів"

    def unmute_user(self, request, queryset):
        for user in queryset:
            asyncio.run(user.unmute())
            ActionLog.objects.create(
                chats_names=user.chats_names,
                user_id=user.user_id,
                action_type="user_unmuted",
                info=f"Розмучено користувача {user.first_name} ({user.user_id})",
            )
            unmute_user_telegram(user.chats_names.chat_id, user.user_id)
    unmute_user.short_description = "Розмутити користувачів"

    def chat_name(self, obj):
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"

admin.site.register(User, UserAdmin)




@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat_name", "user_link", "username", "first_name", "timestamp", "short_message", "action")
    search_fields = ("username", "first_name", "message_text")
    list_filter = ("chats_names", "timestamp")
    ordering = ("-timestamp",)

    def short_message(self, obj):
        return obj.message_text[:50] + "..." if len(obj.message_text) > 50 else obj.message_text
    short_message.short_description = "Повідомлення"

    def chat_name(self, obj):
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"

    def user_link(self, obj):
        # Створюємо посилання на користувача, якщо він існує
        user = User.objects.filter(user_id=obj.user_id).first()
        if user:
            url = reverse("admin:setting_bot_user_change", args=[user.id])  # Замініть 'appname' на своє ім'я додатку
            return format_html('<a href="{}">{}</a>', url, obj.user_id)
        return obj.user_id
    user_link.short_description = "User ID"