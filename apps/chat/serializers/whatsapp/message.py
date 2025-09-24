from rest_framework import serializers
from ...models import WhatsAppMessage


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