"""
Process management tasks - Creation, updates, and lifecycle management
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from apps.taxpayers.models import TaxPayer
from apps.companies.models import Company
from apps.tasks.models import Process, ProcessTemplate, Task
from apps.tasks.process_engine import ProcessTemplateFactory

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_processes_from_taxpayer_settings(self, company_id: int):
    """
    Crea los procesos tributarios según la configuración del TaxPayer
    Se ejecuta después del onboarding cuando se completa la configuración

    Args:
        company_id: ID de la empresa para la cual crear procesos

    Returns:
        dict: Resumen de procesos creados y errores si los hay
    """
    try:
        logger.info(f"🚀 Iniciando creación de procesos para empresa ID: {company_id}")

        # Obtener la empresa y su TaxPayer
        try:
            company = Company.objects.get(id=company_id)
            taxpayer = company.taxpayer
        except Company.DoesNotExist:
            error = f"No se encontró empresa con ID: {company_id}"
            logger.error(error)
            return {'status': 'error', 'message': error}
        except AttributeError:
            error = f"La empresa {company_id} no tiene TaxPayer asociado"
            logger.error(error)
            return {'status': 'error', 'message': error}

        # Obtener configuración de procesos del TaxPayer
        process_settings = taxpayer.get_process_settings()
        logger.info(f"📋 Configuración de procesos: {process_settings}")

        created_processes = []
        errors = []

        # Extraer RUT y DV del tax_id
        tax_id_parts = company.tax_id.split('-')
        company_rut = tax_id_parts[0].replace('.', '')
        company_dv = tax_id_parts[1] if len(tax_id_parts) > 1 else ''

        # Obtener usuario asignado (por defecto el owner de la empresa)
        from apps.accounts.models import UserRole
        owner_role = UserRole.objects.filter(
            company=company,
            role__name='owner',
            active=True
        ).first()

        assigned_to = owner_role.user.email if owner_role else 'admin@fizko.cl'

        with transaction.atomic():
            # 1. Crear proceso F29 mensual si está habilitado
            if process_settings.get('f29_monthly', False):
                try:
                    # Determinar el mes actual para el F29
                    today = timezone.now()
                    period = today.strftime("%Y-%m")

                    # Verificar si ya existe el proceso para este período
                    existing_f29 = Process.objects.filter(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        process_type='f29',
                        config_data__period=period
                    ).exists()

                    if not existing_f29:
                        # Buscar la plantilla F29
                        f29_template = ProcessTemplate.objects.filter(
                            process_type='f29',
                            is_active=True
                        ).first()

                        if f29_template:
                            process = ProcessTemplateFactory.create_monthly_f29_process(
                                company_rut=company_rut,
                                company_dv=company_dv,
                                period=period,
                                assigned_to=assigned_to
                            )
                            created_processes.append({
                                'type': 'F29',
                                'period': period,
                                'process_id': process.id,
                                'name': process.name
                            })
                            logger.info(f"✅ Creado proceso F29 para período {period}")
                        else:
                            error = "No se encontró plantilla F29 activa"
                            errors.append(error)
                            logger.warning(error)
                    else:
                        logger.info(f"ℹ️ Ya existe proceso F29 para período {period}")

                except Exception as e:
                    error = f"Error creando proceso F29: {str(e)}"
                    errors.append(error)
                    logger.error(error)

            # 2. Crear proceso F22 anual si está habilitado
            if process_settings.get('f22_annual', False):
                try:
                    # Determinar el año tributario
                    today = timezone.now()
                    # Si estamos antes de mayo, crear F22 del año anterior
                    # Si estamos después de mayo, crear F22 del año actual
                    if today.month < 5:
                        year = str(today.year - 1)
                    else:
                        year = str(today.year)

                    # Verificar si ya existe el proceso F22 para este año
                    existing_f22 = Process.objects.filter(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        process_type='f22',
                        config_data__year=year
                    ).exists()

                    if not existing_f22:
                        # Buscar la plantilla F22
                        f22_template = ProcessTemplate.objects.filter(
                            process_type='f22',
                            is_active=True
                        ).first()

                        if f22_template:
                            process = ProcessTemplateFactory.create_annual_declaration_process(
                                company_rut=company_rut,
                                company_dv=company_dv,
                                year=year,
                                assigned_to=assigned_to
                            )
                            created_processes.append({
                                'type': 'F22',
                                'year': year,
                                'process_id': process.id,
                                'name': process.name
                            })
                            logger.info(f"✅ Creado proceso F22 para año {year}")
                        else:
                            error = "No se encontró plantilla F22 activa"
                            errors.append(error)
                            logger.warning(error)
                    else:
                        logger.info(f"ℹ️ Ya existe proceso F22 para año {year}")

                except Exception as e:
                    error = f"Error creando proceso F22: {str(e)}"
                    errors.append(error)
                    logger.error(error)

            # 3. Crear proceso F3323 trimestral si está habilitado
            if process_settings.get('f3323_quarterly', False):
                try:
                    # Determinar el trimestre actual
                    today = timezone.now()
                    quarter = (today.month - 1) // 3 + 1
                    period = f"{today.year}-Q{quarter}"

                    # Verificar si ya existe el proceso para este período
                    existing_f3323 = Process.objects.filter(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        process_type='f3323',
                        config_data__period=period
                    ).exists()

                    if not existing_f3323:
                        # Buscar la plantilla F3323
                        f3323_template = ProcessTemplate.objects.filter(
                            process_type='f3323',
                            is_active=True
                        ).first()

                        if f3323_template:
                            # Crear proceso F3323 usando la factory (si existe)
                            # Por ahora, crear un proceso básico
                            process = Process.objects.create(
                                company_rut=company_rut,
                                company_dv=company_dv,
                                name=f"F3323 {period}",
                                description=f"Formulario F3323 Pro Pyme - {period}",
                                process_type='f3323',
                                status='active',
                                assigned_to=assigned_to,
                                config_data={'period': period, 'form_type': 'f3323'}
                            )
                            created_processes.append({
                                'type': 'F3323',
                                'period': period,
                                'process_id': process.id,
                                'name': process.name
                            })
                            logger.info(f"✅ Creado proceso F3323 para período {period}")
                        else:
                            error = "No se encontró plantilla F3323 activa"
                            errors.append(error)
                            logger.warning(error)
                    else:
                        logger.info(f"ℹ️ Ya existe proceso F3323 para período {period}")

                except Exception as e:
                    error = f"Error creando proceso F3323: {str(e)}"
                    errors.append(error)
                    logger.error(error)

        # Resultado final
        result = {
            'status': 'success' if not errors else 'partial',
            'company_id': company_id,
            'company_rut': f"{company_rut}-{company_dv}",
            'created_processes': created_processes,
            'created_count': len(created_processes),
            'errors': errors,
            'timestamp': timezone.now().isoformat()
        }

        if created_processes:
            logger.info(f"✅ Procesos creados exitosamente para empresa {company_id}: {len(created_processes)} procesos")
        else:
            logger.info(f"ℹ️ No se crearon nuevos procesos para empresa {company_id}")

        if errors:
            logger.warning(f"⚠️ Se encontraron {len(errors)} errores durante la creación")

        return result

    except Exception as e:
        error = f"Error crítico creando procesos para empresa {company_id}: {str(e)}"
        logger.error(error)
        # Reintentar la tarea
        raise self.retry(countdown=300, exc=e)


@shared_task(bind=True, max_retries=3)
def ensure_company_processes(self, company_rut, company_dv, assigned_to=None, force_create=False):
    """
    Asegura que una empresa tenga los procesos tributarios requeridos para el período actual.

    Args:
        company_rut: RUT de la empresa
        company_dv: Dígito verificador del RUT
        assigned_to: Email del usuario responsable (opcional)
        force_create: Si es True, crea los procesos incluso si ya existen

    Returns:
        dict: Resultado con procesos creados y errores
    """
    try:
        from .process_engine import ProcessTemplateFactory
        from .models import ProcessTemplate
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        now = timezone.now()
        current_year = now.year
        current_month = now.month

        created_processes = []
        errors = []
        checked_processes = []

        # Determinar el usuario asignado y obtener configuración del TaxPayer
        taxpayer = None
        if not assigned_to:
            # Intentar obtener el owner de la empresa desde el modelo Company si existe
            try:
                from apps.companies.models import Company
                tax_id_with_dv = f"{company_rut}-{company_dv}"
                company = Company.objects.filter(tax_id=tax_id_with_dv).first()
                if company:
                    assigned_to = company.email or 'system@fizko.cl'
                    # Obtener el TaxPayer asociado para revisar configuración
                    taxpayer = getattr(company, 'taxpayer', None)
                else:
                    assigned_to = 'system@fizko.cl'
            except ImportError:
                assigned_to = 'system@fizko.cl'

        # 1. Verificar/crear proceso F29 del mes actual (solo uno por empresa)
        # Verificar primero si el TaxPayer tiene habilitado F29 mensual
        create_f29 = True
        if taxpayer:
            create_f29 = taxpayer.is_process_enabled('f29_monthly')

        if create_f29:
            f29_period = f"{current_year}-{current_month:02d}"
            checked_processes.append(f"F29 {f29_period}")

            # Verificar si ya existe algún proceso F29 activo para esta empresa
            existing_f29 = Process.objects.filter(
                company_rut=company_rut,
                company_dv=company_dv,
                process_type='tax_monthly',
                status__in=['active', 'paused']  # Solo procesos no completados (ya no incluimos draft)
            ).exists()

            # Si no hay ningún proceso F29 activo, crear uno para el período actual
            if not existing_f29 or force_create:
                try:
                    # Verificar si existe plantilla F29
                    f29_template = ProcessTemplate.objects.filter(
                        process_type='tax_monthly',
                        is_active=True
                    ).first()

                    if f29_template:
                        # Crear proceso usando la factory - será recurrente
                        process = ProcessTemplateFactory.create_monthly_f29_process(
                            company_rut=company_rut,
                            company_dv=company_dv,
                            period=f29_period,
                            assigned_to=assigned_to,
                            is_recurring=True
                        )
                        created_processes.append({
                            'type': 'F29',
                            'period': f29_period,
                            'process_id': process.id,
                            'name': process.name
                        })
                        logger.info(f"✅ Creado F29 recurrente para {company_rut}-{company_dv}, período {f29_period}")
                        logger.info(f"ℹ️ Los siguientes períodos se generarán automáticamente al completar este proceso")
                    else:
                        logger.warning("No se encontró plantilla F29 activa. Ejecute primero seed_process_templates")
                        errors.append("No se encontró plantilla F29 activa")

                except Exception as e:
                    error_msg = f"Error creando F29 {f29_period}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            else:
                logger.info(f"ℹ️ Empresa {company_rut}-{company_dv} ya tiene proceso F29 activo")
        else:
            logger.info(f"ℹ️ TaxPayer {company_rut}-{company_dv} no tiene habilitado F29 mensual")

        # 3. Verificar/crear proceso F22 anual (si estamos entre enero y abril)
        if current_month <= 4:  # Solo relevante entre enero y abril
            # Verificar primero si el TaxPayer tiene habilitado F22 anual
            create_f22 = True
            if taxpayer:
                create_f22 = taxpayer.is_process_enabled('f22_annual')

            if create_f22:
                f22_year = str(current_year - 1)  # F22 es para el año anterior
                checked_processes.append(f"F22 {f22_year}")

                existing_f22 = Process.objects.filter(
                    company_rut=company_rut,
                    company_dv=company_dv,
                    process_type='tax_annual',
                    config_data__year=f22_year
                ).exists()

                if not existing_f22 or force_create:
                    try:
                        # Verificar si existe plantilla F22
                        f22_template = ProcessTemplate.objects.filter(
                            process_type='tax_annual',
                            is_active=True
                        ).first()

                        if f22_template:
                            process = ProcessTemplateFactory.create_annual_declaration_process(
                                company_rut=company_rut,
                                company_dv=company_dv,
                                year=f22_year,
                                assigned_to=assigned_to
                            )
                            created_processes.append({
                                'type': 'F22',
                                'year': f22_year,
                                'process_id': process.id,
                                'name': process.name
                            })
                            logger.info(f"✅ Creado F22 para {company_rut}-{company_dv}, año {f22_year}")
                        else:
                            logger.warning("No se encontró plantilla F22 activa")
                            errors.append("No se encontró plantilla F22 activa")

                    except Exception as e:
                        error_msg = f"Error creando F22 {f22_year}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                else:
                    logger.info(f"ℹ️ Empresa {company_rut}-{company_dv} ya tiene proceso F22 para {f22_year}")
            else:
                logger.info(f"ℹ️ TaxPayer {company_rut}-{company_dv} no tiene habilitado F22 anual")

        # 4. Verificar procesos Pro Pyme F3323 (trimestral) si aplica
        # Esto requiere verificar si la empresa está en régimen Pro Pyme
        try:
            from apps.companies.models import Company
            tax_id_with_dv = f"{company_rut}-{company_dv}"
            company = Company.objects.filter(tax_id=tax_id_with_dv).first()

            if company and getattr(company, 'tax_regime', None) == 'pro_pyme':
                # Verificar si el TaxPayer tiene habilitado F3323 trimestral
                create_f3323 = True
                if taxpayer:
                    create_f3323 = taxpayer.is_process_enabled('f3323_quarterly')

                if create_f3323:
                    # Determinar el trimestre actual
                    current_quarter = (current_month - 1) // 3 + 1
                    quarter_map = {
                        1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'
                    }
                    quarter_name = quarter_map[current_quarter]

                    f3323_period = f"{current_year}-{quarter_name}"
                    checked_processes.append(f"F3323 {f3323_period}")

                    existing_f3323 = Process.objects.filter(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        config_data__form_type='f3323',
                        config_data__period=f3323_period
                    ).exists()

                    if not existing_f3323 or force_create:
                        # Aquí podrías crear el proceso F3323
                        logger.info(f"Empresa {company_rut}-{company_dv} en Pro Pyme, requiere F3323 {f3323_period}")
                else:
                    logger.info(f"ℹ️ TaxPayer {company_rut}-{company_dv} no tiene habilitado F3323 trimestral")

        except ImportError:
            # El modelo Company no está disponible
            pass
        except Exception as e:
            logger.warning(f"No se pudo verificar régimen Pro Pyme: {str(e)}")

        # Resumen de resultados
        result = {
            'success': len(errors) == 0,
            'company': f"{company_rut}-{company_dv}",
            'checked_processes': checked_processes,
            'created_processes': created_processes,
            'created_count': len(created_processes),
            'errors': errors,
            'timestamp': now.isoformat()
        }

        if created_processes:
            logger.info(f"✅ Procesos creados para {company_rut}-{company_dv}: {len(created_processes)}")
            # Enviar notificación si se crearon procesos
            from .notifications import send_process_created_notification
            for proc in created_processes:
                send_process_created_notification.delay(proc['process_id'])
        else:
            logger.info(f"ℹ️ Todos los procesos ya existen para {company_rut}-{company_dv}")

        return result

    except Exception as e:
        logger.error(f"Error asegurando procesos para {company_rut}-{company_dv}: {str(e)}")
        raise self.retry(countdown=300, exc=e)  # Reintentar en 5 minutos


@shared_task
def ensure_all_companies_have_processes(dry_run=False):
    """
    Asegura que todas las empresas activas tengan los procesos tributarios requeridos.

    Args:
        dry_run: Si es True, solo simula y reporta qué se crearía sin crear nada

    Returns:
        dict: Resumen de la operación con empresas procesadas y procesos creados
    """
    try:
        # Intentar obtener las empresas desde el modelo Company
        companies_data = []

        try:
            from apps.companies.models import Company

            # Obtener todas las empresas activas
            companies = Company.objects.filter(is_active=True)

            for company in companies:
                # Extraer RUT y DV del tax_id (formato: "RUT-DV")
                if company.tax_id and '-' in company.tax_id:
                    rut_parts = company.tax_id.split('-')
                    if len(rut_parts) == 2:
                        companies_data.append({
                            'rut': rut_parts[0],
                            'dv': rut_parts[1],
                            'name': company.business_name or company.display_name,
                            'assigned_to': company.email or 'system@fizko.cl'
                        })

            logger.info(f"📊 Encontradas {len(companies)} empresas activas en la base de datos")

        except ImportError:
            # Si no existe el modelo Company, buscar en los procesos existentes
            logger.warning("Modelo Company no disponible, obteniendo empresas desde procesos existentes")

            # Obtener empresas únicas desde los procesos existentes
            unique_companies = Process.objects.values('company_rut', 'company_dv').distinct()

            for company in unique_companies:
                if company['company_rut'] and company['company_dv']:
                    companies_data.append({
                        'rut': company['company_rut'],
                        'dv': company['company_dv'],
                        'name': f"{company['company_rut']}-{company['company_dv']}",
                        'assigned_to': 'system@fizko.cl'
                    })

            logger.info(f"📊 Encontradas {len(companies_data)} empresas desde procesos existentes")

        # Procesar cada empresa
        results = {
            'success': True,
            'dry_run': dry_run,
            'companies_processed': 0,
            'companies_with_new_processes': 0,
            'total_processes_created': 0,
            'companies_details': [],
            'errors': [],
            'timestamp': timezone.now().isoformat()
        }

        for company_data in companies_data:
            try:
                company_rut = company_data['rut']
                company_dv = company_data['dv']
                assigned_to = company_data.get('assigned_to', 'system@fizko.cl')

                if dry_run:
                    # Modo simulación: solo reportar qué se crearía
                    logger.info(f"🔍 [DRY RUN] Verificando empresa {company_rut}-{company_dv}")

                    # Simular qué procesos se crearían
                    now = timezone.now()
                    current_year = now.year
                    current_month = now.month

                    would_create = []

                    # Verificar F29 - solo si no hay ningún proceso activo
                    f29_period = f"{current_year}-{current_month:02d}"
                    if not Process.objects.filter(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        process_type='tax_monthly',
                        status__in=['active', 'paused']
                    ).exists():
                        would_create.append(f"F29 {f29_period} (recurrente)")

                    # Verificar F22 si estamos en período
                    if current_month <= 4:
                        f22_year = str(current_year - 1)
                        if not Process.objects.filter(
                            company_rut=company_rut,
                            company_dv=company_dv,
                            process_type='tax_annual',
                            config_data__year=f22_year
                        ).exists():
                            would_create.append(f"F22 {f22_year}")

                    if would_create:
                        results['companies_with_new_processes'] += 1
                        results['total_processes_created'] += len(would_create)

                    results['companies_details'].append({
                        'company': f"{company_rut}-{company_dv}",
                        'name': company_data.get('name', 'Unknown'),
                        'would_create': would_create,
                        'count': len(would_create)
                    })

                else:
                    # Modo real: crear procesos
                    result = ensure_company_processes(
                        company_rut=company_rut,
                        company_dv=company_dv,
                        assigned_to=assigned_to,
                        force_create=False
                    )

                    if result['created_count'] > 0:
                        results['companies_with_new_processes'] += 1
                        results['total_processes_created'] += result['created_count']

                    results['companies_details'].append({
                        'company': f"{company_rut}-{company_dv}",
                        'name': company_data.get('name', 'Unknown'),
                        'created': result.get('created_processes', []),
                        'count': result['created_count'],
                        'errors': result.get('errors', [])
                    })

                    if result.get('errors'):
                        results['errors'].extend(result['errors'])

                results['companies_processed'] += 1

            except Exception as e:
                error_msg = f"Error procesando empresa {company_data}: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                results['success'] = False

        # Logging del resumen
        if dry_run:
            logger.info(f"🔍 [DRY RUN] Simulación completada:")
            logger.info(f"  - Empresas analizadas: {results['companies_processed']}")
            logger.info(f"  - Empresas que necesitan procesos: {results['companies_with_new_processes']}")
            logger.info(f"  - Procesos que se crearían: {results['total_processes_created']}")
        else:
            logger.info(f"✅ Aseguramiento de procesos completado:")
            logger.info(f"  - Empresas procesadas: {results['companies_processed']}")
            logger.info(f"  - Empresas con nuevos procesos: {results['companies_with_new_processes']}")
            logger.info(f"  - Total procesos creados: {results['total_processes_created']}")

            if results['errors']:
                logger.warning(f"  - Errores encontrados: {len(results['errors'])}")

        return results

    except Exception as e:
        logger.error(f"Error en ensure_all_companies_have_processes: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }