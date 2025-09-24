from rest_framework import serializers
from ...models import WebhookEvent


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