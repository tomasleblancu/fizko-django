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
    description: str = None,
    trigger_full_sync: bool = False
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
        trigger_full_sync: Si True, dispara sincronización completa del historial al finalizar exitosamente
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
        
        # Si se solicita, disparar sincronización completa del historial después del sync exitoso
        full_sync_task_id = None
        if trigger_full_sync:
            logger.info(f"🚀 [Task {task_id}] Disparando sincronización COMPLETA del historial...")
            try:
                # Disparar la tarea de sincronización completa - referencia directa a la función
                full_sync_task = sync_sii_documents_full_history_task.delay(
                    company_rut=company_rut,
                    company_dv=company_dv,
                    user_email=user_email
                )
                full_sync_task_id = full_sync_task.id
                logger.info(f"✅ [Task {task_id}] Sincronización completa disparada: {full_sync_task_id}")
            except Exception as e:
                logger.error(f"❌ [Task {task_id}] Error disparando sincronización completa: {str(e)}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'sync_log_id': sync_log.id,
            'company_rut': full_rut,
            'period': f"{fecha_desde} - {fecha_hasta}",
            'results': results,
            'full_sync_triggered': trigger_full_sync,
            'full_sync_task_id': full_sync_task_id
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
    
    task_id = self.request.id
    full_rut = f"{company_rut}-{company_dv}"
    
    logger.info(f"🚀 [Task {task_id}] Iniciando sincronización COMPLETA SII para {full_rut}")
    logger.info(f"   Usuario: {user_email}")
    
    sync_log = None
    
    try:
        # Crear log de sincronización
        sync_log = SIISyncLog.objects.create(
            task_id=task_id,
            company_rut=full_rut,
            sync_type='full_history',
            user_email=user_email or 'system',
            priority='high',
            description=f'Sincronización completa historial - {full_rut}',
            status='running',
            started_at=timezone.now()
        )
        
        # Crear el servicio de sincronización y delegar toda la lógica
        logger.info(f"🔧 [Task {task_id}] Iniciando servicio de sincronización...")
        service = DocumentSyncService(company_rut, company_dv)
        
        # El servicio se encarga de todo: obtener fecha de inicio, procesar períodos, etc.
        results = service.sync_full_history(sync_log=sync_log, task_id=task_id)
        
        # Actualizar log de sincronización con resultados exitosos
        sync_log.status = 'completed'
        sync_log.completed_at = timezone.now()
        sync_log.documents_processed = results['processed']
        sync_log.documents_created = results['created']
        sync_log.documents_updated = results['updated']
        sync_log.errors_count = results['errors']
        sync_log.results_data = results
        sync_log.save()
        
        logger.info(f"🎉 [Task {task_id}] Sincronización COMPLETA finalizada exitosamente")
        logger.info(f"   Procesados: {results['processed']}")
        logger.info(f"   Creados: {results['created']}")
        logger.info(f"   Actualizados: {results['updated']}")
        logger.info(f"   Errores: {results['errors']}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'sync_log_id': sync_log.id,
            'company_rut': full_rut,
            'sync_type': 'full_history',
            'results': results
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
