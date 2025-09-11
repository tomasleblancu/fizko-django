"""
Servicio SII API v2 - Versión simplificada sin dependencias de base de datos.
Adaptado para Django manteniendo compatibilidad mínima.
"""
import requests
import uuid
import logging
import time
from typing import Dict, Any, List, Optional
from functools import wraps
from django.utils import timezone

logger = logging.getLogger(__name__)


def retry_on_sii_unavailable(max_retries: int = 3, base_delay: int = 30):
    """
    Decorador para reintentar automáticamente cuando el SII no está disponible.
    
    Args:
        max_retries: Número máximo de reintentos
        base_delay: Delay base en segundos
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Si es el último intento, lanzar excepción
                    if attempt == max_retries:
                        logger.error(f"Máximo de reintentos alcanzado: {str(e)}")
                        raise
                    
                    # Calcular delay exponencial
                    delay = base_delay * (2 ** attempt)
                    
                    logger.warning(
                        f"Error en intento {attempt + 1}/{max_retries + 1}: {str(e)}. "
                        f"Reintentando en {delay} segundos..."
                    )
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


class SIIServiceV2:
    """Servicio SII API v2 - Versión simplificada para Django."""
    
    BASE_URL = "https://www4.sii.cl/consdcvinternetui/services/data/facadeService"
    COMPLEMENTO_URL = "https://www4.sii.cl/complementowebdcvui/services/data/facadeServiceComplementowebdcv"
    MISIIR_URL = "https://misiir.sii.cl/cgi_misii/CViewCarta.cgi"
    BOLETAS_URL = "https://www4.sii.cl/complementoscvui/services/data/facadeServiceBoletasDiarias"
    
    # Tipos de documentos disponibles
    TIPOS_DOCUMENTO = {
        "33": "Factura Electrónica",
        "34": "Factura Exenta Electrónica", 
        "35": "Boleta Electrónica",
        "38": "Boleta Exenta Electrónica",
        "39": "Guía de Despacho Electrónica",
        "40": "Liquidación Factura Electrónica",
        "43": "Liquidación Factura Electrónica",
        "45": "Factura de Compra Electrónica",
        "48": "Comprobante de Pago Electrónico",
        "52": "Guía de Despacho",
        "56": "Nota de Débito Electrónica",
        "60": "Nota de Crédito",
        "61": "Nota de Crédito Electrónica",
        "110": "Factura de Exportación Electrónica",
        "111": "Nota de Débito de Exportación Electrónica",
        "112": "Nota de Crédito de Exportación Electrónica",
    }
    
    def __init__(
        self, 
        tax_id: str, 
        cookies: Optional[List[Dict[str, Any]]] = None, 
        password: Optional[str] = None,
        validar_cookies: bool = True,
        auto_relogin: bool = True,
        save_fresh_cookies: bool = False
    ):
        """
        Inicializa el servicio SII API v2.
        
        Args:
            tax_id: RUT de la empresa (ej: "12345678-9")
            cookies: Lista de cookies obtenidas del login
            password: Contraseña para hacer login automático
            validar_cookies: Si True, valida las cookies inmediatamente
            auto_relogin: Si True, hace login automático cuando las cookies sean inválidas
            save_fresh_cookies: Si True, guarda las cookies en BD (solo para cookies del RPA)
        """
        # Si no se proporcionan cookies, intentar cargar de la base de datos
        if not cookies:
            cookies = self._load_stored_cookies(tax_id)
            if cookies:
                logger.info(f"🍪 Cargadas {len(cookies)} cookies almacenadas para {tax_id}")
        
        if not cookies and not password:
            raise ValueError("Debe proporcionar cookies o password para el login automático")
        
        self.tax_id = tax_id
        self.password = password
        self.auto_relogin = auto_relogin
        self.cookies = cookies
        
        # Si no hay cookies pero sí password, hacer login automático
        if not self.cookies and self.password:
            logger.info(f"🔐 No hay cookies, haciendo login automático para {tax_id}...")
            self._hacer_login_automatico()
        
        # Configurar headers base
        self._actualizar_headers()
        
        logger.info(f"🌐 SIIServiceV2 inicializado para {tax_id}")
        
        # Validar cookies si se solicita
        if validar_cookies and self.cookies:
            logger.info(f"🔍 Validando cookies para {tax_id}...")
            validacion = self._validar_cookies_inmediato()
            if not validacion['valid']:
                if self.auto_relogin and self.password:
                    logger.warning("⚠️ Cookies inválidas, intentando login automático...")
                    self._hacer_login_automatico()
                    validacion = self._validar_cookies_inmediato()
                    if not validacion['valid']:
                        raise Exception(f"Login automático falló: {validacion['message']}")
                    logger.info("✅ Login automático exitoso")
                else:
                    raise Exception(f"Cookies inválidas: {validacion['message']}")
            else:
                logger.info("✅ Cookies validadas exitosamente")
        
        # Solo guardar cookies si son frescas del RPA
        if save_fresh_cookies and self.cookies:
            self._guardar_cookies_frescas()
    
    def _load_stored_cookies(self, tax_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Carga cookies almacenadas desde la base de datos si existen y son válidas.
        
        Args:
            tax_id: RUT de la empresa
            
        Returns:
            Lista de cookies si se encuentran válidas, None en caso contrario
        """
        try:
            # Importar aquí para evitar dependencias circulares
            from ..models import SIISession
            
            # Extraer RUT y DV del tax_id
            rut_parts = tax_id.split('-')
            company_rut = rut_parts[0]
            company_dv = rut_parts[1].upper() if len(rut_parts) > 1 else 'K'
            
            # Buscar sesión activa y no expirada
            active_session = SIISession.objects.filter(
                company_rut=company_rut,
                company_dv=company_dv,
                is_active=True,
                expires_at__gt=timezone.now()
            ).order_by('-created_at').first()
            
            if active_session and active_session.cookies_data:
                logger.info(f"🍪 Encontrada sesión almacenada para {tax_id} (ID: {active_session.session_id})")
                
                # Actualizar última actividad
                active_session.last_activity = timezone.now()
                active_session.save(update_fields=['last_activity'])
                
                return active_session.cookies_data
            else:
                logger.info(f"🔍 No se encontró sesión válida almacenada para {tax_id}")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ Error cargando cookies almacenadas para {tax_id}: {str(e)}")
            return None
    
    def _hacer_login_automatico(self):
        """Hace login automático usando RPA para obtener nuevas cookies."""
        if not self.password:
            raise Exception("No se puede hacer login automático sin contraseña")
        
        try:
            logger.info(f"🤖 Iniciando login automático para {self.tax_id}...")
            
            # Importar aquí para evitar dependencias circulares
            from ..rpa.sii_rpa_service import RealSIIService
            
            # Crear instancia temporal de RPA para login
            rpa_service = None
            try:
                rpa_service = RealSIIService(
                    tax_id=self.tax_id,
                    password=self.password, 
                    headless=True
                )
                
                if rpa_service.authenticate():
                    self.cookies = rpa_service.get_cookies()
                    logger.info(f"✅ Login automático exitoso, {len(self.cookies)} cookies obtenidas")
                else:
                    raise Exception("Login RPA falló")
                
            finally:
                if rpa_service:
                    rpa_service.close()
            
            # Actualizar headers con las nuevas cookies
            self._actualizar_headers()
            
        except Exception as e:
            logger.error(f"❌ Error en login automático: {str(e)}")
            raise Exception(f"Login automático falló: {str(e)}")
    
    def _actualizar_headers(self):
        """Actualiza los headers con las cookies actuales."""
        if self.cookies:
            self.headers = {
                "Cookie": self._construir_cookie_string(),
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        else:
            self.headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

    def _construir_cookie_string(self) -> str:
        """Construye el string de cookies para las peticiones HTTP."""
        if not self.cookies:
            raise Exception("No hay cookies disponibles")
        cookie_parts = [f"{c['name']}={c['value']}" for c in self.cookies]
        return "; ".join(cookie_parts)
    
    def _generate_metadata(self, namespace: str = None) -> Dict[str, Any]:
        """Genera los metadatos requeridos para las peticiones al SII."""
        token_cookie = next((cookie for cookie in self.cookies if cookie['name'] == 'TOKEN'), None)
        if not token_cookie:
            raise Exception("No se encontró el cookie TOKEN")
        return {
            "namespace": namespace,
            "conversationId": token_cookie['value'],
            "transactionId": str(uuid.uuid4()),
            "page": None
        }
    
    @retry_on_sii_unavailable()
    def get_documentos_compra(
        self,
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        token_recaptcha: str = "t-o-k-e-n-web"
    ) -> Dict[str, Any]:
        """
        Obtiene los documentos de compra del SII.
        
        Args:
            periodo_tributario: Período tributario en formato YYYYMM
            cod_tipo_doc: Código del tipo de documento
            token_recaptcha: Token de reCAPTCHA
        """
        return self._get_documentos_financieros(
            periodo_tributario=periodo_tributario,
            cod_tipo_doc=cod_tipo_doc,
            operacion="COMPRA",
            token_recaptcha=token_recaptcha
        )
    
    @retry_on_sii_unavailable()
    def get_documentos_venta(
        self,
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        token_recaptcha: str = "t-o-k-e-n-web"
    ) -> Dict[str, Any]:
        """
        Obtiene los documentos de venta del SII.
        
        Args:
            periodo_tributario: Período tributario en formato YYYYMM
            cod_tipo_doc: Código del tipo de documento
            token_recaptcha: Token de reCAPTCHA
        """
        return self._get_documentos_financieros(
            periodo_tributario=periodo_tributario,
            cod_tipo_doc=cod_tipo_doc,
            operacion="VENTA",
            token_recaptcha=token_recaptcha
        )
    
    def _get_documentos_financieros(
        self,
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        operacion: str = "COMPRA",
        token_recaptcha: str = "t-o-k-e-n-web"
    ) -> Dict[str, Any]:
        """Método interno para obtener documentos financieros."""
        # Determinar endpoint y acción según operación
        if operacion == "VENTA":
            url = f"{self.BASE_URL}/getDetalleVenta"
            accion_recaptcha = "RCV_DETV"
            namespace = "cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/getDetalleVenta"
            operacion_param = ""
            estado_contab = ""
        else:
            url = f"{self.BASE_URL}/getDetalleCompra"
            accion_recaptcha = "RCV_DETC"
            namespace = "cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/getDetalleCompra"
            operacion_param = operacion
            estado_contab = "REGISTRO"
        
        # Extraer RUT y DV
        rut_parts = self.tax_id.split('-')
        rut = rut_parts[0]
        dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        payload = {
            "metaData": self._generate_metadata(namespace),
            "data": {
                "rutEmisor": rut,
                "dvEmisor": dv.upper(),
                "ptributario": periodo_tributario,
                "codTipoDoc": cod_tipo_doc,
                "operacion": operacion_param,
                "estadoContab": estado_contab,
                "accionRecaptcha": accion_recaptcha,
                "tokenRecaptcha": token_recaptcha
            }
        }
        
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result if result is not None else {}

    @retry_on_sii_unavailable()
    def get_boletas(
        self,
        periodo_tributario: str,
        tipo_documento: str = "35",
        page_size: int = 100,
        page_index: int = 1
    ) -> Dict[str, Any]:
        """
        Obtiene las boletas del SII.
        
        Args:
            periodo_tributario: Período tributario en formato YYYYMM
            tipo_documento: Código del tipo de documento
            page_size: Tamaño de página
            page_index: Índice de página
        """
        url = f"{self.BOLETAS_URL}/obtieneListaBoletasMes"
        namespace = "cl.sii.sdi.lob.diii.dcv.data.impl.boletasdiarias.FacadeSettingApplicationService/obtieneListaBoletasMes"
        
        rut_parts = self.tax_id.split('-')
        rut = rut_parts[0]
        dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        token_cookie = next((cookie for cookie in self.cookies if cookie['name'] == 'TOKEN'), None)
        if not token_cookie:
            raise Exception("No se encontró el cookie TOKEN")
        
        payload = {
            "metaData": {
                "namespace": namespace,
                "conversationId": token_cookie['value'],
                "transactionId": str(uuid.uuid4()),
                "page": {
                    "pageSize": page_size,
                    "pageIndex": page_index
                }
            },
            "data": {
                "rut": rut,
                "dv": dv.upper(),
                "periodo": periodo_tributario,
                "tipoDocumento": tipo_documento
            }
        }
        
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        
        return response.json()

    @retry_on_sii_unavailable()
    def get_resumen_compras_ventas(
        self,
        periodo_tributario: str
    ) -> Dict[str, Any]:
        """
        Obtiene el resumen de compras y ventas combinado.
        
        Args:
            periodo_tributario: Período tributario en formato YYYYMM
        """
        try:
            resumen_compras = self.get_resumen_documentos_financieros(
                periodo_tributario=periodo_tributario,
                operacion="COMPRA"
            )
            
            resumen_ventas = self.get_resumen_documentos_financieros(
                periodo_tributario=periodo_tributario,
                operacion="VENTA"
            )
            
            return {
                "status": "success",
                "periodo_tributario": periodo_tributario,
                "compras": resumen_compras,
                "ventas": resumen_ventas
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error obteniendo resumen: {str(e)}",
                "periodo_tributario": periodo_tributario
            }

    @retry_on_sii_unavailable()
    def get_resumen_documentos_financieros(
        self,
        periodo_tributario: str,
        operacion: str = "COMPRA"
    ) -> Dict[str, Any]:
        """
        Obtiene el resumen de documentos financieros del SII.
        
        Args:
            periodo_tributario: Período tributario en formato YYYYMM
            operacion: Tipo de operación ("COMPRA" o "VENTA")
        """
        url = f"{self.BASE_URL}/getResumen"
        namespace = "cl.sii.sdi.lob.diii.consdcv.data.api.interfaces.FacadeService/getResumen"
        
        rut_parts = self.tax_id.split('-')
        rut = rut_parts[0]
        dv = rut_parts[1] if len(rut_parts) > 1 else '0'
        
        payload = {
            "metaData": self._generate_metadata(namespace),
            "data": {
                "rutEmisor": rut,
                "dvEmisor": dv.upper(),
                "ptributario": periodo_tributario,
                "estadoContab": "REGISTRO",
                "operacion": operacion,
                "busquedaInicial": True
            }
        }
        
        response = requests.post(url, json=payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        
        return response.json()

    @retry_on_sii_unavailable()
    def consultar_contribuyente(self) -> Dict[str, Any]:
        """
        Consulta la información del contribuyente en el servicio MISIIR del SII.
        """
        payload = {'opc': '112'}
        
        headers_post = self.headers.copy()
        headers_post['Content-Type'] = 'application/x-www-form-urlencoded'
        
        response = requests.post(self.MISIIR_URL, data=payload, headers=headers_post, timeout=30)
        response.raise_for_status()
        
        datos_contribuyente = response.json()

        codigo_resp = datos_contribuyente.get('codigoResp')
        if codigo_resp == -2:
            return {
                'status': 'error',
                'message': 'Error al obtener los datos del contribuyente',
                'datos_contribuyente': datos_contribuyente
            }
        
        return {
            'status': 'success',
            'message': 'Datos del contribuyente obtenidos exitosamente',
            'datos_contribuyente': datos_contribuyente
        }

    def _validar_cookies_inmediato(self) -> Dict[str, Any]:
        """Valida las cookies inmediatamente."""
        try:
            token_cookie = next((cookie for cookie in self.cookies if cookie['name'] == 'TOKEN'), None)
            if not token_cookie:
                return {
                    'status': 'error',
                    'message': 'No se encontró el cookie TOKEN requerido',
                    'valid': False
                }
            
            # Hacer consulta simple para validar cookies
            response = self.consultar_contribuyente()
            
            if response.get('status') == 'success':
                return {
                    'status': 'success',
                    'message': 'Cookies válidas',
                    'valid': True
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Las cookies no permiten acceso al SII',
                    'valid': False
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error validando cookies: {str(e)}',
                'valid': False
            }

    def validar_cookies(self) -> Dict[str, Any]:
        """Valida si las cookies siguen siendo válidas."""
        return self._validar_cookies_inmediato()

    def actualizar_cookies(self, cookies_nuevas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Actualiza las cookies del servicio y las valida.
        
        Args:
            cookies_nuevas: Nuevas cookies para reemplazar las actuales
        """
        if not cookies_nuevas:
            raise ValueError('Las nuevas cookies no pueden estar vacías')
        
        token_cookie = next((cookie for cookie in cookies_nuevas if cookie['name'] == 'TOKEN'), None)
        if not token_cookie:
            raise ValueError('Las nuevas cookies no contienen el TOKEN requerido')
        
        # Actualizar cookies
        self.cookies = cookies_nuevas
        self._actualizar_headers()
        
        # Validar nuevas cookies
        validacion = self._validar_cookies_inmediato()
        if not validacion['valid']:
            logger.warning(f"⚠️ Cookies actualizadas pero no son válidas: {validacion['message']}")
        
        return {
            'status': 'success' if validacion['valid'] else 'warning',
            'message': 'Cookies actualizadas exitosamente' if validacion['valid'] else validacion['message'],
            'cookies_updated': True,
            'cookies_valid': validacion['valid']
        }

    def _guardar_cookies_frescas(self):
        """Guarda las cookies frescas en SIISession para persistencia"""
        try:
            if not self.cookies:
                logger.warning(f"⚠️ No hay cookies para guardar para {self.tax_id}")
                return
                
            # Importar aquí para evitar dependencias circulares
            from ..models import SIISession
            from django.utils import timezone
            import uuid
            from datetime import timedelta
            
            # Extraer RUT y DV del tax_id
            rut_parts = self.tax_id.split('-')
            company_rut = rut_parts[0]
            company_dv = rut_parts[1].upper() if len(rut_parts) > 1 else 'K'
            
            # Invalidar sesiones activas existentes para esta empresa
            SIISession.objects.filter(
                company_rut=company_rut,
                company_dv=company_dv,
                is_active=True
            ).update(is_active=False)
            
            # Crear nueva sesión con cookies frescas
            session_id = str(uuid.uuid4())
            session = SIISession.objects.create(
                company_rut=company_rut,
                company_dv=company_dv,
                username=self.tax_id,  # Usar tax_id como username
                session_id=session_id,
                cookies_data=self.cookies,
                is_active=True,
                expires_at=timezone.now() + timedelta(hours=8)  # SII sessions ~8 horas
            )
            
            logger.info(f"💾 Guardadas cookies frescas en nueva sesión {session_id} para {self.tax_id}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando cookies frescas para {self.tax_id}: {str(e)}")

    def get_tipos_documento(self) -> Dict[str, str]:
        """Retorna los tipos de documentos disponibles."""
        return self.TIPOS_DOCUMENTO

    @staticmethod
    def crear_con_password(
        tax_id: str, 
        password: str,
        validar_cookies: bool = True,
        auto_relogin: bool = True
    ) -> 'SIIServiceV2':
        """
        Factory method para crear una instancia solo con tax_id y password.
        
        Args:
            tax_id: RUT de la empresa
            password: Contraseña para el login
            validar_cookies: Si validar cookies inmediatamente
            auto_relogin: Si hacer login automático cuando las cookies sean inválidas
        """
        return SIIServiceV2(
            tax_id=tax_id, 
            cookies=None, 
            password=password,
            validar_cookies=validar_cookies,
            auto_relogin=auto_relogin
        )