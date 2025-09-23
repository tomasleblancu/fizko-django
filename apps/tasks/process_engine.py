"""
Motor de ejecución de procesos
Este módulo maneja la lógica de ejecución automática y seguimiento de procesos
"""

import logging
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import transaction
from celery import shared_task

from .models import Process, ProcessExecution, ProcessTask, Task, TaskLog

logger = logging.getLogger(__name__)


class ProcessEngine:
    """
    Motor principal para la ejecución de procesos
    """

    def __init__(self):
        self.logger = logger

    def start_process(self, process_id: int, context: Optional[Dict[str, Any]] = None) -> ProcessExecution:
        """
        Inicia la ejecución de un proceso
        """
        try:
            process = Process.objects.get(id=process_id)

            if process.status not in ['draft', 'paused']:
                raise ValueError(f"No se puede iniciar proceso en estado: {process.status}")

            # Iniciar proceso
            process.start_process()

            # Crear ejecución
            execution = ProcessExecution.objects.create(
                process=process,
                status='running',
                execution_context=context or {},
                total_steps=process.process_tasks.count()
            )

            self.logger.info(f"Iniciando proceso {process.name} con ejecución {execution.id}")

            # Ejecutar primer paso
            self._execute_next_steps(execution)

            return execution

        except Exception as e:
            self.logger.error(f"Error al iniciar proceso {process_id}: {str(e)}")
            raise

    def _execute_next_steps(self, execution: ProcessExecution) -> None:
        """
        Ejecuta los siguientes pasos disponibles del proceso
        """
        process = execution.process

        # Obtener tareas pendientes en orden de ejecución
        pending_tasks = process.process_tasks.filter(
            task__status='pending'
        ).order_by('execution_order')

        if not pending_tasks.exists():
            self._complete_process_execution(execution)
            return

        # Ejecutar tareas que pueden correr en paralelo o la primera tarea secuencial
        tasks_to_execute = []
        current_order = None

        for process_task in pending_tasks:
            # Si es la primera tarea o puede ejecutarse en paralelo
            if current_order is None:
                current_order = process_task.execution_order
                tasks_to_execute.append(process_task)
            elif (process_task.execution_order == current_order and
                  process_task.can_run_parallel):
                tasks_to_execute.append(process_task)
            else:
                break

        # Ejecutar tareas seleccionadas
        for process_task in tasks_to_execute:
            if self._check_execution_conditions(process_task, execution):
                self._execute_task(process_task, execution)
            elif not process_task.is_optional:
                # Si una tarea obligatoria no puede ejecutarse, fallar el proceso
                self._fail_process_execution(
                    execution,
                    f"No se pueden cumplir las condiciones para la tarea: {process_task.task.title}"
                )
                return

    def _execute_task(self, process_task: ProcessTask, execution: ProcessExecution) -> None:
        """
        Ejecuta una tarea específica del proceso
        """
        task = process_task.task

        try:
            self.logger.info(f"Ejecutando tarea {task.title} del proceso {execution.process.name}")

            # Actualizar contexto de la tarea
            if process_task.context_data:
                task.task_data.update(process_task.context_data)
                task.save()

            # Iniciar tarea
            task.start_task()

            # Si es tarea automática, ejecutarla
            if task.task_type == 'automatic':
                self._execute_automatic_task.delay(task.id, execution.id)
            elif task.task_type == 'scheduled':
                self._schedule_task(task, execution)

            # Log de la ejecución
            TaskLog.objects.create(
                task=task,
                level='info',
                message=f"Tarea iniciada por proceso {execution.process.name}",
                details={'execution_id': execution.id, 'process_task_id': process_task.id}
            )

        except Exception as e:
            self.logger.error(f"Error ejecutando tarea {task.id}: {str(e)}")
            task.fail_task(str(e))
            execution.failed_steps += 1
            execution.error_count += 1
            execution.last_error = str(e)
            execution.save()

    def _check_execution_conditions(self, process_task: ProcessTask, execution: ProcessExecution) -> bool:
        """
        Verifica si se cumplen las condiciones para ejecutar una tarea
        """
        conditions = process_task.execution_conditions

        if not conditions:
            return True

        # Evaluar condiciones basadas en el contexto de ejecución
        context = execution.execution_context

        for condition_key, condition_value in conditions.items():
            if condition_key == 'previous_task_status':
                # Verificar estado de tareas anteriores
                if not self._check_previous_tasks_status(process_task, condition_value):
                    return False

            elif condition_key == 'context_variable':
                # Verificar variables del contexto
                var_name = condition_value.get('name')
                expected_value = condition_value.get('value')
                if context.get(var_name) != expected_value:
                    return False

            elif condition_key == 'company_data':
                # Verificar datos específicos de la empresa
                if not self._check_company_conditions(execution.process, condition_value):
                    return False

        return True

    def _check_previous_tasks_status(self, process_task: ProcessTask, required_status: str) -> bool:
        """
        Verifica que las tareas anteriores tengan el estado requerido
        """
        previous_tasks = process_task.process.process_tasks.filter(
            execution_order__lt=process_task.execution_order
        )

        for prev_task in previous_tasks:
            if not prev_task.is_optional and prev_task.task.status != required_status:
                return False

        return True

    def _check_company_conditions(self, process: Process, conditions: Dict[str, Any]) -> bool:
        """
        Verifica condiciones específicas de la empresa
        """
        # Aquí puedes agregar lógica para verificar datos de la empresa
        # Por ejemplo, verificar configuraciones, permisos, etc.
        return True

    def _complete_process_execution(self, execution: ProcessExecution) -> None:
        """
        Completa la ejecución de un proceso
        """
        execution.status = 'completed'
        execution.completed_at = timezone.now()
        execution.completed_steps = execution.total_steps
        execution.save()

        # Completar proceso
        execution.process.complete_process()

        self.logger.info(f"Proceso {execution.process.name} completado exitosamente")

    def _fail_process_execution(self, execution: ProcessExecution, error_message: str) -> None:
        """
        Marca la ejecución de un proceso como fallida
        """
        execution.status = 'failed'
        execution.completed_at = timezone.now()
        execution.last_error = error_message
        execution.error_count += 1
        execution.save()

        # Fallar proceso
        execution.process.fail_process(error_message)

        self.logger.error(f"Proceso {execution.process.name} falló: {error_message}")

    def _schedule_task(self, task: Task, execution: ProcessExecution) -> None:
        """
        Programa una tarea para ejecución futura
        """
        # Aquí puedes integrar con Celery Beat o el sistema de programación que uses
        self.logger.info(f"Programando tarea {task.title} para ejecución futura")

    def pause_process(self, process_id: int) -> None:
        """
        Pausa la ejecución de un proceso
        """
        try:
            process = Process.objects.get(id=process_id)
            process.status = 'paused'
            process.save()

            # Pausar ejecuciones activas
            active_executions = process.executions.filter(status='running')
            active_executions.update(status='paused')

            self.logger.info(f"Proceso {process.name} pausado")

        except Process.DoesNotExist:
            self.logger.error(f"Proceso {process_id} no encontrado")
            raise

    def resume_process(self, process_id: int) -> None:
        """
        Reanuda la ejecución de un proceso pausado
        """
        try:
            process = Process.objects.get(id=process_id)

            if process.status != 'paused':
                raise ValueError(f"No se puede reanudar proceso en estado: {process.status}")

            process.status = 'active'
            process.save()

            # Reanudar ejecuciones pausadas
            paused_executions = process.executions.filter(status='paused')
            for execution in paused_executions:
                execution.status = 'running'
                execution.save()
                self._execute_next_steps(execution)

            self.logger.info(f"Proceso {process.name} reanudado")

        except Process.DoesNotExist:
            self.logger.error(f"Proceso {process_id} no encontrado")
            raise

    def get_process_status(self, process_id: int) -> Dict[str, Any]:
        """
        Obtiene el estado actual de un proceso
        """
        try:
            process = Process.objects.get(id=process_id)
            active_execution = process.executions.filter(status='running').first()

            status = {
                'process_id': process.id,
                'process_name': process.name,
                'status': process.status,
                'progress_percentage': process.progress_percentage,
                'current_step': None,
                'execution_id': None,
                'total_steps': 0,
                'completed_steps': 0,
                'failed_steps': 0
            }

            if active_execution:
                status.update({
                    'execution_id': active_execution.id,
                    'total_steps': active_execution.total_steps,
                    'completed_steps': active_execution.completed_steps,
                    'failed_steps': active_execution.failed_steps,
                    'last_error': active_execution.last_error
                })

            current_step = process.current_step
            if current_step:
                status['current_step'] = {
                    'task_title': current_step.task.title,
                    'task_status': current_step.task.status,
                    'execution_order': current_step.execution_order
                }

            return status

        except Process.DoesNotExist:
            raise ValueError(f"Proceso {process_id} no encontrado")


