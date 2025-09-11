"""
Integración del SIIServiceV2 (API) con el sistema RPA para obtención optimizada de DTEs
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date

from ..api.servicev2 import SIIServiceV2
from .sii_rpa_service import RealSIIService
from ..utils.exceptions import (
    SIIConnectionError, 
    SIIAuthenticationError,
    SIIValidationError
)

logger = logging.getLogger(__name__)


class SIIIntegratedService:
    """
    Servicio integrado que combina API (rápida) y RPA (robusta) para obtener DTEs de forma optimizada.
    
    Estrategia mejorada:
    1. Verifica si las cookies almacenadas son válidas
    2. Si son válidas, usa solo API (más rápido y eficiente)
    3. Si las cookies son inválidas, usa RPA para obtener cookies frescas
    4. Reintenta con API usando las nuevas cookies
    5. Como último recurso, extrae vía RPA completo
    
    Importante: Solo usa RPA si las cookies están expiradas. Si las cookies son válidas
    pero la API falla, no intenta con RPA automáticamente.
    """
    
    def __init__(self, tax_id: str, password: str, headless: bool = True):
        self.tax_id = tax_id
        self.password = password
        self.headless = headless
        
        # Servicios persistentes
        self.api_service = None
        self.rpa_service = None
        self._session_initialized = False
        
        logger.info(f"🔧 SIIIntegratedService initialized for {tax_id}")
    
    def _initialize_session(self):
        """Inicializa la sesión API una sola vez"""
        if not self._session_initialized:
            logger.info("🔐 Inicializando sesión API por primera vez")
            self.api_service = self._get_api_service(force_new_cookies=False)
            self._session_initialized = True
    
    def _get_api_service(self, force_new_cookies: bool = False, fresh_cookies: List[Dict] = None) -> SIIServiceV2:
        """Obtiene o crea el servicio API reutilizando la instancia"""
        # Si ya tenemos una instancia y no necesitamos cookies nuevas, reutilizarla
        if self.api_service and not force_new_cookies and fresh_cookies is None:
            return self.api_service
        
        # Si necesitamos cookies frescas o es la primera vez, crear nueva instancia
        if force_new_cookies or not self.api_service or fresh_cookies is not None:
            if fresh_cookies:
                logger.info(f"🔄 Creando nueva instancia API con {len(fresh_cookies)} cookies frescas del RPA")
                # Usar cookies frescas directamente y guardarlas
                self.api_service = SIIServiceV2(
                    tax_id=self.tax_id,
                    cookies=fresh_cookies,
                    password=self.password,
                    validar_cookies=False,  # Ya validadas por RPA
                    auto_relogin=True,
                    save_fresh_cookies=True  # Guardar estas cookies frescas
                )
            else:
                logger.info("🔄 Creando nueva instancia API con validación de cookies almacenadas")
                self.api_service = SIIServiceV2.crear_con_password(
                    tax_id=self.tax_id,
                    password=self.password,
                    validar_cookies=True,
                    auto_relogin=True
                )
            self._session_initialized = True
        
        return self.api_service
    
    def _get_rpa_service(self) -> RealSIIService:
        """Obtiene o crea el servicio RPA"""
        if not self.rpa_service:
            self.rpa_service = RealSIIService(
                tax_id=self.tax_id,
                password=self.password,
                headless=self.headless
            )
        return self.rpa_service
    
    def get_resumen_compras_ventas(
        self,
        periodo_tributario: str
    ) -> Dict[str, Any]:
        """
        Obtiene el resumen de compras y ventas para identificar tipos de documentos disponibles.
        
        Args:
            periodo_tributario: Período en formato YYYYMM
            
        Returns:
            Dict con resumen de compras y ventas por tipo de documento
        """
        logger.info(f"📊 Obteniendo resumen compras/ventas período {periodo_tributario}")
        
        # Inicializar sesión si no está lista
        self._initialize_session()
        
        try:
            # Intentar con API primero
            result = self.api_service.get_resumen_compras_ventas(periodo_tributario)
            
            if result.get('status') == 'success':
                logger.info(f"✅ Resumen obtenido exitosamente vía API")
                return result
            else:
                logger.warning(f"⚠️ No se pudo obtener resumen: {result.get('message')}")
                return result
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo resumen: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'periodo_tributario': periodo_tributario
            }
    
    def get_documentos_compra(
        self, 
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        usar_solo_api: bool = False
    ) -> Dict[str, Any]:
        """
        Obtiene documentos de compra con estrategia híbrida API/RPA.
        
        Args:
            periodo_tributario: Período en formato YYYYMM
            cod_tipo_doc: Código del tipo de documento
            usar_solo_api: Si True, solo usa API (más rápido para tests)
        """
        self._initialize_session()
        return self._obtener_documentos(
            operacion="COMPRA",
            periodo_tributario=periodo_tributario,
            cod_tipo_doc=cod_tipo_doc,
            usar_solo_api=usar_solo_api
        )
    
    def get_documentos_venta(
        self, 
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        usar_solo_api: bool = False
    ) -> Dict[str, Any]:
        """
        Obtiene documentos de venta con estrategia híbrida API/RPA.
        
        Args:
            periodo_tributario: Período en formato YYYYMM
            cod_tipo_doc: Código del tipo de documento
            usar_solo_api: Si True, solo usa API (más rápido para tests)
        """
        self._initialize_session()
        return self._obtener_documentos(
            operacion="VENTA",
            periodo_tributario=periodo_tributario,
            cod_tipo_doc=cod_tipo_doc,
            usar_solo_api=usar_solo_api
        )
    
    def _obtener_documentos(
        self,
        operacion: str,
        periodo_tributario: str,
        cod_tipo_doc: str = "33",
        usar_solo_api: bool = False
    ) -> Dict[str, Any]:
        """
        Método interno para obtener documentos con estrategia híbrida mejorada.
        Solo usa RPA si las cookies almacenadas están expiradas.
        """
        logger.info(f"📄 Obteniendo documentos {operacion} período {periodo_tributario}")
        
        # PASO 1: Verificar si tenemos cookies válidas almacenadas
        api_service = self._get_api_service(force_new_cookies=False)
        cookies_validas = False
        
        try:
            logger.info("🔍 Verificando validez de cookies almacenadas")
            validacion = api_service.validar_cookies()
            cookies_validas = validacion.get('valid', False)
            
            if cookies_validas:
                logger.info("✅ Cookies válidas encontradas")
            else:
                logger.info(f"⚠️ Cookies inválidas: {validacion.get('message', 'Sin mensaje')}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error validando cookies: {str(e)}")
            cookies_validas = False
        
        # PASO 2: Si las cookies son válidas, intentar solo con API
        if cookies_validas:
            try:
                logger.info("🚀 Cookies válidas - Extrayendo con API")
                
                if operacion == "COMPRA":
                    result = api_service.get_documentos_compra(periodo_tributario, cod_tipo_doc)
                else:
                    result = api_service.get_documentos_venta(periodo_tributario, cod_tipo_doc)
                
                # Verificar si hay datos válidos
                if self._is_valid_result(result):
                    logger.info(f"✅ API exitosa con cookies válidas: {len(result.get('data', []))} documentos")
                    return self._enrich_result(result, "api_valid_cookies")
                else:
                    logger.warning("⚠️ API con cookies válidas no devolvió datos - posiblemente sin documentos en período")
                    # Si las cookies son válidas pero no hay datos, es resultado válido (período sin documentos)
                    return {
                        'status': 'success',
                        'data': [],
                        'extraction_method': 'api_valid_cookies_no_data',
                        'periodo_tributario': periodo_tributario,
                        'message': 'Sin documentos en el período',
                        'timestamp': datetime.now().isoformat()
                    }
                    
            except Exception as e:
                logger.error(f"❌ Error con API usando cookies válidas: {str(e)}")
                # Si las cookies son válidas pero la API falla, NO intentar con RPA
                # Esto evita el comportamiento no deseado
                return {
                    'status': 'error',
                    'message': f'API falló con cookies válidas: {str(e)}',
                    'data': [],
                    'extraction_method': 'api_valid_cookies_failed',
                    'periodo_tributario': periodo_tributario,
                    'timestamp': datetime.now().isoformat()
                }
        
        # PASO 3: Solo si las cookies no son válidas, usar RPA
        if usar_solo_api:
            logger.info("🔒 Modo solo API habilitado y cookies inválidas")
            return {
                'status': 'error',
                'message': 'Cookies inválidas y modo solo API habilitado',
                'data': [],
                'extraction_method': 'api_only_invalid_cookies'
            }
        
        logger.info("🤖 Cookies inválidas - Renovando con RPA")
        
        # ESTRATEGIA RPA 1: Renovar cookies vía RPA + API
        try:
            logger.info("🔄 Renovando cookies con RPA y reintentando API")
            rpa_service = self._get_rpa_service()
            
            # Autenticar con RPA para obtener cookies frescas
            if rpa_service.authenticate():
                fresh_cookies = rpa_service.get_cookies()
                logger.info(f"🍪 Obtenidas {len(fresh_cookies)} cookies frescas")
                
                # Crear servicio API con cookies frescas directamente
                api_service_fresh = self._get_api_service(force_new_cookies=True, fresh_cookies=fresh_cookies)
                
                if operacion == "COMPRA":
                    result = api_service_fresh.get_documentos_compra(periodo_tributario, cod_tipo_doc)
                else:
                    result = api_service_fresh.get_documentos_venta(periodo_tributario, cod_tipo_doc)
                
                if self._is_valid_result(result):
                    logger.info(f"✅ RPA + API exitoso: {len(result.get('data', []))} documentos")
                    return self._enrich_result(result, "rpa_cookies_api")
                else:
                    logger.warning("⚠️ RPA + API no devolvió datos válidos")
                    
            else:
                logger.error("❌ Autenticación RPA falló")
                
        except Exception as e:
            logger.error(f"❌ RPA + API falló: {str(e)}")
        
        # ESTRATEGIA RPA 2: RPA completo como último recurso
        try:
            logger.info("🔧 RPA completo como último recurso")
            rpa_service = self._get_rpa_service()
            
            # Determinar fecha_desde y fecha_hasta desde el período
            fecha_desde, fecha_hasta = self._periodo_to_fechas(periodo_tributario)
            tipo_operacion = "recibidos" if operacion == "COMPRA" else "emitidos"
            
            dtes = rpa_service.obtener_dtes_reales(
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                tipo_operacion=tipo_operacion
            )
            
            if dtes:
                logger.info(f"✅ RPA completo exitoso: {len(dtes)} documentos")
                return {
                    'status': 'success',
                    'data': dtes,
                    'extraction_method': 'rpa_complete',
                    'periodo_tributario': periodo_tributario,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning("⚠️ RPA completo no devolvió datos")
                
        except Exception as e:
            logger.error(f"❌ RPA completo falló: {str(e)}")
        
        # Si llegamos aquí, todos los métodos fallaron
        logger.error("❌ Todos los métodos de extracción fallaron")
        return {
            'status': 'error',
            'message': 'Todos los métodos de extracción fallaron',
            'data': [],
            'extraction_method': 'all_failed',
            'periodo_tributario': periodo_tributario,
            'timestamp': datetime.now().isoformat()
        }
    
    def _is_valid_result(self, result: Dict[str, Any]) -> bool:
        """Verifica si el resultado de la API es válido"""
        if not isinstance(result, dict):
            return False
        
        data = result.get('data', [])
        return isinstance(data, list) and len(data) > 0
    
    def _enrich_result(self, result: Dict[str, Any], method: str) -> Dict[str, Any]:
        """Enriquece el resultado con metadatos de extracción"""
        enriched = result.copy()
        enriched['extraction_method'] = method
        enriched['timestamp'] = datetime.now().isoformat()
        enriched['status'] = 'success'
        
        # Agregar metadatos a cada documento
        data = enriched.get('data', [])
        for doc in data:
            if isinstance(doc, dict):
                doc['_extraction_method'] = method
                doc['_extraction_timestamp'] = enriched['timestamp']
        
        return enriched
    
    def _periodo_to_fechas(self, periodo_tributario: str) -> Tuple[str, str]:
        """Convierte período YYYYMM a fechas de inicio y fin del mes"""
        try:
            año = int(periodo_tributario[:4])
            mes = int(periodo_tributario[4:6])
            
            fecha_desde = date(año, mes, 1)
            
            # Último día del mes
            if mes == 12:
                fecha_hasta = date(año + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                fecha_hasta = date(año, mes + 1, 1) - datetime.timedelta(days=1)
            
            return fecha_desde.strftime('%Y-%m-%d'), fecha_hasta.strftime('%Y-%m-%d')
            
        except (ValueError, IndexError):
            # Fallback: usar fechas del mes actual
            today = date.today()
            primer_dia = today.replace(day=1)
            if today.month == 12:
                ultimo_dia = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
            else:
                ultimo_dia = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
            
            return primer_dia.strftime('%Y-%m-%d'), ultimo_dia.strftime('%Y-%m-%d')
    
    def get_documentos_periodo_completo(
        self,
        periodo_tributario: str,
        tipos_documento: List[str] = None,
        incluir_compras: bool = True,
        incluir_ventas: bool = True,
        usar_solo_api: bool = False
    ) -> Dict[str, Any]:
        """
        Obtiene todos los documentos de un período completo.
        
        Args:
            periodo_tributario: Período en formato YYYYMM
            tipos_documento: Lista de códigos de documento (ej: ["33", "34", "61"])
            incluir_compras: Si incluir documentos de compra
            incluir_ventas: Si incluir documentos de venta
            usar_solo_api: Si usar solo API (más rápido para tests)
        """
        if not tipos_documento:
            tipos_documento = ["33", "34", "61", "56"]  # Facturas, NC, ND más comunes
        
        logger.info(f"📊 Obteniendo período completo {periodo_tributario}")
        logger.info(f"   Tipos: {tipos_documento}")
        logger.info(f"   Compras: {incluir_compras}, Ventas: {incluir_ventas}")
        
        todos_documentos = []
        errores = []
        
        for tipo_doc in tipos_documento:
            logger.info(f"📄 Procesando tipo documento {tipo_doc}")
            
            if incluir_compras:
                try:
                    docs_compra = self.get_documentos_compra(
                        periodo_tributario, tipo_doc, usar_solo_api
                    )
                    if docs_compra.get('status') == 'success':
                        compras_data = docs_compra.get('data', [])
                        # Marcar como compras
                        for doc in compras_data:
                            doc['_operacion'] = 'COMPRA'
                        todos_documentos.extend(compras_data)
                        logger.info(f"📥 {len(compras_data)} documentos de compra tipo {tipo_doc}")
                    else:
                        errores.append(f"Error compras tipo {tipo_doc}: {docs_compra.get('message')}")
                except Exception as e:
                    error_msg = f"Excepción compras tipo {tipo_doc}: {str(e)}"
                    errores.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            if incluir_ventas:
                try:
                    docs_venta = self.get_documentos_venta(
                        periodo_tributario, tipo_doc, usar_solo_api
                    )
                    if docs_venta.get('status') == 'success':
                        ventas_data = docs_venta.get('data', [])
                        # Marcar como ventas
                        for doc in ventas_data:
                            doc['_operacion'] = 'VENTA'
                        todos_documentos.extend(ventas_data)
                        logger.info(f"📤 {len(ventas_data)} documentos de venta tipo {tipo_doc}")
                    else:
                        errores.append(f"Error ventas tipo {tipo_doc}: {docs_venta.get('message')}")
                except Exception as e:
                    error_msg = f"Excepción ventas tipo {tipo_doc}: {str(e)}"
                    errores.append(error_msg)
                    logger.error(f"❌ {error_msg}")
        
        logger.info(f"📊 Período completo finalizado: {len(todos_documentos)} documentos totales")
        
        return {
            'status': 'success' if todos_documentos else 'partial' if errores else 'error',
            'periodo_tributario': periodo_tributario,
            'tipos_documento': tipos_documento,
            'total_documentos': len(todos_documentos),
            'data': todos_documentos,
            'errores': errores,
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'integrated_complete'
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Prueba la conexión usando la estrategia híbrida"""
        logger.info(f"🔍 Probando conexión para {self.tax_id}")
        
        try:
            # Intentar con API primero
            api_service = self._get_api_service()
            contribuyente = api_service.consultar_contribuyente()
            
            if contribuyente.get('status') == 'success':
                return {
                    'status': 'success',
                    'method': 'api',
                    'message': 'Conexión exitosa vía API',
                    'data': contribuyente,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.warning("⚠️ API falló, probando con RPA...")
                
        except Exception as e:
            logger.warning(f"⚠️ API falló: {str(e)}, probando con RPA...")
        
        try:
            # Probar con RPA
            rpa_service = self._get_rpa_service()
            if rpa_service.authenticate():
                contribuyente_rpa = rpa_service.consultar_contribuyente()
                return {
                    'status': 'success',
                    'method': 'rpa',
                    'message': 'Conexión exitosa vía RPA',
                    'data': contribuyente_rpa,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                raise Exception("Autenticación RPA falló")
                
        except Exception as e:
            return {
                'status': 'error',
                'method': 'both_failed',
                'message': f'Tanto API como RPA fallaron: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def close(self):
        """Cierra todos los servicios y libera recursos"""
        if self.rpa_service:
            self.rpa_service.close()
            self.rpa_service = None
        
        logger.info(f"🔴 SIIIntegratedService closed for {self.tax_id}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_integrated_sii_service(tax_id: str, password: str, headless: bool = True) -> SIIIntegratedService:
    """
    Factory function para crear el servicio integrado SII
    """
    return SIIIntegratedService(tax_id=tax_id, password=password, headless=headless)