"""
Parser robusto para DTEs extraídos del SII
Maneja la conversión de datos raw del RPA a estructuras consistentes
"""
import logging
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class DTEParsingError(Exception):
    """Excepción para errores de parsing de DTEs"""
    pass


class DTEParser:
    """
    Parser robusto para DTEs extraídos del SII
    """
    
    # Mapeo de nombres de documentos a códigos SII
    DOCUMENT_TYPE_MAPPING = {
        'FACTURA ELECTRONICA': 33,
        'FACTURA AFECTA ELECTRONICA': 33,
        'FACTURA NO AFECTA ELECTRONICA': 34,
        'FACTURA EXENTA ELECTRONICA': 34,
        'BOLETA ELECTRONICA': 39,
        'BOLETA AFECTA ELECTRONICA': 39,
        'BOLETA NO AFECTA ELECTRONICA': 41,
        'BOLETA EXENTA ELECTRONICA': 41,
        'FACTURA COMPRA ELECTRONICA': 46,
        'GUIA DESPACHO ELECTRONICA': 52,
        'NOTA DEBITO ELECTRONICA': 56,
        'NOTA CREDITO ELECTRONICA': 61,
        'FACTURA EXPORTACION ELECTRONICA': 110,
        'NOTA DEBITO EXPORTACION ELECTRONICA': 111,
        'NOTA CREDITO EXPORTACION ELECTRONICA': 112,
    }
    
    @classmethod
    def parse_document_type(cls, tipo_documento: Any) -> int:
        """
        Convierte tipo de documento a código numérico SII
        """
        if isinstance(tipo_documento, int):
            return tipo_documento
        
        if isinstance(tipo_documento, str):
            # Limpiar string
            tipo_clean = tipo_documento.upper().strip()
            
            # Buscar en mapeo directo
            if tipo_clean in cls.DOCUMENT_TYPE_MAPPING:
                return cls.DOCUMENT_TYPE_MAPPING[tipo_clean]
            
            # Intentar extraer número del string
            import re
            numbers = re.findall(r'\d+', tipo_clean)
            if numbers:
                try:
                    return int(numbers[0])
                except ValueError:
                    pass
        
        # Fallback a factura electrónica
        logger.warning(f"Tipo documento desconocido: {tipo_documento}, usando 33 por defecto")
        return 33
    
    @classmethod
    def parse_date(cls, fecha_str: Any) -> date:
        """
        Parse fecha desde diferentes formatos
        """
        if isinstance(fecha_str, date):
            return fecha_str
        
        if isinstance(fecha_str, datetime):
            return fecha_str.date()
        
        if not fecha_str or fecha_str == 'None':
            return date.today()
        
        fecha_str = str(fecha_str).strip()
        
        # Formatos comunes del SII
        formats = [
            '%d/%m/%Y',     # 22/09/2025
            '%d-%m-%Y',     # 22-09-2025
            '%Y-%m-%d',     # 2025-09-22
            '%d.%m.%Y',     # 22.09.2025
            '%Y/%m/%d',     # 2025/09/22
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(fecha_str, fmt).date()
            except (ValueError, TypeError):
                continue
        
        logger.warning(f"No se pudo parsear fecha: {fecha_str}, usando fecha actual")
        return date.today()
    
    @classmethod
    def parse_amount(cls, amount: Any) -> Decimal:
        """
        Parse montos de diferentes formatos
        """
        if amount is None or amount == 'None' or amount == '':
            return Decimal('0.00')
        
        if isinstance(amount, Decimal):
            return amount
        
        if isinstance(amount, (int, float)):
            return Decimal(str(amount))
        
        # Limpiar string
        amount_str = str(amount).strip()
        
        # Remover caracteres no numéricos excepto punto y coma
        import re
        cleaned = re.sub(r'[^\d.,\-]', '', amount_str)
        
        if not cleaned:
            return Decimal('0.00')
        
        # Manejar formatos con coma como separador decimal
        if ',' in cleaned and '.' in cleaned:
            # Formato: 1.234.567,89
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned and '.' not in cleaned:
            # Formato: 1234,89
            cleaned = cleaned.replace(',', '.')
        
        try:
            return Decimal(cleaned)
        except (ValueError, InvalidOperation):
            logger.warning(f"No se pudo parsear monto: {amount}, usando 0.00")
            return Decimal('0.00')
    
    @classmethod
    def parse_rut(cls, rut: Any) -> tuple[str, str]:
        """
        Parse RUT y devuelve (numero, dv)
        """
        if not rut or rut == 'None':
            return '00000000', '0'
        
        rut_str = str(rut).strip().upper()
        
        # Remover puntos y guiones
        rut_clean = rut_str.replace('.', '').replace('-', '')
        
        if len(rut_clean) < 2:
            return '00000000', '0'
        
        # Separar número y DV
        rut_num = rut_clean[:-1]
        rut_dv = rut_clean[-1]
        
        # Validar que el número sea numérico
        if not rut_num.isdigit():
            return '00000000', '0'
        
        # Completar con ceros si es necesario
        rut_num = rut_num.zfill(8)
        
        return rut_num, rut_dv
    
    @classmethod
    def parse_dte_data(cls, raw_dte: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse datos raw de DTE a estructura consistente
        """
        try:
            # Parsear campos principales
            folio = raw_dte.get('folio')
            if folio is None or folio == 'None':
                folio = 0
            else:
                try:
                    folio = int(folio)
                except (ValueError, TypeError):
                    folio = 0
            
            tipo_documento = cls.parse_document_type(raw_dte.get('tipo_documento'))
            fecha_emision = cls.parse_date(raw_dte.get('fecha_emision'))
            
            # Parse montos
            monto_neto = cls.parse_amount(raw_dte.get('monto_neto', 0))
            monto_iva = cls.parse_amount(raw_dte.get('monto_iva', 0))
            monto_total = cls.parse_amount(raw_dte.get('monto_total', 0))
            
            # Si no hay monto total pero hay neto + IVA, calcularlo
            if monto_total == 0 and (monto_neto > 0 or monto_iva > 0):
                monto_total = monto_neto + monto_iva
            
            # Parse RUTs
            rut_emisor_num, rut_emisor_dv = cls.parse_rut(raw_dte.get('rut_emisor'))
            rut_receptor_num, rut_receptor_dv = cls.parse_rut(raw_dte.get('rut_receptor'))
            
            # Parse nombres (truncar para evitar errores de DB)
            razon_social_emisor = str(raw_dte.get('razon_social_emisor', ''))[:255]
            razon_social_receptor = str(raw_dte.get('razon_social_receptor', 'Sin especificar'))[:255]
            
            parsed_data = {
                'folio': folio,
                'tipo_documento_code': tipo_documento,
                'fecha_emision': fecha_emision,
                'rut_emisor_num': rut_emisor_num,
                'rut_emisor_dv': rut_emisor_dv,
                'razon_social_emisor': razon_social_emisor,
                'rut_receptor_num': rut_receptor_num,
                'rut_receptor_dv': rut_receptor_dv,
                'razon_social_receptor': razon_social_receptor,
                'monto_neto': monto_neto,
                'monto_iva': monto_iva,
                'monto_total': monto_total,
                'estado': str(raw_dte.get('estado', 'accepted')),
                'sii_track_id': str(raw_dte.get('sii_track_id', '')),
                'raw_data': raw_dte,
            }
            
            logger.debug(f"DTE parseado - Folio: {folio}, Tipo: {tipo_documento}, Total: {monto_total}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parseando DTE: {e}")
            logger.error(f"Raw data: {raw_dte}")
            raise DTEParsingError(f"Error parseando DTE: {str(e)}")
    
    @classmethod
    def parse_batch(cls, raw_dtes: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Parse un lote de DTEs
        Retorna (dtes_parseados, errores)
        """
        parsed_dtes = []
        errors = []
        
        for i, raw_dte in enumerate(raw_dtes):
            try:
                parsed_dte = cls.parse_dte_data(raw_dte)
                parsed_dtes.append(parsed_dte)
            except DTEParsingError as e:
                error_msg = f"DTE #{i}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return parsed_dtes, errors