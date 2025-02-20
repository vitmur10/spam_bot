from django.contrib import admin
from .models import *

@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "mute_time", "max_mentions", "max_emojis", "min_caps_length")


admin.site.register(BannedUser)
admin.site.register(MutedUser)