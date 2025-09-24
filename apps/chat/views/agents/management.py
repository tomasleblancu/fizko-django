from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from ...services.agents.agent_manager import agent_manager
from ...services.agents.base_agent import RuleBasedAgent
from ...services.chat_service import chat_service
from apps.core.permissions import IsCompanyMember


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

        # Probar respuesta usando el nuevo sistema de agentes
        result = chat_service.test_agent_response(
            message_content=message_content,
            company_info={'name': company.name, 'id': company.id},
            sender_info=context.get('sender_info', {})
        )

        return Response(result)


class ResponseRulesView(APIView):
    """Vista para gestionar reglas de respuesta"""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request):
        """Obtiene las reglas de respuesta activas del nuevo sistema de agentes"""
        # Obtener información de todos los agentes activos
        stats = agent_manager.get_manager_stats()

        return Response({
            'agents': stats['agents_by_priority'],
            'total_agents': stats['total_agents'],
            'active_agents': stats['active_agents'],
            'has_fallback': stats['has_fallback']
        })

    def post(self, request):
        """Añade un nuevo agente personalizado"""
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

        # Crear nuevo agente basado en reglas
        new_agent = RuleBasedAgent(
            name=name,
            patterns=patterns,
            response_template=response_text,
            priority=priority,
            conditions=conditions
        )

        # Registrar en el gestor de agentes
        success = agent_manager.register_agent(new_agent)

        if success:
            return Response({
                'status': 'success',
                'message': f'Agent "{name}" added successfully',
                'agent': new_agent.get_agent_info()
            })
        else:
            return Response(
                {'error': f'Failed to register agent "{name}"'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request):
        """Elimina un agente por nombre"""
        agent_name = request.data.get('name')

        if not agent_name:
            return Response(
                {'error': 'Agent name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Eliminar agente del gestor
        success = agent_manager.unregister_agent(agent_name)

        if success:
            return Response({
                'status': 'success',
                'message': f'Agent "{agent_name}" removed successfully'
            })
        else:
            return Response(
                {'error': f'Agent "{agent_name}" not found'},
                status=status.HTTP_404_NOT_FOUND
            )