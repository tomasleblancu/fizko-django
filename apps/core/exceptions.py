from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Manejador de excepciones personalizado
    """
    # Llamar al manejador por defecto primero
    response = exception_handler(exc, context)

    if response is not None:
        # Personalizar el formato de respuesta de error
        custom_response_data = {
            'success': False,
            'error': {
                'message': 'Ha ocurrido un error',
                'details': response.data,
                'code': response.status_code
            }
        }
        
        # Log del error
        logger.error(f"API Error: {exc} - Context: {context}")
        
        response.data = custom_response_data

    return response