import json
import uuid
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from ...models import WebhookEvent
from ...serializers import WebhookEventSerializer
from ...services.whatsapp.whatsapp_processor import WhatsAppProcessor
from apps.core.permissions import IsCompanyMember


@method_decorator(csrf_exempt, name='dispatch')
class WhatsAppWebhookView(View):
    """Vista para recibir webhooks de Kapso"""

    def post(self, request):
        try:
            # Obtener headers importantes
            signature = request.headers.get('X-Webhook-Signature', '')
            idempotency_key = request.headers.get('X-Idempotency-Key', str(uuid.uuid4()))

            # Parsear payload
            payload_data = json.loads(request.body.decode('utf-8'))

            # Verificar si es un webhook de prueba o si podemos omitir verificación
            is_test = payload_data.get('test', False)

            if not is_test:
                # TODO: Implementar verificación de firma cuando tengamos el secreto
                # Por ahora, aceptamos todos los webhooks
                pass

            # Procesar webhook con el nuevo procesador modular
            processor = WhatsAppProcessor()
            result = processor.process_webhook(
                payload_data=payload_data,
                signature=signature,
                idempotency_key=idempotency_key
            )

            # Determinar código de respuesta basado en el resultado
            if result.get('status') == 'success':
                return JsonResponse(result, status=200)
            elif result.get('status') == 'ignored':
                return JsonResponse(result, status=200)
            else:
                return JsonResponse(result, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            print(f"Error procesando webhook: {e}")
            return JsonResponse({'error': 'Internal server error'}, status=500)


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para eventos de webhooks (solo lectura)"""

    serializer_class = WebhookEventSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type', 'processing_status', 'is_test', 'is_batch']
    ordering_fields = ['created_at', 'processing_completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return WebhookEvent.objects.filter(
            company__user_roles__user=self.request.user,
            company__user_roles__active=True
        ).select_related('company', 'conversation', 'message')