import json
import uuid
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.utils import timezone
from django.db import transaction

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, 
    WebhookEvent, MessageTemplate
)
from .serializers import (
    WhatsAppConfigSerializer, WhatsAppConversationSerializer,
    WhatsAppMessageSerializer, MessageTemplateSerializer,
    WebhookEventSerializer, SendMessageSerializer,
    SendTemplateSerializer, MarkConversationReadSerializer
)
from .services import WhatsAppWebhookService, KapsoAPIService
from .response_engine import response_engine
# Removed Celery tasks imports - now using synchronous processing
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
        
        # Procesar como webhook
        result = WhatsAppWebhookService.process_webhook(
            test_payload, 
            "test_signature",
            f"test_{uuid.uuid4()}"
        )
        
        return Response(result)


class WhatsAppConversationViewSet(viewsets.ModelViewSet):
    """ViewSet para conversaciones de WhatsApp"""
    
    serializer_class = WhatsAppConversationSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'whatsapp_config']
    search_fields = ['phone_number', 'contact_name']
    ordering_fields = ['last_active_at', 'created_at', 'message_count']
    ordering = ['-last_active_at']
    
    def get_queryset(self):
        return WhatsAppConversation.objects.filter(
            company__user_roles__user=self.request.user,
            company__user_roles__active=True
        ).select_related('company', 'whatsapp_config').prefetch_related('messages')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marcar conversación como leída"""
        conversation = self.get_object()
        
        serializer = MarkConversationReadSerializer(data=request.data)
        if serializer.is_valid():
            if serializer.validated_data['mark_all']:
                conversation.unread_count = 0
                conversation.save()
                
                # También actualizar mensajes individuales
                conversation.messages.filter(
                    direction='inbound',
                    status='received'
                ).update(status='read')
            
            return Response({'status': 'success'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Obtener mensajes de una conversación con paginación"""
        conversation = self.get_object()
        messages = conversation.messages.all().order_by('-created_at')
        
        # Paginación simple
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_messages = messages[start:end]
        serializer = WhatsAppMessageSerializer(paginated_messages, many=True)
        
        return Response({
            'messages': serializer.data,
            'has_more': end < messages.count(),
            'total': messages.count()
        })


