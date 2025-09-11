"""
Excepciones personalizadas para la integración con SII
Proporciona manejo granular de errores específicos del SII
"""


class SIIBaseException(Exception):
    """Excepción base para errores relacionados con SII"""
    
    def __init__(self, message: str, error_code: str = None, retry_after: int = None):
        super().__init__(message)
        self.error_code = error_code
        self.retry_after = retry_after


class SIIConnectionError(SIIBaseException):
    """Error de conexión al SII"""
    pass


class SIIAuthenticationError(SIIBaseException):
    """Error de autenticación con SII"""
    pass


class SIIRateLimitError(SIIBaseException):
    """Error por límite de velocidad del SII"""
    
    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message, retry_after=retry_after)


class SIITemporaryError(SIIBaseException):
    """Error temporal del SII (servicio no disponible, mantenimiento, etc.)"""
    
    def __init__(self, message: str, retry_after: int = 300):
        super().__init__(message, retry_after=retry_after)


class SIIDataError(SIIBaseException):
    """Error en los datos recibidos del SII"""
    pass


class SIIParsingError(SIIBaseException):
    """Error al parsear datos del SII"""
    pass


class SIIValidationError(SIIBaseException):
    """Error de validación de datos SII"""
    pass


class SIITimeoutError(SIIBaseException):
    """Error por timeout en operaciones SII"""
    
    def __init__(self, message: str, timeout_seconds: int = None):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


class SIIMaintenanceError(SIIBaseException):
    """SII en mantenimiento"""
    
    def __init__(self, message: str = "SII en mantenimiento", retry_after: int = 3600):
        super().__init__(message, retry_after=retry_after)


class SIIPermissionError(SIIBaseException):
    """Error de permisos en SII (usuario sin acceso a cierta funcionalidad)"""
    pass


# Backward compatibility con las excepciones existentes
SIIServiceException = SIIBaseException
SIIUnavailableException = SIITemporaryError
SIIErrorException = SIIBaseException