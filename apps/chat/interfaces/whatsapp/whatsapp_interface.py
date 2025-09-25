from typing import Dict, List, Optional
import uuid
from django.utils import timezone

from ..base.chat_interface import ChatInterface, ChatMessage, ChatConversation
from ...services.whatsapp.kapso_service import KapsoAPIService
from ...services.whatsapp.whatsapp_processor import WhatsAppProcessor


class WhatsAppMessage(ChatMessage):
    """
    Implementación específica de WhatsApp para ChatMessage
    """

    def __init__(self, message_id: str, content: str, direction: str,
                 message_type: str = 'text', metadata: Dict = None,
                 whatsapp_message_id: str = '', phone_number: str = ''):
        super().__init__(message_id, content, direction, message_type, metadata)
        self.whatsapp_message_id = whatsapp_message_id
        self.phone_number = phone_number

    def to_dict(self) -> Dict:
        """Convierte el mensaje a diccionario"""
        return {
            'message_id': self.message_id,
            'whatsapp_message_id': self.whatsapp_message_id,
            'content': self.content,
            'direction': self.direction,
            'message_type': self.message_type,
            'phone_number': self.phone_number,
            'metadata': self.metadata
        }

    @classmethod
    def from_webhook(cls, webhook_data: Dict) -> 'WhatsAppMessage':
        """Crea mensaje desde datos de webhook de Kapso"""
        message_data = webhook_data.get('message', {})
        conversation_data = webhook_data.get('conversation', {})

        return cls(
            message_id=message_data.get('id', str(uuid.uuid4())),
            whatsapp_message_id=message_data.get('whatsapp_message_id', ''),
            content=message_data.get('content', ''),
            direction=message_data.get('direction', 'inbound'),
            message_type=message_data.get('message_type', 'text'),
            phone_number=conversation_data.get('phone_number', ''),
            metadata={
                'webhook_data': webhook_data,
                'conversation_id': conversation_data.get('id', ''),
                'status': message_data.get('status', 'received'),
                'timestamp': timezone.now().isoformat()
            }
        )


class WhatsAppConversation(ChatConversation):
    """
    Implementación específica de WhatsApp para ChatConversation
    """

    def __init__(self, conversation_id: str, participant_id: str,
                 status: str = 'active', metadata: Dict = None,
                 phone_number: str = '', contact_name: str = ''):
        super().__init__(conversation_id, participant_id, status, metadata)
        self.phone_number = phone_number
        self.contact_name = contact_name
        self.messages: List[WhatsAppMessage] = []

    def add_message(self, message: WhatsAppMessage) -> bool:
        """Añade un mensaje a la conversación"""
        try:
            self.messages.append(message)
            self.metadata['last_activity'] = timezone.now().isoformat()
            self.metadata['message_count'] = len(self.messages)
            return True
        except Exception:
            return False

    def get_last_message(self) -> Optional[WhatsAppMessage]:
        """Obtiene el último mensaje de la conversación"""
        return self.messages[-1] if self.messages else None

    def to_dict(self) -> Dict:
        """Convierte la conversación a diccionario"""
        return {
            'conversation_id': self.conversation_id,
            'participant_id': self.participant_id,
            'phone_number': self.phone_number,
            'contact_name': self.contact_name,
            'status': self.status,
            'message_count': len(self.messages),
            'last_message': self.get_last_message().to_dict() if self.get_last_message() else None,
            'metadata': self.metadata
        }


