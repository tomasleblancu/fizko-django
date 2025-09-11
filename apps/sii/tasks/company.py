"""
Tareas de Celery para sincronización de datos de empresa SII
"""
import logging

from celery import shared_task

from apps.companies.models import Company
from apps.taxpayers.models import TaxpayerSiiCredentials
from ..rpa.api_integration import SIIIntegratedService

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='sii')
def sync_company_data_task(self, company_rut: str, user_email: str = None):
    """
    Tarea para sincronizar datos generales de la empresa desde SII
    """
    
    task_id = self.request.id
    logger.info(f"🏢 [Task {task_id}] Iniciando sincronización datos empresa {company_rut}")
    
    try:
        # Obtener empresa y credenciales
        company = Company.objects.get(tax_id=company_rut)
        credentials = TaxpayerSiiCredentials.objects.get(company=company)
        
        # Crear servicio SII integrado
        with SIIIntegratedService(
            tax_id=company_rut,
            password=credentials.get_password(),
            headless=True
        ) as sii_service:
            
            # Probar conexión y obtener datos del contribuyente
            connection_result = sii_service.test_connection()
            
            if connection_result.get('status') != 'success':
                raise Exception(f"Error en conexión con SII: {connection_result.get('message')}")
            
            contribuyente_data = connection_result.get('data', {})
        
        # Actualizar datos de la empresa
        if company.taxpayer:
            company.taxpayer.sync_from_sii_data(contribuyente_data)
            company.taxpayer.save()
            company.sync_taxpayer_data()
            company.save()
        
        logger.info(f"✅ [Task {task_id}] Datos empresa sincronizados exitosamente")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'company_rut': company_rut,
            'updated_fields': list(contribuyente_data.keys()) if contribuyente_data else []
        }
        
    except Exception as e:
        logger.error(f"❌ [Task {task_id}] Error sincronizando empresa: {str(e)}")
        raise