from rest_framework import serializers
from ...models import MessageTemplate


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