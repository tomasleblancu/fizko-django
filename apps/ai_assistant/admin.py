from django.contrib import admin
from .models import ChatSession, ChatMessage, AIUsageLog

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user_email', 'company_rut', 'title', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('session_id', 'user_email', 'title')

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'message_type', 'tokens_used', 'created_at')
    list_filter = ('message_type', 'created_at')

@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ('user_email', 'feature', 'tokens_used', 'cost', 'created_at')
    list_filter = ('feature', 'created_at')
    search_fields = ('user_email', 'feature')
