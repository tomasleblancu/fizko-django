from rest_framework import serializers
from typing import Optional, List, Dict, Any


class ConsultaContribuyenteSerializer(serializers.Serializer):
    """Serializer para consultar datos de contribuyente"""
    tax_id = serializers.CharField(
        max_length=12, 
        help_text="RUT del contribuyente en formato 12345678-9"
    )
    password = serializers.CharField(
        max_length=200, 
        required=False, 
        allow_blank=True,
        help_text="Contraseña del SII - puede ser encriptada o sin encriptar (opcional si se usan cookies)"
    )
    cookies = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        help_text="Lista de cookies del SII (opcional, se usa antes que password)"
    )

    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not re.match(r'^\d{7,8}-[0-9Kk]$', value):
            raise serializers.ValidationError("RUT debe tener formato 12345678-9")
        return value


class CredentialsVerificationSerializer(serializers.Serializer):
    """Serializer para verificar credenciales de contribuyente"""
    tax_id = serializers.CharField(
        max_length=12, 
        help_text="RUT del contribuyente"
    )
    password = serializers.CharField(
        max_length=200, 
        help_text="Contraseña en texto plano"
    )

    def validate_tax_id(self, value):
        """Validate Chilean RUT format"""
        import re
        if not re.match(r'^\d{7,8}-[0-9Kk]$', value):
            raise serializers.ValidationError("RUT debe tener formato 12345678-9")
        return value


class ContribuyenteResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de consulta de contribuyente"""
    status = serializers.CharField()
    timestamp = serializers.CharField()
    tax_id = serializers.CharField()
    data = serializers.DictField()
    authentication_method = serializers.CharField(required=False)
    cookies = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )


class CredentialsVerificationResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de verificación de credenciales"""
    status = serializers.CharField()
    message = serializers.CharField()
    timestamp = serializers.CharField()
    execution_time = serializers.FloatField()
    data = serializers.DictField()


class ErrorResponseSerializer(serializers.Serializer):
    """Serializer para respuestas de error"""
    status = serializers.CharField(default="error")
    message = serializers.CharField()
    timestamp = serializers.CharField()
    error = serializers.CharField(required=False)
    retry_after = serializers.IntegerField(required=False)
    error_type = serializers.CharField(required=False)