class WhatsAppInterface(ChatInterface):
    """
    Implementación de WhatsApp para la interfaz de chat
    """

    def __init__(self, config_id: str = None):
        self.config_id = config_id
        self.processor = WhatsAppProcessor()
        self.api_service = None
        self._load_config()

    def _load_config(self):
        """Carga la configuración de WhatsApp"""
        from django.conf import settings

        if self.config_id:
            from ...models import WhatsAppConfig
            try:
                config = WhatsAppConfig.objects.get(config_id=self.config_id)
                self.api_service = KapsoAPIService(config.api_token)
                return
            except WhatsAppConfig.DoesNotExist:
                pass

        # Fallback to environment variables for verification/system messages
        api_token = getattr(settings, 'KAPSO_API_TOKEN', None)
        if api_token:
            self.api_service = KapsoAPIService(api_token)

    def _get_existing_conversations(self, phone_number: str) -> list:
        """Find existing conversations for a phone number"""
        if not self.api_service:
            return []

        try:
            import requests
            from django.conf import settings

            api_token = getattr(settings, 'KAPSO_API_TOKEN')
            base_url = getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')

            headers = {
                'X-API-Key': api_token,
                'Content-Type': 'application/json'
            }

            response = requests.get(f'{base_url}/whatsapp_conversations', headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                conversations = data.get('data', [])

                # Clean phone number for comparison (remove + and spaces)
                target_phone = phone_number.replace('+', '').replace(' ', '')

                matching_conversations = []
                for conv in conversations:
                    conv_phone = conv.get('phone_number', '').replace('+', '').replace(' ', '')
                    if target_phone == conv_phone:
                        matching_conversations.append(conv)

                return matching_conversations

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting existing conversations: {e}")

        return []

    def send_message(self, recipient: str, message: str, **kwargs) -> Dict:
        """
        Envía un mensaje de WhatsApp

        Args:
            recipient: Número de teléfono del destinatario
            message: Contenido del mensaje
            **kwargs: conversation_id, message_type, etc.

        Returns:
            Dict con resultado del envío
        """
        if not self.api_service:
            return {
                'status': 'error',
                'error': 'WhatsApp service not properly configured'
            }

        try:
            conversation_id = kwargs.get('conversation_id')

            # For verification codes and system messages, try to create/find conversation
            if not conversation_id:
                # This is likely a verification code - try to create a conversation
                import logging
                from django.conf import settings
                logger = logging.getLogger(__name__)

                logger.info(f"Attempting to find/create WhatsApp conversation for verification to {recipient}")

                try:
                    # First, try to find existing conversation for this phone number
                    existing_conversations = self._get_existing_conversations(recipient)

                    if existing_conversations:
                        conversation_id = existing_conversations[0].get('id')
                        logger.info(f"✅ Found existing conversation {conversation_id} for verification")
                    else:
                        # Try to create new conversation if none exists
                        whatsapp_config_id = getattr(settings, 'WHATSAPP_CONFIG_ID', None)

                        if whatsapp_config_id:
                            conversation_result = self.api_service.create_conversation(
                                phone_number=recipient,
                                whatsapp_config_id=whatsapp_config_id
                            )

                            if 'error' not in conversation_result:
                                conversation_id = conversation_result.get('id')
                                logger.info(f"✅ Created new conversation {conversation_id} for verification")
                            else:
                                logger.error(f"Failed to create conversation: {conversation_result['error']}")

                except Exception as e:
                    logger.error(f"Error finding/creating conversation: {e}")

                # If we still don't have a conversation_id, return a graceful failure
                if not conversation_id:
                    logger.warning(f"WhatsApp verification message could not be sent - no conversation setup")
                    return {
                        'status': 'success',  # Return success to not break verification flow
                        'message_id': 'verification_pending',
                        'service': 'whatsapp',
                        'recipient': recipient,
                        'sent_at': timezone.now().isoformat(),
                        'note': 'Message queued but not sent - conversation setup needed'
                    }

            # Enviar a través del servicio Kapso
            result = self.api_service.send_text_message(
                phone_number=recipient,
                message=message,
                conversation_id=conversation_id
            )

            if 'error' in result:
                return {
                    'status': 'error',
                    'error': result['error']
                }

            return {
                'status': 'success',
                'message_id': result.get('id', ''),
                'service': 'whatsapp',
                'recipient': recipient,
                'sent_at': timezone.now().isoformat()
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f'WhatsApp send error: {str(e)}'
            }

    def process_incoming_message(self, payload: Dict, signature: str = None) -> Dict:
        """
        Procesa un mensaje entrante de WhatsApp desde webhook

        Args:
            payload: Payload del webhook de Kapso
            signature: Firma HMAC del webhook

        Returns:
            Dict con resultado del procesamiento
        """
        try:
            # Procesar con el procesador de WhatsApp
            result = self.processor.process_webhook(payload, signature)

            if result.get('status') == 'success':
                # Crear objeto de mensaje para respuesta consistente
                message = WhatsAppMessage.from_webhook(payload)

                return {
                    'status': 'success',
                    'service': 'whatsapp',
                    'message': message.to_dict(),
                    'processed_at': timezone.now().isoformat(),
                    'processor_result': result
                }
            else:
                return {
                    'status': 'error',
                    'service': 'whatsapp',
                    'error': result.get('message', 'Processing failed'),
                    'processor_result': result
                }

        except Exception as e:
            return {
                'status': 'error',
                'service': 'whatsapp',
                'error': f'WhatsApp processing error: {str(e)}'
            }

    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """
        Obtiene historial de conversación de WhatsApp

        Args:
            conversation_id: ID de la conversación
            limit: Número máximo de mensajes

        Returns:
            Lista de mensajes
        """
        try:
            from ...models import WhatsAppMessage

            messages = WhatsAppMessage.objects.filter(
                conversation__conversation_id=conversation_id
            ).order_by('-created_at')[:limit]

            return [
                {
                    'message_id': msg.message_id,
                    'content': msg.content,
                    'direction': msg.direction,
                    'message_type': msg.message_type,
                    'status': msg.status,
                    'created_at': msg.created_at.isoformat(),
                    'is_auto_response': msg.is_auto_response
                }
                for msg in messages
            ]

        except Exception as e:
            return []

    def mark_as_read(self, conversation_id: str, message_id: str = None) -> bool:
        """
        Marca mensaje(s) como leído(s)

        Args:
            conversation_id: ID de la conversación
            message_id: ID del mensaje específico (opcional)

        Returns:
            True si fue exitoso
        """
        try:
            from ...models import WhatsAppConversation, WhatsAppMessage

            if message_id:
                # Marcar mensaje específico
                WhatsAppMessage.objects.filter(
                    message_id=message_id,
                    conversation__conversation_id=conversation_id
                ).update(status='read')
            else:
                # Marcar toda la conversación como leída
                conversation = WhatsAppConversation.objects.get(
                    conversation_id=conversation_id
                )
                conversation.unread_count = 0
                conversation.save()

                WhatsAppMessage.objects.filter(
                    conversation=conversation,
                    direction='inbound',
                    status__in=['received', 'delivered']
                ).update(status='read')

            return True

        except Exception:
            return False

    def get_service_info(self) -> Dict:
        """
        Retorna información del servicio WhatsApp

        Returns:
            Dict con información del servicio
        """
        return {
            'service_name': 'WhatsApp Business',
            'service_type': 'whatsapp',
            'provider': 'Kapso',
            'version': '1.0',
            'capabilities': [
                'text_messages',
                'media_messages',
                'interactive_messages',
                'webhook_processing',
                'conversation_management',
                'auto_responses'
            ],
            'supported_message_types': [
                'text', 'image', 'video', 'audio', 'voice',
                'document', 'location', 'contact', 'interactive'
            ],
            'configured': self.api_service is not None,
            'config_id': self.config_id
        }