import uuid
from typing import Dict, Optional
from django.utils import timezone
from django.db import transaction
from django.conf import settings
import logging

from ...models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, WebhookEvent
)
from .kapso_service import KapsoAPIService
from ..agents.agent_manager import agent_manager, MessageContext

logger = logging.getLogger(__name__)


class WhatsAppProcessor:
    """
    Procesador principal para webhooks y mensajes de WhatsApp
    """

    def __init__(self):
        self.agent_manager = agent_manager
        # Inicializar agentes si no se ha hecho
        if not self.agent_manager.is_initialized:
            self.agent_manager.initialize_default_agents()

    def process_webhook(self, payload_data: Dict, signature: str, idempotency_key: str = None) -> Dict:
        """
        Procesa un webhook recibido de Kapso

        Args:
            payload_data: Datos del webhook
            signature: Firma HMAC del webhook
            idempotency_key: Clave de idempotencia

        Returns:
            Dict con resultado del procesamiento
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        try:
            # Verificar si ya procesamos este evento
            if WebhookEvent.objects.filter(idempotency_key=idempotency_key).exists():
                return {"status": "ignored", "message": "Event already processed"}

            # Determinar el tipo de evento
            event_type = self._determine_event_type(payload_data)
            is_test = payload_data.get('test', False) or payload_data.get('is_test', False)

            # Crear el evento de webhook
            webhook_event = WebhookEvent.objects.create(
                idempotency_key=idempotency_key,
                event_type=event_type,
                webhook_signature=signature,
                raw_payload=payload_data,
                is_test=is_test,
                processing_status='pending'
            )

            # Procesar según el tipo de evento
            result = self._process_by_event_type(webhook_event, payload_data)

            return result

        except Exception as e:
            logger.error(f"Error procesando webhook: {e}")
            return {"status": "error", "message": str(e)}

    def _determine_event_type(self, payload_data: Dict) -> str:
        """
        Determina el tipo de evento del webhook

        Args:
            payload_data: Datos del webhook

        Returns:
            Tipo de evento
        """
        event_type = payload_data.get('type') or payload_data.get('event_type')

        if not event_type and 'message' in payload_data:
            message = payload_data.get('message', {})
            direction = message.get('direction')

            if direction == 'inbound':
                return 'whatsapp.message.received'
            elif direction == 'outbound':
                status = message.get('status', '')
                if status in ['delivered', 'read', 'failed']:
                    return f"whatsapp.message.{status}"
                else:
                    return 'whatsapp.message.sent'

        return event_type or 'unknown'

    def _process_by_event_type(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa el webhook según su tipo

        Args:
            webhook_event: Evento de webhook
            payload_data: Datos del webhook

        Returns:
            Dict con resultado del procesamiento
        """
        event_type = webhook_event.event_type

        if event_type == 'whatsapp.message.received':
            return self._process_message_received(webhook_event, payload_data)
        elif event_type == 'whatsapp.message.sent':
            return self._process_message_sent(webhook_event, payload_data)
        elif event_type in ['whatsapp.message.delivered', 'whatsapp.message.read', 'whatsapp.message.failed']:
            return self._process_message_status(webhook_event, payload_data)
        elif event_type == 'whatsapp.conversation.created':
            return self._process_conversation_created(webhook_event, payload_data)
        elif event_type == 'whatsapp.conversation.ended':
            return self._process_conversation_ended(webhook_event, payload_data)
        else:
            webhook_event.processing_status = 'ignored'
            webhook_event.error_message = f"Tipo de evento no soportado: {event_type}"
            webhook_event.save()
            return {"status": "ignored", "message": f"Event type not supported: {event_type}"}

    def _process_message_received(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa mensaje recibido y genera respuesta automática si corresponde

        Args:
            webhook_event: Evento de webhook
            payload_data: Datos del webhook

        Returns:
            Dict con resultado del procesamiento
        """
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()

        try:
            with transaction.atomic():
                message_data = payload_data.get('message', {})
                conversation_data = payload_data.get('conversation', {})
                whatsapp_config_data = payload_data.get('whatsapp_config', {})

                # Buscar o crear configuración
                config = self._get_config(whatsapp_config_data)
                if not config:
                    raise Exception("WhatsApp configuration not found")

                # Buscar o crear conversación
                conversation = self._get_or_create_conversation(conversation_data, config)

                # Crear mensaje
                message = self._create_message_from_webhook(
                    message_data, conversation, 'inbound'
                )

                if not message:
                    raise Exception("Failed to create message")

                # Actualizar referencias del webhook
                webhook_event.message = message
                webhook_event.conversation = conversation
                webhook_event.company = config.company

                # Generar respuesta automática si está habilitada
                if config.enable_auto_responses and message.message_type == 'text':
                    self._generate_auto_response(message, config)

                webhook_event.processing_status = 'processed'
                webhook_event.processing_completed_at = timezone.now()
                webhook_event.save()

                return {"status": "success", "message_id": str(message.id)}

        except Exception as e:
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save()
            logger.error(f"Error processing received message: {e}")
            raise e

    def _generate_auto_response(self, message: WhatsAppMessage, config: WhatsAppConfig):
        """
        Genera respuesta automática usando el sistema de agentes

        Args:
            message: Mensaje recibido
            config: Configuración de WhatsApp
        """
        try:
            # Crear contexto para el agente
            context = MessageContext(
                message_content=message.content,
                sender_id=message.conversation.phone_number,
                conversation_id=message.conversation.conversation_id,
                company_id=str(config.company.id),
                company_info={
                    'name': config.company.name,
                    'id': config.company.id
                },
                sender_info={
                    'name': message.conversation.contact_name or 'Cliente',
                    'phone': message.conversation.phone_number
                },
                conversation_metadata=message.conversation.metadata,
                message_history=self._get_recent_messages(message.conversation)
            )

            # Obtener respuesta del sistema de agentes
            agent_response = self.agent_manager.get_response(context)

            if not agent_response:
                logger.info(f"📱 No hay respuesta automática para: {message.content[:50]}...")
                return

            # Modo de testing vs producción
            is_test_mode = (
                not hasattr(settings, 'KAPSO_API_TOKEN') or
                not settings.KAPSO_API_TOKEN or
                settings.KAPSO_API_TOKEN == 'test_token'
            )

            if is_test_mode:
                # Simular envío en modo test
                self._simulate_auto_response(message, agent_response, config)
            else:
                # Envío real a través de Kapso
                self._send_auto_response(message, agent_response, config)

        except Exception as e:
            logger.error(f"❌ Error generando respuesta automática: {e}")

    def _simulate_auto_response(self, message: WhatsAppMessage, agent_response, config: WhatsAppConfig):
        """
        Simula el envío de respuesta automática en modo test

        Args:
            message: Mensaje original
            agent_response: Respuesta del agente
            config: Configuración de WhatsApp
        """
        auto_response_message = WhatsAppMessage.objects.create(
            message_id=str(uuid.uuid4()),
            conversation=message.conversation,
            company=config.company,
            message_type='text',
            direction='outbound',
            content=agent_response.message,
            status='sent',
            processing_status='processed',
            is_auto_response=True,
            triggered_by=message,
            whatsapp_message_id=f"test_response_{uuid.uuid4()}",
            metadata={
                'agent_name': agent_response.agent_name,
                'confidence': agent_response.confidence,
                'test_mode': True
            }
        )

        logger.info(f"🧪 TEST MODE - Auto-response simulada: {agent_response.message[:50]}...")
        logger.info(f"🤖 Agente usado: {agent_response.agent_name} (confianza: {agent_response.confidence:.2f})")

    def _send_auto_response(self, message: WhatsAppMessage, agent_response, config: WhatsAppConfig):
        """
        Envía respuesta automática real a través de Kapso

        Args:
            message: Mensaje original
            agent_response: Respuesta del agente
            config: Configuración de WhatsApp
        """
        api_service = KapsoAPIService(config.api_token)

        # Crear registro del mensaje antes de enviarlo
        auto_response_message = WhatsAppMessage.objects.create(
            message_id=str(uuid.uuid4()),
            conversation=message.conversation,
            company=config.company,
            message_type='text',
            direction='outbound',
            content=agent_response.message,
            status='pending',
            processing_status='processing',
            is_auto_response=True,
            triggered_by=message,
            metadata={
                'agent_name': agent_response.agent_name,
                'confidence': agent_response.confidence
            }
        )

        # Enviar a través de Kapso
        result = api_service.send_text_message(
            phone_number=message.conversation.phone_number,
            message=agent_response.message,
            conversation_id=message.conversation.conversation_id
        )

        # Actualizar estado según resultado
        if 'error' not in result:
            auto_response_message.status = 'sent'
            auto_response_message.processing_status = 'processed'
            auto_response_message.whatsapp_message_id = result.get('id', '')
            logger.info(f"✅ Auto-response enviada: {agent_response.message[:50]}...")
            logger.info(f"🤖 Agente: {agent_response.agent_name} (confianza: {agent_response.confidence:.2f})")
        else:
            auto_response_message.status = 'failed'
            auto_response_message.processing_status = 'failed'
            auto_response_message.error_message = result.get('error', 'Unknown error')
            logger.error(f"❌ Error enviando auto-response: {result.get('error')}")

        auto_response_message.save()

    def _get_recent_messages(self, conversation: WhatsAppConversation, limit: int = 5) -> list:
        """
        Obtiene mensajes recientes de una conversación

        Args:
            conversation: Conversación
            limit: Número máximo de mensajes

        Returns:
            Lista de mensajes recientes
        """
        recent_messages = conversation.messages.order_by('-created_at')[:limit]
        return [
            {
                'content': msg.content,
                'direction': msg.direction,
                'created_at': msg.created_at.isoformat(),
                'message_type': msg.message_type
            }
            for msg in recent_messages
        ]

    def _process_message_sent(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """Procesa confirmación de mensaje enviado"""
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()

        try:
            message_data = payload_data.get('message', {})
            message_id = message_data.get('id')

            if message_id:
                try:
                    message = WhatsAppMessage.objects.get(message_id=message_id)
                    message.status = 'sent'
                    message.whatsapp_message_id = message_data.get('whatsapp_message_id', '')
                    message.save()

                    webhook_event.message = message
                    webhook_event.conversation = message.conversation
                    webhook_event.company = message.company
                except WhatsAppMessage.DoesNotExist:
                    pass

            webhook_event.processing_status = 'processed'
            webhook_event.processing_completed_at = timezone.now()
            webhook_event.save()

            return {"status": "success"}

        except Exception as e:
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save()
            raise e

    def _process_message_status(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """Procesa cambios de estado de mensaje"""
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()

        try:
            message_data = payload_data.get('message', {})
            whatsapp_message_id = message_data.get('whatsapp_message_id')

            if whatsapp_message_id:
                try:
                    message = WhatsAppMessage.objects.get(whatsapp_message_id=whatsapp_message_id)

                    if webhook_event.event_type == 'whatsapp.message.delivered':
                        message.status = 'delivered'
                    elif webhook_event.event_type == 'whatsapp.message.read':
                        message.status = 'read'
                    elif webhook_event.event_type == 'whatsapp.message.failed':
                        message.status = 'failed'
                        message.error_message = message_data.get('error_message', '')

                    message.save()

                    webhook_event.message = message
                    webhook_event.conversation = message.conversation
                    webhook_event.company = message.company
                except WhatsAppMessage.DoesNotExist:
                    pass

            webhook_event.processing_status = 'processed'
            webhook_event.processing_completed_at = timezone.now()
            webhook_event.save()

            return {"status": "success"}

        except Exception as e:
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save()
            raise e

    def _process_conversation_created(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """Procesa creación de nueva conversación"""
        webhook_event.processing_status = 'processed'
        webhook_event.processing_completed_at = timezone.now()
        webhook_event.save()
        return {"status": "success"}

    def _process_conversation_ended(self, webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """Procesa finalización de conversación"""
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()

        try:
            conversation_data = payload_data.get('conversation', {})
            conversation_id = conversation_data.get('id')

            if conversation_id:
                try:
                    conversation = WhatsAppConversation.objects.get(conversation_id=conversation_id)
                    conversation.status = 'ended'
                    conversation.save()

                    webhook_event.conversation = conversation
                    webhook_event.company = conversation.company
                except WhatsAppConversation.DoesNotExist:
                    pass

            webhook_event.processing_status = 'processed'
            webhook_event.processing_completed_at = timezone.now()
            webhook_event.save()

            return {"status": "success"}

        except Exception as e:
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save()
            raise e

    def _get_config(self, whatsapp_config_data: Dict) -> Optional[WhatsAppConfig]:
        """Busca configuración de WhatsApp"""
        config_id = whatsapp_config_data.get('id')
        if not config_id:
            return None

        try:
            return WhatsAppConfig.objects.get(config_id=config_id)
        except WhatsAppConfig.DoesNotExist:
            return None

    def _get_or_create_conversation(self, conversation_data: Dict, config: WhatsAppConfig) -> WhatsAppConversation:
        """Busca o crea conversación"""
        conversation_id = conversation_data.get('id')
        phone_number = conversation_data.get('phone_number')

        conversation, created = WhatsAppConversation.objects.get_or_create(
            conversation_id=conversation_id,
            defaults={
                'whatsapp_config': config,
                'company': config.company,
                'phone_number': phone_number,
                'status': conversation_data.get('status', 'active'),
                'last_active_at': timezone.now(),
                'metadata': conversation_data.get('metadata', {})
            }
        )

        return conversation

    def _create_message_from_webhook(self, message_data: Dict, conversation: WhatsAppConversation, direction: str) -> Optional[WhatsAppMessage]:
        """Crea mensaje desde datos de webhook"""
        try:
            message = WhatsAppMessage.objects.create(
                message_id=message_data.get('id'),
                whatsapp_message_id=message_data.get('whatsapp_message_id', ''),
                conversation=conversation,
                company=conversation.company,
                message_type=message_data.get('message_type', 'text'),
                direction=direction,
                content=message_data.get('content', ''),
                message_type_data=message_data.get('message_type_data', {}),
                has_media=message_data.get('has_media', False),
                media_data=message_data.get('media_data') or {},
                status=message_data.get('status', 'received'),
                processing_status='pending',
                metadata=message_data
            )

            # Actualizar contador de la conversación
            conversation.message_count += 1
            if direction == 'inbound':
                conversation.unread_count += 1
            conversation.last_active_at = timezone.now()
            conversation.save()

            return message

        except Exception as e:
            logger.error(f"Error creando mensaje: {e}")
            return None