# Tareas Celery para ejecución asíncrona

@shared_task
def _execute_automatic_task(task_id: int, execution_id: int):
    """
    Tarea Celery para ejecutar tareas automáticas
    """
    try:
        task = Task.objects.get(id=task_id)
        execution = ProcessExecution.objects.get(id=execution_id)

        logger.info(f"Ejecutando tarea automática {task.title}")

        # Aquí puedes agregar la lógica específica para cada tipo de tarea automática
        # Por ejemplo, integración con SII, procesamiento de documentos, etc.

        if task.task_type == 'automatic':
            success = _execute_task_logic(task)

            if success:
                task.complete_task({'executed_by': 'process_engine', 'execution_id': execution_id})
                execution.completed_steps += 1
            else:
                task.fail_task("Error en ejecución automática")
                execution.failed_steps += 1
                execution.error_count += 1

            execution.save()

            # Continuar con el siguiente paso
            engine = ProcessEngine()
            engine._execute_next_steps(execution)

    except Exception as e:
        logger.error(f"Error en tarea automática {task_id}: {str(e)}")
        try:
            task = Task.objects.get(id=task_id)
            task.fail_task(str(e))
            execution = ProcessExecution.objects.get(id=execution_id)
            execution.failed_steps += 1
            execution.error_count += 1
            execution.last_error = str(e)
            execution.save()
        except:
            pass


