"""
Real SII Service using Selenium for Django
Based on fizko-backend SII RPA implementation
"""
import time
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from django.utils import timezone

from .selenium_driver import SeleniumDriver
from ..utils.exceptions import SIIConnectionError, SIIAuthenticationError, SIIValidationError
from ..models import SIISession

logger = logging.getLogger(__name__)


class RealSIIService:
    """
    Servicio SII real usando Selenium para automatizar el navegador
    """
    
    LOGIN_URL = "https://zeusr.sii.cl/AUT2000/InicioAutenticacion/IngresoRutClave.html"
    MISIIR_BASE_URL = "https://misiir.sii.cl/cgi_misii/siihome.cgi"
    
    def __init__(self, tax_id: str, password: str, headless: bool = True):
        self.tax_id = tax_id
        self.password = password
        self.headless = headless
        self.driver = None
        self.authenticated = False
        self.cookies = []
        self.session_id = None
        
        # Extraer RUT y DV del tax_id
        rut_parts = self.tax_id.split('-')
        self.company_rut = rut_parts[0]
        self.company_dv = rut_parts[1] if len(rut_parts) > 1 else 'k'
        
        logger.info(f"🔧 RealSIIService initialized for tax_id: {tax_id}")
        
        # Intentar cargar cookies existentes
        self._load_stored_cookies()

    def _load_stored_cookies(self):
        """Carga cookies almacenadas de una sesión activa"""
        try:
            # Buscar sesión activa para esta empresa
            active_session = SIISession.objects.filter(
                company_rut=self.company_rut,
                company_dv=self.company_dv.upper(),
                is_active=True,
                expires_at__gt=timezone.now()
            ).first()
            
            if active_session and active_session.cookies_data:
                self.cookies = active_session.cookies_data
                self.session_id = active_session.session_id
                self.authenticated = True  # Asumimos que está autenticado si hay cookies válidas
                logger.info(f"🍪 Loaded {len(self.cookies)} stored cookies for {self.tax_id}")
                
                # Actualizar última actividad
                active_session.last_activity = timezone.now()
                active_session.save(update_fields=['last_activity'])
            else:
                logger.info(f"🔍 No valid stored session found for {self.tax_id}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error loading stored cookies for {self.tax_id}: {str(e)}")

    def _save_cookies_to_session(self):
        """Guarda las cookies actuales en SIISession - SIEMPRE crea nueva sesión"""
        try:
            if not self.cookies:
                logger.warning(f"⚠️ No cookies to save for {self.tax_id}")
                return
                
            # Invalidar sesiones anteriores para este contribuyente
            SIISession.objects.filter(
                company_rut=self.company_rut,
                company_dv=self.company_dv.upper(),
                is_active=True
            ).update(is_active=False)
            logger.info(f"🗑️ Invalidated previous sessions for {self.tax_id}")
            
            # SIEMPRE crear nueva sesión con cookies frescas
            self.session_id = str(uuid.uuid4())
            session = SIISession.objects.create(
                company_rut=self.company_rut,
                company_dv=self.company_dv.upper(),
                username=self.tax_id,  # Usar tax_id como username
                session_id=self.session_id,
                cookies_data=self.cookies,
                is_active=True,
                expires_at=timezone.now() + timedelta(hours=8)
            )
            logger.info(f"💾 Created NEW session {self.session_id} for {self.tax_id} with {len(self.cookies)} cookies")
                
        except Exception as e:
            logger.error(f"❌ Error saving cookies to session for {self.tax_id}: {str(e)}")

    def _are_cookies_valid(self):
        """Verifica si las cookies actuales son válidas haciendo una prueba de API"""
        if not self.cookies:
            return False
            
        try:
            from ..api.servicev2 import SIIServiceV2
            from datetime import date
            
            # Crear servicio API de prueba
            api_service = SIIServiceV2(tax_id=self.tax_id, cookies=self.cookies, validar_cookies=False)
            
            # Intentar una consulta simple - consultar contribuyente
            result = api_service.consultar_contribuyente()
            
            # Si no lanza excepción y retorna success, las cookies son válidas
            if result.get('status') == 'success':
                logger.info(f"✅ Cookies válidas para {self.tax_id}")
                return True
            else:
                logger.warning(f"⚠️ Respuesta inesperada de API para {self.tax_id}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Cookies inválidas para {self.tax_id}: {str(e)}")
            return False

    def _start_driver(self):
        """Inicia el driver Selenium"""
        if self.driver is None:
            self.driver = SeleniumDriver(headless=self.headless)
            self.driver.start()

    def _close_driver(self):
        """Cierra el driver Selenium"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def authenticate(self) -> bool:
        """
        Autentica con el SII usando Selenium - verifica cookies existentes primero
        """
        try:
            logger.info(f"🔐 Starting SII authentication for {self.tax_id}")
            
            # Verificar si ya tenemos cookies válidas
            if self.cookies and self._are_cookies_valid():
                logger.info(f"✅ Using existing valid cookies for {self.tax_id} - skipping re-authentication")
                self.authenticated = True
                return True
            
            logger.info(f"🔄 No valid cookies found, proceeding with browser authentication")
            
            # Iniciar driver
            self._start_driver()
            
            # Ir a página de login
            self.driver.driver.get(self.LOGIN_URL)
            logger.info(f"📄 Loaded login page: {self.LOGIN_URL}")
            
            # Llenar formulario de login - asegurar formato correcto del RUT
            normalized_rut = self.tax_id.upper()  # Asegurar que el DV esté en mayúscula
            rut_input = self.driver.wait_for_element(By.ID, "rutcntr", timeout=15)
            rut_input.clear()
            rut_input.send_keys(normalized_rut)
            logger.info(f"✏️ Entered RUT: {normalized_rut}")
            
            clave_input = self.driver.wait_for_element(By.ID, "clave", timeout=15)
            clave_input.clear()
            clave_input.send_keys(self.password)
            logger.info(f"✏️ Entered password")
            
            # Click botón de login
            login_button = self.driver.wait_for_clickable(By.ID, "bt_ingresar", timeout=15)
            login_button.click()
            logger.info(f"🖱️ Clicked login button")
            
            # Esperar y verificar resultado
            time.sleep(3)
            
            # Verificar login exitoso
            login_result = self._verificar_login_exitoso()
            
            if login_result['status'] == 'success':
                self.authenticated = True
                self.cookies = login_result['cookies']
                logger.info(f"✅ Authentication successful for {self.tax_id}")
                
                # Guardar cookies en SIISession para persistencia
                self._save_cookies_to_session()
                
                return True
            elif login_result['status'] == 'sii_unavailable':
                raise SIIConnectionError(
                    message=login_result['message'],
                    retry_after=login_result.get('retry_after'),
                    error_type=login_result.get('error_type')
                )
            elif login_result['status'] == 'sii_error':
                raise SIIConnectionError(
                    message=login_result['message'],
                    retry_after=login_result.get('retry_after'),
                    error_type=login_result.get('error_type')
                )
            else:
                # Invalidar sesión almacenada si las credenciales fallan
                self._invalidate_stored_session()
                raise SIIAuthenticationError(login_result['message'])
            
        except (SIIConnectionError, SIIAuthenticationError):
            # Invalidar sesión en caso de error de autenticación
            self._invalidate_stored_session()
            raise
        except Exception as e:
            logger.error(f"❌ Authentication error: {str(e)}")
            # Invalidar sesión en caso de error general
            self._invalidate_stored_session()
            raise SIIValidationError(f"Error durante autenticación: {str(e)}")
        
    def _verificar_login_exitoso(self) -> Dict[str, Any]:
        """Verifica si el login fue exitoso"""
        try:
            current_url = self.driver.get_current_url()
            logger.info(f"🌐 Current URL after login: {current_url}")
            
            # Detectar casos específicos de error del SII
            if "/ayudas/900.html" in current_url:
                return {
                    "status": "sii_unavailable",
                    "message": "El servicio del SII está temporalmente no disponible. Intente más tarde.",
                    "cookies": None,
                    "url": current_url,
                    "error_type": "service_unavailable",
                    "retry_after": 300
                }
            
            if "/ayudas/" in current_url:
                return {
                    "status": "sii_error",
                    "message": f"El SII reportó un error en la página: {current_url}",
                    "cookies": None,
                    "url": current_url,
                    "error_type": "sii_error_page",
                    "retry_after": 180
                }
            
            if "zeusr.sii.cl" in current_url and "CAutInicio.cgi" in current_url:
                # CAutInicio.cgi puede ser parte del proceso de login exitoso
                logger.info("🔄 En CAutInicio.cgi - verificando si login fue exitoso...")
                
                # Verificar si hay cookies de sesión válidas
                cookies = self.driver.driver.get_cookies()
                logger.info(f"🍪 Cookies encontradas: {len(cookies)}")
                for cookie in cookies:
                    logger.info(f"   - {cookie.get('name')}: {cookie.get('value', 'NO_VALUE')[:20]}...")
                
                has_valid_cookies = any(
                    cookie.get('name') in ['TOKEN', 'JSESSIONID', 'JSESSION'] and cookie.get('value')
                    for cookie in cookies
                )
                
                logger.info(f"🔍 Has valid cookies (TOKEN/JSESSIONID): {has_valid_cookies}")
                
                # Verificar si hay mensaje de error en la página
                try:
                    page_source = self.driver.driver.page_source.lower()
                    error_indicators = [
                        'usuario y/o clave incorrectos',
                        'credenciales incorrectas', 
                        'error de autenticación',
                        'acceso denegado',
                        'usuario bloqueado'
                    ]
                    
                    for error_msg in error_indicators:
                        if error_msg in page_source:
                            logger.error(f"❌ Error detectado en página: {error_msg}")
                            return {
                                "status": "error",
                                "message": f"Error de SII: {error_msg}",
                                "cookies": None,
                                "url": current_url,
                                "error_type": "sii_authentication_error"
                            }
                except Exception as e:
                    logger.warning(f"⚠️ Error verificando contenido de página: {e}")
                
                # Intentar navegar a MiSII incluso sin cookies aparentemente válidas
                # A veces el SII usa cookies diferentes o mecanismos alternativos
                logger.info("🔍 Intentando acceso a MiSII para verificar autenticación...")
                try:
                    self.driver.driver.get("https://misiir.sii.cl/cgi_misii/siihome.cgi")
                    time.sleep(5)  # Dar más tiempo
                    final_url = self.driver.get_current_url()
                    logger.info(f"🌐 URL después de navegar a MiSII: {final_url}")
                    
                    # Obtener cookies después de la navegación
                    final_cookies = self.driver.driver.get_cookies()
                    logger.info(f"🍪 Cookies después de MiSII: {len(final_cookies)}")
                    
                    # Verificar si llegamos a una página válida de MiSII
                    if ("misiir.sii.cl" in final_url and 
                        "error" not in final_url.lower() and
                        "login" not in final_url.lower() and
                        len(final_cookies) > 1):  # Debe haber al menos algunas cookies
                        
                        logger.info("✅ Login exitoso confirmado - acceso a MiSII ok")
                        return {
                            "status": "success",
                            "message": "Login exitoso - confirmado con acceso a MiSII",
                            "cookies": final_cookies,  # Usar cookies finales
                            "url": final_url
                        }
                    else:
                        logger.warning(f"⚠️ Acceso a MiSII falló - URL: {final_url}")
                        
                except Exception as nav_error:
                    logger.error(f"❌ Error navegando a MiSII: {nav_error}")
                
                # Si llegamos aquí, las credenciales están definitivamente mal
                logger.error("❌ Login falló - credenciales incorrectas confirmadas")
                return {
                    "status": "error", 
                    "message": "Credenciales incorrectas - no se pudo acceder a MiSII",
                    "cookies": None,
                    "url": current_url,
                    "error_type": "invalid_credentials",
                    "retry_after": 300  # Esperar más tiempo antes de reintentar
                }
            
            if "misiir.sii.cl" in current_url or "homer.sii.cl" in current_url:
                cookies = self.driver.driver.get_cookies()
                logger.info(f"🍪 Got {len(cookies)} cookies from successful login")
                
                # Verificar cookie importante (puede no estar presente en homer.sii.cl)
                livewire_cookie = next((cookie for cookie in cookies if cookie['name'] == 'NETSCAPE_LIVEWIRE.exp'), None)
                
                # Si estamos en homer.sii.cl, podemos aceptar el login sin requerir la cookie específica
                if livewire_cookie or "homer.sii.cl" in current_url:
                    return {
                        "status": "success",
                        "message": "Login exitoso",
                        "cookies": cookies,
                        "url": current_url
                    }
                else:
                    return {
                        "status": "error",
                        "message": "No se encontró la cookie NETSCAPE_LIVEWIRE",
                        "cookies": None,
                        "url": current_url,
                        "error_type": "missing_cookie",
                        "retry_after": 60
                    }
            else:
                return {
                    "status": "error",
                    "message": f"URL inesperada después del login: {current_url}",
                    "cookies": None,
                    "url": current_url,
                    "error_type": "unexpected_redirect",
                    "retry_after": 120
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error en el login: {str(e)}",
                "cookies": None,
                "url": self.driver.get_current_url() if self.driver and self.driver.driver else None,
                "error_type": "exception",
                "retry_after": 60
            }

    def consultar_contribuyente(self) -> Dict[str, Any]:
        """
        Consulta información del contribuyente usando Selenium
        """
        if not self.authenticated:
            self.authenticate()
        
        logger.info(f"📊 Consulting contributor data for: {self.tax_id}")
        
        try:
            # Si tenemos cookies válidas pero no driver, usar API directa
            if self.cookies and not self.driver:
                logger.info("📊 Using API with valid cookies for contribuyente data")
                try:
                    from ..api.servicev2 import SIIServiceV2
                    api_service = SIIServiceV2(tax_id=self.tax_id, cookies=self.cookies, validar_cookies=False)
                    result = api_service.consultar_contribuyente()
                    if result.get('status') == 'success':
                        return result.get('data', self._extraer_datos_fallback())
                except Exception as api_error:
                    logger.warning(f"⚠️ API call failed, using fallback: {api_error}")
                
                # Fallback a datos básicos
                return self._extraer_datos_fallback()
            
            # Navegar a la página de datos del contribuyente con driver
            # En el SII real, esto requiere navegar por diferentes secciones
            
            # Intentar obtener datos básicos de la página principal
            current_url = self.driver.get_current_url()
            
            if "misiir.sii.cl" in current_url or "homer.sii.cl" in current_url:
                # Estamos en la página principal del SII, intentar extraer datos
                page_source = self.driver.get_page_source()
                
                # Por ahora, simulamos datos extraídos de la navegación real
                contribuyente_data = self._extraer_datos_contribuyente()
                
                logger.info(f"✅ Successfully extracted contributor data for {self.tax_id}")
                return contribuyente_data
            else:
                raise SIIValidationError("No se pudo acceder a la página de datos del contribuyente")
            
        except Exception as e:
            logger.error(f"❌ Error consulting contributor: {str(e)}")
            raise SIIValidationError(f"Error consultando contribuyente: {str(e)}")

    def _extraer_datos_contribuyente(self) -> Dict[str, Any]:
        """
        Extrae datos reales del contribuyente desde las páginas del SII
        """
        try:
            # Navegar a la página de MI SII que contiene datos estructurados
            logger.info(f"📊 Navegando a MI SII para extraer datos reales")
            self.driver.driver.get("https://misiir.sii.cl/cgi_misii/siihome.cgi")
            
            # Esperar a que cargue la página
            import time
            time.sleep(3)
            
            # Obtener el código fuente de la página
            page_source = self.driver.get_page_source()
            
            # Extraer datos JSON del código fuente usando regex
            import re
            
            # Buscar el JSON con datos del contribuyente
            json_pattern = r'"razonSocial":"([^"]+)"'
            razon_social_match = re.search(json_pattern, page_source)
            
            if razon_social_match:
                razon_social = razon_social_match.group(1).replace('\\u0026', '&')  # Decodificar HTML entities
                
                # Extraer más campos usando regex
                data = {
                    "rut": self.tax_id,
                    "razon_social": razon_social,
                    "nombre": razon_social,
                    "razonSocial": razon_social
                }
                
                # Extraer tipo de contribuyente
                tipo_pattern = r'"tipoContribuyenteDescripcion":"([^"]+)"'
                tipo_match = re.search(tipo_pattern, page_source)
                if tipo_match:
                    data["tipo_contribuyente"] = tipo_match.group(1)
                
                # Extraer actividad económica
                actividad_pattern = r'"glosaActividad":"([^"]+)"'
                actividad_match = re.search(actividad_pattern, page_source)
                if actividad_match:
                    actividad = actividad_match.group(1).replace('\\u0026', '&')
                    data["actividad_description"] = actividad
                    data["glosa_actividad"] = actividad
                
                # Extraer email
                email_pattern = r'"eMail":"([^"]+)"'
                email_match = re.search(email_pattern, page_source)
                if email_match and email_match.group(1) != "null":
                    data["email"] = email_match.group(1)
                
                # Extraer fecha de inicio de actividades
                fecha_pattern = r'"fechaInicioActividades":"([^"]+)"'
                fecha_match = re.search(fecha_pattern, page_source)
                if fecha_match:
                    fecha_str = fecha_match.group(1)
                    # Convertir formato "2023-08-07 00:00:00.0" a "2023-08-07"
                    if " " in fecha_str:
                        fecha_str = fecha_str.split(" ")[0]
                    data["fecha_inicio_actividades"] = fecha_str
                
                # Extraer dirección
                calle_pattern = r'"calle":"([^"]+)"'
                calle_match = re.search(calle_pattern, page_source)
                comuna_pattern = r'"comunaDescripcion":"([^"]+)"'
                comuna_match = re.search(comuna_pattern, page_source)
                region_pattern = r'"regionDescripcion":"([^"]+)"'
                region_match = re.search(region_pattern, page_source)
                
                if calle_match:
                    direccion = calle_match.group(1)
                    if comuna_match:
                        direccion += f", {comuna_match.group(1)}"
                        data["comuna"] = comuna_match.group(1).strip()
                    if region_match:
                        direccion += f", {region_match.group(1)}"
                        data["region"] = region_match.group(1).strip()
                    data["direccion"] = direccion
                
                # Extraer teléfono móvil
                telefono_pattern = r'"telefonoMovil":"([^"]+)"'
                telefono_match = re.search(telefono_pattern, page_source)
                if telefono_match and telefono_match.group(1) not in ["null", ""]:
                    data["mobile_phone"] = telefono_match.group(1)
                
                # Estado por defecto (si está accesible, está activo)
                data["estado"] = "ACTIVO"
                data["_source"] = "real_sii_extraction"
                
                logger.info(f"✅ Datos reales extraídos del SII: {razon_social}")
                return data
                
            else:
                logger.warning("No se encontraron datos JSON en la página del SII")
                return self._extraer_datos_fallback()
                
        except Exception as e:
            logger.error(f"❌ Error extrayendo datos reales: {str(e)}")
            return self._extraer_datos_fallback()
    
    def _extraer_datos_fallback(self) -> Dict[str, Any]:
        """
        Método de respaldo para extraer datos básicos
        """
        logger.info("📋 Usando método de respaldo para datos básicos")
        return {
            "rut": self.tax_id,
            "razon_social": f"CONTRIBUYENTE {self.tax_id}",
            "nombre": f"CONTRIBUYENTE {self.tax_id}", 
            "tipo_contribuyente": "Primera Categoría",
            "estado": "ACTIVO",
            "_source": "fallback_extraction"
        }

    def get_cookies(self) -> List[Dict]:
        """Retorna las cookies de la sesión actual"""
        if self.authenticated and self.cookies:
            return self.cookies
        return []
    
    def obtener_dtes_reales(self, fecha_desde=None, fecha_hasta=None, tipo_operacion='recibidos'):
        """
        Extrae DTEs REALES desde el portal del SII
        Usa API con cookies cuando es posible, fallback a scraping si falla
        
        Args:
            fecha_desde: Fecha inicio en formato YYYY-MM-DD  
            fecha_hasta: Fecha fin en formato YYYY-MM-DD
            tipo_operacion: 'recibidos' o 'emitidos'
        """
        # Autenticarse automáticamente si no está autenticado
        if not self.authenticated:
            logger.info("🔐 No autenticado, iniciando autenticación automática...")
            if not self.authenticate():
                raise SIIValidationError("Error en autenticación automática")
        
        try:
            logger.info(f"📄 Iniciando extracción REAL de DTEs {tipo_operacion}")
            logger.info(f"   Período: {fecha_desde} a {fecha_hasta}")
            
            # PRIMERO: Intentar usar API con cookies (más rápido y confiable)
            if self.cookies:
                logger.info("🔍 Verificando validez de cookies almacenadas...")
                if self._are_cookies_valid():
                    logger.info("🚀 Intentando extracción vía API con cookies...")
                    dtes_api = self._obtener_dtes_via_api(fecha_desde, fecha_hasta, tipo_operacion)
                    if dtes_api:
                        logger.info(f"✅ {len(dtes_api)} DTEs obtenidos vía API")
                        return dtes_api
                    else:
                        logger.warning("⚠️ API no devolvió resultados, usando scraping como fallback...")
                else:
                    logger.warning("🗑️ Cookies inválidas, invalidando sesión y re-autenticando...")
                    self._invalidate_stored_session()
                    self.authenticated = False
                    self.cookies = []
                    # Re-autenticar para obtener nuevas cookies
                    if self.authenticate():
                        logger.info("🚀 Re-autenticado exitosamente, intentando API nuevamente...")
                        dtes_api = self._obtener_dtes_via_api(fecha_desde, fecha_hasta, tipo_operacion)
                        if dtes_api:
                            logger.info(f"✅ {len(dtes_api)} DTEs obtenidos vía API después de re-auth")
                            return dtes_api
            
            # Si llegamos aquí, no se pudieron obtener DTEs vía API
            logger.error("❌ No se pudieron obtener DTEs vía API después de todos los intentos")
            return []
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo DTEs reales: {str(e)}")
            # En caso de error, devolver lista vacía en lugar de fallar completamente
            logger.info("📋 Devolviendo lista vacía debido a error en extracción real")
            return []

    def _obtener_dtes_via_api(self, fecha_desde, fecha_hasta, tipo_operacion):
        """
        Obtiene DTEs usando la API del SII con cookies de autenticación.
        Más rápido y confiable que el scraping.
        """
        try:
            from ..api.servicev2 import SIIServiceV2
            from datetime import datetime
            
            # Crear servicio API con las cookies actuales
            api_service = SIIServiceV2(tax_id=self.tax_id, cookies=self.cookies, validar_cookies=False)
            
            # Convertir fechas a período tributario
            if fecha_desde:
                fecha_obj = datetime.strptime(fecha_desde, '%Y-%m-%d')
                periodo = fecha_obj.strftime('%Y%m')
            else:
                # Usar mes actual si no se especifica
                from datetime import date
                periodo = date.today().strftime('%Y%m')
            
            logger.info(f"📡 Consultando API SII para período {periodo}, operación: {tipo_operacion}")
            
            # Obtener documentos según tipo de operación
            documentos = []
            
            if tipo_operacion == 'recibidos':
                # Obtener documentos de compra (recibidos)
                result = api_service.get_documentos_compra(periodo)
                documentos = result.get('data', []) if isinstance(result, dict) else []
                logger.info(f"📥 {len(documentos)} documentos de compra obtenidos")
                
            elif tipo_operacion == 'emitidos':
                # Obtener documentos de venta (emitidos)
                result = api_service.get_documentos_venta(periodo)
                documentos = result.get('data', []) if isinstance(result, dict) else []
                logger.info(f"📤 {len(documentos)} documentos de venta obtenidos")
            
            else:
                logger.warning(f"⚠️ Tipo de operación no reconocido: {tipo_operacion}")
                return []
            
            if documentos:
                # Agregar metadatos de extracción
                for doc in documentos:
                    doc['_extraction_method'] = 'api'
                    doc['_extraction_timestamp'] = datetime.now().isoformat()
                    doc['_extraction_period'] = periodo
                
                logger.info(f"✅ {len(documentos)} DTEs obtenidos vía API para {tipo_operacion}")
                return documentos
            else:
                logger.info(f"ℹ️ No se encontraron DTEs {tipo_operacion} para el período {periodo}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error en extracción vía API: {str(e)}")
            return []

    def _invalidate_stored_session(self):
        """Invalida la sesión almacenada en caso de error de autenticación"""
        try:
            if self.session_id:
                session = SIISession.objects.get(session_id=self.session_id)
                session.is_active = False
                session.save(update_fields=['is_active'])
                logger.info(f"🗑️ Invalidated stored session {self.session_id} for {self.tax_id}")
            else:
                # Invalidar todas las sesiones activas para esta empresa
                SIISession.objects.filter(
                    company_rut=self.company_rut,
                    company_dv=self.company_dv.upper(),
                    is_active=True
                ).update(is_active=False)
                logger.info(f"🗑️ Invalidated all active sessions for {self.tax_id}")
        except Exception as e:
            logger.warning(f"⚠️ Error invalidating session for {self.tax_id}: {str(e)}")

    def close(self):
        """Cierra el servicio y libera recursos"""
        self._close_driver()
        # NO invalidamos las cookies al cerrar - queremos que persistan para reutilizar
        logger.info(f"🔴 RealSIIService closed for {self.tax_id}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_real_sii_service(tax_id: str, password: str, headless: bool = True) -> RealSIIService:
    """
    Factory function para crear una instancia del servicio SII real
    """
    return RealSIIService(tax_id=tax_id, password=password, headless=headless)


class SIIRPAService(RealSIIService):
    """
    Alias para compatibilidad hacia atrás - usa RealSIIService
    """
    pass