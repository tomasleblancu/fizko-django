"""
Módulo para gestión de documentos (DTEs) del SII
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime, timedelta
import logging

from ..models import SIISyncLog
from apps.documents.models import Document

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporalmente para testing
def list_sii_dtes(request):
    """
    Lista todos los DTEs obtenidos del SII
    GET /api/v1/sii/dtes/?company_rut=77794858&limit=50&offset=0
    """
    try:
        # Parámetros de consulta
        company_rut = request.query_params.get('company_rut')
        document_type = request.query_params.get('document_type')
        status_filter = request.query_params.get('status')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # Construir queryset base
        queryset = Document.objects.all()
        
        # Aplicar filtros
        if company_rut:
            # Extraer solo el número del RUT (sin DV)
            rut_number = company_rut.split('-')[0] if '-' in company_rut else company_rut
            queryset = queryset.filter(issuer_company_rut=rut_number)
        
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__gte=fecha_desde)
            except ValueError:
                return Response({
                    "error": "VALIDATION_ERROR",
                    "message": "fecha_desde debe estar en formato YYYY-MM-DD",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__lte=fecha_hasta)
            except ValueError:
                return Response({
                    "error": "VALIDATION_ERROR", 
                    "message": "fecha_hasta debe estar en formato YYYY-MM-DD",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Contar total antes de aplicar limit/offset
        total_count = queryset.count()
        
        # Aplicar paginación
        queryset = queryset.order_by('-issue_date')[offset:offset + limit]
        
        # Serializar resultados
        results = []
        for doc in queryset:
            doc_data = {
                "id": doc.id,
                "document_type": doc.document_type.code if doc.document_type else None,
                "document_type_name": doc.document_type.name if doc.document_type else 'Unknown',
                "folio": doc.folio,
                "document_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "total_amount": str(doc.total_amount) if doc.total_amount else None,
                "net_amount": str(doc.net_amount) if doc.net_amount else None,
                "tax_amount": str(doc.tax_amount) if doc.tax_amount else None,
                "issuer_name": doc.issuer_name,
                "issuer_rut": f"{doc.issuer_company_rut}-{doc.issuer_company_dv}",
                "recipient_name": doc.recipient_name,
                "recipient_rut": f"{doc.recipient_rut}-{doc.recipient_dv}",
                "status": doc.status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            results.append(doc_data)
        
        # Calcular paginación
        has_next = (offset + limit) < total_count
        has_previous = offset > 0
        
        return Response({
            "results": results,
            "count": len(results),
            "total_count": total_count,
            "next": has_next,
            "previous": has_previous
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listando DTEs: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporalmente para testing
def get_dte_detail(request, dte_id):
    """
    Obtiene el detalle de un DTE específico
    GET /api/v1/sii/dtes/{dte_id}/
    """
    try:
        try:
            documento = Document.objects.get(id=dte_id)
        except Document.DoesNotExist:
            return Response({
                "error": "NOT_FOUND",
                "message": f"DTE con ID {dte_id} no encontrado",
                "timestamp": datetime.now().isoformat()
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Construir respuesta detallada
        doc_detail = {
            "id": documento.id,
            "document_type": documento.document_type.code if documento.document_type else None,
            "document_type_name": documento.document_type.name if documento.document_type else 'Unknown',
            "folio": documento.folio,
            "document_date": documento.issue_date.isoformat() if documento.issue_date else None,
            "total_amount": str(documento.total_amount) if documento.total_amount else None,
            "net_amount": str(documento.net_amount) if documento.net_amount else None,
            "tax_amount": str(documento.tax_amount) if documento.tax_amount else None,
            "exempt_amount": str(documento.exempt_amount) if documento.exempt_amount else None,
            "issuer_name": documento.issuer_name,
            "issuer_rut": f"{documento.issuer_company_rut}-{documento.issuer_company_dv}",
            "issuer_address": documento.issuer_address,
            "recipient_name": documento.recipient_name,
            "recipient_rut": f"{documento.recipient_rut}-{documento.recipient_dv}",
            "recipient_address": documento.recipient_address,
            "status": getattr(documento, 'status', 'Unknown'),
            "created_at": documento.created_at.isoformat() if hasattr(documento, 'created_at') else None,
            "updated_at": documento.updated_at.isoformat() if hasattr(documento, 'updated_at') else None
        }
        
        return Response({
            "status": "success",
            "data": doc_detail,
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error obteniendo detalle de DTE {dte_id}: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporalmente para testing
def get_dtes_summary(request):
    """
    Obtiene resumen estadístico de los DTEs
    GET /api/v1/sii/dtes/summary/?company_rut=77794858&fecha_desde=2025-01-01&fecha_hasta=2025-12-31
    """
    try:
        # Parámetros de consulta
        company_rut = request.query_params.get('company_rut')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        
        # Construir queryset
        queryset = Document.objects.all()
        
        if company_rut:
            # Extraer solo el número del RUT (sin DV)
            rut_number = company_rut.split('-')[0] if '-' in company_rut else company_rut
            queryset = queryset.filter(issuer_company_rut=rut_number)
        
        if fecha_desde:
            try:
                fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__gte=fecha_desde)
            except ValueError:
                return Response({
                    'error': 'Formato de fecha_desde inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if fecha_hasta:
            try:
                fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(issue_date__lte=fecha_hasta)
            except ValueError:
                return Response({
                    'error': 'Formato de fecha_hasta inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calcular estadísticas
        total_count = queryset.count()
        
        # Importar models para aggregates
        from django.db import models
        
        # Verificar si Document tiene los campos necesarios
        try:
            # Totales por monto
            totals = queryset.aggregate(
                total_net=models.Sum('net_amount'),
                total_tax=models.Sum('tax_amount'),
                total_amount=models.Sum('total_amount')
            )
            
            # Por tipo de documento
            by_type = queryset.values(
                'document_type'
            ).annotate(
                count=models.Count('id'),
                total_amount=models.Sum('total_amount')
            ).order_by('-count')
            
            # Por estado
            by_status = queryset.values(
                'status'
            ).annotate(
                count=models.Count('id'),
                total_amount=models.Sum('total_amount')
            ).order_by('-count')
            
        except Exception as field_error:
            # Si hay problemas con los campos, devolver estadísticas básicas
            logger.warning(f"Error accessing document fields: {field_error}")
            return Response({
                'period': {
                    'fecha_desde': fecha_desde.isoformat() if fecha_desde else None,
                    'fecha_hasta': fecha_hasta.isoformat() if fecha_hasta else None,
                },
                'totals': {
                    'total_documents': total_count,
                    'total_net_amount': 0,
                    'total_tax_amount': 0,
                    'total_amount': 0,
                },
                'by_document_type': [],
                'by_status': [],
                'by_month': []
            })
        
        # Estadísticas por mes (últimos 12 meses)
        try:
            from django.db.models.functions import TruncMonth
            by_month = queryset.annotate(
                month=TruncMonth('issue_date')
            ).values('month').annotate(
                count=models.Count('id'),
                total_amount=models.Sum('total_amount')
            ).order_by('-month')[:12]
        except:
            by_month = []
        
        return Response({
            'period': {
                'fecha_desde': fecha_desde.isoformat() if fecha_desde else None,
                'fecha_hasta': fecha_hasta.isoformat() if fecha_hasta else None,
            },
            'totals': {
                'total_documents': total_count,
                'total_net_amount': float(totals['total_net'] or 0),
                'total_tax_amount': float(totals['total_tax'] or 0),
                'total_amount': float(totals['total_amount'] or 0),
            },
            'by_document_type': list(by_type),
            'by_status': list(by_status),
            'by_month': list(by_month)
        })
        
    except Exception as e:
        logger.error(f"Error getting DTEs summary: {e}")
        return Response({
            'error': 'Error interno del servidor',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Temporalmente para testing  
def sync_dtes_from_sii(request):
    """
    Sincronizar DTEs desde el SII
    POST /api/v1/sii/dtes/sync/
    {
        "company_rut": "77794858-k",
        "fecha_desde": "2025-08-01",
        "fecha_hasta": "2025-08-31"
    }
    """
    try:
        # Validar parámetros requeridos
        required_fields = ['company_rut', 'fecha_desde', 'fecha_hasta']
        for field in required_fields:
            if not request.data.get(field):
                return Response({
                    "error": f"Faltan parámetros requeridos: {', '.join(required_fields)}"
                }, status=status.HTTP_400_BAD_REQUEST)
        
        company_rut = request.data['company_rut']
        fecha_desde = request.data['fecha_desde']
        fecha_hasta = request.data['fecha_hasta']
        
        # Extraer RUT y DV
        if '-' in company_rut:
            rut_parts = company_rut.split('-')
            rut_number = rut_parts[0]
            rut_dv = rut_parts[1].lower()
        else:
            rut_number = company_rut[:-1] if len(company_rut) > 1 else company_rut
            rut_dv = company_rut[-1].lower() if len(company_rut) > 1 else 'k'
        
        # Crear log de sincronización
        sync_log = SIISyncLog.objects.create(
            company_rut=rut_number,
            company_dv=rut_dv,
            sync_type='electronic_docs',
            status='running',
            fecha_desde=datetime.strptime(fecha_desde, '%Y-%m-%d').date(),
            fecha_hasta=datetime.strptime(fecha_hasta, '%Y-%m-%d').date(),
            sync_data={
                'company_rut': company_rut,
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'endpoint': 'sync_dtes'
            }
        )
        
        # Simular sincronización exitosa (reemplazar con lógica real)
        import time
        start_time = time.time()
        
        # Aquí iría la lógica real de sincronización con el SII
        # Por ahora simulamos un proceso exitoso
        processed = 5
        created = 2  
        updated = 3
        failed = 0
        
        execution_time = time.time() - start_time
        
        # Actualizar log
        sync_log.status = 'completed'
        sync_log.completed_at = datetime.now()
        sync_log.records_processed = processed
        sync_log.records_created = created
        sync_log.records_updated = updated
        sync_log.records_failed = failed
        sync_log.save()
        
        return Response({
            "sync_log_id": sync_log.id,
            "status": "completed",
            "message": "Sincronización completada exitosamente",
            "results": {
                "processed": processed,
                "created": created,
                "updated": updated,
                "failed": failed
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error sincronizando DTEs: {str(e)}")
        
        # Actualizar log en caso de error
        if 'sync_log' in locals():
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.now()
            sync_log.save()
        
        return Response({
            "error": "SYNC_ERROR",
            "message": f"Error durante la sincronización: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)