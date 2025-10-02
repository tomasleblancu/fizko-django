"""
Factory para crear procesos desde plantillas configurables
"""
import logging
from datetime import date, timedelta
from typing import Dict, Any, Optional
from django.utils import timezone

from apps.tasks.models import (
    Process,
    ProcessTemplateConfig,
    ProcessTemplateTask,
    Task,
    ProcessTask
)
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class ProcessTemplateFactory:
    """
    Factory mejorado para crear procesos desde ProcessTemplateConfig
    """

    @staticmethod
    def create_from_config(
        template: ProcessTemplateConfig,
        company: Company,
        created_by: str,
        assigned_to: str = None,
        start_date: date = None,
        config_overrides: Dict[str, Any] = None
    ) -> Optional[Process]:
        """
        Crea un proceso completo desde una ProcessTemplateConfig

        Args:
            template: Configuración de plantilla
            company: Empresa para la cual crear el proceso
            created_by: Email del creador
            assigned_to: Email del asignado (si None, usa created_by)
            start_date: Fecha de inicio (si None, usa hoy)
            config_overrides: Sobrescribir valores de configuración

        Returns:
            Proceso creado o None si falla
        """
        if not template.is_available():
            logger.error(f"Plantilla '{template.name}' no está disponible")
            return None

        try:
            # Valores por defecto
            if assigned_to is None:
                assigned_to = created_by

            if start_date is None:
                start_date = timezone.now()

            # Extraer RUT y DV
            rut_parts = company.tax_id.split('-')
            company_rut = rut_parts[0].replace('.', '')
            company_dv = rut_parts[1] if len(rut_parts) > 1 else 'K'

            # Preparar configuración
            config_data = {
                **template.default_values,
                **template.template_config
            }

            if config_overrides:
                config_data.update(config_overrides)

            # Crear proceso
            process = Process.objects.create(
                name=template.name,
                description=template.description,
                process_type=template.process_type,
                company=company,
                company_rut=company_rut,
                company_dv=company_dv,
                created_by=created_by,
                assigned_to=assigned_to,
                status='active',
                start_date=start_date,
                config_data=config_data,
                is_recurring=template.default_recurrence_type is not None,
                recurrence_type=template.default_recurrence_type,
                recurrence_config=template.default_recurrence_config or {}
            )

            # Crear tareas del proceso
            ProcessTemplateFactory._create_tasks_from_template(
                process=process,
                template=template,
                start_date=start_date
            )

            # Incrementar contador de uso
            template.increment_usage()

            logger.info(f"Proceso '{process.name}' creado desde template config '{template.name}'")
            return process

        except Exception as e:
            logger.error(f"Error creando proceso desde template config: {str(e)}")
            return None

    @staticmethod
    def _create_tasks_from_template(
        process: Process,
        template: ProcessTemplateConfig,
        start_date: date
    ):
        """
        Crea tareas desde ProcessTemplateTask

        Args:
            process: Proceso padre
            template: Template con las tareas
            start_date: Fecha de inicio del proceso
        """
        template_tasks = template.template_tasks.all().order_by('execution_order')

        for template_task in template_tasks:
            # Calcular fecha límite
            due_date = ProcessTemplateFactory._calculate_task_due_date(
                start_date=start_date,
                offset_days=template_task.due_date_offset_days
            )

            # Crear tarea
            task = Task.objects.create(
                title=template_task.task_title,
                description=template_task.task_description,
                task_type=template_task.task_type,
                company_rut=process.company_rut,
                company_dv=process.company_dv,
                assigned_to=process.assigned_to,
                created_by=process.created_by,
                priority=template_task.priority,
                status='pending',
                due_date=due_date,
                task_data=template_task.task_config,
                estimated_duration=timedelta(hours=template_task.estimated_hours) if template_task.estimated_hours else None
            )

            # Vincular tarea con proceso
            ProcessTask.objects.create(
                process=process,
                task=task,
                execution_order=template_task.execution_order,
                is_optional=template_task.is_optional,
                can_run_parallel=template_task.can_run_parallel,
                due_date_offset_days=template_task.due_date_offset_days,
                due_date_from_previous=template_task.due_date_from_previous,
                context_data={
                    'template_task_id': template_task.id,
                    'template_id': template.id
                }
            )

    @staticmethod
    def _calculate_task_due_date(start_date: date, offset_days: int = None) -> Optional[date]:
        """
        Calcula la fecha límite de una tarea

        Args:
            start_date: Fecha de inicio del proceso
            offset_days: Días desde el inicio

        Returns:
            Fecha límite o None
        """
        if offset_days is None:
            return None

        return start_date + timedelta(days=offset_days)

    @staticmethod
    def create_monthly_f29_process(
        company_rut: str,
        company_dv: str,
        period: str,
        assigned_to: str = 'admin@fizko.cl',
        template: ProcessTemplateConfig = None
    ) -> Optional[Process]:
        """
        Crea proceso F29 mensual (método legacy, ahora usa templates)

        Args:
            company_rut: RUT sin formato
            company_dv: Dígito verificador
            period: Período en formato YYYY-MM
            assigned_to: Email del asignado
            template: Template a usar (si None, busca uno por defecto)

        Returns:
            Proceso creado o None
        """
        try:
            # Buscar template F29 si no se proporciona
            if template is None:
                template = ProcessTemplateConfig.objects.filter(
                    process_type='tax_monthly',
                    is_active=True,
                    status='active'
                ).first()

                if not template:
                    logger.warning("No hay template F29 disponible, creando proceso legacy")
                    return ProcessTemplateFactory._create_legacy_f29_process(
                        company_rut, company_dv, period, assigned_to
                    )

            # Obtener empresa
            from apps.companies.models import Company
            full_rut = f"{company_rut}-{company_dv}"
            company = Company.objects.filter(tax_id=full_rut).first()

            if not company:
                logger.error(f"No se encontró empresa con RUT {full_rut}")
                return None

            # Crear desde template
            return ProcessTemplateFactory.create_from_config(
                template=template,
                company=company,
                created_by=assigned_to,
                assigned_to=assigned_to,
                config_overrides={'period': period}
            )

        except Exception as e:
            logger.error(f"Error creando proceso F29: {str(e)}")
            return None

    @staticmethod
    def _create_legacy_f29_process(
        company_rut: str,
        company_dv: str,
        period: str,
        assigned_to: str
    ) -> Optional[Process]:
        """
        Crea proceso F29 de manera legacy (sin template)
        Solo se usa si no hay templates configurados
        """
        try:
            from apps.companies.models import Company
            full_rut = f"{company_rut}-{company_dv}"
            company = Company.objects.filter(tax_id=full_rut).first()

            if not company:
                logger.error(f"No se encontró empresa con RUT {full_rut}")
                return None

            process = Process.objects.create(
                name=f"F29 {period} - {full_rut}",
                description=f"Declaración mensual de IVA período {period}",
                process_type='tax_monthly',
                company=company,
                company_rut=company_rut,
                company_dv=company_dv,
                created_by=assigned_to,
                assigned_to=assigned_to,
                status='active',
                config_data={'period': period, 'form_type': 'f29'}
            )

            logger.info(f"Proceso F29 legacy creado: {process.name}")
            return process

        except Exception as e:
            logger.error(f"Error creando proceso F29 legacy: {str(e)}")
            return None

    @staticmethod
    def clone_template(template: ProcessTemplateConfig, new_name: str, created_by: str) -> Optional[ProcessTemplateConfig]:
        """
        Clona una plantilla completa con todas sus tareas

        Args:
            template: Template a clonar
            new_name: Nombre para la nueva plantilla
            created_by: Email del creador

        Returns:
            Nueva plantilla clonada o None
        """
        try:
            # Crear nueva plantilla
            new_template = ProcessTemplateConfig.objects.create(
                name=new_name,
                description=template.description,
                process_type=template.process_type,
                status='inactive',  # Inactiva por defecto
                is_active=False,
                default_recurrence_type=template.default_recurrence_type,
                default_recurrence_config=template.default_recurrence_config.copy() if template.default_recurrence_config else {},
                template_config=template.template_config.copy() if template.template_config else {},
                available_variables=template.available_variables.copy() if template.available_variables else [],
                default_values=template.default_values.copy() if template.default_values else {},
                created_by=created_by
            )

            # Clonar tareas
            for task in template.template_tasks.all():
                ProcessTemplateTask.objects.create(
                    template=new_template,
                    task_title=task.task_title,
                    task_description=task.task_description,
                    task_type=task.task_type,
                    priority=task.priority,
                    execution_order=task.execution_order,
                    is_optional=task.is_optional,
                    can_run_parallel=task.can_run_parallel,
                    due_date_offset_days=task.due_date_offset_days,
                    due_date_from_previous=task.due_date_from_previous,
                    estimated_hours=task.estimated_hours,
                    task_config=task.task_config.copy() if task.task_config else {}
                )

            logger.info(f"Template '{template.name}' clonado como '{new_name}'")
            return new_template

        except Exception as e:
            logger.error(f"Error clonando template: {str(e)}")
            return None
