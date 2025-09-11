"""
SII Service for Django - Mock implementation for testing
"""
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List, Any
from django.conf import settings
import os

logger = logging.getLogger(__name__)


class SIIServiceException(Exception):
    """Base exception for SII service"""
    pass


class SIIAuthenticationException(SIIServiceException):
    """Exception for authentication failures"""
    pass


class SIIUnavailableException(SIIServiceException):
    """Exception when SII service is unavailable"""
    def __init__(self, message: str, retry_after: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.error_type = error_type


class SIIErrorException(SIIServiceException):
    """Exception for SII errors"""
    def __init__(self, message: str, retry_after: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.retry_after = retry_after
        self.error_type = error_type


class MockSIIService:
    """
    Mock SII Service for testing purposes.
    This simulates the behavior of the real SII service using the fizko-backend implementation.
    """
    
    def __init__(self, tax_id: str, password: Optional[str] = None, cookies: Optional[List[Dict]] = None):
        self.tax_id = tax_id
        self.password = password
        self.cookies = cookies or []
        self.authenticated = False
        
        # Test credentials from environment
        self.test_tax_id = os.getenv('SII_TEST_TAX_ID', '77794858-k')
        self.test_password = os.getenv('SII_TEST_PASSWORD', 'SiiPfufl574@#')
        
        logger.info(f"🔧 MockSIIService initialized for tax_id: {tax_id}")

    def authenticate(self) -> bool:
        """
        Mock authentication - checks against test credentials
        """
        try:
            # If using cookies, simulate cookie validation
            if self.cookies and len(self.cookies) > 0:
                logger.info(f"🍪 Using cookies for authentication: {len(self.cookies)} cookies")
                # Simulate some cookies might be invalid
                self.authenticated = True
                return True
            
            # Password authentication
            if not self.password:
                raise SIIAuthenticationException("No password or cookies provided")
            
            # Check against test credentials
            if self.tax_id == self.test_tax_id and self.password == self.test_password:
                logger.info(f"✅ Authentication successful for {self.tax_id}")
                self.authenticated = True
                return True
            else:
                logger.warning(f"❌ Authentication failed for {self.tax_id}")
                raise SIIAuthenticationException(f"Invalid credentials for {self.tax_id}")
        
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            self.authenticated = False
            raise

    def consultar_contribuyente(self) -> Dict[str, Any]:
        """
        Mock contribuyente consultation - returns sample data for test RUT
        """
        if not self.authenticated:
            self.authenticate()
        
        logger.info(f"📊 Consultando contribuyente: {self.tax_id}")
        
        # Return mock data based on test credentials
        if self.tax_id == self.test_tax_id:
            mock_data = {
                "rut": self.tax_id,
                "razon_social": "EMPRESA DE PRUEBAS FIZKO LTDA.",
                "nombre": "EMPRESA DE PRUEBAS FIZKO LTDA.",
                "razonSocial": "EMPRESA DE PRUEBAS FIZKO LTDA.",
                "tipo_contribuyente": "Primera Categoría",
                "estado": "ACTIVO",
                "fecha_inicio_actividades": "2020-01-15",
                "direccion": "AV PROVIDENCIA 1234, PROVIDENCIA, REGION METROPOLITANA",
                "comuna": "PROVIDENCIA",
                "region": "REGION METROPOLITANA",
                "telefono": "+56 2 2234 5678",
                "email": "contacto@fizko-test.cl",
                "actividades_economicas": [
                    {
                        "codigo": "620200",
                        "descripcion": "Consultores en programas de informática"
                    },
                    {
                        "codigo": "741000", 
                        "descripcion": "Actividades especializadas de diseño"
                    }
                ],
                "representante_legal": {
                    "nombre": "JUAN CARLOS EMPRESARIO",
                    "rut": "12345678-9"
                }
            }
            
            logger.info(f"✅ Contribuyente data retrieved for {self.tax_id}")
            return mock_data
        else:
            # For any other RUT, return generic mock data
            return {
                "rut": self.tax_id,
                "razon_social": "EMPRESA GENERICA S.A.",
                "nombre": "EMPRESA GENERICA S.A.",
                "tipo_contribuyente": "Primera Categoría",
                "estado": "ACTIVO"
            }

    def get_cookies(self) -> List[Dict]:
        """
        Return current session cookies
        """
        if self.authenticated:
            # Return mock cookies
            return [
                {"name": "JSESSIONID", "value": "mock_session_123", "domain": ".sii.cl"},
                {"name": "sii_auth", "value": "mock_auth_token", "domain": ".sii.cl"}
            ]
        return []


def create_sii_service(tax_id: str, password: Optional[str] = None, cookies: Optional[List[Dict]] = None, use_real: bool = True) -> Any:
    """
    Factory function to create SII service instance
    """
    if use_real and password:
        try:
            # Intentar usar servicio real con Selenium
            from .rpa.sii_rpa_service import create_real_sii_service
            logger.info(f"🌐 Creating REAL SII service for {tax_id}")
            return create_real_sii_service(tax_id=tax_id, password=password)
        except Exception as e:
            logger.warning(f"⚠️ Failed to create real SII service, falling back to mock: {str(e)}")
            # Fallback al servicio mock si hay problemas
            logger.info(f"🔧 Creating MOCK SII service for {tax_id} (fallback)")
            return MockSIIService(tax_id=tax_id, password=password, cookies=cookies)
    else:
        # Usar servicio mock para testing
        logger.info(f"🔧 Creating MOCK SII service for {tax_id}")
        return MockSIIService(tax_id=tax_id, password=password, cookies=cookies)


def verify_sii_credentials(tax_id: str, password: str, use_real: bool = True) -> Dict[str, Any]:
    """
    Verify SII credentials and return basic contributor information
    """
    start_time = time.time()
    
    try:
        # Create service instance
        service = create_sii_service(tax_id=tax_id, password=password, use_real=use_real)
        
        try:
            # Authenticate
            service.authenticate()
            
            # Get contributor data
            contribuyente_data = service.consultar_contribuyente()
            
            execution_time = time.time() - start_time
            
            result = {
                "status": "success",
                "message": "Credenciales válidas",
                "timestamp": datetime.now().isoformat(),
                "execution_time": round(execution_time, 2),
                "data": {
                    "tax_id": tax_id,
                    "valid_credentials": True,
                    "company_name": contribuyente_data.get("razon_social", ""),
                    "company_type": contribuyente_data.get("tipo_contribuyente", ""),
                    "status": contribuyente_data.get("estado", "")
                }
            }
            
            return result
            
        finally:
            # Cerrar servicio para liberar recursos
            if hasattr(service, 'close'):
                service.close()
        
    except SIIAuthenticationException as e:
        execution_time = time.time() - start_time
        return {
            "status": "error",
            "message": "Credenciales inválidas",
            "timestamp": datetime.now().isoformat(),
            "execution_time": round(execution_time, 2),
            "data": {
                "tax_id": tax_id,
                "valid_credentials": False,
                "error": str(e)
            }
        }
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Error verifying credentials: {str(e)}")
        raise SIIServiceException(f"Error interno: {str(e)}")