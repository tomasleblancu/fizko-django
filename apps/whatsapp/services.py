import hashlib
import hmac
import json
import uuid
from datetime import datetime
from typing import Dict, Optional, List
import requests
from django.conf import settings
from django.utils import timezone
from django.db import transaction

from .models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, 
    WebhookEvent, MessageTemplate
)


class WhatsAppWebhookService:
    """
    Servicio para procesar webhooks de Kapso WhatsApp API
    """
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        """
        Verifica la firma HMAC-SHA256 del webhook
        """
        try:
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Comparación segura para prevenir ataques de timing
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            print(f"Error verificando firma webhook: {e}")
            return False
    
    @staticmethod
    def process_webhook(payload_data: Dict, signature: str, idempotency_key: str) -> Dict:
        """
        Procesa un webhook recibido de Kapso
        """
        try:
            # Verificar si ya procesamos este evento
            if WebhookEvent.objects.filter(idempotency_key=idempotency_key).exists():
                return {"status": "ignored", "message": "Event already processed"}
            
            # Determinar el tipo de evento
            event_type = payload_data.get('type') or payload_data.get('event_type')
            
            # Si no encontramos event_type, intentar deducirlo del contenido
            if not event_type:
                if 'message' in payload_data:
                    message = payload_data.get('message', {})
                    # Para mensajes de Kapso, usar la dirección para determinar si es entrante
                    if message.get('direction') == 'inbound':
                        # Es un mensaje entrante, independiente del status
                        event_type = 'whatsapp.message.received'
                    elif message.get('status') in ['delivered', 'read', 'failed']:
                        event_type = f"whatsapp.message.{message['status']}"
                    elif message.get('direction') == 'outbound':
                        event_type = 'whatsapp.message.sent'
                    else:
                        event_type = 'unknown'
                else:
                    event_type = 'unknown'
            
            is_batch = payload_data.get('batch', False)
            is_test = payload_data.get('test', False) or payload_data.get('is_test', False)
            
            # Crear el evento de webhook
            webhook_event = WebhookEvent.objects.create(
                idempotency_key=idempotency_key,
                event_type=event_type,
                webhook_signature=signature,
                raw_payload=payload_data,
                is_test=is_test,
                is_batch=is_batch,
                batch_size=len(payload_data.get('data', [])) if is_batch else None,
                processing_status='pending'
            )
            
            # Procesar según el tipo de evento
            if event_type == 'whatsapp.message.received':
                return WhatsAppWebhookService._process_message_received(webhook_event, payload_data)
            elif event_type == 'whatsapp.message.sent':
                return WhatsAppWebhookService._process_message_sent(webhook_event, payload_data)
            elif event_type == 'whatsapp.conversation.created':
                return WhatsAppWebhookService._process_conversation_created(webhook_event, payload_data)
            elif event_type == 'whatsapp.conversation.ended':
                return WhatsAppWebhookService._process_conversation_ended(webhook_event, payload_data)
            elif event_type in ['whatsapp.message.delivered', 'whatsapp.message.read', 'whatsapp.message.failed']:
                return WhatsAppWebhookService._process_message_status(webhook_event, payload_data)
            else:
                webhook_event.processing_status = 'ignored'
                webhook_event.error_message = f"Tipo de evento no soportado: {event_type}"
                webhook_event.save()
                return {"status": "ignored", "message": f"Event type not supported: {event_type}"}
                
        except Exception as e:
            print(f"Error procesando webhook: {e}")
            return {"status": "error", "message": str(e)}
    
    @staticmethod
    def _process_message_received(webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa mensaje recibido (puede ser batch)
        """
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()
        
        try:
            messages_processed = 0
            
            # Si es batch, procesar cada mensaje
            if webhook_event.is_batch:
                data_items = payload_data.get('data', [])
            else:
                data_items = [payload_data]
            
            for item in data_items:
                message_data = item.get('message', {})
                conversation_data = item.get('conversation', {})
                whatsapp_config_data = item.get('whatsapp_config', {})
                
                # Buscar o crear configuración
                config = WhatsAppWebhookService._get_or_create_config(whatsapp_config_data)
                if not config:
                    continue
                
                # Buscar o crear conversación
                conversation = WhatsAppWebhookService._get_or_create_conversation(
                    conversation_data, config
                )
                
                # Crear mensaje
                message = WhatsAppWebhookService._create_message_from_webhook(
                    message_data, conversation, 'inbound'
                )
                
                if message:
                    messages_processed += 1
                    
                    # Marcar webhook event con referencia al último mensaje procesado
                    webhook_event.message = message
                    webhook_event.conversation = conversation
                    webhook_event.company = config.company
                    
                    # Enviar respuesta automática si está habilitada (inmediatamente)
                    if config.enable_auto_responses:
                        WhatsAppWebhookService._send_auto_response_sync(message, config)
            
            webhook_event.processing_status = 'processed'
            webhook_event.processing_completed_at = timezone.now()
            webhook_event.processed_data = {'messages_processed': messages_processed}
            webhook_event.save()
            
            return {"status": "success", "messages_processed": messages_processed}
                
        except Exception as e:
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save()
            raise e
    
    @staticmethod
    def _process_message_sent(webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa confirmación de mensaje enviado
        """
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()
        
        try:
            message_data = payload_data.get('message', {})
            message_id = message_data.get('id')
            
            if message_id:
                # Buscar mensaje por ID y actualizar estado
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
    
    @staticmethod
    def _process_message_status(webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa cambios de estado de mensaje (delivered, read, failed)
        """
        webhook_event.processing_status = 'processing'
        webhook_event.processing_started_at = timezone.now()
        webhook_event.save()
        
        try:
            message_data = payload_data.get('message', {})
            whatsapp_message_id = message_data.get('whatsapp_message_id')
            
            if whatsapp_message_id:
                try:
                    message = WhatsAppMessage.objects.get(whatsapp_message_id=whatsapp_message_id)
                    
                    # Actualizar estado según el tipo de evento
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
    
    @staticmethod
    def _process_conversation_created(webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa creación de nueva conversación
        """
        # Lógica similar a _process_message_received pero sin crear mensaje
        webhook_event.processing_status = 'processed'
        webhook_event.processing_completed_at = timezone.now()
        webhook_event.save()
        return {"status": "success"}
    
    @staticmethod
    def _process_conversation_ended(webhook_event: WebhookEvent, payload_data: Dict) -> Dict:
        """
        Procesa finalización de conversación
        """
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
    
    @staticmethod
    def _get_or_create_config(whatsapp_config_data: Dict) -> Optional[WhatsAppConfig]:
        """
        Busca o crea configuración de WhatsApp
        """
        config_id = whatsapp_config_data.get('id')
        if not config_id:
            return None
        
        try:
            return WhatsAppConfig.objects.get(config_id=config_id)
        except WhatsAppConfig.DoesNotExist:
            # En webhook, no creamos config automáticamente
            # Debe ser configurada previamente
            return None
    
    @staticmethod
    def _get_or_create_conversation(conversation_data: Dict, config: WhatsAppConfig) -> WhatsAppConversation:
        """
        Busca o crea conversación
        """
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
    
    @staticmethod
    def _create_message_from_webhook(message_data: Dict, conversation: WhatsAppConversation, direction: str) -> Optional[WhatsAppMessage]:
        """
        Crea mensaje desde datos de webhook
        """
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
                media_data=message_data.get('media_data') or {},  # Fix null constraint
                status=message_data.get('status', 'received'),
                processing_status='pending',
                metadata=message_data
            )
            
            return message
            
        except Exception as e:
            print(f"Error creando mensaje: {e}")
            return None
    
    @staticmethod
    def _send_auto_response_sync(message: WhatsAppMessage, config: WhatsAppConfig):
        """
        Envía respuesta automática para mensaje entrante (inmediatamente)
        """
        try:
            # Solo responder a mensajes de texto para evitar spam
            if message.message_type != 'text':
                return
            
            
            # Generar respuesta automática basada en el contenido
            response_message = WhatsAppWebhookService._generate_auto_response_message(message, config)
            
            # Enviar inmediatamente
            result = WhatsAppWebhookService.send_message_sync(
                config=config,
                phone_number=message.conversation.phone_number,
                message=response_message,
                is_auto_response=True,
                triggered_by=message
            )
            
            if result.get('status') == 'success':
                print(f"✅ Auto-response enviada a {message.conversation.phone_number}: {response_message[:50]}...")
            else:
                print(f"❌ Error enviando auto-response: {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            print(f"❌ Error enviando auto-response: {e}")
    
    @staticmethod
    def _generate_auto_response_message(message: WhatsAppMessage, config: WhatsAppConfig) -> str:
        """
        Genera mensaje de respuesta automática inteligente
        """
        content = message.content.lower().strip()
        company_name = config.company.name
        
        # Respuestas contextuales basadas en el contenido
        if any(word in content for word in ['hola', 'buenas', 'buenos dias', 'buenas tardes']):
            return f"¡Hola! 👋 Soy el asistente digital de {company_name}. ¿En qué puedo ayudarte hoy?"
        
        elif any(word in content for word in ['factura', 'boleta', 'documento', 'dte']):
            return f"📄 Perfecto, te puedo ayudar con temas de facturación y documentos tributarios. {company_name} maneja todos los documentos electrónicos. ¿Qué necesitas específicamente?"
        
        elif any(word in content for word in ['impuesto', 'sii', 'tributario', 'f29', 'f3323']):
            return f"🏛️ Excelente, especialistas en temas tributarios. {company_name} te puede asesorar con el SII, F29, F3323 y todos los impuestos. ¿Cuál es tu consulta?"
        
        elif any(word in content for word in ['precio', 'costo', 'valor', 'tarifa']):
            return f"💰 Te contactamos pronto con información de nuestros servicios y tarifas. {company_name} tiene planes flexibles para empresas de todos los tamaños."
        
        elif any(word in content for word in ['ayuda', 'problema', 'error', 'no funciona']):
            return f"🆘 ¡No te preocupes! El equipo de soporte de {company_name} está aquí para ayudarte. Descríbeme el problema y te orientamos."
        
        elif any(word in content for word in ['gracias', 'perfecto', 'excelente', 'ok']):
            return f"😊 ¡De nada! Es un placer ayudarte. {company_name} siempre está disponible para lo que necesites."
        
        else:
            # Respuesta genérica pero útil
            return f"🤖 Gracias por contactar a {company_name}. Hemos recibido tu mensaje y un miembro de nuestro equipo te responderá pronto. \n\n💡 Mientras tanto, ¿sabías que manejamos:\n• Facturas electrónicas\n• Documentos SII\n• Asesoría tributaria\n• Automatización contable"
    
    @staticmethod
    def send_message_sync(config: WhatsAppConfig, phone_number: str, message: str, 
                         is_auto_response: bool = False, triggered_by: WhatsAppMessage = None) -> Dict:
        """
        Envía mensaje de WhatsApp sincrónicamente
        """
        import uuid
        
        try:
            # Buscar conversación existente o crear nueva
            try:
                conversation = WhatsAppConversation.objects.filter(
                    whatsapp_config=config,
                    phone_number=phone_number
                ).first()
                
                if not conversation:
                    conversation = WhatsAppConversation.objects.create(
                        whatsapp_config=config,
                        phone_number=phone_number,
                        company=config.company,
                        status='active',
                        last_active_at=timezone.now()
                    )
                else:
                    # Actualizar última actividad
                    conversation.last_active_at = timezone.now()
                    conversation.save()
            except Exception as e:
                print(f"Error manejando conversación: {e}")
                return {'status': 'error', 'error': str(e)}
            
            # Crear registro del mensaje antes de enviarlo
            whatsapp_message = WhatsAppMessage.objects.create(
                message_id=str(uuid.uuid4()),
                conversation=conversation,
                company=config.company,
                message_type='text',
                direction='outbound',
                content=message,
                status='pending',
                processing_status='processing',
                is_auto_response=is_auto_response,
                triggered_by=triggered_by
            )
            
            # Enviar a través de Kapso API usando conversation_id
            api_service = KapsoAPIService(config.api_token)
            # Necesitamos obtener el conversation_id real de Kapso desde la conversación
            conversation_kapso_id = conversation.conversation_id if hasattr(conversation, 'conversation_id') else None
            
            if not conversation_kapso_id:
                return {
                    'status': 'error',
                    'error': 'No se pudo obtener conversation_id de Kapso'
                }
            
            result = api_service.send_text_message(
                phone_number=phone_number,
                message=message,
                conversation_id=conversation_kapso_id
            )
            
            # Actualizar estado según respuesta
            if 'error' not in result:
                whatsapp_message.status = 'sent'
                whatsapp_message.processing_status = 'processed'
                whatsapp_message.whatsapp_message_id = result.get('message_id', '')
                whatsapp_message.save()
                
                return {
                    'status': 'success',
                    'message_id': str(whatsapp_message.id),
                    'whatsapp_message_id': whatsapp_message.whatsapp_message_id
                }
            else:
                whatsapp_message.status = 'failed'
                whatsapp_message.processing_status = 'failed'
                whatsapp_message.error_message = result.get('error', 'Unknown error')
                whatsapp_message.save()
                
                return {
                    'status': 'error',
                    'error': result.get('error', 'Failed to send message')
                }
                
        except Exception as e:
            print(f"❌ Error enviando mensaje: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def send_template_message_sync(config: WhatsAppConfig, phone_number: str, 
                                  template: 'MessageTemplate', variables: Dict = None) -> Dict:
        """
        Envía mensaje usando plantilla sincrónicamente
        """
        try:
            # Renderizar plantilla
            rendered = template.render_message(variables or {})
            message_text = rendered['body']
            
            # Enviar como mensaje de texto normal
            result = WhatsAppWebhookService.send_message_sync(
                config=config,
                phone_number=phone_number,
                message=message_text,
                is_auto_response=False
            )
            
            # Actualizar contadores de plantilla si fue exitoso
            if result.get('status') == 'success':
                template.usage_count += 1
                template.last_used_at = timezone.now()
                template.save()
            
            return result
            
        except Exception as e:
            print(f"❌ Error enviando plantilla: {str(e)}")
            return {
                'status': 'error', 
                'error': str(e)
            }


class KapsoAPIService:
    """
    Servicio para interactuar con la API de Kapso
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
        Envía mensaje de texto usando la API correcta de Kapso
        """
        # Headers correctos para Kapso
        headers = {
            'X-API-Key': self.api_token,
            'Content-Type': 'application/json'
        }
        
        # Payload con estructura correcta de Kapso
        payload = {
            "message": {
                "content": message,
                "message_type": "text"
            }
        }
        
        try:
            # URL correcta de Kapso con conversation_id
            url = f'{self.base_url}/whatsapp_conversations/{conversation_id}/whatsapp_messages'
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ Mensaje enviado via Kapso: {phone_number} (conv: {conversation_id})")
                return result
            else:
                error_msg = f"Kapso API error {response.status_code}: {response.text[:200]}"
                print(f"❌ Error Kapso: {error_msg}")
                return {'error': error_msg}
                
        except requests.exceptions.Timeout:
            error_msg = "Timeout conectando con Kapso API"
            print(f"❌ {error_msg}")
            return {'error': error_msg}
        except Exception as e:
            error_msg = f"Error enviando mensaje: {str(e)}"
            print(f"❌ {error_msg}")
            return {'error': error_msg}
    
    def send_template_message(self, phone_number: str, template_name: str, 
                            template_params: List[str], whatsapp_config_id: str,
                            language: str = 'es') -> Dict:
        """
        Envía mensaje usando plantilla
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
        
        response = requests.post(
            f'{self.base_url}/whatsapp/messages',
            headers=self.headers,
            json=payload,
            timeout=30
        )
        
        return response.json() if response.status_code == 200 else {'error': response.text}