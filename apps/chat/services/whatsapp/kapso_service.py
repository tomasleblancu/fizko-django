import requests
from typing import Dict, List
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class KapsoAPIService:
    """
    Servicio para interactuar con la API de Kapso WhatsApp Business
    """

    def __init__(self, api_token: str, base_url: str = None):
        self.api_token = api_token
        self.base_url = base_url or getattr(settings, 'KAPSO_API_BASE_URL', 'https://app.kapso.ai/api/v1')
        self.headers = {
            'X-API-Key': api_token,
            'Content-Type': 'application/json'
        }

    def send_text_message(self, phone_number: str, message: str, conversation_id: str) -> Dict:
        """
        Envía mensaje de texto usando la API de Kapso

        Args:
            phone_number: Número de destino
            message: Contenido del mensaje
            conversation_id: ID de conversación en Kapso

        Returns:
            Dict con resultado de la API
        """
        payload = {
            "message": {
                "content": message,
                "message_type": "text"
            }
        }

        try:
            url = f'{self.base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages'

            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Mensaje enviado via Kapso: {phone_number} (conv: {conversation_id})")
                return result
            else:
                error_msg = f"Kapso API error {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ Error Kapso: {error_msg}")
                return {'error': error_msg}

        except requests.exceptions.Timeout:
            error_msg = "Timeout conectando con Kapso API"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}
        except Exception as e:
            error_msg = f"Error enviando mensaje: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}

    def send_media_message(self, phone_number: str, media_url: str,
                          media_type: str, conversation_id: str, caption: str = '') -> Dict:
        """
        Envía mensaje con media (imagen, video, audio, documento)

        Args:
            phone_number: Número de destino
            media_url: URL del archivo media
            media_type: Tipo de media (image, video, audio, document)
            conversation_id: ID de conversación en Kapso
            caption: Texto adicional (opcional)

        Returns:
            Dict con resultado de la API
        """
        payload = {
            "message": {
                "message_type": media_type,
                "media_url": media_url,
                "caption": caption
            }
        }

        try:
            url = f'{self.base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages'

            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60  # Timeout mayor para media
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Media {media_type} enviado via Kapso: {phone_number}")
                return result
            else:
                error_msg = f"Kapso API error {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ Error Kapso media: {error_msg}")
                return {'error': error_msg}

        except Exception as e:
            error_msg = f"Error enviando media: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}

    def send_template_message(self, phone_number: str, template_name: str,
                            template_params: List[str], whatsapp_config_id: str,
                            language: str = 'es') -> Dict:
        """
        Envía mensaje usando plantilla de WhatsApp Business

        Args:
            phone_number: Número de destino
            template_name: Nombre de la plantilla
            template_params: Parámetros de la plantilla
            whatsapp_config_id: ID de configuración de WhatsApp
            language: Idioma de la plantilla

        Returns:
            Dict con resultado de la API
        """
        payload = {
            'whatsapp_config_id': whatsapp_config_id,
            'phone_number': phone_number,
            'message_type': 'template',
            'template': {
                'name': template_name,
                'language': language,
                'params': template_params
            }
        }

        try:
            response = requests.post(
                f'{self.base_url}/whatsapp/messages',
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Template '{template_name}' enviado via Kapso: {phone_number}")
                return result
            else:
                error_msg = f"Kapso template error {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ Error Kapso template: {error_msg}")
                return {'error': error_msg}

        except Exception as e:
            error_msg = f"Error enviando template: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}

    def get_conversation_info(self, conversation_id: str) -> Dict:
        """
        Obtiene información de una conversación

        Args:
            conversation_id: ID de la conversación

        Returns:
            Dict con información de la conversación
        """
        try:
            response = requests.get(
                f'{self.base_url}/whatsapp_conversations/{conversation_id}',
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f"Error getting conversation: {response.status_code}"}

        except Exception as e:
            return {'error': f"Error fetching conversation: {str(e)}"}

    def get_message_status(self, message_id: str) -> Dict:
        """
        Obtiene el estado de un mensaje

        Args:
            message_id: ID del mensaje

        Returns:
            Dict con estado del mensaje
        """
        try:
            response = requests.get(
                f'{self.base_url}/whatsapp_messages/{message_id}',
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f"Error getting message status: {response.status_code}"}

        except Exception as e:
            return {'error': f"Error fetching message status: {str(e)}"}

    def create_conversation(self, phone_number: str, whatsapp_config_id: str) -> Dict:
        """
        Crea una nueva conversación

        Args:
            phone_number: Número de teléfono del contacto
            whatsapp_config_id: ID de configuración de WhatsApp

        Returns:
            Dict con información de la conversación creada
        """
        payload = {
            'phone_number': phone_number,
            'whatsapp_config_id': whatsapp_config_id
        }

        try:
            response = requests.post(
                f'{self.base_url}/whatsapp_conversations',
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Conversación creada via Kapso: {phone_number}")
                return result
            else:
                error_msg = f"Error creating conversation {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ Error Kapso create conversation: {error_msg}")
                return {'error': error_msg}

        except Exception as e:
            error_msg = f"Error creating conversation: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {'error': error_msg}

    def list_conversations(self, whatsapp_config_id: str, limit: int = 50) -> Dict:
        """
        Lista conversaciones de una configuración

        Args:
            whatsapp_config_id: ID de configuración de WhatsApp
            limit: Límite de conversaciones a retornar

        Returns:
            Dict con lista de conversaciones
        """
        try:
            params = {
                'whatsapp_config_id': whatsapp_config_id,
                'limit': limit
            }

            response = requests.get(
                f'{self.base_url}/whatsapp_conversations',
                headers=self.headers,
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f"Error listing conversations: {response.status_code}"}

        except Exception as e:
            return {'error': f"Error fetching conversations: {str(e)}"}

    def validate_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """
        Valida la firma de un webhook de Kapso

        Args:
            payload: Payload del webhook como string
            signature: Firma recibida
            secret: Secreto de webhook

        Returns:
            True si la firma es válida
        """
        import hashlib
        import hmac

        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_signature)

        except Exception as e:
            logger.error(f"Error validating webhook signature: {e}")
            return False

    def get_service_status(self) -> Dict:
        """
        Verifica el estado del servicio Kapso

        Returns:
            Dict con estado del servicio
        """
        try:
            response = requests.get(
                f'{self.base_url}/health',
                headers=self.headers,
                timeout=10
            )

            return {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_time': response.elapsed.total_seconds(),
                'status_code': response.status_code
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }