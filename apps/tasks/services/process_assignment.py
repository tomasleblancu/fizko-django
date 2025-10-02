"""
Servicio de asignación automática de procesos tributarios
"""
import logging
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

from apps.tasks.models import (
    ProcessTemplateConfig,
    ProcessAssignmentRule,
    CompanySegment,
    Process
)
from apps.companies.models import Company
from apps.taxpayers.models import TaxPayer

logger = logging.getLogger(__name__)


class ProcessAssignmentService:
    """
    Servicio para evaluar segmentos de empresas y asignar procesos automáticamente
    """

    @staticmethod
    def evaluate_company_segment(company: Company) -> Optional[CompanySegment]:
        """
        Evalúa a qué segmento pertenece una empresa según los criterios definidos

        Args:
            company: Empresa a evaluar

        Returns:
            CompanySegment si encuentra un segmento aplicable, None si no
        """
        if not hasattr(company, 'taxpayer'):
            logger.warning(f"Empresa {company.id} no tiene taxpayer asociado")
            return None

        # Obtener todos los segmentos activos ordenados por tipo
        active_segments = CompanySegment.objects.filter(is_active=True).order_by('segment_type')

        for segment in active_segments:
            if ProcessAssignmentService._matches_segment_criteria(company, segment):
                logger.info(f"Empresa {company.business_name} asignada al segmento '{segment.name}'")
                return segment

        logger.info(f"Empresa {company.business_name} no coincide con ningún segmento")
        return None

    @staticmethod
    def _matches_segment_criteria(company: Company, segment: CompanySegment) -> bool:
        """
        Verifica si una empresa cumple con los criterios de un segmento

        Args:
            company: Empresa a evaluar
            segment: Segmento con criterios

        Returns:
            True si la empresa cumple los criterios, False si no
        """
        criteria = segment.criteria
        if not criteria:
            return False

        try:
            # Evaluar criterios por tamaño (número de empleados)
            if 'size' in criteria:
                size_criteria = criteria['size']
                # TODO: Agregar campo employees_count al modelo Company
                # Por ahora asumimos que no cumple si no está implementado
                if 'min_employees' in size_criteria or 'max_employees' in size_criteria:
                    # Placeholder: implementar cuando se agregue el campo
                    pass

            # Evaluar criterios por actividad económica
            if 'economic_activity' in criteria:
                activities = criteria['economic_activity']
                if not isinstance(activities, list):
                    activities = [activities]

                # TODO: Agregar campo economic_activity al TaxPayer
                # Por ahora retornamos False si no está implementado
                pass

            # Evaluar criterios por régimen tributario
            if 'tax_regime' in criteria:
                tax_regimes = criteria['tax_regime']
                if not isinstance(tax_regimes, list):
                    tax_regimes = [tax_regimes]

                # Verificar si el taxpayer tiene configuración de procesos que indica régimen
                taxpayer = company.taxpayer
                settings = taxpayer.get_process_settings()

                # Inferir régimen por configuración
                if 'f29_monthly' in tax_regimes and settings.get('f29_monthly'):
                    return True
                if 'f3323_quarterly' in tax_regimes and settings.get('f3323_quarterly'):
                    return True

            # Evaluar criterios por ingresos anuales
            if 'annual_revenue' in criteria:
                revenue_criteria = criteria['annual_revenue']
                # TODO: Implementar cuando se agregue campo de ingresos
                pass

            # Evaluar criterios personalizados
            if 'custom_conditions' in criteria:
                custom = criteria['custom_conditions']
                if not isinstance(custom, list):
                    custom = [custom]

                taxpayer = company.taxpayer
                settings = taxpayer.get_process_settings()

                # Ejemplos de condiciones personalizadas
                if 'has_exports' in custom:
                    # TODO: Implementar verificación de exportaciones
                    pass

                if 'requires_f3323' in custom:
                    if settings.get('f3323_quarterly'):
                        return True

            # Si llegamos aquí y no hay criterios específicos evaluados,
            # retornamos False por defecto
            return False

        except Exception as e:
            logger.error(f"Error evaluando criterios del segmento {segment.name}: {str(e)}")
            return False

    @staticmethod
    def assign_segment_to_company(company: Company, auto_assign_processes: bool = True) -> Optional[CompanySegment]:
        """
        Asigna el segmento correcto a una empresa y opcionalmente sus procesos

        Args:
            company: Empresa a la cual asignar segmento
            auto_assign_processes: Si se deben asignar procesos automáticamente

        Returns:
            CompanySegment asignado o None
        """
        if not hasattr(company, 'taxpayer'):
            logger.warning(f"Empresa {company.id} no tiene taxpayer asociado")
            return None

        # Evaluar segmento
        segment = ProcessAssignmentService.evaluate_company_segment(company)

        if segment:
            # Asignar segmento al taxpayer
            taxpayer = company.taxpayer
            taxpayer.company_segment = segment
            taxpayer.save(update_fields=['company_segment'])

            logger.info(f"Segmento '{segment.name}' asignado a {company.business_name}")

            # Asignar procesos si se solicita
            if auto_assign_processes:
                ProcessAssignmentService.assign_processes_by_rules(company)

        return segment

    @staticmethod
    def assign_processes_by_rules(company: Company) -> List[Process]:
        """
        Asigna procesos a una empresa según las reglas de asignación del segmento

        Args:
            company: Empresa a la cual asignar procesos

        Returns:
            Lista de procesos creados
        """
        if not hasattr(company, 'taxpayer'):
            logger.warning(f"Empresa {company.id} no tiene taxpayer asociado")
            return []

        taxpayer = company.taxpayer
        if not taxpayer.company_segment:
            logger.info(f"Empresa {company.business_name} no tiene segmento asignado")
            return []

        # Obtener reglas aplicables
        rules = ProcessAssignmentRule.objects.filter(
            segment=taxpayer.company_segment,
            is_active=True,
            auto_apply=True
        ).select_related('template').order_by('-priority')

        created_processes = []

        with transaction.atomic():
            for rule in rules:
                if rule.is_valid() and rule.applies_to_company(company):
                    try:
                        # Aplicar plantilla a la empresa
                        process = ProcessAssignmentService.apply_template_to_company(
                            template=rule.template,
                            company=company,
                            created_by=taxpayer.company.taxpayer_sii_credentials.user.email if hasattr(company, 'taxpayer_sii_credentials') else 'system'
                        )

                        if process:
                            created_processes.append(process)
                            logger.info(f"Proceso '{process.name}' creado para {company.business_name} desde plantilla '{rule.template.name}'")

                    except Exception as e:
                        logger.error(f"Error aplicando plantilla '{rule.template.name}' a {company.business_name}: {str(e)}")
                        continue

        return created_processes

    @staticmethod
    def apply_template_to_company(
        template: ProcessTemplateConfig,
        company: Company,
        created_by: str = 'system',
        config_overrides: Dict[str, Any] = None
    ) -> Optional[Process]:
        """
        Aplica una plantilla de proceso a una empresa específica

        Args:
            template: Plantilla a aplicar
            company: Empresa objetivo
            created_by: Email del usuario que crea el proceso
            config_overrides: Sobrescribir valores de configuración

        Returns:
            Proceso creado o None si falla
        """
        if not template.is_available():
            logger.warning(f"Plantilla '{template.name}' no está disponible")
            return None

        try:
            # Extraer RUT y DV
            rut_parts = company.tax_id.split('-')
            company_rut = rut_parts[0].replace('.', '')
            company_dv = rut_parts[1] if len(rut_parts) > 1 else 'K'

            # Preparar configuración del proceso
            config_data = {**template.template_config}
            if config_overrides:
                config_data.update(config_overrides)

            # Determinar recurrencia
            is_recurring = template.default_recurrence_type is not None
            recurrence_config = template.default_recurrence_config if is_recurring else {}

            # Crear el proceso
            process = Process.objects.create(
                name=f"{template.name} - {company.business_name}",
                description=template.description,
                process_type=template.process_type,
                company=company,
                company_rut=company_rut,
                company_dv=company_dv,
                created_by=created_by,
                assigned_to=created_by,
                status='active',
                config_data=config_data,
                is_recurring=is_recurring,
                recurrence_type=template.default_recurrence_type,
                recurrence_config=recurrence_config
            )

            # Crear tareas del proceso desde la plantilla
            ProcessAssignmentService._create_tasks_from_template(process, template)

            # Incrementar contador de uso de la plantilla
            template.increment_usage()

            logger.info(f"Proceso '{process.name}' creado exitosamente desde plantilla '{template.name}'")
            return process

        except Exception as e:
            logger.error(f"Error creando proceso desde plantilla '{template.name}': {str(e)}")
            return None

    @staticmethod
    def _create_tasks_from_template(process: Process, template: ProcessTemplateConfig):
        """
        Crea las tareas de un proceso basándose en las tareas de la plantilla

        Args:
            process: Proceso recién creado
            template: Plantilla con las definiciones de tareas
        """
        from apps.tasks.models import Task, ProcessTask

        template_tasks = template.template_tasks.all().order_by('execution_order')

        for template_task in template_tasks:
            # Crear la tarea
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
                task_data=template_task.task_config
            )

            # Vincular tarea con el proceso
            ProcessTask.objects.create(
                process=process,
                task=task,
                execution_order=template_task.execution_order,
                is_optional=template_task.is_optional,
                can_run_parallel=template_task.can_run_parallel,
                due_date_offset_days=template_task.due_date_offset_days,
                due_date_from_previous=template_task.due_date_from_previous,
                context_data={'template_task_id': template_task.id}
            )

            logger.debug(f"Tarea '{task.title}' creada para proceso '{process.name}'")

    @staticmethod
    def get_applicable_templates(company: Company) -> List[ProcessTemplateConfig]:
        """
        Obtiene todas las plantillas de procesos aplicables a una empresa

        Args:
            company: Empresa a evaluar

        Returns:
            Lista de plantillas aplicables
        """
        if not hasattr(company, 'taxpayer'):
            return []

        taxpayer = company.taxpayer
        if not taxpayer.company_segment:
            # Intentar asignar segmento automáticamente
            ProcessAssignmentService.assign_segment_to_company(company, auto_assign_processes=False)
            taxpayer.refresh_from_db()

            if not taxpayer.company_segment:
                return []

        # Obtener reglas activas para el segmento
        rules = ProcessAssignmentRule.objects.filter(
            segment=taxpayer.company_segment,
            is_active=True
        ).select_related('template').order_by('-priority')

        # Filtrar plantillas que aplican
        applicable_templates = []
        for rule in rules:
            if rule.is_valid() and rule.applies_to_company(company):
                if rule.template.is_available():
                    applicable_templates.append(rule.template)

        return applicable_templates

    @staticmethod
    def bulk_assign_segments(companies: List[Company] = None) -> Dict[str, Any]:
        """
        Asigna segmentos en masa a múltiples empresas

        Args:
            companies: Lista de empresas. Si es None, procesa todas las empresas

        Returns:
            Dict con estadísticas del proceso
        """
        if companies is None:
            companies = Company.objects.all()

        stats = {
            'total': 0,
            'assigned': 0,
            'failed': 0,
            'no_segment': 0
        }

        for company in companies:
            stats['total'] += 1

            try:
                segment = ProcessAssignmentService.assign_segment_to_company(
                    company,
                    auto_assign_processes=False  # No asignar procesos automáticamente en masa
                )

                if segment:
                    stats['assigned'] += 1
                else:
                    stats['no_segment'] += 1

            except Exception as e:
                logger.error(f"Error asignando segmento a {company.business_name}: {str(e)}")
                stats['failed'] += 1

        logger.info(f"Asignación masiva completada: {stats}")
        return stats
