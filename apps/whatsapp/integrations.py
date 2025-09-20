from typing import Optional, Dict, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

from apps.notifications.models import Notification, NotificationPreference
from .models import WhatsAppMessage, WhatsAppConfig, MessageTemplate
from .services import WhatsAppWebhookService


class WhatsAppNotificationService:
    """
    Servicio para integrar WhatsApp con el sistema de notificaciones
    """
    
    @staticmethod
    def create_notification_from_whatsapp_message(whatsapp_message: WhatsAppMessage) -> Optional[Notification]:
        """
        Crea una notificación del sistema desde un mensaje de WhatsApp recibido
        """
        try:
            # Solo crear notificaciones para mensajes importantes entrantes
            if whatsapp_message.direction != 'inbound' or whatsapp_message.is_auto_response:
                return None
            
            # Buscar usuarios de la empresa para notificar
            company = whatsapp_message.company
            user_emails = company.user_roles.filter(
                active=True
            ).values_list('user__email', flat=True)
            
            # Crear notificación para cada usuario
            notifications_created = []
            
            for user_email in user_emails:
                # Verificar preferencias de notificación
                if not WhatsAppNotificationService._should_notify_user(
                    user_email, 'whatsapp_message'
                ):
                    continue
                
                notification = Notification.objects.create(
                    user_email=user_email,
                    company_rut=company.tax_id.split('-')[0] if '-' in company.tax_id else company.tax_id[:8],
                    company_dv=company.tax_id.split('-')[1] if '-' in company.tax_id else company.tax_id[-1],
                    title=f"Nuevo mensaje de WhatsApp",
                    message=f"Mensaje de {whatsapp_message.conversation.phone_number}: {whatsapp_message.content[:100]}...",
                    notification_type='info',
                    action_url=f"/whatsapp/conversations/{whatsapp_message.conversation.id}/",
                    metadata={
                        'whatsapp_message_id': str(whatsapp_message.id),
                        'conversation_id': str(whatsapp_message.conversation.id),
                        'phone_number': whatsapp_message.conversation.phone_number,
                        'message_type': whatsapp_message.message_type
                    }
                )
                notifications_created.append(notification)
            
            return notifications_created[0] if notifications_created else None
            
        except Exception as e:
            print(f"Error creando notificación desde mensaje WhatsApp: {e}")
            return None
    
    @staticmethod
    def send_whatsapp_from_notification(notification_type: str, company_id: int, 
                                      recipient_phone: str, message_data: Dict) -> Dict:
        """
        Envía mensaje de WhatsApp basado en tipo de notificación del sistema
        """
        try:
            from apps.companies.models import Company
            company = Company.objects.get(id=company_id)
            
            if not hasattr(company, 'whatsapp_config') or not company.whatsapp_config.is_active:
                return {'status': 'error', 'message': 'No active WhatsApp configuration'}
            
            # Mapear tipos de notificación a plantillas de WhatsApp
            template_mapping = {
                'tax_deadline_reminder': 'tax_reminder',
                'document_received': 'document_alert',
                'payment_overdue': 'payment_due',
                'sii_sync_error': 'support',
                'form_submission_due': 'tax_reminder'
            }
            
            template_type = template_mapping.get(notification_type, 'custom')
            
            # Buscar plantilla apropiada
            try:
                template = MessageTemplate.objects.get(
                    company=company,
                    template_type=template_type,
                    is_active=True
                )
                
                # Renderizar plantilla con datos
                rendered = template.render_message(message_data)
                message_text = rendered['body']
                
                # Enviar mensaje sincrónicamente
                result = WhatsAppWebhookService.send_message_sync(
                    config=company.whatsapp_config,
                    phone_number=recipient_phone,
                    message=message_text
                )

                return {
                    'status': result.get('status', 'error'),
                    'message_id': result.get('message_id'),
                    'template_used': template.name,
                    'error': result.get('error')
                }
                
            except MessageTemplate.DoesNotExist:
                # Crear mensaje genérico si no hay plantilla
                generic_message = WhatsAppNotificationService._create_generic_message(
                    notification_type, message_data
                )
                
                result = WhatsAppWebhookService.send_message_sync(
                    config=company.whatsapp_config,
                    phone_number=recipient_phone,
                    message=generic_message
                )

                return {
                    'status': result.get('status', 'error'),
                    'message_id': result.get('message_id'),
                    'message': 'Sent with generic template',
                    'error': result.get('error')
                }
            
        except Exception as e:
            print(f"Error enviando WhatsApp desde notificación: {e}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def sync_tax_deadline_reminders():
        """
        Sincroniza recordatorios de vencimientos tributarios con WhatsApp
        """
        try:
            from apps.companies.models import Company
            from apps.forms.models import TaxForm  # Asumiendo que existe
            
            # Buscar empresas con configuración WhatsApp activa
            companies_with_whatsapp = Company.objects.filter(
                whatsapp_config__is_active=True,
                whatsapp_config__enable_auto_responses=True
            ).select_related('whatsapp_config')
            
            results = []
            
            for company in companies_with_whatsapp:
                # Verificar si hay vencimientos próximos (próximos 7 días)
                upcoming_deadline = timezone.now().date() + timedelta(days=7)
                
                # Aquí deberías implementar la lógica para buscar formularios próximos a vencer
                # Por ahora, simularemos con fechas conocidas de Chile
                chile_tax_deadlines = [
                    {'date': '2024-02-12', 'form': 'F29', 'description': 'Formulario 29 - Enero'},
                    {'date': '2024-03-12', 'form': 'F29', 'description': 'Formulario 29 - Febrero'},
                    # ... más fechas
                ]
                
                # Obtener contactos para notificar (usuarios de la empresa)
                user_phones = []
                for user_role in company.user_roles.filter(active=True).select_related('user'):
                    if hasattr(user_role.user, 'profile') and user_role.user.profile.phone:
                        user_phones.append(user_role.user.profile.phone)
                
                if user_phones:
                    # Enviar recordatorios masivos sincrónicamente
                    sent_count = 0
                    for phone in user_phones:
                        try:
                            result = WhatsAppWebhookService.send_message_sync(
                                config=company.whatsapp_config,
                                phone_number=phone,
                                message=f"Recordatorio tributario: F29 vence el {upcoming_deadline}. - {company.name}"
                            )
                            if result.get('status') == 'success':
                                sent_count += 1
                        except Exception as e:
                            print(f"Error enviando recordatorio a {phone}: {e}")

                    results.append({
                        'company': company.name,
                        'phones_notified': sent_count,
                        'total_phones': len(user_phones)
                    })
            
            return {
                'status': 'success',
                'companies_processed': len(results),
                'details': results
            }
            
        except Exception as e:
            print(f"Error sincronizando recordatorios tributarios: {e}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def handle_new_document_notification(document_data: Dict) -> Dict:
        """
        Maneja notificación de nuevo documento tributario via WhatsApp
        """
        try:
            company_id = document_data.get('company_id')
            document_type = document_data.get('document_type', 'Documento')
            document_number = document_data.get('document_number', 'N/A')
            amount = document_data.get('amount')
            
            if not company_id:
                return {'status': 'error', 'message': 'Company ID required'}
            
            from apps.companies.models import Company
            company = Company.objects.get(id=company_id)
            
            # Obtener contactos para notificar
            user_phones = []
            for user_role in company.user_roles.filter(active=True).select_related('user'):
                if hasattr(user_role.user, 'profile') and user_role.user.profile.phone:
                    user_phones.append(user_role.user.profile.phone)
            
            # Enviar alertas individuales sincrónicamente
            alerts_sent = 0
            for phone in user_phones:
                try:
                    message = f"Nuevo documento: {document_type} #{document_number}"
                    if amount:
                        message += f" por ${amount}"
                    message += f" - {company.name}"

                    result = WhatsAppWebhookService.send_message_sync(
                        config=company.whatsapp_config,
                        phone_number=phone,
                        message=message
                    )
                    if result.get('status') == 'success':
                        alerts_sent += 1
                except Exception as e:
                    print(f"Error enviando alerta a {phone}: {e}")

            return {
                'status': 'success',
                'alerts_sent': alerts_sent,
                'total_phones': len(user_phones)
            }
            
        except Exception as e:
            print(f"Error enviando alerta de documento: {e}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def _should_notify_user(user_email: str, notification_type: str) -> bool:
        """
        Verifica si se debe notificar al usuario según sus preferencias
        """
        try:
            # Buscar preferencias del usuario para WhatsApp
            preference = NotificationPreference.objects.get(
                user_email=user_email,
                notification_type=notification_type,
                channel='whatsapp'  # Necesitarías agregar este canal al modelo
            )
            return preference.is_enabled
        except NotificationPreference.DoesNotExist:
            # Por defecto, permitir notificaciones
            return True
    
    @staticmethod
    def _create_generic_message(notification_type: str, data: Dict) -> str:
        """
        Crea mensaje genérico cuando no hay plantilla disponible
        """
        templates = {
            'tax_deadline_reminder': f"Recordatorio: Vencimiento tributario próximo - {data.get('form_type', 'N/A')} el {data.get('deadline_date', 'N/A')}",
            'document_received': f"Nuevo documento recibido: {data.get('document_type', 'N/A')} #{data.get('document_number', 'N/A')}",
            'payment_overdue': f"Pago vencido: {data.get('description', 'N/A')} por {data.get('amount', 'N/A')}",
            'sii_sync_error': f"Error de sincronización con SII: {data.get('error_message', 'Error desconocido')}",
            'form_submission_due': f"Formulario pendiente: {data.get('form_type', 'N/A')} vence {data.get('due_date', 'pronto')}"
        }
        
        return templates.get(notification_type, f"Notificación: {data.get('message', 'Sin detalles')}")


class WhatsAppIntegrationTriggers:
    """
    Triggers para integrar eventos del sistema con WhatsApp
    """
    
    @staticmethod
    def on_sii_document_received(document_data: Dict):
        """
        Trigger cuando se recibe un nuevo documento del SII
        """
        return WhatsAppNotificationService.handle_new_document_notification(document_data)
    
    @staticmethod
    def on_tax_form_due_soon(form_data: Dict):
        """
        Trigger cuando un formulario tributario está próximo a vencer
        """
        company_id = form_data.get('company_id')
        if not company_id:
            return {'status': 'error', 'message': 'Company ID required'}
        
        return WhatsAppNotificationService.send_whatsapp_from_notification(
            notification_type='tax_deadline_reminder',
            company_id=company_id,
            recipient_phone=form_data.get('contact_phone', ''),
            message_data={
                'form_type': form_data.get('form_type', 'F29'),
                'due_date': form_data.get('due_date', ''),
                'company_name': form_data.get('company_name', ''),
                'amount_due': form_data.get('amount_due', 'N/A')
            }
        )
    
    @staticmethod
    def on_payment_overdue(payment_data: Dict):
        """
        Trigger cuando un pago está vencido
        """
        company_id = payment_data.get('company_id')
        if not company_id:
            return {'status': 'error', 'message': 'Company ID required'}
        
        return WhatsAppNotificationService.send_whatsapp_from_notification(
            notification_type='payment_overdue',
            company_id=company_id,
            recipient_phone=payment_data.get('contact_phone', ''),
            message_data=payment_data
        )
    
    @staticmethod
    def on_sii_sync_error(error_data: Dict):
        """
        Trigger cuando hay error en sincronización con SII
        """
        company_id = error_data.get('company_id')
        if not company_id:
            return {'status': 'error', 'message': 'Company ID required'}
        
        return WhatsAppNotificationService.send_whatsapp_from_notification(
            notification_type='sii_sync_error',
            company_id=company_id,
            recipient_phone=error_data.get('contact_phone', ''),
            message_data={
                'error_message': error_data.get('error_message', 'Error desconocido'),
                'sync_type': error_data.get('sync_type', 'N/A'),
                'company_name': error_data.get('company_name', '')
            }
        )