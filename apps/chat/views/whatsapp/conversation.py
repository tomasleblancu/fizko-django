from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from ...models import WhatsAppConversation
from ...serializers import (
    WhatsAppConversationSerializer,
    WhatsAppMessageSerializer,
    MarkConversationReadSerializer
)
from apps.core.permissions import IsCompanyMember


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