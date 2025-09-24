"""
Tareas de Celery para sincronización de formularios tributarios desde SII
"""
import logging
from datetime import datetime
from typing import Optional

from celery import shared_task
from django.utils import timezone

from ..models import SIISyncLog
from ..rpa.sii_rpa_service import RealSIIService
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='sii', autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_tax_forms_task(
    self,
    company_rut: str,
    company_dv: str,
    anio: str,
    mes: Optional[str] = None,
    user_email: str = None,
    folio: Optional[str] = None,
    form_type: str = 'f29'
):
    """
    Tarea de Celery para sincronizar formularios tributarios desde SII.

    Args:
        company_rut: RUT de la empresa sin dígito verificador
        company_dv: Dígito verificador de la empresa
        anio: Año a consultar (YYYY)
        mes: Mes a consultar (MM), opcional para búsqueda anual
        user_email: Email del usuario que solicita la sincronización
        folio: Folio específico a consultar, opcional
        form_type: Tipo de formulario ('f29', 'f3323', etc.)
    """
    task_id = self.request.id
    full_rut = f"{company_rut}-{company_dv}"

    logger.info(f"🚀 [Task {task_id}] Iniciando sincronización de formularios {form_type.upper()} para {full_rut}")
    logger.info(f"   Período: {anio}-{mes if mes else 'TODO'}")
    logger.info(f"   Usuario: {user_email}")
    logger.info(f"   Folio específico: {folio if folio else 'TODOS'}")

    # Crear log de sincronización
    sync_log = SIISyncLog.objects.create(
        company_rut=company_rut,
        company_dv=company_dv.upper(),
        task_id=task_id,
        sync_type='tax_forms',
        status='running',
        user_email=user_email or 'system',
        description=f"Sincronización formularios {form_type.upper()} - {anio}-{mes if mes else 'TODO'}",
        sync_data={
            'anio': anio,
            'mes': mes,
            'folio': folio,
            'form_type': form_type
        }
    )

    try:
        # Obtener credenciales SII de la empresa específica
        from apps.companies.models import Company
        from apps.taxpayers.models import TaxpayerSiiCredentials

        # Buscar la empresa por RUT
        full_company_rut = f"{company_rut}-{company_dv}"
        try:
            company = Company.objects.get(tax_id=full_company_rut)
            logger.info(f"📍 [Task {task_id}] Empresa encontrada: {company.business_name}")
        except Company.DoesNotExist:
            raise ValueError(f"Company not found for RUT {full_company_rut}")

        # Obtener credenciales SII de la empresa
        credentials = TaxpayerSiiCredentials.objects.filter(company=company).first()
        if not credentials:
            raise ValueError(f"No SII credentials found for company {full_company_rut}")

        # Usar credenciales de la empresa
        sii_tax_id = credentials.tax_id
        sii_password = credentials.get_password()

        if not sii_tax_id or not sii_password:
            raise ValueError(f"Invalid SII credentials for company {full_company_rut}")

        logger.info(f"🔑 [Task {task_id}] Usando credenciales SII de la empresa: {sii_tax_id}")

        # Crear servicio SII con credenciales de la empresa
        with RealSIIService(tax_id=sii_tax_id, password=sii_password, headless=True) as sii_service:
            logger.info(f"🔍 [Task {task_id}] Extrayendo formularios desde SII...")

            if form_type.lower() == 'f29':
                # Buscar formularios F29
                resultado = sii_service.buscar_formularios_f29(
                    anio=anio,
                    mes=mes,
                    folio=folio
                )

                if resultado['status'] == 'success':
                    formularios = resultado['data']['formularios']
                    total_formularios = len(formularios)

                    logger.info(f"✅ [Task {task_id}] {total_formularios} formularios encontrados en SII")

                    # Importar y usar servicio de sincronización
                    from apps.forms.services.sync_service import FormsSyncService
                    sync_service = FormsSyncService()

                    # Sincronizar formularios a la base de datos
                    resultado_sync = sync_service.sync_forms_from_sii(
                        formularios=formularios,
                        company_rut=company_rut,
                        company_dv=company_dv,
                        form_type=form_type
                    )

                    # Actualizar log con resultados
                    sync_log.status = 'completed'
                    sync_log.completed_at = timezone.now()
                    sync_log.records_created = resultado_sync['created_count']
                    sync_log.records_updated = resultado_sync['updated_count']
                    sync_log.records_failed = resultado_sync['error_count']
                    sync_log.records_processed = total_formularios
                    sync_log.sync_data.update({
                        'sync_results': resultado_sync,
                        'total_found_in_sii': total_formularios
                    })
                    sync_log.save()

                    logger.info(f"✅ [Task {task_id}] Sincronización completada:")
                    logger.info(f"   - Creados: {resultado_sync['created_count']}")
                    logger.info(f"   - Actualizados: {resultado_sync['updated_count']}")
                    logger.info(f"   - Errores: {resultado_sync['error_count']}")

                    return {
                        'status': 'success',
                        'task_id': task_id,
                        'company': full_rut,
                        'period': f"{anio}-{mes if mes else 'TODO'}",
                        'found_in_sii': total_formularios,
                        'created': resultado_sync['created_count'],
                        'updated': resultado_sync['updated_count'],
                        'errors': resultado_sync['error_count'],
                        'sync_data': resultado_sync,  # Incluir datos completos del servicio de sincronización
                        'message': f'Sincronización completada exitosamente'
                    }

                else:
                    # Error en búsqueda SII
                    error_msg = resultado.get('message', 'Error desconocido en búsqueda SII')
                    logger.error(f"❌ [Task {task_id}] Error en búsqueda SII: {error_msg}")
                    raise Exception(f"Error en búsqueda SII: {error_msg}")

            else:
                raise ValueError(f"Tipo de formulario '{form_type}' no soportado")

    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en sincronización: {str(e)}")

        # Actualizar log con error
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()

        # Re-lanzar excepción para activar retry de Celery
        raise


