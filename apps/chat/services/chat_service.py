from typing import Dict, List, Optional, Type
from django.utils import timezone
import logging

from ..interfaces.base.chat_interface import ChatInterface
from ..interfaces.whatsapp.whatsapp_interface import WhatsAppInterface
from .langchain.supervisor import multi_agent_system

logger = logging.getLogger(__name__)


class ChatServiceRegistry:
    """
    Registro de servicios de chat disponibles
    """

    def __init__(self):
        self._services: Dict[str, Type[ChatInterface]] = {}
        self._instances: Dict[str, ChatInterface] = {}
        self._register_default_services()

    def _register_default_services(self):
        """Registra los servicios de chat por defecto"""
        self.register_service('whatsapp', WhatsAppInterface)

    def register_service(self, service_type: str, service_class: Type[ChatInterface]):
        """
        Registra un nuevo tipo de servicio de chat

        Args:
            service_type: Identificador del tipo de servicio
            service_class: Clase que implementa ChatInterface
        """
        self._services[service_type] = service_class
        logger.info(f"Chat service '{service_type}' registered")

    def get_service(self, service_type: str, config_id: str = None) -> Optional[ChatInterface]:
        """
        Obtiene una instancia de servicio de chat

        Args:
            service_type: Tipo de servicio ('whatsapp', 'telegram', etc.)
            config_id: ID de configuración específica (opcional)

        Returns:
            Instancia del servicio o None si no existe
        """
        if service_type not in self._services:
            logger.error(f"Unknown chat service type: {service_type}")
            return None

        try:
            instance_key = f"{service_type}_{config_id or 'default'}"

            if instance_key not in self._instances:
                service_class = self._services[service_type]
                self._instances[instance_key] = service_class(config_id=config_id)

            return self._instances[instance_key]

        except Exception as e:
            logger.error(f"Error creating chat service instance: {e}")
            return None

    def list_available_services(self) -> List[str]:
        """
        Lista los tipos de servicios disponibles

        Returns:
            Lista de tipos de servicios registrados
        """
        return list(self._services.keys())

    def get_service_info(self, service_type: str) -> Dict:
        """
        Obtiene información de un tipo de servicio

        Args:
            service_type: Tipo de servicio

        Returns:
            Dict con información del servicio
        """
        if service_type not in self._services:
            return {'error': f'Service type {service_type} not found'}

        try:
            # Crear instancia temporal para obtener info
            temp_instance = self._services[service_type]()
            return temp_instance.get_service_info()
        except Exception as e:
            return {'error': f'Error getting service info: {str(e)}'}


