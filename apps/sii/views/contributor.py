"""
Módulo para consultas de contribuyente en el SII
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from datetime import datetime
import logging
import os

from ..serializers import ConsultaContribuyenteSerializer
from ..api.servicev2 import SIIServiceV2
from ..utils.exceptions import (
    SIIServiceException,
    SIIAuthenticationError,
    SIITemporaryError,
    SIIBaseException
)
from .common import handle_sii_exceptions

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])  # Temporalmente para testing
def consultar_contribuyente(request):
    """
    Consultar datos de contribuyente en el SII
    
    POST /api/v1/sii/contribuyente/
    {
        "tax_id": "77794858-k",
        "password": "SiiPfufl574@#",
        "cookies": [...] // opcional
    }
    
    GET /api/v1/sii/contribuyente/?rut=77794858-k
    """
    try:
        # Soportar tanto GET como POST
        if request.method == 'GET':
            # Para GET, obtener RUT de query params y usar credenciales de prueba
            tax_id = request.query_params.get('rut')
            if not tax_id:
                return Response({
                    "error": "VALIDATION_ERROR",
                    "message": "RUT es requerido como parámetro query",
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Usar credenciales de prueba del .env
            password = os.getenv('SII_TEST_PASSWORD')
            cookies = []
        else:
            # Para POST, validar datos como antes
            serializer = ConsultaContribuyenteSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    "error": "VALIDATION_ERROR",
                    "message": "Datos inválidos",
                    "details": serializer.errors,
                    "timestamp": datetime.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            tax_id = validated_data['tax_id']
            password = validated_data.get('password')
            cookies = validated_data.get('cookies', [])
        
        logger.info(f"🔍 Consultando contribuyente: {tax_id}")
        
        # Extract RUT parts for service initialization
        rut_parts = tax_id.split('-')
        company_rut = rut_parts[0]
        company_dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        # Create SII service
        sii_service = SIIServiceV2(
            company_rut=company_rut,
            company_dv=company_dv,
            password=password,
            stored_cookies=cookies
        )
        
        # Authenticate and get contributor data
        contribuyente_data = sii_service.get_taxpayer_info()
        
        # Determine authentication method
        auth_method = "cookies" if cookies else "password"
        
        # Build response
        response_data = {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "tax_id": tax_id,
            "data": contribuyente_data,
            "authentication_method": auth_method,
            "cookies": sii_service.get_cookies()
        }
        
        logger.info(f"✅ Contribuyente consultado exitosamente: {tax_id}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except (SIIServiceException, SIIAuthenticationError, SIITemporaryError, SIIBaseException) as e:
        logger.error(f"SII Error consultando contribuyente: {str(e)}")
        return handle_sii_exceptions(e)
    except Exception as e:
        logger.error(f"Error interno consultando contribuyente: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)