"""
Tareas de Celery para sincronización de documentos SII
Refactorizado para usar servicios de negocio
"""
import logging

from celery import shared_task
from django.utils import timezone

from ..services import DocumentSyncService
from ..models import SIISyncLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='sii', autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def sync_sii_documents_task(
    self,
    company_rut: str,
    company_dv: str, 
    fecha_desde: str,
    fecha_hasta: str,
    user_email: str = None,
    priority: str = 'normal',
    description: str = None
):
    """
    Tarea de Celery para sincronizar documentos SII.
    Delega la lógica de negocio al servicio DocumentSyncService.
    
    Args:
        company_rut: RUT de la empresa sin dígito verificador
        company_dv: Dígito verificador de la empresa
        fecha_desde: Fecha inicio en formato YYYY-MM-DD
        fecha_hasta: Fecha fin en formato YYYY-MM-DD
        user_email: Email del usuario que solicita la sincronización
        priority: Prioridad de la tarea (high, normal, low)
        description: Descripción personalizada de la sincronización
    """
    task_id = self.request.id
    full_rut = f"{company_rut}-{company_dv}"
    
    logger.info(f"🚀 [Task {task_id}] Iniciando sincronización SII para {full_rut}")
    logger.info(f"   Período: {fecha_desde} a {fecha_hasta}")
    logger.info(f"   Usuario: {user_email}")
    logger.info(f"   Prioridad: {priority}")
    
    # Crear log de sincronización
    sync_log = SIISyncLog.objects.create(
        task_id=task_id,
        company_rut=full_rut,
        sync_type='documents',
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        user_email=user_email or 'system',
        priority=priority,
        description=description or f'Sincronización documentos {fecha_desde} - {fecha_hasta}',
        status='running',
        started_at=timezone.now()
    )
    
    try:
        # Delegar al servicio de sincronización
        service = DocumentSyncService(company_rut, company_dv)
        results = service.sync_period(
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            sync_log=sync_log,
            task_id=task_id
        )
        
        # Actualizar log de sincronización con resultados exitosos
        sync_log.status = 'completed'
        sync_log.completed_at = timezone.now()
        sync_log.documents_processed = results['processed']
        sync_log.documents_created = results['created']
        sync_log.documents_updated = results['updated']
        sync_log.errors_count = results['errors']
        sync_log.results_data = results
        sync_log.save()
        
        logger.info(f"🎉 [Task {task_id}] Sincronización completada exitosamente")
        logger.info(f"   Procesados: {results['processed']}")
        logger.info(f"   Creados: {results['created']}")
        logger.info(f"   Actualizados: {results['updated']}")
        logger.info(f"   Errores: {results['errors']}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'sync_log_id': sync_log.id,
            'company_rut': full_rut,
            'period': f"{fecha_desde} - {fecha_hasta}",
            'results': results
        }
        
    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en sincronización SII: {str(e)}")
        
        # Actualizar log de sincronización con error
        sync_log.status = 'failed'
        sync_log.completed_at = timezone.now()
        sync_log.error_message = str(e)
        sync_log.save()
        
        # Re-lanzar excepción para que Celery maneje reintentos
        raise