class ChatService:
    """
    Servicio principal de chat que unifica todas las interfaces
    """

    def __init__(self):
        self.registry = ChatServiceRegistry()
        # El sistema multi-agente supervisor maneja automáticamente el enrutamiento

    def send_message(self, service_type: str, recipient: str, message: str,
                    config_id: str = None, **kwargs) -> Dict:
        """
        Envía un mensaje a través del servicio especificado

        Args:
            service_type: Tipo de servicio ('whatsapp', etc.)
            recipient: Destinatario del mensaje
            message: Contenido del mensaje
            config_id: ID de configuración específica
            **kwargs: Parámetros adicionales específicos del servicio

        Returns:
            Dict con resultado del envío
        """
        try:
            service = self.registry.get_service(service_type, config_id)
            if not service:
                return {
                    'status': 'error',
                    'error': f'Service {service_type} not available'
                }

            result = service.send_message(recipient, message, **kwargs)
            result['service_type'] = service_type
            result['sent_at'] = timezone.now().isoformat()

            logger.info(f"Message sent via {service_type} to {recipient}")
            return result

        except Exception as e:
            logger.error(f"Error sending message via {service_type}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'service_type': service_type
            }

    def process_incoming_message(self, service_type: str, payload: Dict,
                                signature: str = None, config_id: str = None) -> Dict:
        """
        Procesa un mensaje entrante de cualquier servicio

        Args:
            service_type: Tipo de servicio que recibió el mensaje
            payload: Datos del mensaje entrante
            signature: Firma de seguridad (opcional)
            config_id: ID de configuración específica

        Returns:
            Dict con resultado del procesamiento
        """
        try:
            service = self.registry.get_service(service_type, config_id)
            if not service:
                return {
                    'status': 'error',
                    'error': f'Service {service_type} not available'
                }

            result = service.process_incoming_message(payload, signature)
            result['service_type'] = service_type
            result['processed_at'] = timezone.now().isoformat()

            logger.info(f"Message processed from {service_type}")
            return result

        except Exception as e:
            logger.error(f"Error processing message from {service_type}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'service_type': service_type
            }

    def get_conversation_history(self, service_type: str, conversation_id: str,
                               limit: int = 50, config_id: str = None) -> List[Dict]:
        """
        Obtiene historial de conversación de cualquier servicio

        Args:
            service_type: Tipo de servicio
            conversation_id: ID de la conversación
            limit: Número máximo de mensajes
            config_id: ID de configuración específica

        Returns:
            Lista de mensajes
        """
        try:
            service = self.registry.get_service(service_type, config_id)
            if not service:
                return []

            return service.get_conversation_history(conversation_id, limit)

        except Exception as e:
            logger.error(f"Error getting conversation history from {service_type}: {e}")
            return []

    def mark_as_read(self, service_type: str, conversation_id: str,
                    message_id: str = None, config_id: str = None) -> bool:
        """
        Marca mensaje(s) como leído(s) en cualquier servicio

        Args:
            service_type: Tipo de servicio
            conversation_id: ID de la conversación
            message_id: ID del mensaje específico (opcional)
            config_id: ID de configuración específica

        Returns:
            True si fue exitoso
        """
        try:
            service = self.registry.get_service(service_type, config_id)
            if not service:
                return False

            return service.mark_as_read(conversation_id, message_id)

        except Exception as e:
            logger.error(f"Error marking as read in {service_type}: {e}")
            return False

    def get_available_services(self) -> List[Dict]:
        """
        Obtiene lista de servicios disponibles con su información

        Returns:
            Lista de servicios con información detallada
        """
        services = []
        for service_type in self.registry.list_available_services():
            info = self.registry.get_service_info(service_type)
            info['service_type'] = service_type
            services.append(info)

        return services

    def get_service_status(self, service_type: str = None) -> Dict:
        """
        Obtiene estado de uno o todos los servicios

        Args:
            service_type: Tipo específico de servicio (opcional)

        Returns:
            Dict con estado de servicios
        """
        if service_type:
            service = self.registry.get_service(service_type)
            if not service:
                return {'error': f'Service {service_type} not found'}

            info = service.get_service_info()
            info['service_type'] = service_type
            info['checked_at'] = timezone.now().isoformat()
            return info

        else:
            # Estado de todos los servicios
            all_services = {}
            for stype in self.registry.list_available_services():
                try:
                    service = self.registry.get_service(stype)
                    if service:
                        info = service.get_service_info()
                        info['checked_at'] = timezone.now().isoformat()
                        all_services[stype] = info
                except Exception as e:
                    all_services[stype] = {
                        'status': 'error',
                        'error': str(e),
                        'checked_at': timezone.now().isoformat()
                    }

            return {
                'total_services': len(all_services),
                'services': all_services
            }

    def test_agent_response(self, message_content: str, service_type: str = 'whatsapp',
                           company_info: Dict = None, sender_info: Dict = None) -> Dict:
        """
        Prueba qué respuesta automática se generaría para un mensaje

        Args:
            message_content: Contenido del mensaje a probar
            service_type: Tipo de servicio (para contexto)
            company_info: Información de la empresa (opcional)
            sender_info: Información del remitente (opcional)

        Returns:
            Dict con información de la prueba
        """
        try:
            # Usar el nuevo sistema multi-agente con supervisor
            metadata = {
                'company_info': company_info or {},
                'sender_info': sender_info or {}
            }

            response = multi_agent_system.process(
                message=message_content,
                metadata=metadata
            )

            result = {
                'message': message_content,
                'response': response,
                'service_type': service_type,
                'tested_at': timezone.now().isoformat(),
                'system': 'multi_agent_supervisor',
                'success': True
            }

            return result

        except Exception as e:
            return {
                'error': f'Error testing agent response: {str(e)}',
                'service_type': service_type,
                'tested_at': timezone.now().isoformat()
            }

    def get_chat_analytics(self, service_type: str = None, days: int = 30) -> Dict:
        """
        Obtiene analíticas de chat para uno o todos los servicios

        Args:
            service_type: Tipo específico de servicio (opcional)
            days: Número de días para el análisis

        Returns:
            Dict con analíticas
        """
        from datetime import timedelta
        from django.utils import timezone
        from ..models import WhatsAppMessage

        try:
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)

            if service_type == 'whatsapp' or service_type is None:
                # Analíticas de WhatsApp
                whatsapp_messages = WhatsAppMessage.objects.filter(
                    created_at__range=[start_date, end_date]
                )

                analytics = {
                    'period_days': days,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'whatsapp': {
                        'total_messages': whatsapp_messages.count(),
                        'inbound_messages': whatsapp_messages.filter(direction='inbound').count(),
                        'outbound_messages': whatsapp_messages.filter(direction='outbound').count(),
                        'auto_responses': whatsapp_messages.filter(is_auto_response=True).count(),
                        'conversations': whatsapp_messages.values('conversation').distinct().count()
                    }
                }

                # Agregar información del sistema supervisor
                analytics['system'] = {
                    'type': 'multi_agent_supervisor',
                    'agents_available': ['tax', 'dte', 'sii', 'general'],
                    'description': 'Sistema supervisor multi-agente con LangGraph'
                }

                return analytics

            else:
                return {
                    'error': f'Analytics not available for service type: {service_type}'
                }

        except Exception as e:
            return {
                'error': f'Error getting chat analytics: {str(e)}'
            }


# Instancia global del servicio de chat
chat_service = ChatService()