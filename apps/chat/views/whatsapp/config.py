import uuid
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from ...models import WhatsAppConfig
from ...serializers import WhatsAppConfigSerializer
from ...services.whatsapp.whatsapp_processor import WhatsAppProcessor
from apps.core.permissions import IsCompanyMember


class WhatsAppConfigViewSet(viewsets.ModelViewSet):
    """ViewSet para configuraciones de WhatsApp"""

    serializer_class = WhatsAppConfigSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'is_coexistence']

    def get_queryset(self):
        return WhatsAppConfig.objects.filter(
            company__user_roles__user=self.request.user,
            company__user_roles__active=True
        ).select_related('company')

    def perform_create(self, serializer):
        # Asignar empresa actual del usuario
        company = self.request.user.companies.filter(
            user_roles__active=True
        ).first()
        serializer.save(company=company)

    @action(detail=True, methods=['post'])
    def test_webhook(self, request, pk=None):
        """Enviar webhook de prueba"""
        config = self.get_object()

        # Crear evento de prueba
        test_payload = {
            "type": "whatsapp.message.received",
            "test": True,
            "message": {
                "id": str(uuid.uuid4()),
                "message_type": "text",
                "content": "Mensaje de prueba",
                "direction": "inbound",
                "status": "received"
            },
            "conversation": {
                "id": str(uuid.uuid4()),
                "phone_number": "+56912345678",
                "status": "active"
            },
            "whatsapp_config": {
                "id": config.config_id,
                "name": config.display_name,
                "phone_number_id": config.phone_number_id
            }
        }

        # Procesar como webhook con el nuevo procesador
        processor = WhatsAppProcessor()
        result = processor.process_webhook(
            test_payload,
            "test_signature",
            f"test_{uuid.uuid4()}"
        )

        return Response(result)