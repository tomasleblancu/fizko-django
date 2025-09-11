"""
Módulo para verificación de credenciales SII
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from datetime import datetime
import logging
import os

from ..serializers import CredentialsVerificationSerializer
from ..api.servicev2 import SIIServiceV2
from ..utils.exceptions import (
    SIIServiceException,
    SIIAuthenticationError,
    SIITemporaryError,
    SIIBaseException
)
from .common import handle_sii_exceptions

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])  # Temporalmente para testing
def verificar_credenciales(request):
    """
    Verificar credenciales de contribuyente en el SII
    
    POST /api/v1/sii/verificar-credenciales/
    {
        "tax_id": "77794858-k",
        "password": "SiiPfufl574@#"
    }
    """
    try:
        # Validate input data
        serializer = CredentialsVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "error": "VALIDATION_ERROR",
                "message": "Datos inválidos", 
                "details": serializer.errors,
                "timestamp": datetime.now().isoformat()
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        tax_id = validated_data['tax_id']
        password = validated_data['password']
        
        logger.info(f"🔐 Verificando credenciales: {tax_id}")
        
        # Verify credentials using SII service
        use_real_service = os.getenv('SII_USE_REAL_SERVICE', 'false').lower() == 'true'
        
        # Use the crear_con_password factory method for proper initialization
        sii_service = SIIServiceV2.crear_con_password(
            tax_id=tax_id,
            password=password,
            validar_cookies=True,
            auto_relogin=True
        )
        
        try:
            # The service already handles authentication internally
            response = sii_service.consultar_contribuyente()
            
            if response.get('status') == 'success':
                # El método consultar_contribuyente devuelve datos en 'datos_contribuyente'
                taxpayer_data = response.get('datos_contribuyente', {})
                contribuyente = taxpayer_data.get('contribuyente', {})
                
                result = {
                    'status': 'success',
                    'timestamp': datetime.now().isoformat(),
                    'data': {
                        'company_name': contribuyente.get('razonSocial', 'N/A'),
                        'company_type': contribuyente.get('tipoContribuyenteDescripcion', 'N/A'),
                        'tax_id': tax_id,
                        'valid_credentials': True,
                        'email': contribuyente.get('eMail'),
                        'fecha_inicio_actividades': contribuyente.get('fechaInicioActividades'),
                        'segmento': contribuyente.get('segmentoDescripcion')
                    }
                }
            else:
                result = {
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'message': response.get('message', 'Error verificando credenciales'),
                    'data': {
                        'tax_id': tax_id,
                        'valid_credentials': False
                    }
                }
        except Exception as e:
            result = {
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'message': str(e)
            }
        finally:
            if hasattr(sii_service, 'close'):
                sii_service.close()
        
        if result['status'] == 'success':
            logger.info(f"✅ Credenciales válidas: {tax_id}")
            return Response(result, status=status.HTTP_200_OK)
        else:
            logger.warning(f"❌ Credenciales inválidas: {tax_id}")
            return Response(result, status=status.HTTP_401_UNAUTHORIZED)
        
    except (SIIServiceException, SIIAuthenticationError, SIITemporaryError, SIIBaseException) as e:
        logger.error(f"SII Error verificando credenciales: {str(e)}")
        return handle_sii_exceptions(e)
    except Exception as e:
        logger.error(f"Error interno verificando credenciales: {str(e)}")
        return Response({
            "error": "INTERNAL_ERROR",
            "message": f"Error interno: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)