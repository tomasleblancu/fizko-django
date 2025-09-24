from rest_framework import serializers


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