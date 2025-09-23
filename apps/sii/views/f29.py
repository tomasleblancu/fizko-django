"""
Views para manejo de formularios F29
Módulo separado para no interferir con views existentes
"""
import logging
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from ..rpa.f29.f29_service import F29Service
from ..utils.exceptions import SIIValidationError, SIIConnectionError

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def obtener_formulario_f29(request):
    """
    Obtiene un formulario F29 específico desde SII.

    Query Parameters:
        folio (str): Folio del formulario F29 (requerido)
        periodo (str): Período tributario (opcional)

    Returns:
        JSON con datos del formulario F29
    """
    try:
        # Validar parámetros
        folio = request.GET.get('folio')
        if not folio:
            return Response({
                'status': 'error',
                'message': 'Parámetro folio es requerido',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        periodo = request.GET.get('periodo')

        logger.info(f"📋 Solicitud F29 folio: {folio}, período: {periodo}")

        # TODO: Obtener credenciales SII de la empresa del usuario
        # Por ahora usar credenciales de configuración
        tax_id = getattr(settings, 'SII_TAX_ID', None)
        password = getattr(settings, 'SII_PASSWORD', None)

        if not tax_id or not password:
            return Response({
                'status': 'error',
                'message': 'Credenciales SII no configuradas',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Crear servicio F29
        f29_service = F29Service(tax_id=tax_id, password=password, headless=True)

        try:
            # Obtener formulario
            resultado = f29_service.obtener_formulario_f29(folio, periodo)

            if resultado.get('status') == 'success':
                return Response({
                    'status': 'success',
                    'data': resultado,
                    'timestamp': datetime.now().isoformat()
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'error',
                    'message': resultado.get('message', 'Error desconocido'),
                    'data': resultado,
                    'timestamp': datetime.now().isoformat()
                }, status=status.HTTP_502_BAD_GATEWAY)

        finally:
            f29_service.close()

    except SIIConnectionError as e:
        logger.error(f"❌ Error de conexión SII: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error de conexión con SII: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    except SIIValidationError as e:
        logger.error(f"❌ Error de validación SII: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error de validación: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"❌ Error inesperado: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_codigos_f29(request):
    """
    Lista todos los códigos F29 disponibles desde el CSV.

    Query Parameters:
        subject (str): Filtrar por subject (opcional)
        task (str): Filtrar por task (opcional)

    Returns:
        JSON con códigos F29 disponibles
    """
    try:
        import csv
        import os

        # Filtros opcionales
        subject_filter = request.GET.get('subject')
        task_filter = request.GET.get('task')

        # Cargar códigos desde CSV
        csv_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'rpa', 'codigos_f29.csv'
        )

        if not os.path.exists(csv_path):
            return Response({
                'status': 'error',
                'message': 'Archivo de códigos F29 no encontrado',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        codigos = []
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Aplicar filtros si están presentes
                if subject_filter and row.get('subject', '') != subject_filter:
                    continue
                if task_filter and row.get('task', '') != task_filter:
                    continue

                codigos.append({
                    'code': row.get('code', ''),
                    'name': row.get('name', ''),
                    'type': row.get('type', ''),
                    'task': row.get('task', ''),
                    'subject': row.get('subject', ''),
                    'has_xpath': bool(row.get('xpath', '').strip())
                })

        return Response({
            'status': 'success',
            'data': {
                'codigos': codigos,
                'total': len(codigos),
                'filters_applied': {
                    'subject': subject_filter,
                    'task': task_filter
                }
            },
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"❌ Error listando códigos F29: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error listando códigos: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_f29(request):
    """
    Health check específico para funcionalidad F29.

    Returns:
        JSON con estado del módulo F29
    """
    try:
        import os

        # Verificar archivos necesarios
        csv_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'rpa', 'codigos_f29.csv'
        )

        csv_exists = os.path.exists(csv_path)
        csv_readable = False
        total_codes = 0

        if csv_exists:
            try:
                import csv
                with open(csv_path, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    total_codes = sum(1 for row in reader)
                csv_readable = True
            except Exception:
                pass

        # Verificar credenciales
        credentials_configured = bool(
            getattr(settings, 'SII_TAX_ID', None) and
            getattr(settings, 'SII_PASSWORD', None)
        )

        health_status = {
            'module': 'F29',
            'status': 'healthy' if csv_readable and credentials_configured else 'degraded',
            'components': {
                'csv_file': {
                    'exists': csv_exists,
                    'readable': csv_readable,
                    'total_codes': total_codes,
                    'path': csv_path
                },
                'credentials': {
                    'configured': credentials_configured
                },
                'services': {
                    'f29_service': 'available',
                    'rpa_integration': 'available'
                }
            },
            'timestamp': datetime.now().isoformat()
        }

        response_status = status.HTTP_200_OK if health_status['status'] == 'healthy' else status.HTTP_206_PARTIAL_CONTENT

        return Response(health_status, status=response_status)

    except Exception as e:
        logger.error(f"❌ Error en health check F29: {str(e)}")
        return Response({
            'module': 'F29',
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def buscar_formularios_f29(request):
    """
    Busca formularios F29 en el SII sin necesidad de folio específico.

    Query Parameters:
        anio (str): Año a consultar (obligatorio si no se busca por folio)
        mes (str): Mes a consultar (opcional, solo para búsqueda por período)
        folio (str): Folio específico a consultar (opcional)

    Returns:
        JSON con formularios F29 encontrados
    """
    try:
        from django.conf import settings
        from ..rpa.sii_rpa_service import RealSIIService

        # Parámetros de búsqueda
        anio = request.GET.get('anio')
        mes = request.GET.get('mes')
        folio = request.GET.get('folio')

        logger.info(f"🔍 Búsqueda F29 solicitada - Año: {anio}, Mes: {mes}, Folio: {folio}")

        # Validar parámetros
        if not folio and not anio:
            return Response({
                'status': 'error',
                'message': 'Debe especificar año o folio para la búsqueda',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        if mes and not anio:
            return Response({
                'status': 'error',
                'message': 'Si especifica mes debe también especificar año',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        if anio and (not anio.isdigit() or len(anio) != 4):
            return Response({
                'status': 'error',
                'message': 'El año debe ser un número de 4 dígitos',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        if mes and (not mes.isdigit() or int(mes) < 1 or int(mes) > 12):
            return Response({
                'status': 'error',
                'message': 'El mes debe ser un número entre 1 y 12',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verificar credenciales
        tax_id = getattr(settings, 'SII_TAX_ID', None)
        password = getattr(settings, 'SII_PASSWORD', None)

        if not tax_id or not password:
            return Response({
                'status': 'error',
                'message': 'Credenciales SII no configuradas',
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Crear servicio SII
        sii_service = RealSIIService(
            tax_id=tax_id,
            password=password,
            headless=True
        )

        try:
            # Buscar formularios
            resultado = sii_service.buscar_formularios_f29(
                anio=anio,
                mes=mes,
                folio=folio
            )

            if resultado['status'] == 'success':
                response_data = {
                    'status': 'success',
                    'data': resultado['data'],
                    'message': resultado['message'],
                    'timestamp': datetime.now().isoformat()
                }
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                # Error en la búsqueda
                error_data = {
                    'status': 'error',
                    'message': resultado['message'],
                    'error_type': resultado.get('error_type', 'unknown'),
                    'data': resultado.get('data', {}),
                    'timestamp': datetime.now().isoformat()
                }
                return Response(error_data, status=status.HTTP_502_BAD_GATEWAY)

        finally:
            # Cerrar servicio SII
            sii_service.close()

    except Exception as e:
        logger.error(f"❌ Error buscando formularios F29: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Error interno: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)