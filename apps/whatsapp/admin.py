from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, 
    WebhookEvent, MessageTemplate
)


@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ['company', 'display_name', 'phone_number', 'is_active', 'webhook_verified_at']
    list_filter = ['is_active', 'is_coexistence', 'enable_auto_responses']
    search_fields = ['company__business_name', 'display_name', 'phone_number']
    readonly_fields = ['config_id', 'webhook_verified_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'display_name', 'phone_number', 'is_active')
        }),
        ('Configuración Kapso', {
            'fields': ('config_id', 'phone_number_id', 'business_account_id', 'api_token', 'webhook_secret')
        }),
        ('Configuración de Funcionamiento', {
            'fields': ('is_coexistence', 'enable_auto_responses', 'business_hours_start', 'business_hours_end')
        }),
        ('Información de Sistema', {
            'fields': ('webhook_verified_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')


@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'contact_name', 'company', 'status', 'message_count', 'unread_count', 'last_active_at']
    list_filter = ['status', 'whatsapp_config__company', 'created_at']
    search_fields = ['phone_number', 'contact_name', 'company__business_name']
    readonly_fields = ['conversation_id', 'message_count', 'unread_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información del Contacto', {
            'fields': ('phone_number', 'contact_name', 'whatsapp_config', 'company')
        }),
        ('Estado de la Conversación', {
            'fields': ('status', 'last_active_at', 'message_count', 'unread_count')
        }),
        ('Metadata', {
            'fields': ('metadata', 'tags'),
            'classes': ('collapse',)
        }),
        ('Información de Sistema', {
            'fields': ('conversation_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company', 'whatsapp_config')
    
    actions = ['mark_as_read', 'archive_conversations']
    
    def mark_as_read(self, request, queryset):
        for conversation in queryset:
            conversation.unread_count = 0
            conversation.save()
        self.message_user(request, f"{queryset.count()} conversaciones marcadas como leídas.")
    mark_as_read.short_description = "Marcar como leídas"
    
    def archive_conversations(self, request, queryset):
        queryset.update(status='archived')
        self.message_user(request, f"{queryset.count()} conversaciones archivadas.")
    archive_conversations.short_description = "Archivar conversaciones"


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['get_conversation_info', 'direction', 'message_type', 'content_preview', 'status', 'created_at']
    list_filter = ['direction', 'message_type', 'status', 'processing_status', 'is_auto_response', 'created_at']
    search_fields = ['conversation__phone_number', 'content', 'conversation__contact_name']
    readonly_fields = ['message_id', 'whatsapp_message_id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información del Mensaje', {
            'fields': ('conversation', 'direction', 'message_type', 'content')
        }),
        ('Estado y Procesamiento', {
            'fields': ('status', 'processing_status', 'error_message')
        }),
        ('Datos Adicionales', {
            'fields': ('has_media', 'media_data', 'message_type_data'),
            'classes': ('collapse',)
        }),
        ('Respuesta Automática', {
            'fields': ('is_auto_response', 'triggered_by'),
            'classes': ('collapse',)
        }),
        ('Información de Sistema', {
            'fields': ('message_id', 'whatsapp_message_id', 'metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_conversation_info(self, obj):
        return f"{obj.conversation.phone_number} ({obj.conversation.contact_name or 'Sin nombre'})"
    get_conversation_info.short_description = 'Conversación'
    
    def content_preview(self, obj):
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    content_preview.short_description = 'Contenido'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('conversation', 'company')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'processing_status', 'get_company_info', 'is_test', 'is_batch', 'created_at']
    list_filter = ['event_type', 'processing_status', 'is_test', 'is_batch', 'created_at']
    search_fields = ['idempotency_key', 'company__business_name']
    readonly_fields = ['idempotency_key', 'webhook_signature', 'raw_payload', 'processed_data', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información del Evento', {
            'fields': ('event_type', 'idempotency_key', 'webhook_signature', 'is_test', 'is_batch', 'batch_size')
        }),
        ('Referencias', {
            'fields': ('company', 'conversation', 'message')
        }),
        ('Procesamiento', {
            'fields': ('processing_status', 'processing_attempts', 'processing_started_at', 'processing_completed_at')
        }),
        ('Errores', {
            'fields': ('error_message', 'error_details'),
            'classes': ('collapse',)
        }),
        ('Datos del Webhook', {
            'fields': ('raw_payload', 'processed_data'),
            'classes': ('collapse',)
        }),
        ('Información de Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_company_info(self, obj):
        if obj.company:
            return obj.company.business_name
        return 'Sin empresa'
    get_company_info.short_description = 'Empresa'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company', 'conversation', 'message')
    
    actions = ['retry_failed_events', 'mark_as_processed']
    
    def retry_failed_events(self, request, queryset):
        failed_events = queryset.filter(processing_status='failed')
        for event in failed_events:
            # Aquí podrías agregar lógica para reintentar el procesamiento
            event.processing_status = 'pending'
            event.processing_attempts = 0
            event.error_message = ''
            event.save()
        self.message_user(request, f"{failed_events.count()} eventos marcados para reintento.")
    retry_failed_events.short_description = "Reintentar eventos fallidos"
    
    def mark_as_processed(self, request, queryset):
        queryset.update(processing_status='processed')
        self.message_user(request, f"{queryset.count()} eventos marcados como procesados.")
    mark_as_processed.short_description = "Marcar como procesados"


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'template_type', 'language', 'is_active', 'is_approved', 'usage_count', 'last_used_at']
    list_filter = ['template_type', 'language', 'is_active', 'is_approved', 'company']
    search_fields = ['name', 'company__business_name', 'body_text']
    readonly_fields = ['usage_count', 'last_used_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'name', 'template_type', 'language')
        }),
        ('Contenido de la Plantilla', {
            'fields': ('subject', 'body_text', 'footer_text')
        }),
        ('Variables Disponibles', {
            'fields': ('available_variables',),
            'description': 'Lista las variables que pueden ser utilizadas en esta plantilla'
        }),
        ('Configuración', {
            'fields': ('is_active', 'is_approved')
        }),
        ('Estadísticas de Uso', {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        ('Información de Sistema', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company')
    
    actions = ['activate_templates', 'deactivate_templates', 'duplicate_template']
    
    def activate_templates(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"{queryset.count()} plantillas activadas.")
    activate_templates.short_description = "Activar plantillas"
    
    def deactivate_templates(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"{queryset.count()} plantillas desactivadas.")
    deactivate_templates.short_description = "Desactivar plantillas"
    
    def duplicate_template(self, request, queryset):
        for template in queryset:
            template.pk = None
            template.name = f"{template.name} (Copia)"
            template.is_active = False
            template.usage_count = 0
            template.last_used_at = None
            template.save()
        self.message_user(request, f"{queryset.count()} plantillas duplicadas.")
    duplicate_template.short_description = "Duplicar plantillas"