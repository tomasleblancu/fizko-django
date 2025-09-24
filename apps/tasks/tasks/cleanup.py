"""
Cleanup and maintenance tasks
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone

from apps.tasks.models import Process, ProcessExecution, Task

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_process_executions():
    """
    Limpia ejecuciones de proceso antiguas para mantener la BD optimizada
    """
    try:
        # Eliminar ejecuciones de más de 6 meses
        cutoff_date = timezone.now() - timedelta(days=180)

        old_executions = ProcessExecution.objects.filter(
            started_at__lt=cutoff_date,
            status__in=['completed', 'failed', 'cancelled']
        )

        count = old_executions.count()
        old_executions.delete()

        logger.info(f"🧹 Limpieza completada: {count} ejecuciones antiguas eliminadas")

        return {'success': True, 'deleted_count': count}

    except Exception as e:
        logger.error(f"Error en limpieza de ejecuciones: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task
def cleanup_old_results():
    """
    Limpia resultados de tareas antiguas de Celery
    """
    try:
        # Esta tarea se ejecuta automáticamente según la configuración de Celery
        # result_expires en celery.py ya maneja la limpieza automática
        # Esta función puede ser expandida para limpieza personalizada adicional

        logger.info("🧹 Limpieza de resultados de Celery ejecutada")
        return {'success': True, 'message': 'Cleanup ejecutado exitosamente'}

    except Exception as e:
        logger.error(f"Error en limpieza de resultados: {str(e)}")
        return {'success': False, 'error': str(e)}