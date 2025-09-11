import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from .models import (
    WhatsAppConfig, WhatsAppConversation, WhatsAppMessage, 
    WebhookEvent, MessageTemplate
)
from .services import WhatsAppWebhookService, KapsoAPIService


@shared_task(bind=True, max_retries=3)
def process_webhook_async(self, payload_data: Dict, signature: str, idempotency_key: str):
    """
    Procesa webhook de WhatsApp de forma asíncrona
    """
    try:
        result = WhatsAppWebhookService.process_webhook(
            payload_data=payload_data,
            signature=signature,
            idempotency_key=idempotency_key
        )
        
        print(f"✅ Webhook procesado: {idempotency_key} - {result.get('status')}")
        return result
        
    except Exception as exc:
        print(f"❌ Error procesando webhook: {idempotency_key} - {str(exc)}")
        
        # Intentar reintento con backoff exponencial
        if self.request.retries < self.max_retries:
            # Backoff: 60s, 300s (5min), 900s (15min)
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown, exc=exc)
        
        # Si fallaron todos los reintentos, marcar el webhook como failed
        try:
            webhook_event = WebhookEvent.objects.get(idempotency_key=idempotency_key)
            webhook_event.processing_status = 'failed'
            webhook_event.error_message = str(exc)
            webhook_event.processing_attempts = self.request.retries + 1
            webhook_event.save()
        except WebhookEvent.DoesNotExist:
            pass
        
        raise exc


@shared_task(bind=True, max_retries=3)
def send_message_async(self, config_id: int, phone_number: str, message: str, 
                      is_template: bool = False, template_id: Optional[int] = None):
    """
    Envía mensaje de WhatsApp de forma asíncrona
    """
    try:
        # Obtener configuración
        config = WhatsAppConfig.objects.get(id=config_id, is_active=True)
        
        # Buscar o crear conversación
        conversation, created = WhatsAppConversation.objects.get_or_create(
            whatsapp_config=config,
            phone_number=phone_number,
            defaults={
                'company': config.company,
                'status': 'active',
                'last_active_at': timezone.now()
            }
        )
        
        # Crear registro del mensaje antes de enviarlo
        whatsapp_message = WhatsAppMessage.objects.create(
            message_id=str(uuid.uuid4()),
            conversation=conversation,
            company=config.company,
            message_type='template' if is_template else 'text',
            direction='outbound',
            content=message,
            status='pending',
            processing_status='processing',
            is_auto_response=False
        )
        
        # Enviar a través de Kapso API
        api_service = KapsoAPIService(config.api_token)
        
        if is_template and template_id:
            # TODO: Implementar envío de plantillas cuando tengamos la API específica
            result = api_service.send_text_message(
                phone_number=phone_number,
                message=message,
                whatsapp_config_id=config.config_id
            )
        else:
            result = api_service.send_text_message(
                phone_number=phone_number,
                message=message,
                whatsapp_config_id=config.config_id
            )
        
        # Actualizar estado según respuesta
        if 'error' not in result:
            whatsapp_message.status = 'sent'
            whatsapp_message.processing_status = 'processed'
            whatsapp_message.whatsapp_message_id = result.get('message_id', '')
        else:
            whatsapp_message.status = 'failed'
            whatsapp_message.processing_status = 'failed'
            whatsapp_message.error_message = result.get('error', 'Unknown error')
        
        whatsapp_message.save()
        
        # Actualizar contadores de plantilla si aplica
        if is_template and template_id:
            try:
                template = MessageTemplate.objects.get(id=template_id)
                template.usage_count += 1
                template.last_used_at = timezone.now()
                template.save()
            except MessageTemplate.DoesNotExist:
                pass
        
        print(f"📱 Mensaje enviado: {phone_number} - {whatsapp_message.status}")
        return {
            'status': 'success',
            'message_id': str(whatsapp_message.id),
            'whatsapp_message_id': whatsapp_message.whatsapp_message_id
        }
        
    except WhatsAppConfig.DoesNotExist:
        print(f"❌ Configuración WhatsApp no encontrada: {config_id}")
        raise Exception("WhatsApp configuration not found or inactive")
        
    except Exception as exc:
        print(f"❌ Error enviando mensaje: {str(exc)}")
        
        # Actualizar mensaje con error si existe
        try:
            whatsapp_message.status = 'failed'
            whatsapp_message.processing_status = 'failed'
            whatsapp_message.error_message = str(exc)
            whatsapp_message.save()
        except:
            pass
        
        # Reintento con backoff
        if self.request.retries < self.max_retries:
            countdown = 30 * (2 ** self.request.retries)  # 30s, 60s, 120s
            raise self.retry(countdown=countdown, exc=exc)
        
        raise exc


