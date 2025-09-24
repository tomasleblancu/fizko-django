from django.db import models
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from ...models import WhatsAppMessage
from ...serializers import WhatsAppMessageSerializer
from apps.core.permissions import IsCompanyMember


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