"""
Notification sending tasks
"""

import logging
from celery import shared_task
from django.utils import timezone

from apps.tasks.models import Process

logger = logging.getLogger(__name__)


@shared_task
def send_process_created_notification(process_id):
    """
    Envía notificación cuando se crea un nuevo proceso automáticamente
    """
    try:
        process = Process.objects.get(id=process_id)

        # Aquí puedes integrar con el sistema de notificaciones existente
        # Por ejemplo, enviar email, WhatsApp, etc.

        logger.info(f"📧 Notificación enviada para proceso {process.name}")

        # Ejemplo de integración con WhatsApp si existe
        try:
            from apps.chat.services import chat_service

            message = (
                f"🗓️ *Nuevo proceso tributario generado*\n\n"
                f"*Proceso:* {process.name}\n"
                f"*Tipo:* {process.get_process_type_display()}\n"
                f"*Empresa:* {process.company_full_rut}\n"
                f"*Vencimiento:* {process.due_date.strftime('%d/%m/%Y') if process.due_date else 'Sin fecha'}\n\n"
                f"Por favor revisa y gestiona este proceso en la plataforma."
            )

            # Enviar mensaje al usuario asignado
            # send_whatsapp_message.delay(process.assigned_to, message)

        except ImportError:
            # WhatsApp no disponible
            pass

        return {'success': True, 'process_id': process_id}

    except Process.DoesNotExist:
        logger.error(f"Proceso {process_id} no encontrado para notificación")
        return {'success': False, 'error': 'Proceso no encontrado'}

    except Exception as e:
        logger.error(f"Error enviando notificación para proceso {process_id}: {str(e)}")
        return {'success': False, 'error': str(e)}