@shared_task
def send_tax_reminder_bulk(company_id: int, template_name: str, phone_numbers: list, variables: Dict = None):
    """
    Envía recordatorios tributarios masivos
    """
    try:
        from apps.companies.models import Company
        company = Company.objects.get(id=company_id)
        
        if not hasattr(company, 'whatsapp_config') or not company.whatsapp_config.is_active:
            print(f"❌ Empresa {company.name} no tiene configuración WhatsApp activa")
            return {'status': 'error', 'message': 'No active WhatsApp configuration'}
        
        # Buscar plantilla
        try:
            template = MessageTemplate.objects.get(
                company=company,
                name=template_name,
                is_active=True
            )
        except MessageTemplate.DoesNotExist:
            print(f"❌ Plantilla '{template_name}' no encontrada para empresa {company.name}")
            return {'status': 'error', 'message': 'Template not found'}
        
        # Renderizar mensaje
        rendered = template.render_message(variables or {})
        message_text = rendered['body']
        
        # Enviar a cada número
        sent_count = 0
        failed_count = 0
        
        for phone_number in phone_numbers:
            try:
                # Programar envío asíncrono
                send_message_async.delay(
                    config_id=company.whatsapp_config.id,
                    phone_number=phone_number,
                    message=message_text,
                    is_template=True,
                    template_id=template.id
                )
                sent_count += 1
                
            except Exception as e:
                print(f"❌ Error programando mensaje para {phone_number}: {e}")
                failed_count += 1
        
        print(f"📊 Recordatorio masivo programado: {sent_count} exitosos, {failed_count} fallidos")
        
        return {
            'status': 'success',
            'sent_count': sent_count,
            'failed_count': failed_count,
            'template_used': template_name
        }
        
    except Company.DoesNotExist:
        print(f"❌ Empresa no encontrada: {company_id}")
        return {'status': 'error', 'message': 'Company not found'}
        
    except Exception as exc:
        print(f"❌ Error en envío masivo: {str(exc)}")
        return {'status': 'error', 'message': str(exc)}


@shared_task
def send_document_alert(company_id: int, phone_number: str, document_type: str, 
                       document_number: str, amount: str = None):
    """
    Envía alerta sobre nuevo documento tributario
    """
    try:
        from apps.companies.models import Company
        company = Company.objects.get(id=company_id)
        
        if not hasattr(company, 'whatsapp_config') or not company.whatsapp_config.is_active:
            return {'status': 'error', 'message': 'No active WhatsApp configuration'}
        
        # Buscar plantilla de alerta de documento
        try:
            template = MessageTemplate.objects.get(
                company=company,
                template_type='document_alert',
                is_active=True
            )
        except MessageTemplate.DoesNotExist:
            # Crear mensaje genérico si no hay plantilla
            message_text = f"Nuevo documento: {document_type} #{document_number}"
            if amount:
                message_text += f" por ${amount}"
        else:
            # Usar plantilla
            variables = {
                'document_type': document_type,
                'document_number': document_number,
                'amount': amount or 'N/A',
                'company_name': company.name
            }
            rendered = template.render_message(variables)
            message_text = rendered['body']
        
        # Enviar mensaje
        task = send_message_async.delay(
            config_id=company.whatsapp_config.id,
            phone_number=phone_number,
            message=message_text,
            is_template=True if 'template' in locals() else False,
            template_id=template.id if 'template' in locals() else None
        )
        
        print(f"📄 Alerta de documento enviada: {document_type} #{document_number} a {phone_number}")
        
        return {
            'status': 'success',
            'task_id': str(task.id),
            'document_type': document_type,
            'document_number': document_number
        }
        
    except Exception as exc:
        print(f"❌ Error enviando alerta de documento: {str(exc)}")
        return {'status': 'error', 'message': str(exc)}


