from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ...models import MessageTemplate, WhatsAppConversation
from ...serializers import (
    SendMessageSerializer,
    SendTemplateSerializer,
    MarkConversationReadSerializer
)
from ...services.chat_service import chat_service
from apps.core.permissions import IsCompanyMember


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

            # Enviar mensaje usando el servicio modular
            result = chat_service.send_message(
                service_type='whatsapp',
                recipient=serializer.validated_data['phone_number'],
                message=serializer.validated_data['message'],
                config_id=config.config_id,
                conversation_id=serializer.validated_data.get('conversation_id')
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

                # Enviar mensaje usando plantilla con el servicio modular
                message_text = rendered['body']
                result = chat_service.send_message(
                    service_type='whatsapp',
                    recipient=serializer.validated_data['phone_number'],
                    message=message_text,
                    config_id=config.config_id,
                    conversation_id=serializer.validated_data.get('conversation_id')
                )

                # Actualizar contadores de plantilla si fue exitoso
                if result.get('status') == 'success':
                    template.usage_count += 1
                    template.last_used_at = timezone.now()
                    template.save()

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