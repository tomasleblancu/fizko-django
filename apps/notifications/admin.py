from django.contrib import admin
from .models import Notification, NotificationPreference

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user_email', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'user_email', 'message')

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'notification_type', 'channel', 'is_enabled')
    list_filter = ('notification_type', 'channel', 'is_enabled')
    search_fields = ('user_email', 'notification_type')
