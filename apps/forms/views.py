"""
Views para formularios tributarios
"""
import logging
from datetime import datetime

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import models

from .models import TaxForm, TaxFormTemplate
from .serializers import TaxFormSerializer, TaxFormTemplateSerializer, TaxFormDetailsSerializer

logger = logging.getLogger(__name__)


class TaxFormTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para templates de formularios tributarios
    """
    queryset = TaxFormTemplate.objects.filter(is_active=True)
    serializer_class = TaxFormTemplateSerializer
    permission_classes = [IsAuthenticated]


class TaxFormViewSet(viewsets.ModelViewSet):
    """
    ViewSet para formularios tributarios
    """
    serializer_class = TaxFormSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filtrar formularios por empresa del usuario"""
        # TODO: Implementar filtro por empresa asociada al usuario
        # Por ahora retornar todos
        queryset = TaxForm.objects.select_related('company', 'template').all()

        # Filtros opcionales
        company_rut = self.request.query_params.get('company_rut')
        company_id = self.request.query_params.get('company_id')
        form_type = self.request.query_params.get('form_type')
        tax_year = self.request.query_params.get('tax_year')
        status_filter = self.request.query_params.get('status')

        # Filtrar por company (preferir company_id sobre company_rut)
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        elif company_rut:
            # Mantener compatibilidad con filtro legacy
            queryset = queryset.filter(company_rut=company_rut)

        if form_type:
            queryset = queryset.filter(template__form_type=form_type)
        if tax_year:
            queryset = queryset.filter(tax_year=tax_year)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-tax_year', '-tax_month', 'template__form_code')

    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """
        Endpoint para obtener los detalles extraídos de un formulario F29
        """
        try:
            tax_form = self.get_object()

            # Usar serializer especializado para detalles
            serializer = TaxFormDetailsSerializer(tax_form)

            return Response({
                'status': 'success',
                'data': serializer.data,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"❌ Error obteniendo detalles del formulario: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error obteniendo detalles: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def with_details(self, request):
        """
        Endpoint para listar formularios que tienen detalles extraídos
        """
        try:
            # Filtrar formularios con detalles extraídos
            queryset = self.get_queryset().filter(details_extracted=True)

            # Aplicar filtros adicionales si vienen en query params
            company_id = request.query_params.get('company_id')
            form_type = request.query_params.get('form_type')

            if company_id:
                queryset = queryset.filter(company_id=company_id)
            if form_type:
                queryset = queryset.filter(template__form_type=form_type)

            # Paginar
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = TaxFormDetailsSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = TaxFormDetailsSerializer(queryset, many=True)
            return Response({
                'status': 'success',
                'data': serializer.data,
                'count': queryset.count(),
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"❌ Error listando formularios con detalles: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error listando formularios: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def extraction_status(self, request):
        """
        Endpoint para obtener estadísticas de extracción de detalles
        """
        try:
            queryset = self.get_queryset()

            # Estadísticas generales
            total_forms = queryset.count()
            with_details = queryset.filter(details_extracted=True).count()
            needing_extraction = queryset.filter(
                details_extracted=False,
                sii_folio__isnull=False,
                sii_folio__gt=''
            ).count()

            # Por company si se especifica
            company_id = request.query_params.get('company_id')
            if company_id:
                queryset = queryset.filter(company_id=company_id)

            stats = {
                'total_forms': total_forms,
                'with_details': with_details,
                'needing_extraction': needing_extraction,
                'extraction_percentage': round((with_details / total_forms * 100) if total_forms > 0 else 0, 2),
                'by_form_type': {},
                'recent_extractions': []
            }

            # Estadísticas por tipo de formulario
            from django.db.models import Count
            by_type = queryset.values('template__form_type').annotate(
                total=Count('id'),
                extracted=Count('id', filter=models.Q(details_extracted=True))
            ).order_by('template__form_type')

            for item in by_type:
                form_type = item['template__form_type']
                stats['by_form_type'][form_type] = {
                    'total': item['total'],
                    'extracted': item['extracted'],
                    'percentage': round((item['extracted'] / item['total'] * 100) if item['total'] > 0 else 0, 2)
                }

            # Extracciones recientes (últimas 10)
            recent = queryset.filter(details_extracted=True).order_by('-details_extracted_at')[:10]
            stats['recent_extractions'] = TaxFormDetailsSerializer(recent, many=True).data

            return Response({
                'status': 'success',
                'data': stats,
                'timestamp': datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
            return Response({
                'status': 'error',
                'message': f'Error obteniendo estadísticas: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forms_summary(request):
    """
    Endpoint para obtener resumen de formularios por empresa
    """
    try:
        company_rut = request.GET.get('company_rut')
        if not company_rut:
            return Response({
                'status': 'error',
                'message': 'Parámetro company_rut es requerido',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        # Obtener estadísticas
        forms = TaxForm.objects.filter(company_rut=company_rut)

        summary = {
            'company_rut': company_rut,
            'total_forms': forms.count(),
            'by_status': {},
            'by_form_type': {},
            'by_year': {},
            'recent_forms': []
        }

        # Contar por estado
        for form in forms:
            status_key = form.status
            summary['by_status'][status_key] = summary['by_status'].get(status_key, 0) + 1

        # Contar por tipo de formulario
        for form in forms:
            form_type = form.template.form_type
            summary['by_form_type'][form_type] = summary['by_form_type'].get(form_type, 0) + 1

        # Contar por año
        for form in forms:
            year = str(form.tax_year)
            summary['by_year'][year] = summary['by_year'].get(year, 0) + 1

        # Formularios recientes (últimos 5)
        recent = forms.order_by('-created_at')[:5]
        summary['recent_forms'] = TaxFormSerializer(recent, many=True).data

        return Response({
            'status': 'success',
            'data': summary,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error obteniendo resumen: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
