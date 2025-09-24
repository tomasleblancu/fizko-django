"""
Deadline checking and alert tasks
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone

from apps.tasks.models import Process, ProcessExecution, Task

logger = logging.getLogger(__name__)


@shared_task
def check_process_deadlines():
    """
    Revisa procesos y tareas próximas a vencer para enviar alertas
    """
    try:
        # Buscar procesos que vencen en los próximos 3 días
        deadline_threshold = timezone.now() + timedelta(days=3)

        upcoming_processes = Process.objects.filter(
            due_date__lte=deadline_threshold,
            due_date__gte=timezone.now(),
            status__in=['active', 'paused']
        )

        for process in upcoming_processes:
            days_until_deadline = (process.due_date - timezone.now()).days

            # Enviar alerta según cercanía del vencimiento
            if days_until_deadline <= 1:
                send_urgent_deadline_alert.delay(process.id)
            elif days_until_deadline <= 3:
                send_deadline_reminder.delay(process.id)

        # Buscar procesos vencidos
        overdue_processes = Process.objects.filter(
            due_date__lt=timezone.now(),
            status__in=['active', 'paused']
        )

        for process in overdue_processes:
            send_overdue_alert.delay(process.id)

        logger.info(f"✅ Revisión de vencimientos completada: {upcoming_processes.count()} próximos, {overdue_processes.count()} vencidos")

        return {
            'success': True,
            'upcoming_count': upcoming_processes.count(),
            'overdue_count': overdue_processes.count()
        }

    except Exception as e:
        logger.error(f"Error revisando vencimientos: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def send_deadline_reminder(process_id):
    """
    Envía recordatorio de vencimiento próximo
    """
    try:
        process = Process.objects.get(id=process_id)
        days_left = (process.due_date - timezone.now()).days

        # Aquí integrar con sistema de notificaciones
        logger.info(f"⏰ Recordatorio de vencimiento enviado para {process.name} ({days_left} días)")

        return {'success': True, 'process_id': process_id, 'days_left': days_left}

    except Process.DoesNotExist:
        logger.error(f"Proceso {process_id} no encontrado para recordatorio")
        return {'success': False, 'error': 'Proceso no encontrado'}


@shared_task
def send_urgent_deadline_alert(process_id):
    """
    Envía alerta urgente de vencimiento inminente
    """
    try:
        process = Process.objects.get(id=process_id)

        # Aquí integrar con sistema de notificaciones urgentes
        logger.warning(f"🚨 Alerta urgente enviada para {process.name} - VENCE HOY/MAÑANA")

        return {'success': True, 'process_id': process_id}

    except Process.DoesNotExist:
        logger.error(f"Proceso {process_id} no encontrado para alerta urgente")
        return {'success': False, 'error': 'Proceso no encontrado'}


@shared_task
def send_overdue_alert(process_id):
    """
    Envía alerta de proceso vencido
    """
    try:
        process = Process.objects.get(id=process_id)
        days_overdue = (timezone.now() - process.due_date).days

        # Aquí integrar con sistema de notificaciones
        logger.error(f"❌ Alerta de vencimiento enviada para {process.name} ({days_overdue} días vencido)")

        return {'success': True, 'process_id': process_id, 'days_overdue': days_overdue}

    except Process.DoesNotExist:
        logger.error(f"Proceso {process_id} no encontrado para alerta de vencimiento")
        return {'success': False, 'error': 'Proceso no encontrado'}