@shared_task(bind=True, queue='sii', autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def sync_all_historical_forms_task(
    self,
    company_rut: str,
    company_dv: str,
    user_email: str = None,
    form_type: str = 'f29'
):
    """
    Tarea para sincronizar TODOS los formularios históricos desde el inicio de actividades.
    Similar a sync_sii_documents_full_history_task pero para formularios tributarios.

    Args:
        company_rut: RUT de la empresa sin dígito verificador
        company_dv: Dígito verificador de la empresa
        user_email: Email del usuario que solicita la sincronización
        form_type: Tipo de formulario ('f29', 'f3323', etc.)
    """
    task_id = self.request.id
    full_rut = f"{company_rut}-{company_dv}"

    logger.info(f"🚀 [Task {task_id}] Iniciando sincronización HISTÓRICA COMPLETA {form_type.upper()} para {full_rut}")
    logger.info(f"   Usuario: {user_email}")

    # Crear log de sincronización
    sync_log = SIISyncLog.objects.create(
        company_rut=company_rut,
        company_dv=company_dv.upper(),
        task_id=task_id,
        sync_type='tax_forms',
        status='running',
        user_email=user_email or 'system',
        description=f"Sincronización histórica completa formularios {form_type.upper()}",
        priority='high',
        sync_data={
            'form_type': form_type,
            'sync_type': 'full_history'
        }
    )

    try:
        # Obtener credenciales SII de la empresa específica
        from apps.companies.models import Company
        from apps.taxpayers.models import TaxpayerSiiCredentials

        # Buscar la empresa por RUT
        try:
            company = Company.objects.get(tax_id=full_rut)
            logger.info(f"📍 [Task {task_id}] Empresa encontrada: {company.business_name}")
        except Company.DoesNotExist:
            raise ValueError(f"Company not found for RUT {full_rut}")

        # Obtener credenciales SII de la empresa
        credentials = TaxpayerSiiCredentials.objects.filter(company=company).first()
        if not credentials:
            raise ValueError(f"No SII credentials found for company {full_rut}")

        # Usar credenciales de la empresa
        sii_tax_id = credentials.tax_id
        sii_password = credentials.get_password()

        if not sii_tax_id or not sii_password:
            raise ValueError(f"Invalid SII credentials for company {full_rut}")

        logger.info(f"🔑 [Task {task_id}] Usando credenciales SII de la empresa: {sii_tax_id}")

        # Primero, obtener información del contribuyente para determinar fecha de inicio
        logger.info(f"🔍 [Task {task_id}] Obteniendo información del contribuyente...")

        with RealSIIService(tax_id=sii_tax_id, password=sii_password, headless=True) as sii_service:
            # Obtener datos del contribuyente
            contribuyente_data = sii_service.consultar_contribuyente()

            # Extraer fecha de inicio de actividades
            fecha_inicio_str = None
            if isinstance(contribuyente_data, dict):
                fecha_inicio_str = contribuyente_data.get('fecha_inicio_actividades')

            # Determinar año de inicio
            if fecha_inicio_str:
                try:
                    # Parsear fecha en formato YYYY-MM-DD o DD-MM-YYYY
                    if '-' in fecha_inicio_str:
                        parts = fecha_inicio_str.split('-')
                        if len(parts[0]) == 4:  # YYYY-MM-DD
                            anio_inicio = int(parts[0])
                        else:  # DD-MM-YYYY
                            anio_inicio = int(parts[2])
                    else:
                        # Asumir año actual menos 5 años si no hay formato reconocible
                        anio_inicio = datetime.now().year - 5
                except:
                    anio_inicio = datetime.now().year - 5
            else:
                # Por defecto, últimos 5 años si no se encuentra fecha
                anio_inicio = datetime.now().year - 5

            anio_actual = datetime.now().year

            logger.info(f"📅 [Task {task_id}] Período detectado: {anio_inicio} a {anio_actual}")
            logger.info(f"   Fecha inicio actividades: {fecha_inicio_str or 'No disponible'}")

        # Actualizar log con período detectado
        sync_log.sync_data.update({
            'anio_inicio': anio_inicio,
            'anio_fin': anio_actual,
            'fecha_inicio_actividades': fecha_inicio_str
        })
        sync_log.save()

        # Contadores globales
        total_procesados = 0
        total_creados = 0
        total_actualizados = 0
        total_errores = 0
        total_extraction_tasks = 0
        resultados_por_anio = {}

        # Procesar año por año
        for anio in range(anio_inicio, anio_actual + 1):
            logger.info(f"📅 [Task {task_id}] Procesando año {anio}...")

            try:
                # Ejecutar sincronización para este año (síncronamente para mejor control)
                resultado = sync_tax_forms_task(
                    company_rut=company_rut,
                    company_dv=company_dv,
                    anio=str(anio),
                    user_email=user_email,
                    form_type=form_type
                )

                # Actualizar contadores
                total_procesados += resultado.get('found_in_sii', 0)
                total_creados += resultado.get('created', 0)
                total_actualizados += resultado.get('updated', 0)
                total_errores += resultado.get('errors', 0)

                # Obtener IDs de formularios sincronizados y enviar tareas de extracción de detalles
                extraction_tasks_sent = 0
                if hasattr(resultado, 'get'):
                    # El resultado proviene del servicio de sincronización que ahora incluye form_ids
                    sync_data = resultado.get('sync_data', {})
                    created_form_ids = sync_data.get('created_form_ids', [])
                    updated_form_ids = sync_data.get('updated_form_ids', [])

                    # Combinar IDs de formularios creados y actualizados
                    all_form_ids = created_form_ids + updated_form_ids

                    # Enviar tarea de extracción de detalles para cada formulario
                    # for form_id in all_form_ids:
                    #     try:
                    #         extract_form_details_task.delay(
                    #             form_id=form_id,
                    #             force_refresh=False
                    #         )
                    #         extraction_tasks_sent += 1
                    #     except Exception as e:
                    #         logger.error(f"❌ [Task {task_id}] Error enviando tarea de extracción para form_id {form_id}: {str(e)}")

                    total_extraction_tasks += extraction_tasks_sent
                    logger.info(f"🔍 [Task {task_id}] {extraction_tasks_sent} tareas de extracción de detalles enviadas para año {anio}")

                resultados_por_anio[str(anio)] = {
                    'found': resultado.get('found_in_sii', 0),
                    'created': resultado.get('created', 0),
                    'updated': resultado.get('updated', 0),
                    'errors': resultado.get('errors', 0),
                    'extraction_tasks_sent': extraction_tasks_sent,
                    'status': 'completed'
                }

                logger.info(f"✅ [Task {task_id}] Año {anio} completado - {resultado.get('found_in_sii', 0)} formularios, {extraction_tasks_sent} extracciones enviadas")

            except Exception as e:
                logger.error(f"❌ [Task {task_id}] Error procesando año {anio}: {str(e)}")
                total_errores += 1
                resultados_por_anio[str(anio)] = {
                    'status': 'failed',
                    'error': str(e)
                }

        # Actualizar log con resultados finales
        sync_log.status = 'completed'
        sync_log.completed_at = timezone.now()
        sync_log.records_processed = total_procesados
        sync_log.records_created = total_creados
        sync_log.records_updated = total_actualizados
        sync_log.records_failed = total_errores
        sync_log.sync_data.update({
            'resultados_por_anio': resultados_por_anio,
            'total_anios_procesados': len(resultados_por_anio),
            'total_extraction_tasks_sent': total_extraction_tasks
        })
        sync_log.save()

        logger.info(f"🎉 [Task {task_id}] Sincronización histórica COMPLETA finalizada:")
        logger.info(f"   - Período: {anio_inicio} a {anio_actual} ({anio_actual - anio_inicio + 1} años)")
        logger.info(f"   - Total procesados: {total_procesados}")
        logger.info(f"   - Total creados: {total_creados}")
        logger.info(f"   - Total actualizados: {total_actualizados}")
        logger.info(f"   - Total errores: {total_errores}")
        logger.info(f"   - Tareas de extracción enviadas: {total_extraction_tasks}")

        return {
            'status': 'success',
            'task_id': task_id,
            'company': full_rut,
            'period': f"{anio_inicio}-{anio_actual}",
            'years_processed': anio_actual - anio_inicio + 1,
            'total_processed': total_procesados,
            'total_created': total_creados,
            'total_updated': total_actualizados,
            'total_errors': total_errores,
            'extraction_tasks_sent': total_extraction_tasks,
            'results_by_year': resultados_por_anio,
            'message': f'Sincronización histórica completa exitosa ({anio_inicio}-{anio_actual}) - {total_extraction_tasks} tareas de extracción enviadas'
        }

    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en sincronización histórica completa: {str(e)}")

        # Actualizar log con error
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()

        # Re-lanzar excepción para activar retry de Celery
        raise


@shared_task(bind=True, queue="sii", autoretry_for=(Exception,), retry_kwargs={"max_retries": 2, "countdown": 180})
def extract_form_details_task(
    self,
    form_id: int,
    force_refresh: bool = False
):
    """
    Tarea para extraer detalles completos de un formulario F29 específico.

    Args:
        form_id: ID del TaxForm
        force_refresh: Si True, fuerza nueva extracción aunque ya existan detalles
    """
    task_id = self.request.id

    logger.info(f"🔍 [Task {task_id}] Iniciando extracción de detalles para form_id: {form_id}")

    try:
        from apps.forms.models import TaxForm
        from apps.forms.services.detail_extraction_service import F29DetailExtractionService

        # Obtener formulario
        try:
            tax_form = TaxForm.objects.select_related("company").get(id=form_id)
        except TaxForm.DoesNotExist:
            raise ValueError(f"TaxForm con ID {form_id} no encontrado")

        logger.info(f"  📋 Formulario: {tax_form.sii_folio} - {tax_form.tax_period}")

        # Crear servicio de extracción
        extraction_service = F29DetailExtractionService()

        # Extraer detalles
        resultado = extraction_service.extract_form_details(tax_form, force_refresh)

        logger.info(f"✅ [Task {task_id}] Extracción completada: {resultado['status']}")

        return {
            "status": "success",
            "task_id": task_id,
            "form_id": form_id,
            "folio": tax_form.sii_folio,
            "extraction_result": resultado,
            "message": f"Extracción de detalles completada: {resultado['status']}"
        }

    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en extracción de detalles: {str(e)}")
        raise


@shared_task(bind=True, queue="sii", autoretry_for=(Exception,), retry_kwargs={"max_retries": 1, "countdown": 300})
def extract_multiple_forms_details_task(
    self,
    company_id: int = None,
    force_refresh: bool = False,
    max_forms: int = 10
):
    """
    Tarea para extraer detalles de múltiples formularios F29.

    Args:
        company_id: ID de Company específica (opcional)
        force_refresh: Si True, fuerza nueva extracción aunque ya existan detalles
        max_forms: Máximo número de formularios a procesar
    """
    task_id = self.request.id

    logger.info(f"🔄 [Task {task_id}] Iniciando extracción múltiple de detalles")
    logger.info(f"   Company ID: {company_id}, Force refresh: {force_refresh}, Max forms: {max_forms}")

    try:
        from apps.forms.services.detail_extraction_service import F29DetailExtractionService
        from apps.companies.models import Company

        # Obtener company si se especifica
        company = None
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                logger.info(f"  🏢 Company: {company.business_name} ({company.tax_id})")
            except Company.DoesNotExist:
                raise ValueError(f"Company con ID {company_id} no encontrada")

        # Crear servicio de extracción
        extraction_service = F29DetailExtractionService()

        # Obtener formularios que necesitan extracción
        forms_to_process = extraction_service.get_forms_needing_details(company, max_forms)

        if not forms_to_process:
            logger.info(f"  ℹ️ No hay formularios que necesiten extracción de detalles")
            return {
                "status": "success",
                "task_id": task_id,
                "message": "No hay formularios que necesiten extracción de detalles"
            }

        logger.info(f"  📋 {len(forms_to_process)} formularios para procesar")

        # Procesar formularios
        resultado = extraction_service.extract_multiple_forms_details(
            forms_to_process,
            force_refresh,
            max_forms
        )

        logger.info(f"✅ [Task {task_id}] Extracción múltiple completada:")
        logger.info(f"   - Procesados: {resultado['total_processed']}")
        logger.info(f"   - Exitosos: {resultado['success_count']}")
        logger.info(f"   - Errores: {resultado['error_count']}")

        return {
            "status": "success",
            "task_id": task_id,
            "company_id": company_id,
            "extraction_results": resultado,
            "message": f"Extracción múltiple completada: {resultado['success_count']} exitosos de {resultado['total_processed']} procesados"
        }

    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en extracción múltiple: {str(e)}")
        raise