class WhatsAppMessageViewSet(viewsets.ModelViewSet):
    """ViewSet para mensajes de WhatsApp"""
    
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['direction', 'message_type', 'status', 'conversation']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return WhatsAppMessage.objects.filter(
            company__user_roles__user=self.request.user,
            company__user_roles__active=True
        ).select_related('company', 'conversation')
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Obtener métricas de mensajes"""
        queryset = self.get_queryset()
        
        analytics = {
            'total_messages': queryset.count(),
            'inbound_messages': queryset.filter(direction='inbound').count(),
            'outbound_messages': queryset.filter(direction='outbound').count(),
            'by_status': dict(
                queryset.values_list('status').annotate(
                    count=models.Count('id')
                )
            ),
            'by_type': dict(
                queryset.values_list('message_type').annotate(
                    count=models.Count('id')
                )
            )
        }
        
        return Response(analytics)


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet para plantillas de mensajes"""
    
    serializer_class = MessageTemplateSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['template_type', 'language', 'is_active', 'is_approved']
    
    def get_queryset(self):
        return MessageTemplate.objects.filter(
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
    def preview(self, request, pk=None):
        """Vista previa de plantilla con variables"""
        template = self.get_object()
        variables = request.data.get('variables', {})
        
        rendered = template.render_message(variables)
        
        return Response({
            'rendered_message': rendered,
            'available_variables': template.available_variables
        })


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
            
            # Procesar webhook directamente (sincrónicamente)
            result = WhatsAppWebhookService.process_webhook(
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


class SendMessageView(APIView):
    """Vista para enviar mensajes de WhatsApp"""
    
    permission_classes = [IsAuthenticated, IsCompanyMember]
    
    def post(self, request):
        serializer = SendMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            # Obtener configuración de WhatsApp de la empresa
            company = request.user.companies.filter(
                user_roles__active=True
            ).first()
            
            if not company or not hasattr(company, 'whatsapp_config'):
                return Response(
                    {'error': 'No WhatsApp configuration found for company'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            config = company.whatsapp_config
            
            # Enviar mensaje directamente
            result = WhatsAppWebhookService.send_message_sync(
                config=config,
                phone_number=serializer.validated_data['phone_number'],
                message=serializer.validated_data['message']
            )
            
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SendTemplateView(APIView):
    """Vista para enviar mensajes usando plantillas"""
    
    permission_classes = [IsAuthenticated, IsCompanyMember]
    
    def post(self, request):
        serializer = SendTemplateSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                template = MessageTemplate.objects.get(
                    id=serializer.validated_data['template_id'],
                    company__user_roles__user=request.user,
                    company__user_roles__active=True,
                    is_active=True
                )
                
                # Renderizar plantilla
                variables = serializer.validated_data.get('variables', {})
                rendered = template.render_message(variables)
                
                # Obtener configuración de WhatsApp
                config = template.company.whatsapp_config
                
                # Enviar mensaje directamente
                result = WhatsAppWebhookService.send_template_message_sync(
                    config=config,
                    phone_number=serializer.validated_data['phone_number'],
                    template=template,
                    variables=variables
                )
                
                result['rendered_message'] = rendered
                return Response(result)
                
            except MessageTemplate.DoesNotExist:
                return Response(
                    {'error': 'Template not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MarkConversationReadView(APIView):
    """Vista para marcar conversación como leída"""
    
    permission_classes = [IsAuthenticated, IsCompanyMember]
    
    def post(self, request, conversation_id):
        try:
            conversation = WhatsAppConversation.objects.get(
                id=conversation_id,
                company__user_roles__user=request.user,
                company__user_roles__active=True
            )
            
            serializer = MarkConversationReadSerializer(data=request.data)
            if serializer.is_valid():
                if serializer.validated_data['mark_all']:
                    conversation.unread_count = 0
                    conversation.save()
                
                return Response({'status': 'success'})
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except WhatsAppConversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class TestResponseView(APIView):
    """Vista para probar respuestas automáticas"""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def post(self, request):
        """Prueba qué respuesta se generaría para un mensaje"""
        message_content = request.data.get('message', '')
        context = request.data.get('context', {})

        if not message_content:
            return Response(
                {'error': 'Message content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtener empresa del usuario
        company = request.user.companies.filter(
            user_roles__active=True
        ).first()

        if not company:
            return Response(
                {'error': 'No active company found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Probar respuesta
        result = response_engine.test_response(message_content, company, context)

        return Response(result)


class ResponseRulesView(APIView):
    """Vista para gestionar reglas de respuesta"""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request):
        """Obtiene las reglas de respuesta activas"""
        rules_data = []

        for rule in response_engine.rules:
            rules_data.append({
                'name': rule.name,
                'patterns': rule.patterns,
                'response': rule.response,
                'priority': rule.priority,
                'conditions': rule.conditions
            })

        return Response({
            'rules': rules_data,
            'total_rules': len(rules_data)
        })

    def post(self, request):
        """Añade una nueva regla personalizada"""
        from .response_engine import ResponseRule

        name = request.data.get('name')
        patterns = request.data.get('patterns', [])
        response_text = request.data.get('response')
        priority = request.data.get('priority', 5)
        conditions = request.data.get('conditions', {})

        if not all([name, patterns, response_text]):
            return Response(
                {'error': 'Name, patterns, and response are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Crear nueva regla
        new_rule = ResponseRule(
            name=name,
            patterns=patterns,
            response=response_text,
            priority=priority,
            conditions=conditions
        )

        # Añadir al motor
        response_engine.add_rule(new_rule)

        return Response({
            'status': 'success',
            'message': f'Rule "{name}" added successfully',
            'rule': {
                'name': new_rule.name,
                'patterns': new_rule.patterns,
                'response': new_rule.response,
                'priority': new_rule.priority
            }
        })

    def delete(self, request):
        """Elimina una regla por nombre"""
        rule_name = request.data.get('name')

        if not rule_name:
            return Response(
                {'error': 'Rule name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Eliminar regla
        response_engine.remove_rule(rule_name)

        return Response({
            'status': 'success',
            'message': f'Rule "{rule_name}" removed successfully'
        })


class ResponseAnalyticsView(APIView):
    """Vista para analíticas de respuestas automáticas"""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request):
        """Obtiene estadísticas de respuestas automáticas"""
        # Obtener empresa del usuario
        company = request.user.companies.filter(
            user_roles__active=True
        ).first()

        if not company:
            return Response(
                {'error': 'No active company found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Estadísticas de mensajes automáticos
        from datetime import timedelta
        from django.utils import timezone

        last_30_days = timezone.now() - timedelta(days=30)

        auto_messages = WhatsAppMessage.objects.filter(
            company=company,
            is_auto_response=True,
            created_at__gte=last_30_days
        )

        inbound_messages = WhatsAppMessage.objects.filter(
            company=company,
            direction='inbound',
            created_at__gte=last_30_days
        )

        analytics = {
            'period': '30 days',
            'total_inbound_messages': inbound_messages.count(),
            'total_auto_responses': auto_messages.count(),
            'response_rate': (
                auto_messages.count() / inbound_messages.count() * 100
                if inbound_messages.count() > 0 else 0
            ),
            'active_rules': len(response_engine.rules),
            'conversations_with_auto_responses': auto_messages.values('conversation').distinct().count(),
            'avg_response_time': '< 1 second (synchronous)',
        }

        return Response(analytics)