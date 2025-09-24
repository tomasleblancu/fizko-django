"""
Celery tasks for company-related background operations.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='companies.cleanup_old_completed_tasks',
    soft_time_limit=300,  # 5 minutos
    time_limit=360,  # 6 minutos
)
def cleanup_old_completed_tasks(self, hours_old=1):
    """
    Elimina tareas de seguimiento completadas más antiguas que el tiempo especificado.

    Args:
        hours_old (int): Horas de antigüedad para considerar una tarea como vieja

    Returns:
        dict: Resultado de la operación con estadísticas de limpieza
    """
    try:
        from .models import BackgroundTaskTracker

        logger.info(f"Iniciando limpieza de tareas completadas hace más de {hours_old} horas")

        # Usar el método del modelo para limpiar tareas
        deleted_count = BackgroundTaskTracker.cleanup_old_completed_tasks(hours_old=hours_old)

        logger.info(f"✅ Limpieza completada: eliminadas {deleted_count} tareas antiguas")

        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'hours_old': hours_old,
            'completed_at': timezone.now().isoformat()
        }

    except Exception as e:
        error_msg = f"Error durante limpieza de tareas: {str(e)}"
        logger.error(f"❌ {error_msg}")

        # Re-raise para que Celery marque la tarea como fallida
        raise self.retry(
            exc=e,
            countdown=60,  # Reintentar en 1 minuto
            max_retries=3
        )


@shared_task(
    bind=True,
    name='companies.update_task_statuses',
    soft_time_limit=600,  # 10 minutos
    time_limit=720,  # 12 minutos
)
def update_task_statuses(self):
    """
    Actualiza el estado de todas las tareas activas consultando Celery.
    Esta tarea se ejecuta periódicamente para mantener los estados sincronizados.

    Returns:
        dict: Resultado de la operación con estadísticas de actualización
    """
    try:
        from .models import BackgroundTaskTracker
        from celery.result import AsyncResult

        logger.info("Iniciando actualización de estados de tareas activas")

        # Obtener todas las tareas activas (pendientes o ejecutándose)
        active_trackers = BackgroundTaskTracker.objects.filter(
            status__in=['pending', 'running']
        )

        updated_count = 0
        completed_count = 0
        failed_count = 0
        error_count = 0

        for tracker in active_trackers:
            try:
                # Obtener resultado actual desde Celery
                celery_result = AsyncResult(tracker.task_id)

                # Guardar estado anterior
                previous_status = tracker.status

                # Actualizar el tracker con el estado actual de Celery
                tracker.update_from_celery_result(celery_result)

                # Contar cambios
                if tracker.status != previous_status:
                    updated_count += 1

                    if tracker.status == 'success':
                        completed_count += 1
                    elif tracker.status == 'failed':
                        failed_count += 1

                    logger.info(f"Tarea {tracker.task_id} cambió de {previous_status} a {tracker.status}")

            except Exception as e:
                error_count += 1
                logger.error(f"Error actualizando tarea {tracker.task_id}: {str(e)}")
                continue

        logger.info(f"✅ Actualización completada: {updated_count} tareas actualizadas, "
                   f"{completed_count} completadas, {failed_count} fallidas, {error_count} errores")

        return {
            'status': 'success',
            'total_active_tasks': active_trackers.count(),
            'updated_count': updated_count,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'error_count': error_count,
            'completed_at': timezone.now().isoformat()
        }

    except Exception as e:
        error_msg = f"Error durante actualización de estados: {str(e)}"
        logger.error(f"❌ {error_msg}")

        # Re-raise para que Celery marque la tarea como fallida
        raise self.retry(
            exc=e,
            countdown=120,  # Reintentar en 2 minutos
            max_retries=3
        )


@shared_task(
    bind=True,
    name='companies.cleanup_orphaned_trackers',
    soft_time_limit=600,  # 10 minutos
    time_limit=720,  # 12 minutos
)
def cleanup_orphaned_trackers(self, max_age_hours=24):
    """
    Limpia trackers huérfanos (tareas que ya no existen en Celery pero siguen marcadas como activas).

    Args:
        max_age_hours (int): Máxima edad en horas para considerar un tracker como potencialmente huérfano

    Returns:
        dict: Resultado de la operación con estadísticas de limpieza
    """
    try:
        from .models import BackgroundTaskTracker
        from celery.result import AsyncResult

        logger.info(f"Iniciando limpieza de trackers huérfanos (más antiguos que {max_age_hours} horas)")

        # Obtener tareas activas más antiguas que max_age_hours
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        old_active_trackers = BackgroundTaskTracker.objects.filter(
            status__in=['pending', 'running'],
            created_at__lt=cutoff_time
        )

        orphaned_count = 0
        marked_failed_count = 0
        error_count = 0

        for tracker in old_active_trackers:
            try:
                # Intentar obtener el resultado desde Celery
                celery_result = AsyncResult(tracker.task_id)

                # Si la tarea no existe en Celery o está en un estado final desconocido
                if celery_result.state == 'PENDING' and not celery_result.result:
                    # Marcar como fallida por ser huérfana
                    tracker.status = 'failed'
                    tracker.completed_at = timezone.now()
                    tracker.error_message = f'Tarea huérfana - no encontrada en Celery después de {max_age_hours} horas'
                    tracker.save()

                    orphaned_count += 1
                    logger.warning(f"Tarea huérfana marcada como fallida: {tracker.task_id}")

                elif celery_result.state in ['FAILURE', 'REVOKED']:
                    # Actualizar con el estado real
                    tracker.update_from_celery_result(celery_result)
                    marked_failed_count += 1
                    logger.info(f"Tarea marcada como {celery_result.state}: {tracker.task_id}")

            except Exception as e:
                error_count += 1
                logger.error(f"Error verificando tarea {tracker.task_id}: {str(e)}")
                continue

        logger.info(f"✅ Limpieza de huérfanos completada: {orphaned_count} huérfanas, "
                   f"{marked_failed_count} fallidas, {error_count} errores")

        return {
            'status': 'success',
            'total_checked': old_active_trackers.count(),
            'orphaned_count': orphaned_count,
            'marked_failed_count': marked_failed_count,
            'error_count': error_count,
            'max_age_hours': max_age_hours,
            'completed_at': timezone.now().isoformat()
        }

    except Exception as e:
        error_msg = f"Error durante limpieza de huérfanos: {str(e)}"
        logger.error(f"❌ {error_msg}")

        # Re-raise para que Celery marque la tarea como fallida
        raise self.retry(
            exc=e,
            countdown=300,  # Reintentar en 5 minutos
            max_retries=2
        )