@shared_task(bind=True, queue='sii', autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 300})
def sync_sii_documents_full_history_task(self, company_rut: str, company_dv: str, user_email: str = None):
    """
    Tarea de Celery para sincronizar todos los documentos electrónicos desde el inicio de actividades.
    Esta tarea orquesta múltiples llamadas a sync_sii_documents_task para cada período mensual.
    
    Args:
        company_rut: RUT de la empresa sin dígito verificador
        company_dv: Dígito verificador de la empresa
        user_email: Email del usuario que solicita la sincronización
    """
    from datetime import datetime, date
    from dateutil.relativedelta import relativedelta
    from apps.companies.models import Company
    
    task_id = self.request.id
    full_rut = f"{company_rut}-{company_dv}"
    
    logger.info(f"🚀 [Task {task_id}] Iniciando sincronización COMPLETA SII para {full_rut}")
    logger.info(f"   Usuario: {user_email}")
    
    sync_log = None
    
    try:
        # Obtener fecha de inicio de actividades de la empresa PRIMERO
        logger.info(f"📅 [Task {task_id}] Obteniendo fecha de inicio de actividades...")
        
        try:
            company = Company.objects.get(tax_id=full_rut)
            if hasattr(company, 'taxpayer') and company.taxpayer and company.taxpayer.fecha_inicio_actividades:
                fecha_inicio = company.taxpayer.fecha_inicio_actividades
                logger.info(f"✅ Fecha de inicio de actividades encontrada: {fecha_inicio}")
            else:
                # Si no tenemos la fecha, usar el servicio SII para obtenerla
                logger.info("🔍 Obteniendo fecha de inicio desde SII...")
                service = DocumentSyncService(company_rut, company_dv)
                taxpayer_info = service.sii_service.get_taxpayer_info()
                fecha_inicio_str = taxpayer_info.get('fecha_inicio_actividades')
                if fecha_inicio_str:
                    # Convertir string a date si es necesario
                    if isinstance(fecha_inicio_str, str):
                        fecha_inicio = datetime.strptime(fecha_inicio_str.split()[0], '%d/%m/%Y').date()
                    else:
                        fecha_inicio = fecha_inicio_str
                    logger.info(f"✅ Fecha de inicio obtenida del SII: {fecha_inicio}")
                else:
                    # Fallback: usar hace 5 años
                    fecha_inicio = date.today() - relativedelta(years=5)
                    logger.warning(f"⚠️ No se pudo obtener fecha de inicio, usando fallback: {fecha_inicio}")
                    
        except Company.DoesNotExist:
            # Empresa no existe en BD, usar el servicio para obtener info
            logger.info("🔍 Empresa no encontrada en BD, obteniendo info del SII...")
            service = DocumentSyncService(company_rut, company_dv)
            taxpayer_info = service.sii_service.get_taxpayer_info()
            fecha_inicio_str = taxpayer_info.get('fecha_inicio_actividades')
            if fecha_inicio_str:
                if isinstance(fecha_inicio_str, str):
                    fecha_inicio = datetime.strptime(fecha_inicio_str.split()[0], '%d/%m/%Y').date()
                else:
                    fecha_inicio = fecha_inicio_str
                logger.info(f"✅ Fecha de inicio obtenida del SII: {fecha_inicio}")
            else:
                fecha_inicio = date.today() - relativedelta(years=5)
                logger.warning(f"⚠️ No se pudo obtener fecha de inicio, usando fallback: {fecha_inicio}")
        
        # Calcular períodos mensuales desde fecha de inicio hasta hoy
        fecha_fin = date.today()
        
        # AHORA crear el log de sincronización principal con las fechas correctas
        sync_log = SIISyncLog.objects.create(
            task_id=task_id,
            company_rut=full_rut,
            sync_type='full_history',
            fecha_desde=fecha_inicio.strftime('%Y-%m-%d'),
            fecha_hasta=fecha_fin.strftime('%Y-%m-%d'),
            user_email=user_email or 'system',
            priority='high',
            description=f'Sincronización completa desde {fecha_inicio} hasta {fecha_fin}',
            status='running',
            started_at=timezone.now()
        )
        
        periodos = []
        
        current_date = fecha_inicio.replace(day=1)  # Primer día del mes
        while current_date <= fecha_fin:
            # Último día del mes
            next_month = current_date + relativedelta(months=1)
            ultimo_dia_mes = next_month - relativedelta(days=1)
            
            # No procesar fechas futuras
            if ultimo_dia_mes > fecha_fin:
                ultimo_dia_mes = fecha_fin
            
            periodos.append({
                'desde': current_date.strftime('%Y-%m-%d'),
                'hasta': ultimo_dia_mes.strftime('%Y-%m-%d'),
                'descripcion': f"{current_date.strftime('%B %Y')}"
            })
            
            current_date = next_month
            
            # No procesar más allá de la fecha actual
            if current_date > fecha_fin:
                break
        
        # Actualizar descripción del log con el número de períodos
        sync_log.description = f'Sincronización completa: {len(periodos)} períodos desde {fecha_inicio} hasta {fecha_fin}'
        sync_log.save()
        
        logger.info(f"📋 [Task {task_id}] Períodos a sincronizar: {len(periodos)}")
        logger.info(f"   Desde: {fecha_inicio} | Hasta: {fecha_fin}")
        
        # Ejecutar sincronizaciones de períodos usando sync_sii_documents_task
        resultados_periodos = []
        total_processed = 0
        total_created = 0
        total_updated = 0
        total_errors = 0
        
        for i, periodo in enumerate(periodos, 1):
            try:
                logger.info(f"🔄 [Task {task_id}] Sincronizando período {i}/{len(periodos)}: {periodo['descripcion']}")
                
                # Crear una subtarea para este período
                subtask_description = f"Período {i}/{len(periodos)}: {periodo['descripcion']}"
                
                # Usar el servicio directamente en lugar de llamar a la tarea
                try:
                    service = DocumentSyncService(company_rut, company_dv)
                    periodo_sync_log = SIISyncLog.objects.create(
                        task_id=f"{task_id}-period-{i}",
                        company_rut=full_rut,
                        sync_type='documents',
                        fecha_desde=periodo['desde'],
                        fecha_hasta=periodo['hasta'],
                        user_email=user_email or 'system',
                        priority='high',
                        description=subtask_description,
                        status='running',
                        started_at=timezone.now()
                    )
                    
                    results = service.sync_period(
                        fecha_desde=periodo['desde'],
                        fecha_hasta=periodo['hasta'],
                        sync_log=periodo_sync_log,
                        task_id=f"{task_id}-period-{i}"
                    )
                    
                    # Actualizar log del período
                    periodo_sync_log.status = 'completed'
                    periodo_sync_log.completed_at = timezone.now()
                    periodo_sync_log.documents_processed = results['processed']
                    periodo_sync_log.documents_created = results['created']
                    periodo_sync_log.documents_updated = results['updated']
                    periodo_sync_log.errors_count = results['errors']
                    periodo_sync_log.results_data = results
                    periodo_sync_log.save()
                    
                    resultado = {
                        'status': 'success',
                        'results': results
                    }
                except Exception as e:
                    logger.error(f"❌ [Task {task_id}] Error en período {i}: {str(e)}")
                    resultado = {
                        'status': 'error',
                        'error': str(e)
                    }
                
                if resultado['status'] == 'success':
                    logger.info(f"✅ [Task {task_id}] Período {i} completado: {resultado['results']['processed']} docs")
                    resultados_periodos.append({
                        'periodo': periodo['descripcion'],
                        'status': 'success',
                        'results': resultado['results']
                    })
                    
                    # Acumular totales
                    total_processed += resultado['results']['processed']
                    total_created += resultado['results']['created']
                    total_updated += resultado['results']['updated']
                    total_errors += resultado['results']['errors']
                else:
                    logger.warning(f"⚠️ [Task {task_id}] Período {i} falló")
                    resultados_periodos.append({
                        'periodo': periodo['descripcion'],
                        'status': 'failed',
                        'error': str(resultado.get('error', 'Error desconocido'))
                    })
                    total_errors += 1
                    
            except Exception as e:
                logger.error(f"❌ [Task {task_id}] Error en período {i} ({periodo['descripcion']}): {str(e)}")
                resultados_periodos.append({
                    'periodo': periodo['descripcion'],
                    'status': 'failed',
                    'error': str(e)
                })
                total_errors += 1
            
            # Actualizar progreso
            progreso = int((i / len(periodos)) * 100)
            sync_log.progress_percentage = progreso
            sync_log.save()
        
        # Actualizar log final
        sync_log.status = 'completed'
        sync_log.completed_at = timezone.now()
        sync_log.progress_percentage = 100
        sync_log.documents_processed = total_processed
        sync_log.documents_created = total_created
        sync_log.documents_updated = total_updated
        sync_log.errors_count = total_errors
        sync_log.results_data = {
            'periods_processed': len(periodos),
            'period_results': resultados_periodos,
            'summary': {
                'processed': total_processed,
                'created': total_created,
                'updated': total_updated,
                'errors': total_errors
            }
        }
        sync_log.save()
        
        logger.info(f"🎉 [Task {task_id}] Sincronización COMPLETA exitosa")
        logger.info(f"   Períodos procesados: {len(periodos)}")
        logger.info(f"   Documentos procesados: {total_processed}")
        logger.info(f"   Documentos creados: {total_created}")
        logger.info(f"   Documentos actualizados: {total_updated}")
        logger.info(f"   Errores: {total_errors}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'sync_log_id': sync_log.id,
            'company_rut': full_rut,
            'periods_processed': len(periodos),
            'fecha_desde': fecha_inicio.strftime('%Y-%m-%d'),
            'fecha_hasta': fecha_fin.strftime('%Y-%m-%d'),
            'results': {
                'processed': total_processed,
                'created': total_created,
                'updated': total_updated,
                'errors': total_errors
            },
            'period_details': resultados_periodos
        }
        
    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error en sincronización completa SII: {str(e)}")
        
        # Actualizar log de sincronización con error (si existe)
        if sync_log:
            sync_log.status = 'failed'
            sync_log.completed_at = timezone.now()
            sync_log.error_message = str(e)
            sync_log.save()
        
        # Re-lanzar excepción para que Celery la maneje
        raise