def _execute_task_logic(task: Task) -> bool:
    """
    Lógica específica para ejecutar diferentes tipos de tareas automáticas
    """
    task_data = task.task_data

    # Ejemplo de lógica basada en el tipo de proceso
    if 'sii_sync' in task.title.lower():
        return _execute_sii_sync_task(task)
    elif 'document_process' in task.title.lower():
        return _execute_document_processing_task(task)
    elif 'tax_calculation' in task.title.lower():
        return _execute_tax_calculation_task(task)
    else:
        # Tarea genérica - marcar como completada
        logger.info(f"Ejecutando tarea genérica: {task.title}")
        return True


def _execute_sii_sync_task(task: Task) -> bool:
    """
    Ejecuta tareas de sincronización con el SII
    """
    # Aquí integrarías con tu sistema SII existente
    logger.info(f"Ejecutando sincronización SII para tarea: {task.title}")
    # Ejemplo: sii_service.sync_documents(company_rut=task.company_rut)
    return True


def _execute_document_processing_task(task: Task) -> bool:
    """
    Ejecuta tareas de procesamiento de documentos
    """
    logger.info(f"Ejecutando procesamiento de documentos para tarea: {task.title}")
    # Ejemplo: document_service.process_documents(task.task_data)
    return True


def _execute_tax_calculation_task(task: Task) -> bool:
    """
    Ejecuta tareas de cálculos tributarios
    """
    logger.info(f"Ejecutando cálculo tributario para tarea: {task.title}")
    # Ejemplo: tax_service.calculate_taxes(task.task_data)
    return True


# Funciones de utilidad para crear procesos comunes

class ProcessTemplateFactory:
    """
    Factory para crear procesos comunes basados en plantillas
    """

    @staticmethod
    def create_monthly_f29_process(company_rut: str, company_dv: str,
                                  period: str, assigned_to: str) -> Process:
        """
        Crea un proceso para declaración F29 mensual
        """
        process_name = f"F29 {period} - {company_rut}-{company_dv}"

        process = Process.objects.create(
            name=process_name,
            description=f"Declaración F29 para el período {period}",
            process_type='tax_monthly',
            company_rut=company_rut,
            company_dv=company_dv,
            assigned_to=assigned_to,
            created_by=assigned_to,
            config_data={
                'period': period,
                'form_type': 'f29',
                'auto_submit': False
            }
        )

        # Crear tareas del proceso
        tasks_config = [
            {
                'title': f'Sincronizar DTEs del SII - {period}',
                'task_type': 'automatic',
                'order': 1,
                'optional': False,
                'parallel': False
            },
            {
                'title': f'Validar documentos recibidos - {period}',
                'task_type': 'manual',
                'order': 2,
                'optional': False,
                'parallel': False
            },
            {
                'title': f'Calcular montos IVA - {period}',
                'task_type': 'automatic',
                'order': 3,
                'optional': False,
                'parallel': False
            },
            {
                'title': f'Generar borrador F29 - {period}',
                'task_type': 'automatic',
                'order': 4,
                'optional': False,
                'parallel': False
            },
            {
                'title': f'Revisión final F29 - {period}',
                'task_type': 'manual',
                'order': 5,
                'optional': False,
                'parallel': False
            },
            {
                'title': f'Enviar F29 al SII - {period}',
                'task_type': 'automatic',
                'order': 6,
                'optional': True,
                'parallel': False,
                'conditions': {'previous_task_status': 'completed'}
            }
        ]

        for task_config in tasks_config:
            # Crear tarea
            task = Task.objects.create(
                title=task_config['title'],
                task_type=task_config['task_type'],
                company_rut=company_rut,
                company_dv=company_dv,
                assigned_to=assigned_to,
                created_by=assigned_to,
                task_data={
                    'period': period,
                    'form_type': 'f29'
                }
            )

            # Asociar tarea al proceso
            ProcessTask.objects.create(
                process=process,
                task=task,
                execution_order=task_config['order'],
                is_optional=task_config['optional'],
                can_run_parallel=task_config['parallel'],
                execution_conditions=task_config.get('conditions', {})
            )

        return process

    @staticmethod
    def create_annual_declaration_process(company_rut: str, company_dv: str,
                                        year: str, assigned_to: str) -> Process:
        """
        Crea un proceso para declaración anual
        """
        process_name = f"Declaración Anual {year} - {company_rut}-{company_dv}"

        process = Process.objects.create(
            name=process_name,
            description=f"Declaración de renta anual para el año {year}",
            process_type='tax_annual',
            company_rut=company_rut,
            company_dv=company_dv,
            assigned_to=assigned_to,
            created_by=assigned_to,
            config_data={
                'year': year,
                'requires_external_accountant': True,
                'estimated_duration_days': 30
            }
        )

        # Las tareas específicas se agregarían según los requerimientos
        return process