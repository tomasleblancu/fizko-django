from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Sum, Count, Case, When, DecimalField
from datetime import datetime, timedelta
import logging

from .models import Document, DocumentType
from .serializers import DocumentSerializer
from apps.core.permissions import IsCompanyMember
from apps.companies.models import Company

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Solo para testing
def auth_debug(request):
    """Endpoint temporal para debug de autenticación y testing de datos reales"""
    from apps.documents.models import Document
    from apps.companies.models import Company
    from apps.accounts.models import UserRole
    from django.db.models import Sum, Count
    
    # Datos básicos
    response_data = {
        'database_stats': {
            'total_documents': Document.objects.count(),
            'total_companies': Company.objects.count(),
            'total_user_roles': UserRole.objects.count()
        }
    }
    
    # Si hay documentos, mostrar muestra de datos reales
    if Document.objects.exists():
        company_id = 31  # Company ID de los documentos que vemos en la BD
        
        try:
            company = Company.objects.get(id=company_id)
            company_rut = company.tax_id.split('-')[0]
            company_dv = company.tax_id.split('-')[1].upper()
            
            # Query similar a la que usa financial_summary
            from datetime import date
            start_date = date(2024, 1, 1)
            end_date = date(2025, 12, 31)
            
            queryset = Document.objects.filter(
                company=company,
                issue_date__gte=start_date,
                issue_date__lte=end_date
            )
            
            # Ventas (emitidas por la empresa)
            ventas_queryset = queryset.filter(
                issuer_company_rut=company_rut,
                issuer_company_dv=company_dv
            )
            
            ventas_stats = ventas_queryset.aggregate(
                total=Sum('total_amount') or 0,
                cantidad=Count('id'),
                iva=Sum('tax_amount') or 0
            )
            
            # Compras (recibidas por la empresa)
            compras_queryset = queryset.filter(
                recipient_rut=company_rut,
                recipient_dv=company_dv
            )
            
            compras_stats = compras_queryset.aggregate(
                total=Sum('total_amount') or 0,
                cantidad=Count('id'),
                iva=Sum('tax_amount') or 0
            )
            
            response_data['real_data_sample'] = {
                'company': {
                    'id': company.id,
                    'name': company.name,
                    'tax_id': company.tax_id
                },
                'ventas': {
                    'total': float(ventas_stats['total'] or 0),
                    'cantidad': ventas_stats['cantidad'],
                    'iva': float(ventas_stats['iva'] or 0)
                },
                'compras': {
                    'total': float(compras_stats['total'] or 0),
                    'cantidad': compras_stats['cantidad'],
                    'iva': float(compras_stats['iva'] or 0)
                },
                'query_info': {
                    'total_docs_in_period': queryset.count(),
                    'docs_as_issuer': ventas_queryset.count(),
                    'docs_as_recipient': compras_queryset.count()
                }
            }
            
        except Company.DoesNotExist:
            response_data['error'] = f'Company {company_id} no encontrada'
        except Exception as e:
            response_data['error'] = str(e)
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def debug_frontend_dates(request):
    """Debug: Ver qué fechas está enviando el frontend"""
    return Response({
        'query_params': dict(request.query_params),
        'company_id': request.query_params.get('company_id'),
        'start_date': request.query_params.get('start_date'),
        'end_date': request.query_params.get('end_date'),
        'headers': dict(request.headers),
        'all_docs_dates': [
            doc.issue_date.isoformat() 
            for doc in Document.objects.filter(company_id=31).order_by('issue_date')
        ]
    })


