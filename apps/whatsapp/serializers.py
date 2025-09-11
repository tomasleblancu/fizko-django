from rest_framework import serializers
from .models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, 
    WebhookEvent, MessageTemplate
)


class WhatsAppConfigSerializer(serializers.ModelSerializer):
    """Serializer para configuración de WhatsApp"""
    
    class Meta:
        model = WhatsAppConfig
        fields = [
            'id', 'company', 'config_id', 'phone_number_id', 'business_account_id',
            'phone_number', 'display_phone_number', 'display_name', 'is_active',
            'is_coexistence', 'webhook_verified_at', 'enable_auto_responses',
            'business_hours_start', 'business_hours_end', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_token': {'write_only': True},
            'webhook_secret': {'write_only': True}
        }


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    """Serializer para mensajes de WhatsApp"""
    
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'message_id', 'whatsapp_message_id', 'conversation', 'company',
            'message_type', 'direction', 'content', 'message_type_data',
            'has_media', 'media_data', 'status', 'processing_status',
            'metadata', 'error_message', 'is_auto_response', 'triggered_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'message_id', 'whatsapp_message_id', 'created_at', 'updated_at'
        ]


class WhatsAppConversationSerializer(serializers.ModelSerializer):
    """Serializer para conversaciones de WhatsApp"""
    
    recent_messages = WhatsAppMessageSerializer(
        source='messages',
        many=True,
        read_only=True
    )
    
    class Meta:
        model = WhatsAppConversation
        fields = [
            'id', 'conversation_id', 'whatsapp_config', 'company',
            'phone_number', 'contact_name', 'status', 'last_active_at',
            'metadata', 'tags', 'message_count', 'unread_count',
            'recent_messages', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'conversation_id', 'message_count', 'unread_count',
            'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        """Personalizar representación para incluir solo mensajes recientes"""
        data = super().to_representation(instance)
        
        # Limitar mensajes recientes a los últimos 10
        if 'recent_messages' in data:
            data['recent_messages'] = data['recent_messages'][:10]
        
        return data


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer para plantillas de mensajes"""
    
    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'company', 'name', 'template_type', 'language',
            'subject', 'body_text', 'footer_text', 'available_variables',
            'is_active', 'is_approved', 'usage_count', 'last_used_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'usage_count', 'last_used_at', 'created_at', 'updated_at'
        ]


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer para eventos de webhooks"""
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'idempotency_key', 'event_type', 'webhook_signature',
            'company', 'conversation', 'message', 'raw_payload',
            'processed_data', 'processing_status', 'processing_attempts',
            'processing_started_at', 'processing_completed_at',
            'error_message', 'error_details', 'is_test', 'is_batch',
            'batch_size', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at'
        ]


class SendMessageSerializer(serializers.Serializer):
    """Serializer para envío de mensajes"""
    
    phone_number = serializers.CharField(max_length=20)
    message = serializers.CharField(max_length=4096)
    whatsapp_config_id = serializers.UUIDField(required=False)
    
    def validate_phone_number(self, value):
        """Validar formato del número de teléfono"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Número debe incluir código de país (+)")
        return value


class SendTemplateSerializer(serializers.Serializer):
    """Serializer para envío de mensajes con plantilla"""
    
    phone_number = serializers.CharField(max_length=20)
    template_id = serializers.IntegerField()
    variables = serializers.DictField(required=False, default=dict)
    whatsapp_config_id = serializers.UUIDField(required=False)
    
    def validate_phone_number(self, value):
        """Validar formato del número de teléfono"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Número debe incluir código de país (+)")
        return value


class MarkConversationReadSerializer(serializers.Serializer):
    """Serializer para marcar conversación como leída"""
    
    mark_all = serializers.BooleanField(default=True)