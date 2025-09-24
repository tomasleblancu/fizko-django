from rest_framework import serializers
from ...models import WhatsAppConversation
from .message import WhatsAppMessageSerializer


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