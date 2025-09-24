from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from ...models import MessageTemplate
from ...serializers import MessageTemplateSerializer
from apps.core.permissions import IsCompanyMember


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