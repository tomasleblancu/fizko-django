"""
Recurring process generation tasks
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from apps.tasks.models import Process, ProcessExecution, Task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_recurring_process(self, process_id):
    """
    Tarea de Celery para crear el siguiente proceso en una serie recurrente
    """
    try:
        with transaction.atomic():
            # Obtener el proceso padre
            parent_process = Process.objects.select_for_update().get(id=process_id)

            if not parent_process.is_recurring:
                logger.warning(f"Proceso {process_id} no es recurrente, cancelando generación")
                return

            # Verificar que el proceso padre esté completado
            if parent_process.status != 'completed':
                logger.warning(f"Proceso {process_id} no está completado, cancelando generación")
                return

            # Verificar que no existe ya un proceso para el siguiente período
            next_period_data = parent_process._calculate_next_period_data()
            if not next_period_data:
                logger.error(f"No se pudo calcular siguiente período para proceso {process_id}")
                return

            existing_process = Process.objects.filter(
                company_rut=parent_process.company_rut,
                company_dv=parent_process.company_dv,
                process_type=parent_process.process_type,
                config_data__period=next_period_data['config_data'].get('period')
            ).exists()

            if existing_process:
                logger.info(f"Ya existe proceso para período {next_period_data['config_data'].get('period')}")
                return

            # Generar el siguiente proceso
            next_process = parent_process.generate_next_occurrence()

            if next_process:
                logger.info(f"✅ Proceso recurrente creado: {next_process.name} (ID: {next_process.id})")

                # Enviar notificación al usuario asignado
                from .notifications import send_process_created_notification
                send_process_created_notification.delay(next_process.id)

                return {
                    'success': True,
                    'parent_process_id': process_id,
                    'new_process_id': next_process.id,
                    'new_process_name': next_process.name
                }
            else:
                logger.error(f"Error generando siguiente proceso para {process_id}")
                return {'success': False, 'error': 'No se pudo generar el proceso'}

    except Process.DoesNotExist:
        logger.error(f"Proceso {process_id} no encontrado")
        return {'success': False, 'error': 'Proceso no encontrado'}

    except Exception as e:
        logger.error(f"Error creando proceso recurrente para {process_id}: {str(e)}")
        # Reintentar la tarea
        raise self.retry(countdown=60, exc=e)


@shared_task
def generate_monthly_processes_batch():
    """
    Genera procesos mensuales en lote para todas las empresas que los requieran
    Esta tarea se puede ejecutar mensualmente para asegurar que todos los procesos se generen
    """
    try:
        # Buscar todos los procesos F29 recurrentes completados
        monthly_processes = Process.objects.filter(
            process_type='tax_monthly',
            is_recurring=True,
            recurrence_type='monthly',
            status='completed'
        )

        generated_count = 0
        errors = []

        for process in monthly_processes:
            try:
                # Verificar si ya se generó el proceso del siguiente mes
                next_period_data = process._calculate_next_period_data()
                if not next_period_data:
                    continue

                existing = Process.objects.filter(
                    company_rut=process.company_rut,
                    company_dv=process.company_dv,
                    process_type=process.process_type,
                    config_data__period=next_period_data['config_data'].get('period')
                ).exists()

                if not existing:
                    # Generar proceso del siguiente mes
                    next_process = process.generate_next_occurrence()
                    if next_process:
                        generated_count += 1
                        logger.info(f"✅ Generado proceso mensual: {next_process.name}")

            except Exception as e:
                error_msg = f"Error generando proceso para {process.company_full_rut}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        logger.info(f"🗓️ Generación mensual en lote completada: {generated_count} procesos generados")

        return {
            'success': True,
            'generated_count': generated_count,
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Error en generación mensual en lote: {str(e)}")
        return {'success': False, 'error': str(e)}