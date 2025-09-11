"""
Módulo para operaciones de sincronización con el SII
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime
import logging

from apps.companies.models import Company
from ..api.servicev2 import SIIServiceV2
from ..utils.exceptions import (
    SIIConnectionError, 
    SIIAuthenticationError,
    SIIValidationError
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_company_dtes(request):
    """
    Sincroniza DTEs de una empresa usando la nueva estructura robusta
    POST /api/v1/sii/sync-dtes/
    """
    try:
        # Validar datos de entrada
        company_id = request.data.get('company_id')
        fecha_desde = request.data.get('fecha_desde')
        fecha_hasta = request.data.get('fecha_hasta')
        tipos_operacion = request.data.get('tipos_operacion', ['recibidos', 'emitidos'])
        
        if not all([company_id, fecha_desde, fecha_hasta]):
            return Response({
                'error': 'Faltan campos requeridos: company_id, fecha_desde, fecha_hasta'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener empresa
        try:
            company = Company.objects.get(id=company_id, is_active=True)
        except Company.DoesNotExist:
            return Response({
                'error': 'Empresa no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener credenciales de la empresa
        try:
            from apps.taxpayers.models import TaxpayerSiiCredentials
            credentials = TaxpayerSiiCredentials.objects.get(company=company)
            password = credentials.get_password()
        except TaxpayerSiiCredentials.DoesNotExist:
            return Response({
                'error': 'Empresa no tiene credenciales SII configuradas'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Crear servicio SII y ejecutar sincronización
        sii_service = SIIServiceV2.crear_con_password(
            tax_id=company.tax_id,
            password=password
        )
        
        # Obtener documentos por período
        periodo = datetime.strptime(fecha_desde, '%Y-%m-%d').strftime('%Y%m')
        
        result = {'status': 'success', 'data': []}
        
        if 'recibidos' in tipos_operacion:
            docs_compra = sii_service.get_documentos_compra(periodo)
            result['data'].extend(docs_compra.get('data', []))
            
        if 'emitidos' in tipos_operacion:
            docs_venta = sii_service.get_documentos_venta(periodo)
            result['data'].extend(docs_venta.get('data', []))
            
            return Response(result, status=status.HTTP_200_OK)
            
    except SIIAuthenticationError as e:
        return Response({
            'error': 'Error de autenticación SII',
            'detail': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except SIIValidationError as e:
        return Response({
            'error': 'Error de validación',
            'detail': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except SIIConnectionError as e:
        return Response({
            'error': 'Error de conexión SII',
            'detail': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        logger.error(f"Error inesperado en sync_company_dtes: {e}")
        return Response({
            'error': 'Error interno del servidor',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def test_sii_connection(request):
    """
    Prueba la conexión SII para una empresa
    POST /api/v1/sii/test-connection/
    """
    try:
        company_id = request.data.get('company_id')
        
        if not company_id:
            return Response({
                'error': 'company_id requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener empresa
        try:
            company = Company.objects.get(id=company_id, is_active=True)
        except Company.DoesNotExist:
            return Response({
                'error': 'Empresa no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener credenciales de la empresa
        try:
            from apps.taxpayers.models import TaxpayerSiiCredentials
            credentials = TaxpayerSiiCredentials.objects.get(company=company)
            password = credentials.get_password()
        except TaxpayerSiiCredentials.DoesNotExist:
            return Response({
                'error': 'Empresa no tiene credenciales SII configuradas'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Probar conexión
        try:
            sii_service = SIIServiceV2.crear_con_password(
                tax_id=company.tax_id,
                password=password
            )
            
            # Hacer una consulta simple para probar
            contribuyente_info = sii_service.consultar_contribuyente()
            
            if contribuyente_info.get('status') == 'success':
                result = {
                    'status': 'success',
                    'message': 'Conexión SII exitosa',
                    'company': company.name,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                result = {
                    'status': 'error',
                    'message': 'Error en conexión SII',
                    'company': company.name,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            result = {
                'status': 'error',
                'message': f'Error de conexión: {str(e)}',
                'company': company.name,
                'timestamp': datetime.now().isoformat()
            }
            
            response_status = status.HTTP_200_OK if result['status'] == 'success' else status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(result, status=response_status)
            
    except Exception as e:
        logger.error(f"Error en test_sii_connection: {e}")
        return Response({
            'error': 'Error interno del servidor',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_sync_history(request, company_id):
    """
    Obtiene el historial de sincronizaciones de una empresa
    GET /api/v1/sii/sync-history/<company_id>/
    """
    try:
        # Obtener empresa
        try:
            company = Company.objects.get(id=company_id, is_active=True)
        except Company.DoesNotExist:
            return Response({
                'error': 'Empresa no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        limit = int(request.query_params.get('limit', 10))
        
        # Obtener historial desde el modelo SIISyncLog directamente
        from ..models import SIISyncLog
        
        rut_parts = company.tax_id.split('-')
        sync_logs = SIISyncLog.objects.filter(
            company_rut=rut_parts[0],
            company_dv=rut_parts[1] if len(rut_parts) > 1 else '0'
        ).order_by('-started_at')[:limit]
        
        history = []
        for log in sync_logs:
            history.append({
                'id': log.id,
                'sync_type': log.sync_type,
                'status': log.status,
                'started_at': log.started_at.isoformat(),
                'completed_at': log.completed_at.isoformat() if log.completed_at else None,
                'period': f"{log.fecha_desde} - {log.fecha_hasta}" if log.fecha_desde and log.fecha_hasta else None,
                'documents_processed': log.documents_processed,
                'documents_created': log.documents_created,
                'documents_updated': log.documents_updated,
                'errors_count': log.errors_count,
                'success_rate': log.success_rate,
                'description': log.description
            })
            
            return Response({
                'company': company.name,
                'history': history
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Error en get_sync_history: {e}")
        return Response({
            'error': 'Error interno del servidor',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_taxpayer_info(request):
    """
    Sincroniza información del contribuyente desde SII
    POST /api/v1/sii/sync-taxpayer/
    """
    try:
        company_id = request.data.get('company_id')
        
        if not company_id:
            return Response({
                'error': 'company_id requerido'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener empresa
        try:
            company = Company.objects.get(id=company_id, is_active=True)
        except Company.DoesNotExist:
            return Response({
                'error': 'Empresa no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Obtener credenciales de la empresa
        try:
            from apps.taxpayers.models import TaxpayerSiiCredentials
            credentials = TaxpayerSiiCredentials.objects.get(company=company)
            password = credentials.get_password()
        except TaxpayerSiiCredentials.DoesNotExist:
            return Response({
                'error': 'Empresa no tiene credenciales SII configuradas'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Sincronizar información del contribuyente
        sii_service = SIIServiceV2.crear_con_password(
            tax_id=company.tax_id,
            password=password
        )
        
        contribuyente_info = sii_service.consultar_contribuyente()
        
        result = {
            'status': 'success' if contribuyente_info.get('status') == 'success' else 'error',
            'company': company.name,
            'taxpayer_data': contribuyente_info,
            'timestamp': datetime.now().isoformat()
        }
        
        return Response(result, status=status.HTTP_200_OK)
            
    except SIIAuthenticationError as e:
        return Response({
            'error': 'Error de autenticación SII',
            'detail': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)
        
    except Exception as e:
        logger.error(f"Error en sync_taxpayer_info: {e}")
        return Response({
            'error': 'Error interno del servidor',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)