class DocumentViewSet(viewsets.ViewSet):
    """ViewSet para gestión de documentos electrónicos"""
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsCompanyMember]
    
    def get_queryset(self):
        """Filtrar documentos por empresa del usuario"""
        return Document.objects.all().order_by('-issue_date', '-folio')
    
    def get_company(self, request):
        """
        Obtiene y valida la empresa del request.
        Los permisos ya validaron que el usuario tiene acceso.
        """
        company_id = request.query_params.get('company_id')
        if not company_id:
            raise ValueError("Se requiere el parámetro company_id")
        
        try:
            company_id = int(company_id)
            return Company.objects.get(id=company_id)
        except (ValueError, Company.DoesNotExist):
            raise ValueError(f"Empresa con ID {company_id} no encontrada")
    
    def list(self, request):
        """
        Endpoint para obtener lista de documentos con datos reales
        GET /api/v1/documents/?company_id=1&tipo_operacion=venta&fecha_desde=2024-01-01&fecha_hasta=2024-12-31
        """
        try:
            company = self.get_company(request)
            
            # Parámetros de filtro
            tipo_operacion = request.query_params.get('tipo_operacion')  # ✅ Sin default, muestra TODOS por defecto
            fecha_desde = request.query_params.get('fecha_desde')
            fecha_hasta = request.query_params.get('fecha_hasta')
            page_size = int(request.query_params.get('page_size', 50))
            page = int(request.query_params.get('page', 1))
            
            # Construir query base - documentos de la empresa
            queryset = self.get_queryset().filter(company=company)
            
            # Filtrar por tipo de operación solo si se especifica
            if tipo_operacion == 'venta':
                # Documentos emitidos por la empresa
                queryset = queryset.filter(
                    issuer_company_rut=company.tax_id.split('-')[0],
                    issuer_company_dv=company.tax_id.split('-')[1].upper()
                )
            elif tipo_operacion == 'compra':
                # Documentos recibidos por la empresa
                queryset = queryset.filter(
                    recipient_rut=company.tax_id.split('-')[0],
                    recipient_dv=company.tax_id.split('-')[1].upper()
                )
            # Si no se especifica tipo_operacion, mostrar TODOS los documentos (ventas + compras)
            
            # Filtros de fecha
            if fecha_desde:
                try:
                    fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                    queryset = queryset.filter(issue_date__gte=fecha_desde_dt)
                except ValueError:
                    pass
            
            if fecha_hasta:
                try:
                    fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                    queryset = queryset.filter(issue_date__lte=fecha_hasta_dt)
                except ValueError:
                    pass
            
            # Aplicar paginación
            total_count = queryset.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            
            documents = queryset[start_index:end_index]
            
            # Serializar documentos para el frontend
            results = []
            for doc in documents:
                # Determinar tipo de operación basado en los datos del documento
                company_rut = company.tax_id.split('-')[0]
                company_dv = company.tax_id.split('-')[1].upper()
                
                # Verificar si la empresa es el emisor o receptor
                is_issuer = (doc.issuer_company_rut == company_rut and 
                           doc.issuer_company_dv == company_dv)
                is_receiver = (doc.recipient_rut == company_rut and 
                             doc.recipient_dv == company_dv)
                
                if is_issuer:
                    doc_operation = 'issued'
                    doc_tipo_operacion = 'venta' 
                elif is_receiver:
                    doc_operation = 'received'
                    doc_tipo_operacion = 'compra'
                else:
                    # Fallback basado en raw_data
                    doc_operation = 'issued' if doc.raw_data.get('tipo_operacion') == 'emitidos' else 'received'
                    doc_tipo_operacion = 'venta' if doc.raw_data.get('tipo_operacion') == 'emitidos' else 'compra'
                
                results.append({
                    'id': doc.id,
                    'document_type': str(doc.document_type.code),
                    'folio': str(doc.folio),
                    'issue_date': doc.issue_date.isoformat(),
                    'created_at': doc.created_at.isoformat(),
                    # Frontend expected fields
                    'receiver_name': doc.recipient_name,
                    'receiver_rut': doc.recipient_full_rut,
                    'sender_name': doc.issuer_name,
                    'sender_rut': f"{doc.issuer_company_rut}-{doc.issuer_company_dv}",
                    # Compatibility fields for ElectronicDocument interface
                    'razon_social_emisor': doc.issuer_name,
                    'rut_emisor': f"{doc.issuer_company_rut}-{doc.issuer_company_dv}",
                    'total_amount': float(doc.total_amount),
                    'net_amount': float(doc.net_amount),
                    'tax_amount': float(doc.tax_amount),
                    'operation': doc_operation,
                    'track_id': doc.sii_track_id or '',
                    'status': doc.status,
                    # Backward compatibility fields
                    'razon_social_receptor': doc.recipient_name,
                    'rut_receptor': doc.recipient_full_rut,
                    'monto_total': float(doc.total_amount),
                    'monto_iva': float(doc.tax_amount),
                    'monto_neto': float(doc.net_amount),
                    'tipo_operacion': doc_tipo_operacion,
                })
            
            # Calcular next/previous
            has_next = end_index < total_count
            has_previous = page > 1
            
            return Response({
                'results': results,
                'count': total_count,
                'next': f'?page={page + 1}' if has_next else None,
                'previous': f'?page={page - 1}' if has_previous else None,
                'page': page,
                'page_size': page_size
            })
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en list documents: {str(e)}")
            return Response({
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], url_path='financial-summary')
    def financial_summary(self, request):
        """
        Endpoint para obtener resumen financiero por período con datos reales
        GET /api/v1/documents/financial-summary/?company_id=1&start_date=2024-01-01&end_date=2024-12-31
        """
        try:
            # Validar empresa y parámetros
            company = self.get_company(request)
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if not all([start_date, end_date]):
                return Response({
                    'error': 'Faltan parámetros requeridos: start_date, end_date'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                start_date_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Query base: documentos de la empresa en el período
            queryset = self.get_queryset().filter(
                company=company,
                issue_date__gte=start_date_dt,
                issue_date__lte=end_date_dt
            )
            
            # Separar entre documentos emitidos (ventas) y recibidos (compras)
            company_rut = company.tax_id.split('-')[0]
            company_dv = company.tax_id.split('-')[1].upper()
            
            # VENTAS: Documentos emitidos por la empresa
            ventas_queryset = queryset.filter(
                issuer_company_rut=company_rut,
                issuer_company_dv=company_dv
            )
            
            ventas_stats = ventas_queryset.aggregate(
                total=Sum('total_amount') or 0,
                cantidad=Count('id'),
                iva=Sum('tax_amount') or 0
            )
            
            # COMPRAS: Documentos recibidos por la empresa
            compras_queryset = queryset.filter(
                recipient_rut=company_rut,
                recipient_dv=company_dv
            )
            
            compras_stats = compras_queryset.aggregate(
                total=Sum('total_amount') or 0,
                cantidad=Count('id'),
                iva=Sum('tax_amount') or 0
            )
            
            return Response({
                'ventas': {
                    'total': float(ventas_stats['total'] or 0),
                    'cantidad': ventas_stats['cantidad'],
                    'iva': float(ventas_stats['iva'] or 0)
                },
                'compras': {
                    'total': float(compras_stats['total'] or 0),
                    'cantidad': compras_stats['cantidad'],
                    'iva': float(compras_stats['iva'] or 0)
                },
                'periodo': {
                    'inicio': start_date_dt.isoformat(),
                    'fin': end_date_dt.isoformat()
                }
            })
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en financial_summary: {str(e)}")
            return Response({
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def stats(self, request, pk=None):
        """
        Endpoint para obtener estadísticas de documentos por período con datos reales
        GET /api/v1/documents/stats/?company_id=1&start_date=2024-01-01&end_date=2024-12-31&group_by=month
        """
        try:
            # Validar empresa y parámetros
            company = self.get_company(request)
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            group_by = request.query_params.get('group_by', 'month')
            
            if not all([start_date, end_date]):
                return Response({
                    'error': 'Faltan parámetros requeridos: start_date, end_date'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                start_date_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Query base: documentos de la empresa en el período
            queryset = self.get_queryset().filter(
                company=company,
                issue_date__gte=start_date_dt,
                issue_date__lte=end_date_dt
            )
            
            company_rut = company.tax_id.split('-')[0]
            company_dv = company.tax_id.split('-')[1].upper()
            
            # Generar estadísticas por período
            stats = []
            current = start_date_dt.replace(day=1)  # Primer día del mes
            
            while current <= end_date_dt:
                # Calcular fin del período (mes)
                if current.month == 12:
                    next_month = current.replace(year=current.year + 1, month=1)
                else:
                    next_month = current.replace(month=current.month + 1)
                
                period_end = next_month - timedelta(days=1)
                
                # Filtrar documentos del período actual
                period_docs = queryset.filter(
                    issue_date__gte=current,
                    issue_date__lte=period_end
                )
                
                # Ventas (emitidas por la empresa)
                ventas_queryset = period_docs.filter(
                    issuer_company_rut=company_rut,
                    issuer_company_dv=company_dv
                )
                
                ventas_stats = ventas_queryset.aggregate(
                    sales_count=Count('id'),
                    sales_amount=Sum('total_amount') or 0
                )
                
                # Compras (recibidas por la empresa)
                compras_queryset = period_docs.filter(
                    recipient_rut=company_rut,
                    recipient_dv=company_dv
                )
                
                compras_stats = compras_queryset.aggregate(
                    purchase_count=Count('id'),
                    purchase_amount=Sum('total_amount') or 0
                )
                
                stats.append({
                    'period': current.isoformat(),
                    'sales_amount': float(ventas_stats['sales_amount'] or 0),
                    'purchase_amount': float(compras_stats['purchase_amount'] or 0),
                    'document_count': ventas_stats['sales_count'] + compras_stats['purchase_count'],
                    'sales_count': ventas_stats['sales_count'],
                    'purchase_count': compras_stats['purchase_count']
                })
                
                # Siguiente mes
                current = next_month
            
            return Response(stats)
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error en stats: {str(e)}")
            return Response({
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def sales_documents(self, request):
        """
        Endpoint para obtener documentos de venta - redirige al método list con tipo_operacion=venta
        GET /api/v1/documents/sales_documents/?company_id=1&fecha_desde=2024-01-01&fecha_hasta=2024-12-31&page_size=100
        """
        # Normalizar parámetros para usar el método list
        mutable_params = request.query_params.copy()
        mutable_params['tipo_operacion'] = 'venta'
        
        # Mapear fecha_desde/fecha_hasta para compatibilidad
        if 'fecha_desde' in mutable_params:
            mutable_params['fecha_desde'] = mutable_params['fecha_desde']
        if 'fecha_hasta' in mutable_params:
            mutable_params['fecha_hasta'] = mutable_params['fecha_hasta']
        
        # Crear nuevo request con los parámetros normalizados
        request._request.GET = mutable_params
        
        # Usar el método list que ya tiene datos reales
        return self.list(request)