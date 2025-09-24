from rest_framework import serializers
from ...models import WhatsAppConfig


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