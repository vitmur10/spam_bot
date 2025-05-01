import asyncio
import csv
import json
import os
from datetime import timedelta

from django.db.models import Sum
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
    list_filter = ("action_type", "created_at", "chat")
    search_fields = ("username", "user_id", "message", "info")
    ordering = ("-created_at",)

    actions = ["export_as_csv", "export_as_json", "delete_old_logs", "ban_user", "unban_user", "mute_user", "unmute_user"]

    def user_link(self, obj):
        try:
            user = ChatUser.objects.get(user_id=obj.user_id)
            url = reverse("admin:setting_bot_chatuser_change", args=[user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user_id)
        except ChatUser.DoesNotExist:
            return obj.user_id
    user_link.short_description = "User ID"

    def mute_duration_field(self, obj):
        form = MuteUserInlineForm(initial={'mute_duration': 5})
        return form.as_p()
    mute_duration_field.short_description = 'Тривалість мутації'

    def ban_user(self, request, queryset):
        for log in queryset:
            try:
                user = ChatUser.objects.get(user_id=log.user_id)
                membership = ChatMembership.objects.get(user=user, chat=log.chat)
            except (ChatUser.DoesNotExist, ChatMembership.DoesNotExist):
                continue
            asyncio.run(membership.ban())
            ActionLog.objects.create(
                chat=log.chat,
                user_id=user.user_id,
                action_type="user_banned",
                info=f"Заблоковано користувача {user.first_name} ({user.user_id})",
            )
            ban_user_telegram(log.chat.chat_id, user.user_id)
    ban_user.short_description = "Заблокувати користувачів"

    def unban_user(self, request, queryset):
        for log in queryset:
            try:
                user = ChatUser.objects.get(user_id=log.user_id)
                membership = ChatMembership.objects.get(user=user, chat=log.chat)
            except (ChatUser.DoesNotExist, ChatMembership.DoesNotExist):
                continue
            asyncio.run(membership.unban())
            ActionLog.objects.create(
                chat=log.chat,
                user_id=user.user_id,
                action_type="user_unbanned",
                info=f"Розблоковано користувача {user.first_name} ({user.user_id})",
            )
            unban_user_telegram(log.chat.chat_id, user.user_id)
    unban_user.short_description = "Розблокувати користувачів"

    def mute_user(self, request, queryset):
        mute_duration = request.POST.get('mute_duration', None)
        if mute_duration:
            mute_duration = timedelta(minutes=int(mute_duration))
            for log in queryset:
                try:
                    user = ChatUser.objects.get(user_id=log.user_id)
                    membership = ChatMembership.objects.get(user=user, chat=log.chat)
                except (ChatUser.DoesNotExist, ChatMembership.DoesNotExist):
                    continue
                asyncio.run(membership.mute(mute_duration))
                ActionLog.objects.create(
                    chat=log.chat,
                    user_id=user.user_id,
                    action_type="user_muted",
                    info=f"Замучено користувача {user.first_name} ({user.user_id}) до {membership.mute_until}",
                )
                mute_user_telegram(log.chat.chat_id, user.user_id, mute_duration)
    mute_user.short_description = "Замутити користувачів"

    def unmute_user(self, request, queryset):
        for log in queryset:
            try:
                user = ChatUser.objects.get(user_id=log.user_id)
                membership = ChatMembership.objects.get(user=user, chat=log.chat)
            except (ChatUser.DoesNotExist, ChatMembership.DoesNotExist):
                continue
            asyncio.run(membership.unmute())
            ActionLog.objects.create(
                chat=log.chat,
                user_id=user.user_id,
                action_type="user_unmuted",
                info=f"Розмучено користувача {user.first_name} ({user.user_id})",
            )
            unmute_user_telegram(log.chat.chat_id, user.user_id)
    unmute_user.short_description = "Розмутити користувачів"

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="action_logs.csv"'
        writer = csv.writer(response, dialect="excel")
        writer.writerow(["created_at", "chat_name", "user_id", "username", "action_type", "message_text", "info"])

        for log in queryset.iterator():
            message_text = log.message.message_text if log.message else "Без тексту"
            info = log.info if log.info else "Без додаткової інформації"
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
            log["info"] = log["info"] if log["info"] else "Без додаткової інформації"
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
        return obj.chat.name if obj.chat else "Без чату"
    chat_name.short_description = "Назва чату"

    def info(self, obj):
        return obj.info if obj.info else "Без додаткової інформації"
    info.short_description = "Інформація"

admin.site.register(ActionLog, ActionLogAdmin)

class ChatMembershipInline(admin.TabularInline):
    model = ChatMembership
    extra = 0
    readonly_fields = (
        'chat', 'status', 'is_banned', 'is_muted', 'mute_count',
        'mute_until', 'message_count', 'last_message_date'
    )
    can_delete = False
    show_change_link = False
class TotalMuteCountFilter(admin.SimpleListFilter):
    title = 'Кількість мутів'
    parameter_name = 'mute_count'

    def lookups(self, request, model_admin):
        return (
            ('less_than_15', 'До 15'),
            ('greater_than_or_equal_15', 'Від 15'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'less_than_15':
            return queryset.filter(chatmembership__mute_count__lt=15)
        if self.value() == 'greater_than_or_equal_15':
            return queryset.filter(chatmembership__mute_count__gte=15)
        return queryset

class TotalMessageCountFilter(admin.SimpleListFilter):
    title = 'Кількість повідомлень'
    parameter_name = 'message_count'

    def lookups(self, request, model_admin):
        return (
            ('less_than_15', 'До 15'),
            ('greater_than_or_equal_15', 'Від 15'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'less_than_15':
            return queryset.filter(chatmembership__message_count__lt=15)
        if self.value() == 'greater_than_or_equal_15':
            return queryset.filter(chatmembership__message_count__gte=15)
        return queryset


@admin.register(ChatUser)
class ChatUserAdmin(admin.ModelAdmin):
    list_display = (
        "username", "first_name", "get_chats", 'get_status_display',
        'total_mute_count', 'message_count_link', 'action_log_link'
    )
    actions = ['ban_user', 'unban_user', 'mute_user', 'unmute_user']
    search_fields = ('first_name', 'user_id', 'username')
    inlines = [ChatMembershipInline]

    # Додаємо фільтри
    list_filter = (
        'chatmembership__status',  # Фільтр за статусом у чаті
        TotalMuteCountFilter,  # Фільтр за кількістю мутів "до 15" або "від 15"
        TotalMessageCountFilter,  # Фільтр за кількістю повідомлень "до 15" або "від 15"
    )

    def get_chats(self, obj):
        return ", ".join([m.chat.name for m in ChatMembership.objects.filter(user=obj)])

    get_chats.short_description = "Чати"

    def get_status_display(self, obj):
        statuses = []
        for m in ChatMembership.objects.filter(user=obj):
            statuses.append(f"{m.chat.name}: {m.get_status()}")
        return format_html("<br>".join(statuses))

    get_status_display.short_description = "Статуси"

    def total_mute_count(self, obj):
        return sum(m.mute_count for m in ChatMembership.objects.filter(user=obj))

    total_mute_count.short_description = "Кількість мутів"

    def total_message_count(self, obj):
        return sum(m.message_count for m in ChatMembership.objects.filter(user=obj))

    total_message_count.short_description = "Повідомлень загалом"

    def message_count_link(self, obj):
        url = reverse('admin:setting_bot_message_changelist') + f'?user_id={obj.user_id}'
        total = self.total_message_count(obj)
        return format_html('<a href="{}">{}</a>', url, total)

    message_count_link.short_description = "Повідомлення"

    def action_log_link(self, obj):
        url = reverse('admin:setting_bot_actionlog_changelist') + f'?user_id={obj.user_id}'
        return format_html('<a href="{}">Логи</a>', url)

    action_log_link.short_description = 'Дії'

    def ban_user(self, request, queryset):
        for user in queryset:
            for m in ChatMembership.objects.filter(user=user):
                asyncio.run(m.ban())
                ActionLog.objects.create(
                    chat=m.chat,
                    user_id=user.user_id,
                    action_type="user_banned",
                    info=f"Заблоковано користувача {user.first_name} ({user.user_id})",
                )
                ban_user_telegram(m.chat.chat_id, user.user_id)

    ban_user.short_description = "Заблокувати користувача"

    def unban_user(self, request, queryset):
        for user in queryset:
            for m in ChatMembership.objects.filter(user=user):
                asyncio.run(m.unban())
                ActionLog.objects.create(
                    chat=m.chat,
                    user_id=user.user_id,
                    action_type="user_unbanned",
                    info=f"Розблоковано користувача {user.first_name} ({user.user_id})",
                )
                unban_user_telegram(m.chat.chat_id, user.user_id)

    unban_user.short_description = "Розблокувати користувача"

    def mute_user(self, request, queryset):
        mute_duration = request.POST.get('mute_duration', 5)  # default 5 хвилин
        mute_duration = timedelta(minutes=int(mute_duration))
        for user in queryset:
            for m in ChatMembership.objects.filter(user=user):
                asyncio.run(m.mute(mute_duration))
                ActionLog.objects.create(
                    chat=m.chat,
                    user_id=user.user_id,
                    action_type="user_muted",
                    info=f"Замучено користувача {user.first_name} ({user.user_id}) до {m.mute_until}",
                )
                mute_user_telegram(m.chat.chat_id, user.user_id, mute_duration)

    mute_user.short_description = "Замутити користувача"

    def unmute_user(self, request, queryset):
        for user in queryset:
            for m in ChatMembership.objects.filter(user=user):
                asyncio.run(m.unmute())
                ActionLog.objects.create(
                    chat=m.chat,
                    user_id=user.user_id,
                    action_type="user_unmuted",
                    info=f"Розмучено користувача {user.first_name} ({user.user_id})",
                )
                unmute_user_telegram(m.chat.chat_id, user.user_id)

    unmute_user.short_description = "Розмутити користувача"


@admin.register(ChatMembership)
class ChatMembershipAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'short_chat_name', 'status', 'is_banned', 'is_muted',
        'mute_count', 'mute_until', 'last_message_date',
        'message_link', 'action_log_link'
    )
    search_fields = ('user__username', 'user__user_id', 'chat__name')
    list_filter = ('is_banned', 'is_muted', 'chat__name')
    ordering = ['-last_message_date']
    actions = ['ban_user', 'unban_user', 'mute_user', 'unmute_user']

    def short_chat_name(self, obj):
        name = obj.chat.name
        return name[:35] + '…' if len(name) > 35 else name
    short_chat_name.short_description = "Chat"
    short_chat_name.admin_order_field = 'chat__name'

    def total_message_count(self, obj):
        return sum(m.message_count for m in ChatMembership.objects.filter(user=obj.user))
    total_message_count.short_description = "Повідомлень загалом"

    def message_link(self, obj):
        url = reverse('admin:setting_bot_message_changelist') + f'?user_id={obj.user.user_id}'
        total = self.total_message_count(obj)
        return format_html('<a href="{}">{}</a>', url, total)
    message_link.short_description = 'Повідомлення'

    def action_log_link(self, obj):
        url = reverse('admin:setting_bot_actionlog_changelist') + f'?user_id={obj.user.user_id}'
        return format_html('<a href="{}">Дії</a>', url)
    action_log_link.short_description = 'Дії'

    def ban_user(self, request, queryset):
        for m in queryset:
            asyncio.run(m.ban())
            ActionLog.objects.create(
                chat=m.chat,
                user_id=m.user.user_id,
                action_type="user_banned",
                info=f"Заблоковано користувача {m.user.first_name} ({m.user.user_id})",
            )
            ban_user_telegram(m.chat.chat_id, m.user.user_id)
    ban_user.short_description = "Заблокувати користувача"

    def unban_user(self, request, queryset):
        for m in queryset:
            asyncio.run(m.unban())
            ActionLog.objects.create(
                chat=m.chat,
                user_id=m.user.user_id,
                action_type="user_unbanned",
                info=f"Розблоковано користувача {m.user.first_name} ({m.user.user_id})",
            )
            unban_user_telegram(m.chat.chat_id, m.user.user_id)
    unban_user.short_description = "Розблокувати користувача"

    def mute_user(self, request, queryset):
        mute_duration = timedelta(minutes=5)  # можна зробити форму для вводу тривалості
        for m in queryset:
            asyncio.run(m.mute(mute_duration))
            ActionLog.objects.create(
                chat=m.chat,
                user_id=m.user.user_id,
                action_type="user_muted",
                info=f"Замучено користувача {m.user.first_name} ({m.user.user_id}) до {m.mute_until}",
            )
            mute_user_telegram(m.chat.chat_id, m.user.user_id, mute_duration)
    mute_user.short_description = "Замутити користувача"

    def unmute_user(self, request, queryset):
        for m in queryset:
            asyncio.run(m.unmute())
            ActionLog.objects.create(
                chat=m.chat,
                user_id=m.user.user_id,
                action_type="user_unmuted",
                info=f"Розмучено користувача {m.user.first_name} ({m.user.user_id})",
            )
            unmute_user_telegram(m.chat.chat_id, m.user.user_id)
    unmute_user.short_description = "Розмутити користувача"


@admin.register(Chats)
class ChatsAdmin(admin.ModelAdmin):
    list_display = ('name', 'chat_id')
    search_fields = ('name', 'chat_id')




@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat_name", "user_link", "username", "first_name", "timestamp", "short_message", "action", 'mute_duration_field')
    search_fields = ("username", "first_name", "message_text")
    list_filter = ("chats_names", "timestamp")
    ordering = ("-timestamp",)

    actions = ["export_as_csv", "export_as_json", "ban_user", "unban_user", "mute_user", "unmute_user"]

    def short_message(self, obj):
        return obj.message_text[:50] + "..." if len(obj.message_text) > 50 else obj.message_text
    short_message.short_description = "Повідомлення"

    def chat_name(self, obj):
        return obj.chats_names.name if obj.chats_names else "Без чату"
    chat_name.short_description = "Назва чату"

    def user_link(self, obj):
        user = ChatUser.objects.filter(user_id=obj.user_id).first()
        if user:
            url = reverse("admin:setting_bot_chatuser_change", args=[user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user_id)
        return obj.user_id
    user_link.short_description = "User ID"

    def mute_duration_field(self, obj):
        form = MuteUserInlineForm(initial={'mute_duration': 5})
        return form.as_p()
    mute_duration_field.short_description = 'Тривалість мутації'

    def get_membership(self, user_id, chat):
        user = ChatUser.objects.filter(user_id=user_id).first()
        if not user:
            return None
        return ChatMembership.objects.filter(user=user, chat=chat).first()

    def ban_user(self, request, queryset):
        for message in queryset:
            membership = self.get_membership(message.user_id, message.chats_names)
            if membership:
                asyncio.run(membership.ban())
                ActionLog.objects.create(
                    chat=message.chats_names,
                    user_id=message.user_id,
                    action_type="user_banned",
                    info=f"Заблоковано користувача ({message.user_id})"
                )
                ban_user_telegram(message.chats_names.chat_id, message.user_id)

    ban_user.short_description = "Заблокувати користувачів"

    def unban_user(self, request, queryset):
        for message in queryset:
            membership = self.get_membership(message.user_id, message.chats_names)
            if membership:
                asyncio.run(membership.unban())
                ActionLog.objects.create(
                    chat=message.chats_names,
                    user_id=message.user_id,
                    action_type="user_unbanned",
                    info=f"Розблоковано користувача ({message.user_id})"
                )
                unban_user_telegram(message.chats_names.chat_id, message.user_id)

    unban_user.short_description = "Розблокувати користувачів"

    def mute_user(self, request, queryset):
        mute_duration_minutes = request.POST.get('mute_duration')
        if mute_duration_minutes:
            mute_duration = timedelta(minutes=int(mute_duration_minutes))
            for message in queryset:
                membership = self.get_membership(message.user_id, message.chats_names)
                if membership:
                    asyncio.run(membership.mute(mute_duration))
                    ActionLog.objects.create(
                        chat=message.chats_names,
                        user_id=message.user_id,
                        action_type="user_muted",
                        info=f"Замучено до {membership.mute_until}"
                    )
                    mute_user_telegram(message.chats_names.chat_id, message.user_id, mute_duration)

    mute_user.short_description = "Замутити користувачів"

    def unmute_user(self, request, queryset):
        for message in queryset:
            membership = self.get_membership(message.user_id, message.chats_names)
            if membership:
                asyncio.run(membership.unmute())
                ActionLog.objects.create(
                    chat=message.chats_names,
                    user_id=message.user_id,
                    action_type="user_unmuted",
                    info=f"Розмучено користувача ({message.user_id})"
                )
                unmute_user_telegram(message.chats_names.chat_id, message.user_id)

    unmute_user.short_description = "Розмутити користувачів"

    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="message_logs.csv"'
        writer = csv.writer(response, dialect="excel")
        writer.writerow(["timestamp", "chat_name", "user_id", "username", "message_text", "info"])

        for message in queryset.iterator():
            info = message.info if message.info else "Без додаткової інформації"
            writer.writerow([message.timestamp, message.chats_names, message.user_id, message.username, message.message_text, info])

        return response

    export_as_csv.short_description = "Експортувати у CSV"

    def export_as_json(self, request, queryset):
        response = HttpResponse(content_type="application/json")
        response["Content-Disposition"] = 'attachment; filename="message_logs.json"'

        logs = list(queryset.values("timestamp", "chat_name", "user_id", "username", "message_text", "info"))

        for log in logs:
            log["timestamp"] = log["timestamp"].isoformat()
            log["info"] = log["info"] if log["info"] else "Без додаткової інформації"

        response.write(json.dumps(logs, ensure_ascii=False, indent=4))
        return response

    export_as_json.short_description = "Експортувати у JSON"