@shared_task
def cleanup_old_webhook_events():
    """
    Limpia eventos de webhooks antiguos (más de 30 días)
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Eliminar eventos de prueba más antiguos (7 días)
        test_cutoff = timezone.now() - timedelta(days=7)
        deleted_test = WebhookEvent.objects.filter(
            is_test=True,
            created_at__lt=test_cutoff
        ).delete()
        
        # Eliminar eventos procesados antiguos
        deleted_old = WebhookEvent.objects.filter(
            processing_status='processed',
            created_at__lt=cutoff_date
        ).delete()
        
        print(f"🧹 Limpieza completada: {deleted_test[0]} eventos de prueba, {deleted_old[0]} eventos antiguos")
        
        return {
            'status': 'success',
            'deleted_test_events': deleted_test[0],
            'deleted_old_events': deleted_old[0]
        }
        
    except Exception as exc:
        print(f"❌ Error en limpieza de webhooks: {str(exc)}")
        return {'status': 'error', 'message': str(exc)}


@shared_task
def process_auto_responses():
    """
    Procesa respuestas automáticas para mensajes pendientes
    """
    try:
        # Buscar mensajes entrantes sin procesar de los últimos 5 minutos
        recent_time = timezone.now() - timedelta(minutes=5)
        pending_messages = WhatsAppMessage.objects.filter(
            direction='inbound',
            processing_status='pending',
            created_at__gte=recent_time
        ).select_related('conversation', 'company')
        
        processed_count = 0
        
        for message in pending_messages:
            try:
                # Verificar si la empresa tiene respuestas automáticas habilitadas
                config = message.conversation.whatsapp_config
                if not config.enable_auto_responses:
                    message.processing_status = 'processed'
                    message.save()
                    continue
                
                # Lógica simple de respuesta automática
                content_lower = message.content.lower()
                auto_response = None
                
                if any(word in content_lower for word in ['hola', 'buenos días', 'buenas tardes', 'hi']):
                    auto_response = f"Hola! Gracias por contactar a {message.company.name}. ¿En qué podemos ayudarte?"
                
                elif any(word in content_lower for word in ['help', 'ayuda', 'info', 'información']):
                    auto_response = ("Puedes consultarnos sobre:\n"
                                   "• Estado de facturas\n"
                                   "• Vencimientos tributarios\n"
                                   "• Documentos electrónicos\n"
                                   "• Soporte técnico")
                
                elif any(word in content_lower for word in ['gracias', 'thanks']):
                    auto_response = "¡De nada! Estamos aquí para ayudarte."
                
                # Enviar respuesta automática si aplica
                if auto_response:
                    send_message_async.delay(
                        config_id=config.id,
                        phone_number=message.conversation.phone_number,
                        message=auto_response
                    )
                
                # Marcar mensaje como procesado
                message.processing_status = 'processed'
                message.save()
                processed_count += 1
                
            except Exception as e:
                print(f"❌ Error procesando respuesta automática para mensaje {message.id}: {e}")
                message.processing_status = 'failed'
                message.error_message = str(e)
                message.save()
        
        print(f"🤖 Respuestas automáticas procesadas: {processed_count}")
        
        return {
            'status': 'success',
            'processed_count': processed_count
        }
        
    except Exception as exc:
        print(f"❌ Error procesando respuestas automáticas: {str(exc)}")
        return {'status': 'error', 'message': str(exc)}


@shared_task(bind=True, max_retries=2)
def send_auto_response_async(self, message_id: str, config_id: int, response_message: str):
    """
    Envía respuesta automática específica para un mensaje
    """
    try:
        # Obtener el mensaje original
        original_message = WhatsAppMessage.objects.get(id=message_id)
        config = WhatsAppConfig.objects.get(id=config_id, is_active=True)
        
        # Verificar si ya se envió una respuesta automática reciente para esta conversación
        recent_auto_response = WhatsAppMessage.objects.filter(
            conversation=original_message.conversation,
            direction='outbound',
            is_auto_response=True,
            created_at__gte=timezone.now() - timezone.timedelta(minutes=30)
        ).exists()
        
        if recent_auto_response:
            print(f"📱 Skip auto-response para {original_message.conversation.phone_number} - ya existe respuesta reciente")
            return {'status': 'skipped', 'reason': 'Recent auto-response exists'}
        
        # Crear registro del mensaje de respuesta automática
        auto_response_message = WhatsAppMessage.objects.create(
            message_id=str(uuid.uuid4()),
            conversation=original_message.conversation,
            company=config.company,
            message_type='text',
            direction='outbound',
            content=response_message,
            status='pending',
            processing_status='processing',
            is_auto_response=True,
            triggered_by=original_message
        )
        
        # Enviar a través de Kapso API
        api_service = KapsoAPIService(config.api_token)
        result = api_service.send_text_message(
            phone_number=original_message.conversation.phone_number,
            message=response_message,
            whatsapp_config_id=config.config_id
        )
        
        # Actualizar estado según respuesta
        if 'error' not in result:
            auto_response_message.status = 'sent'
            auto_response_message.processing_status = 'processed'
            auto_response_message.whatsapp_message_id = result.get('message_id', '')
            
            print(f"📱 Auto-response enviada a {original_message.conversation.phone_number}: {response_message[:50]}...")
            
            return {
                'status': 'success',
                'message_id': str(auto_response_message.id),
                'phone_number': original_message.conversation.phone_number
            }
        else:
            auto_response_message.status = 'failed'
            auto_response_message.processing_status = 'failed'
            auto_response_message.error_message = result.get('error', 'Unknown error')
            
            print(f"❌ Error enviando auto-response: {result.get('error')}")
            raise Exception(result.get('error', 'Failed to send message'))
            
        auto_response_message.save()
        
    except (WhatsAppMessage.DoesNotExist, WhatsAppConfig.DoesNotExist) as e:
        print(f"❌ Recurso no encontrado para auto-response: {e}")
        return {'status': 'error', 'message': str(e)}
        
    except Exception as exc:
        print(f"❌ Error en auto-response: {str(exc)}")
        
        # Actualizar mensaje con error si existe
        try:
            auto_response_message.status = 'failed'
            auto_response_message.processing_status = 'failed'
            auto_response_message.error_message = str(exc)
            auto_response_message.save()
        except:
            pass
        
        # Reintento
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)  # 60s, 120s
            print(f"🔄 Reintentando auto-response en {countdown}s...")
            raise self.retry(countdown=countdown, exc=exc)
        
        return {'status': 'error', 'message': str(exc)}