"""
Utilidades comunes para los views de SII
"""
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime

from ..utils.exceptions import (
    SIIServiceException,
    SIIAuthenticationError,
    SIITemporaryError,
    SIIBaseException
)


def handle_sii_exceptions(e: Exception) -> Response:
    """
    Handle SII exceptions and return appropriate HTTP response
    """
    if isinstance(e, SIITemporaryError):
        return Response({
            "error": "SII_UNAVAILABLE",
            "message": str(e),
            "retry_after": getattr(e, 'retry_after', None),
            "error_type": getattr(e, 'error_type', None),
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    elif isinstance(e, SIIBaseException):
        return Response({
            "error": "SII_ERROR", 
            "message": str(e),
            "retry_after": getattr(e, 'retry_after', None),
            "error_type": getattr(e, 'error_type', None),
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_502_BAD_GATEWAY)
    
    elif isinstance(e, SIIAuthenticationError):
        return Response({
            "error": "SII_AUTH_ERROR",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    else:
        return Response({
            "error": "INTERNAL_ERROR",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)