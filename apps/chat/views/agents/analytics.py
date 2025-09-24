from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ...services.chat_service import chat_service
from apps.core.permissions import IsCompanyMember


class ResponseAnalyticsView(APIView):
    """Vista para analíticas de respuestas automáticas"""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request):
        """Obtiene estadísticas de respuestas automáticas del nuevo sistema"""
        # Obtener empresa del usuario
        company = request.user.companies.filter(
            user_roles__active=True
        ).first()

        if not company:
            return Response(
                {'error': 'No active company found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Usar el servicio de chat para obtener analíticas
        analytics = chat_service.get_chat_analytics(service_type='whatsapp', days=30)

        # Agregar información específica de la empresa
        analytics['company'] = {
            'name': company.name,
            'id': company.id
        }

        return Response(analytics)