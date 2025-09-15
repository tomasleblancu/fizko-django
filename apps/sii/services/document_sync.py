"""
Servicio para sincronización de documentos SII
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from django.db import transaction
from django.utils import timezone

from apps.companies.models import Company
from apps.taxpayers.models import TaxpayerSiiCredentials
from ..rpa.api_integration import SIIIntegratedService
from ..models import SIISyncLog

logger = logging.getLogger(__name__)


class DocumentSyncService:
    """
    Servicio para sincronización de documentos desde el SII.
    Encapsula toda la lógica de negocio para la sincronización.
    """
    
    def __init__(self, company_rut: str, company_dv: str):
        """
        Inicializa el servicio de sincronización.
        
        Args:
            company_rut: RUT de la empresa sin dígito verificador
            company_dv: Dígito verificador de la empresa
        """
        self.company_rut = company_rut
        self.company_dv = company_dv
        self.full_rut = f"{company_rut}-{company_dv}"
        self.company = None
        self.credentials = None
        
        # Inicializar empresa y credenciales
        self._initialize()
    
    def _initialize(self):
        """Inicializa la empresa y credenciales"""
        self.company = self._get_company()
        self.credentials = self._get_credentials()
        
    def _get_company(self) -> Company:
        """
        Obtiene la empresa de la base de datos.
        
        Returns:
            Company: Instancia de la empresa
            
        Raises:
            ValueError: Si la empresa no existe
        """
        try:
            return Company.objects.get(tax_id=self.full_rut)
        except Company.DoesNotExist:
            raise ValueError(f"Empresa con RUT {self.full_rut} no encontrada")
    
    def _get_credentials(self) -> TaxpayerSiiCredentials:
        """
        Obtiene las credenciales SII de la empresa.
        
        Returns:
            TaxpayerSiiCredentials: Credenciales de la empresa
            
        Raises:
            ValueError: Si no existen credenciales
        """
        try:
            return TaxpayerSiiCredentials.objects.get(company=self.company)
        except TaxpayerSiiCredentials.DoesNotExist:
            raise ValueError(f"Credenciales SII no encontradas para empresa {self.full_rut}")
    
    def sync_period(
        self, 
        fecha_desde: str, 
        fecha_hasta: str,
        sync_log: SIISyncLog,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sincroniza documentos para un período específico.
        
        Args:
            fecha_desde: Fecha inicio en formato YYYY-MM-DD
            fecha_hasta: Fecha fin en formato YYYY-MM-DD
            sync_log: Log de sincronización para actualizar
            task_id: ID de la tarea de Celery (opcional)
            
        Returns:
            Dict con los resultados de la sincronización
            
        Raises:
            ValueError: Si las fechas son inválidas
        """
        # Validar fechas
        self._validate_dates(fecha_desde, fecha_hasta)
        
        logger.info(f"🚀 Iniciando sincronización para {self.full_rut}")
        logger.info(f"   Período: {fecha_desde} a {fecha_hasta}")
        
        # Obtener períodos tributarios
        periodos = self._get_periodos_from_dates(fecha_desde, fecha_hasta)
        logger.info(f"📅 Períodos a procesar: {periodos}")
        
        all_dtes = []
        sii_password = self.credentials.get_password()
        
        # Usar servicio integrado SII
        with SIIIntegratedService(
            tax_id=self.full_rut, 
            password=sii_password, 
            headless=True
        ) as sii_service:
            logger.info(f"✅ Servicio SII integrado creado para {self.full_rut}")
            
            # Procesar cada período
            for periodo in periodos:
                logger.info(f"📅 Procesando período {periodo}")
                
                # Extraer documentos del período
                dtes_periodo = self._extract_periodo_documents(
                    sii_service, 
                    periodo, 
                    task_id
                )
                all_dtes.extend(dtes_periodo)
        
        logger.info(f"🎯 Extracción completada: {len(all_dtes)} documentos totales")
        
        # Procesar y almacenar DTEs
        from .dte_processor import DTEProcessor
        processor = DTEProcessor(self.company)
        results = processor.process_batch(all_dtes, sync_log)
        
        logger.info(f"✅ Procesamiento completado: {results['created']} creados, {results['updated']} actualizados")
        
        return results
    
    def sync_full_history(
        self,
        sync_log: SIISyncLog,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sincroniza todo el historial de documentos desde el inicio de actividades.
        
        Args:
            sync_log: Log de sincronización para actualizar
            task_id: ID de la tarea de Celery (opcional)
            
        Returns:
            Dict con los resultados de la sincronización
        """
        # Determinar fecha de inicio
        fecha_inicio = self._get_fecha_inicio_actividades()
        fecha_hasta = date.today()
        
        logger.info(f"🚀 Iniciando sincronización COMPLETA para {self.full_rut}")
        logger.info(f"   Período: {fecha_inicio} a {fecha_hasta}")
        
        # Obtener todos los períodos
        periodos = self._get_periodos_from_dates(
            fecha_inicio.isoformat(),
            fecha_hasta.isoformat()
        )
        
        total_periodos = len(periodos)
        logger.info(f"📅 Períodos a procesar: {total_periodos} ({periodos[0]} - {periodos[-1]})")
        
        all_dtes = []
        processed_periodos = 0
        sii_password = self.credentials.get_password()
        
        # Procesar y almacenar resultados parciales
        from .dte_processor import DTEProcessor
        processor = DTEProcessor(self.company)
        
        total_results = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }
        
        with SIIIntegratedService(
            tax_id=self.full_rut,
            password=sii_password,
            headless=True
        ) as sii_service:
            logger.info(f"✅ Servicio SII integrado creado")
            
            for i, periodo in enumerate(periodos, 1):
                logger.info(f"📅 Procesando período {periodo} ({i}/{total_periodos})")
                
                # Actualizar progreso cada 10 períodos
                if i % 10 == 0:
                    self._update_sync_progress(sync_log, i, total_periodos)
                
                # Extraer documentos del período
                dtes_periodo = self._extract_periodo_documents(
                    sii_service,
                    periodo,
                    task_id
                )
                all_dtes.extend(dtes_periodo)
                processed_periodos += 1
                
                # Procesar en lotes para evitar consumir mucha memoria
                if len(all_dtes) >= 1000:
                    logger.info(f"📊 Procesando lote de {len(all_dtes)} documentos...")
                    batch_results = processor.process_batch(all_dtes, sync_log)
                    
                    # Acumular resultados
                    self._accumulate_results(total_results, batch_results)
                    
                    # Actualizar log con resultados parciales
                    self._update_sync_log_results(sync_log, total_results)
                    
                    logger.info(f"✅ Lote procesado: {batch_results['created']} creados, {batch_results['updated']} actualizados")
                    all_dtes = []  # Limpiar lista para siguiente lote
        
        # Procesar DTEs finales si quedan
        if all_dtes:
            logger.info(f"📊 Procesando último lote de {len(all_dtes)} documentos...")
            final_results = processor.process_batch(all_dtes, sync_log)
            self._accumulate_results(total_results, final_results)
        
        logger.info(f"🎉 Sincronización COMPLETA exitosa")
        logger.info(f"   Períodos procesados: {processed_periodos}")
        logger.info(f"   Documentos procesados: {total_results['processed']}")
        logger.info(f"   Documentos creados: {total_results['created']}")
        logger.info(f"   Documentos actualizados: {total_results['updated']}")
        logger.info(f"   Errores: {total_results['errors']}")
        
        return {
            'periods_processed': processed_periodos,
            **total_results
        }
    
    def _extract_periodo_documents(
        self, 
        sii_service: SIIIntegratedService,
        periodo: str,
        task_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Extrae documentos de un período específico.
        
        Args:
            sii_service: Servicio SII integrado
            periodo: Período tributario (YYYYMM)
            task_id: ID de la tarea (opcional)
            
        Returns:
            Lista de DTEs extraídos
        """
        dtes = []
        
        # Extraer documentos de compra
        dtes.extend(self._extract_compras(sii_service, periodo, task_id))
        
        # Extraer documentos de venta
        dtes.extend(self._extract_ventas(sii_service, periodo, task_id))
        
        return dtes
    
    def _extract_compras(
        self,
        sii_service: SIIIntegratedService, 
        periodo: str,
        task_id: Optional[str]
    ) -> List[Dict]:
        """
        Extrae documentos de compra (recibidos) de un período.
        Primero obtiene el resumen para identificar tipos de documentos disponibles.
        
        Args:
            sii_service: Servicio SII integrado
            periodo: Período tributario (YYYYMM)
            task_id: ID de la tarea (opcional)
            
        Returns:
            Lista de documentos de compra
        """
        try:
            logger.info(f"📥 Extrayendo documentos de compra período {periodo}")
            
            # Primero obtener resumen para identificar tipos de documentos
            logger.info(f"📊 Obteniendo resumen de compras para identificar tipos de documentos...")
            resumen = sii_service.get_resumen_compras_ventas(periodo)
            
            all_docs = []
            
            if resumen.get('status') == 'success' and resumen.get('compras'):
                compras_data = resumen['compras'].get('data', [])
                
                # Identificar tipos de documentos con datos
                tipos_con_datos = []
                if isinstance(compras_data, list):
                    for item in compras_data:
                        if isinstance(item, dict):
                            tipo_codigo = str(item.get('rsmnTipoDocInteger', ''))
                            cantidad = item.get('rsmnTotDoc', 0)
                            nombre = item.get('dcvNombreTipoDoc', f'Tipo {tipo_codigo}')
                            if tipo_codigo and cantidad > 0:
                                tipos_con_datos.append(tipo_codigo)
                                logger.info(f"   Tipo {tipo_codigo} ({nombre}): {cantidad} documentos")
                
                # Si no hay tipos identificados, intentar con los comunes
                if not tipos_con_datos:
                    logger.info("   No se encontraron tipos en resumen, intentando con tipos comunes...")
                    tipos_con_datos = ['33', '34', '46', '56', '61']  # Facturas, NC, ND, Factura Compra
                
                # Extraer documentos para cada tipo
                for cod_tipo in tipos_con_datos:
                    logger.info(f"   📄 Extrayendo documentos tipo {cod_tipo}...")
                    result = sii_service.get_documentos_compra(periodo, cod_tipo_doc=cod_tipo)
                    
                    if result.get('status') == 'success':
                        docs = result.get('data', [])
                        if docs:
                            logger.info(f"      ✅ {len(docs)} documentos tipo {cod_tipo} extraídos")
                            # Agregar metadatos
                            for doc in docs:
                                doc['tipo_operacion'] = 'recibidos'
                                doc['company_rut'] = self.full_rut
                                doc['extraction_task_id'] = task_id
                                doc['periodo_tributario'] = periodo
                            all_docs.extend(docs)
            else:
                # Si falla el resumen, intentar con tipo 33 por defecto
                logger.warning(f"⚠️ No se pudo obtener resumen, extrayendo tipo 33 por defecto")
                result = sii_service.get_documentos_compra(periodo)
                if result.get('status') == 'success':
                    docs = result.get('data', [])
                    for doc in docs:
                        doc['tipo_operacion'] = 'recibidos'
                        doc['company_rut'] = self.full_rut
                        doc['extraction_task_id'] = task_id
                        doc['periodo_tributario'] = periodo
                    all_docs.extend(docs)
            
            logger.info(f"✅ Total documentos de compra extraídos: {len(all_docs)}")
            return all_docs
                
        except Exception as e:
            logger.error(f"❌ Error extrayendo documentos de compra período {periodo}: {str(e)}")
            return []
    
    def _create_synthetic_document_type_48(
        self,
        resumen_item: Dict,
        periodo: str,
        task_id: Optional[str]
    ) -> Dict:
        """
        Crea un documento sintético para tipo 48 (Comprobante de pago electrónico).
        En lugar de extraer documentos individuales, usa los datos del resumen.

        Args:
            resumen_item: Item del resumen que contiene los datos agregados
            periodo: Período tributario (YYYYMM)
            task_id: ID de la tarea (opcional)

        Returns:
            Dict con el documento sintético
        """
        from datetime import datetime

        # Convertir período a fecha (primer día del mes)
        año = int(periodo[:4])
        mes = int(periodo[4:6])
        fecha_periodo = datetime(año, mes, 1).date().isoformat()

        # Extraer datos del resumen
        total_amount = resumen_item.get('rsmnMntTotal', 0)
        cantidad_docs = resumen_item.get('rsmnTotDoc', 0)
        nombre_tipo = resumen_item.get('dcvNombreTipoDoc', 'Comprobante de pago electrónico')

        logger.info(f"   📄 Creando documento sintético tipo 48 para período {periodo}")
        logger.info(f"      Total: ${total_amount:,.0f}, Cantidad: {cantidad_docs}")
        logger.info(f"      Resumen original: {resumen_item}")

        # Crear documento sintético en formato RPA compatible
        doc_sintetico = {
            # Metadatos de extracción
            'tipo_operacion': 'emitidos',
            'company_rut': self.full_rut,
            'extraction_task_id': task_id,
            'periodo_tributario': periodo,
            'is_synthetic': True,

            # Campos en formato RPA (esperados por DTEValidator y DTEMapper)
            'folio': int(periodo),  # Campo requerido por validator
            'tipo_documento': '48',  # Campo esperado por RPA format
            'fecha_emision': fecha_periodo,  # Campo RPA
            'monto_total': total_amount,  # Campo RPA
            'monto_neto': 0,  # Campo RPA
            'monto_iva': 0,  # Campo RPA

            # Emisor (empresa actual) - formato RPA
            'rut_emisor': self.full_rut,  # Con formato XX.XXX.XXX-X
            'razon_social_emisor': self.company.name if self.company else f'Empresa {self.full_rut}',

            # Receptor genérico - formato RPA
            'rut_receptor': '96790240-3',  # RUT genérico SII con formato completo
            'razon_social_receptor': f'Comprobantes de Pago Electrónicos - {nombre_tipo}',

            # Datos adicionales específicos del resumen
            'quantity_docs': cantidad_docs,
            'xml_data': '',  # Vacío para documentos sintéticos

            # Datos adicionales del resumen (raw_data esperado por mapper)
            'raw_data': {
                'original_resumen_item': resumen_item,
                'synthetic_type_48': True,
                'extraction_date': datetime.now().isoformat(),
                'periodo': periodo
            }
        }

        logger.info(f"      ✅ Documento sintético tipo 48 estructura completa creada")
        logger.debug(f"      📋 Estructura: {doc_sintetico}")
        return doc_sintetico

    def _create_synthetic_document_type_39(
        self,
        resumen_item: Dict,
        periodo: str,
        task_id: Optional[str]
    ) -> Dict:
        """
        Crea un documento sintético para tipo 39 (Boleta Electrónica).
        En lugar de extraer documentos individuales, usa los datos del resumen.

        Args:
            resumen_item: Item del resumen que contiene los datos agregados
            periodo: Período tributario (YYYYMM)
            task_id: ID de la tarea (opcional)

        Returns:
            Dict con el documento sintético
        """
        from datetime import datetime

        # Convertir período a fecha (primer día del mes)
        año = int(periodo[:4])
        mes = int(periodo[4:6])
        fecha_periodo = datetime(año, mes, 1).date().isoformat()

        # Extraer datos del resumen
        total_amount = resumen_item.get('rsmnMntTotal', 0)
        cantidad_docs = resumen_item.get('rsmnTotDoc', 0)
        nombre_tipo = resumen_item.get('dcvNombreTipoDoc', 'Boleta Electrónica')

        logger.info(f"   📄 Creando documento sintético tipo 39 para período {periodo}")
        logger.info(f"      Total: ${total_amount:,.0f}, Cantidad: {cantidad_docs}")

        # Crear documento sintético en formato RPA compatible
        doc_sintetico = {
            # Metadatos de extracción
            'tipo_operacion': 'emitidos',
            'company_rut': self.full_rut,
            'extraction_task_id': task_id,
            'periodo_tributario': periodo,
            'is_synthetic': True,

            # Campos en formato RPA (esperados por DTEValidator y DTEMapper)
            'folio': int(periodo),  # Campo requerido por validator
            'tipo_documento': '39',  # Campo esperado por RPA format
            'fecha_emision': fecha_periodo,  # Campo RPA
            'monto_total': total_amount,  # Campo RPA
            'monto_neto': 0,  # Campo RPA (boletas suelen ser exentas/sin IVA desglosado)
            'monto_iva': 0,  # Campo RPA

            # Emisor (empresa actual) - formato RPA
            'rut_emisor': self.full_rut,  # Con formato XX.XXX.XXX-X
            'razon_social_emisor': self.company.name if self.company else f'Empresa {self.full_rut}',

            # Receptor genérico - formato RPA
            'rut_receptor': '66666666-6',  # RUT genérico para consumidor final
            'razon_social_receptor': f'Boletas Electrónicas - {nombre_tipo}',

            # Datos adicionales específicos del resumen
            'quantity_docs': cantidad_docs,
            'xml_data': '',  # Vacío para documentos sintéticos

            # Datos adicionales del resumen (raw_data esperado por mapper)
            'raw_data': {
                'original_resumen_item': resumen_item,
                'synthetic_type_39': True,
                'extraction_date': datetime.now().isoformat(),
                'periodo': periodo
            }
        }

        return doc_sintetico

    def _extract_ventas(
        self,
        sii_service: SIIIntegratedService,
        periodo: str,
        task_id: Optional[str]
    ) -> List[Dict]:
        """
        Extrae documentos de venta (emitidos) de un período.
        Primero obtiene el resumen para identificar tipos de documentos disponibles.
        
        Args:
            sii_service: Servicio SII integrado
            periodo: Período tributario (YYYYMM)
            task_id: ID de la tarea (opcional)
            
        Returns:
            Lista de documentos de venta
        """
        try:
            logger.info(f"📤 Extrayendo documentos de venta período {periodo}")
            
            # Primero obtener resumen para identificar tipos de documentos
            logger.info(f"📊 Obteniendo resumen de ventas para identificar tipos de documentos...")
            resumen = sii_service.get_resumen_compras_ventas(periodo)
            
            all_docs = []
            
            if resumen.get('status') == 'success' and resumen.get('ventas'):
                ventas_data = resumen['ventas'].get('data', [])
                
                # Identificar tipos de documentos con datos
                tipos_con_datos = []
                resumen_items = {}  # Para almacenar items del resumen por tipo
                if isinstance(ventas_data, list):
                    for item in ventas_data:
                        if isinstance(item, dict):
                            tipo_codigo = str(item.get('rsmnTipoDocInteger', ''))
                            cantidad = item.get('rsmnTotDoc', 0)
                            nombre = item.get('dcvNombreTipoDoc', f'Tipo {tipo_codigo}')
                            if tipo_codigo and cantidad > 0:
                                tipos_con_datos.append(tipo_codigo)
                                resumen_items[tipo_codigo] = item  # Almacenar item completo
                                logger.info(f"   Tipo {tipo_codigo} ({nombre}): {cantidad} documentos")
                
                # Si no hay tipos identificados, intentar con los comunes
                if not tipos_con_datos:
                    logger.info("   No se encontraron tipos en resumen, intentando con tipos comunes...")
                    tipos_con_datos = ['33', '34', '39', '41', '52', '56', '61']  # Facturas, Boletas, GD, NC, ND
                    # Para tipos especiales sin resumen, no podemos crear documentos sintéticos
                    resumen_items = {}
                
                # Extraer documentos para cada tipo
                for cod_tipo in tipos_con_datos:
                    if cod_tipo == '48':
                        # Manejo especial para tipo 48 (Comprobante de pago electrónico)
                        logger.info(f"   📄 Procesando tipo 48 (Comprobante de pago electrónico) - usando resumen")
                        logger.info(f"      🔍 Verificando resumen_items para tipo 48...")
                        logger.info(f"      📊 Claves disponibles en resumen: {list(resumen_items.keys())}")

                        if cod_tipo in resumen_items:
                            logger.info(f"      ✅ Encontrado item en resumen para tipo 48")
                            doc_sintetico = self._create_synthetic_document_type_48(
                                resumen_items[cod_tipo],
                                periodo,
                                task_id
                            )
                            all_docs.append(doc_sintetico)
                            logger.info(f"      ✅ Documento sintético tipo 48 agregado a all_docs (total: {len(all_docs)})")
                        else:
                            logger.warning(f"      ⚠️ No se encontró item en resumen para tipo 48 - no se puede crear documento sintético")
                            logger.warning(f"      📊 Tipos disponibles en resumen: {list(resumen_items.keys())}")
                    elif cod_tipo == '39':
                        # Manejo especial para tipo 39 (Boleta Electrónica)
                        logger.info(f"   📄 Procesando tipo 39 (Boleta Electrónica) - usando resumen")
                        if cod_tipo in resumen_items:
                            doc_sintetico = self._create_synthetic_document_type_39(
                                resumen_items[cod_tipo],
                                periodo,
                                task_id
                            )
                            all_docs.append(doc_sintetico)
                            logger.info(f"      ✅ Documento sintético tipo 39 creado")
                        else:
                            logger.warning(f"      ⚠️ No se encontró item en resumen para tipo 39 - no se puede crear documento sintético")
                    else:
                        # Proceso normal para otros tipos
                        logger.info(f"   📄 Extrayendo documentos tipo {cod_tipo}...")
                        result = sii_service.get_documentos_venta(periodo, cod_tipo_doc=cod_tipo)

                        if result.get('status') == 'success':
                            docs = result.get('data', [])
                            if docs:
                                logger.info(f"      ✅ {len(docs)} documentos tipo {cod_tipo} extraídos")
                                # Agregar metadatos
                                for doc in docs:
                                    doc['tipo_operacion'] = 'emitidos'
                                    doc['company_rut'] = self.full_rut
                                    doc['extraction_task_id'] = task_id
                                    doc['periodo_tributario'] = periodo
                                all_docs.extend(docs)
                        else:
                            logger.warning(f"      ⚠️ No se pudieron extraer documentos tipo {cod_tipo}")
            else:
                # Si falla el resumen, intentar con tipo 33 por defecto
                logger.warning(f"⚠️ No se pudo obtener resumen, extrayendo tipo 33 por defecto")
                result = sii_service.get_documentos_venta(periodo)
                if result.get('status') == 'success':
                    docs = result.get('data', [])
                    for doc in docs:
                        doc['tipo_operacion'] = 'emitidos'
                        doc['company_rut'] = self.full_rut
                        doc['extraction_task_id'] = task_id
                        doc['periodo_tributario'] = periodo
                    all_docs.extend(docs)
            
            logger.info(f"✅ Total documentos de venta extraídos: {len(all_docs)}")
            return all_docs
                
        except Exception as e:
            logger.error(f"❌ Error extrayendo documentos de venta período {periodo}: {str(e)}")
            return []
    
    def _validate_dates(self, fecha_desde: str, fecha_hasta: str):
        """
        Valida que las fechas sean correctas.
        
        Args:
            fecha_desde: Fecha inicio en formato YYYY-MM-DD
            fecha_hasta: Fecha fin en formato YYYY-MM-DD
            
        Raises:
            ValueError: Si las fechas son inválidas
        """
        try:
            start_date = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            end_date = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            
            if start_date > end_date:
                raise ValueError(f"Fecha desde ({fecha_desde}) no puede ser posterior a fecha hasta ({fecha_hasta})")
            
            # Validar que no sea fecha futura
            if end_date > date.today():
                raise ValueError(f"Fecha hasta ({fecha_hasta}) no puede ser futura")
                
        except ValueError as e:
            if "time data" in str(e):
                raise ValueError(f"Formato de fecha inválido. Use YYYY-MM-DD")
            raise
    
    def _get_fecha_inicio_actividades(self) -> date:
        """
        Obtiene la fecha de inicio de actividades de la empresa.
        
        Returns:
            date: Fecha de inicio de actividades o hace 5 años si no existe
        """
        if hasattr(self.company, 'taxpayer') and self.company.taxpayer:
            if hasattr(self.company.taxpayer, 'fecha_inicio_actividades'):
                if self.company.taxpayer.fecha_inicio_actividades:
                    return self.company.taxpayer.fecha_inicio_actividades
        
        # Si no hay fecha de inicio, usar hace 5 años como máximo
        fecha_default = date.today() - timedelta(days=5*365)
        logger.warning(f"⚠️ No hay fecha de inicio de actividades para {self.full_rut}, usando: {fecha_default}")
        return fecha_default
    
    def _get_periodos_from_dates(self, fecha_desde: str, fecha_hasta: str) -> List[str]:
        """
        Convierte un rango de fechas a lista de períodos tributarios (YYYYMM).
        
        Args:
            fecha_desde: Fecha inicio en formato YYYY-MM-DD
            fecha_hasta: Fecha fin en formato YYYY-MM-DD
            
        Returns:
            Lista de períodos en formato YYYYMM
        """
        try:
            start_date = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            end_date = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            
            periodos = []
            current_date = start_date.replace(day=1)  # Primer día del mes
            
            while current_date <= end_date:
                periodo = current_date.strftime('%Y%m')
                if periodo not in periodos:
                    periodos.append(periodo)
                
                # Avanzar al próximo mes
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            
            return periodos
            
        except ValueError as e:
            logger.error(f"Error parseando fechas {fecha_desde} - {fecha_hasta}: {e}")
            # Fallback: período del mes actual
            return [date.today().strftime('%Y%m')]
    
    def _update_sync_progress(self, sync_log: SIISyncLog, current: int, total: int):
        """
        Actualiza el progreso de la sincronización.
        
        Args:
            sync_log: Log de sincronización
            current: Período actual
            total: Total de períodos
        """
        try:
            sync_log.refresh_from_db()
            sync_log.progress_percentage = int((current / total) * 100)
            sync_log.save(update_fields=['progress_percentage'])
            logger.info(f"📊 Progreso: {sync_log.progress_percentage}%")
        except Exception as e:
            logger.warning(f"⚠️ Error actualizando progreso: {e}")
    
    def _accumulate_results(self, total_results: Dict, batch_results: Dict):
        """
        Acumula resultados de un lote en los totales.
        
        Args:
            total_results: Resultados totales acumulados
            batch_results: Resultados del lote actual
        """
        total_results['processed'] += batch_results.get('processed', 0)
        total_results['created'] += batch_results.get('created', 0)
        total_results['updated'] += batch_results.get('updated', 0)
        total_results['errors'] += batch_results.get('errors', 0)
        
        # Acumular detalles de errores si existen
        if 'error_details' in batch_results:
            total_results['error_details'].extend(batch_results['error_details'])
    
    def _update_sync_log_results(self, sync_log: SIISyncLog, results: Dict):
        """
        Actualiza el log de sincronización con resultados parciales.
        
        Args:
            sync_log: Log de sincronización
            results: Resultados acumulados
        """
        try:
            sync_log.refresh_from_db()
            sync_log.documents_processed = results['processed']
            sync_log.documents_created = results['created']
            sync_log.documents_updated = results['updated']
            sync_log.errors_count = results['errors']
            sync_log.save(update_fields=[
                'documents_processed',
                'documents_created', 
                'documents_updated',
                'errors_count'
            ])
        except Exception as e:
            logger.warning(f"⚠️ Error actualizando log de sincronización: {e}")