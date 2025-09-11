"""
Mapeador de DTEs a modelos de Django
"""
import logging
import re
from datetime import datetime, date
from typing import Dict, Any, Optional

from apps.companies.models import Company
from apps.documents.models import DocumentType

logger = logging.getLogger(__name__)


class DTEMapper:
    """
    Mapeador que convierte DTEs del SII a modelos de Document de Django.
    """
    
    # Mapeo de tipos de documento string a códigos numéricos
    TYPE_MAPPING = {
        'factura electrónica': 33,
        'factura': 33,
        'factura no afecta': 34,
        'factura exenta': 34,
        'nota de crédito': 61,
        'nota credito': 61,
        'nota de débito': 56,
        'nota debito': 56,
        'boleta electrónica': 39,
        'boleta': 39,
        'boleta exenta': 41,
        'guía de despacho': 52,
        'guia de despacho': 52,
        'factura de compra': 46,
        'liquidación factura': 43,
        'liquidacion factura': 43,
    }
    
    def __init__(self, company: Company):
        """
        Inicializa el mapeador.
        
        Args:
            company: Empresa propietaria de los documentos
        """
        self.company = company
        self.company_rut_parts = self._parse_company_rut()
    
    def _parse_company_rut(self) -> Dict[str, str]:
        """
        Parsea el RUT de la empresa en sus componentes.
        
        Returns:
            Dict con 'rut' y 'dv'
        """
        if '-' in self.company.tax_id:
            parts = self.company.tax_id.split('-')
            return {
                'rut': parts[0],
                'dv': parts[1].upper() if len(parts) > 1 else '0'
            }
        else:
            # Asumir formato sin guión
            return {
                'rut': self.company.tax_id[:-1] if len(self.company.tax_id) > 1 else self.company.tax_id,
                'dv': self.company.tax_id[-1].upper() if self.company.tax_id else '0'
            }
    
    def map_to_document(self, dte_data: Dict) -> Dict[str, Any]:
        """
        Mapea un DTE a los campos del modelo Document.
        
        Args:
            dte_data: Datos del DTE desde el SII
            
        Returns:
            Dict con los campos mapeados para Document
        """
        # Detectar formato del DTE
        is_api_format = 'detNroDoc' in dte_data
        
        if is_api_format:
            return self._map_api_format(dte_data)
        else:
            return self._map_rpa_format(dte_data)
    
    def _map_api_format(self, dte_data: Dict) -> Dict[str, Any]:
        """
        Mapea un DTE en formato API del SII.
        
        Args:
            dte_data: DTE en formato API
            
        Returns:
            Dict con campos para Document
        """
        # Extraer información básica
        folio = dte_data.get('detNroDoc')
        tipo_documento_raw = dte_data.get('detTipoDoc') or dte_data.get('codTDoc', 33)
        fecha_emision = self._parse_date(dte_data.get('detFchDoc'))
        
        # Determinar tipo de operación y RUT emisor
        tipo_operacion = dte_data.get('tipo_operacion', 'recibidos')
        
        if tipo_operacion == 'recibidos':
            # Para documentos recibidos, el emisor es el proveedor
            rut_emisor = dte_data.get('detRutDoc', '')
            dv_emisor = dte_data.get('detDvDoc', '')
            nombre_emisor = dte_data.get('detRznSoc', 'Sin nombre')
            
            # El receptor es la empresa
            rut_receptor = self.company_rut_parts['rut']
            dv_receptor = self.company_rut_parts['dv']
            nombre_receptor = self.company.business_name or self.company.display_name
        else:
            # Para documentos emitidos, el emisor es la empresa
            rut_emisor = self.company_rut_parts['rut']
            dv_emisor = self.company_rut_parts['dv']
            nombre_emisor = self.company.business_name or self.company.display_name
            
            # El receptor debe venir en los datos
            rut_receptor = str(dte_data.get('detRutDoc', '00000000'))
            dv_receptor = str(dte_data.get('detDvDoc', '0'))
            nombre_receptor = dte_data.get('detRznSoc', 'Cliente')
        
        # Obtener o crear tipo de documento
        document_type = self._get_or_create_document_type(tipo_documento_raw)
        
        # Parsear montos
        net_amount = self._parse_amount(dte_data.get('detMntNeto', 0))
        tax_amount = self._parse_amount(dte_data.get('detMntIVA', 0))
        total_amount = self._parse_amount(dte_data.get('detMntTotal', 0))
        
        # Generar track_id único
        track_id = self._generate_track_id(folio)
        
        return {
            'company': self.company,  # Agregar relación con Company
            'issuer_company_rut': str(rut_emisor)[:12],
            'issuer_company_dv': str(dv_emisor)[:1],
            'issuer_name': str(nombre_emisor)[:255],
            'issuer_address': '',  # No disponible en datos SII
            'document_type': document_type,
            'folio': folio or 0,
            'issue_date': fecha_emision or date.today(),
            'recipient_rut': str(rut_receptor)[:12],
            'recipient_dv': str(dv_receptor)[:1],
            'recipient_name': str(nombre_receptor)[:255],
            'net_amount': net_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'status': 'accepted',  # Asumimos aceptado por defecto
            'sii_track_id': track_id,
            'xml_data': dte_data.get('xml_data', ''),
            'raw_data': dte_data
        }
    
    def _map_rpa_format(self, dte_data: Dict) -> Dict[str, Any]:
        """
        Mapea un DTE en formato RPA (procesado).
        
        Args:
            dte_data: DTE en formato RPA
            
        Returns:
            Dict con campos para Document
        """
        # Extraer información básica
        folio = dte_data.get('folio')
        tipo_documento_raw = dte_data.get('tipo_documento')
        fecha_emision = self._parse_date(dte_data.get('fecha_emision'))
        
        # Parsear RUT emisor
        rut_emisor_full = dte_data.get('rut_emisor', self.company.tax_id)
        if '-' in str(rut_emisor_full):
            rut_parts = str(rut_emisor_full).split('-')
            rut_emisor = rut_parts[0]
            dv_emisor = rut_parts[1] if len(rut_parts) > 1 else '0'
        else:
            rut_emisor = str(rut_emisor_full)[:-1] if len(str(rut_emisor_full)) > 1 else str(rut_emisor_full)
            dv_emisor = str(rut_emisor_full)[-1] if rut_emisor_full else '0'
        
        # Determinar tipo de operación
        tipo_operacion = dte_data.get('tipo_operacion', 'recibidos')
        
        if tipo_operacion == 'recibidos':
            # El receptor es la empresa
            rut_receptor = self.company_rut_parts['rut']
            dv_receptor = self.company_rut_parts['dv']
            nombre_receptor = self.company.business_name or self.company.display_name
            nombre_emisor = dte_data.get('razon_social_emisor', 'Proveedor')
        else:
            # El emisor es la empresa
            rut_emisor = self.company_rut_parts['rut']
            dv_emisor = self.company_rut_parts['dv']
            nombre_emisor = self.company.business_name or self.company.display_name
            
            # Parsear RUT receptor
            rut_receptor_full = dte_data.get('rut_receptor', '00000000-0')
            if '-' in str(rut_receptor_full):
                receptor_parts = str(rut_receptor_full).split('-')
                rut_receptor = receptor_parts[0]
                dv_receptor = receptor_parts[1] if len(receptor_parts) > 1 else '0'
            else:
                rut_receptor = str(rut_receptor_full)[:-1] if len(str(rut_receptor_full)) > 1 else str(rut_receptor_full)
                dv_receptor = str(rut_receptor_full)[-1] if rut_receptor_full else '0'
            
            nombre_receptor = dte_data.get('razon_social_receptor', 'Cliente')
        
        # Mapear tipo de documento
        tipo_documento_code = self._map_document_type(tipo_documento_raw)
        document_type = self._get_or_create_document_type(tipo_documento_code)
        
        # Parsear montos
        net_amount = self._parse_amount(dte_data.get('monto_neto', dte_data.get('monto_total', 0)))
        tax_amount = self._parse_amount(dte_data.get('monto_iva', 0))
        total_amount = self._parse_amount(dte_data.get('monto_total', 0))
        
        # Generar track_id único
        track_id = self._generate_track_id(folio)
        
        return {
            'company': self.company,  # Agregar relación con Company
            'issuer_company_rut': str(rut_emisor)[:12],
            'issuer_company_dv': str(dv_emisor)[:1].upper(),
            'issuer_name': str(nombre_emisor)[:255],
            'issuer_address': '',
            'document_type': document_type,
            'folio': folio or 0,
            'issue_date': fecha_emision or date.today(),
            'recipient_rut': str(rut_receptor)[:12],
            'recipient_dv': str(dv_receptor)[:1].upper(),
            'recipient_name': str(nombre_receptor)[:255],
            'net_amount': net_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            'status': 'accepted',
            'sii_track_id': track_id,
            'xml_data': dte_data.get('xml_data', ''),
            'raw_data': dte_data
        }
    
    def _get_or_create_document_type(self, tipo_codigo: int) -> DocumentType:
        """
        Obtiene o crea un tipo de documento.
        
        Args:
            tipo_codigo: Código numérico del tipo de documento
            
        Returns:
            DocumentType instance
        """
        # Mapeo de códigos a nombres descriptivos
        type_names = {
            33: 'Factura Electrónica',
            34: 'Factura Exenta Electrónica',
            35: 'Boleta Electrónica',
            38: 'Boleta Exenta Electrónica',
            39: 'Boleta Electrónica',
            40: 'Liquidación Factura Electrónica',
            43: 'Liquidación Factura Electrónica',
            45: 'Factura de Compra Electrónica',
            46: 'Factura de Compra',
            48: 'Comprobante de Pago Electrónico',
            52: 'Guía de Despacho',
            56: 'Nota de Débito Electrónica',
            60: 'Nota de Crédito',
            61: 'Nota de Crédito Electrónica',
            110: 'Factura de Exportación Electrónica',
            111: 'Nota de Débito de Exportación Electrónica',
            112: 'Nota de Crédito de Exportación Electrónica',
        }
        
        doc_type, created = DocumentType.objects.get_or_create(
            code=tipo_codigo,
            defaults={
                'name': type_names.get(tipo_codigo, f'DTE Tipo {tipo_codigo}'),
                'is_electronic': True,
                'is_dte': True,
                'category': self._get_document_category(tipo_codigo)
            }
        )
        
        if created:
            logger.info(f"📄 Creado nuevo tipo de documento: {doc_type.name} (código {tipo_codigo})")
        
        return doc_type
    
    def _get_document_category(self, tipo_codigo: int) -> str:
        """
        Determina la categoría del documento según su tipo.
        
        Args:
            tipo_codigo: Código del tipo de documento
            
        Returns:
            Categoría del documento
        """
        if tipo_codigo in [33, 34, 43, 45, 46, 110]:
            return 'invoice'
        elif tipo_codigo in [35, 38, 39, 41]:
            return 'receipt'
        elif tipo_codigo in [56, 111]:
            return 'debit_note'
        elif tipo_codigo in [60, 61, 112]:
            return 'credit_note'
        elif tipo_codigo == 52:
            return 'delivery_guide'
        else:
            return 'other'
    
    def _map_document_type(self, tipo_str: Any) -> int:
        """
        Mapea string o int de tipo de documento a código numérico.
        
        Args:
            tipo_str: Tipo de documento (string o int)
            
        Returns:
            Código numérico del tipo
        """
        if not tipo_str:
            return 33  # Default: Factura Electrónica
        
        # Si ya es un entero, devolverlo directamente
        if isinstance(tipo_str, int):
            return tipo_str
        
        # Si es string, procesarlo
        tipo_lower = str(tipo_str).lower()
        
        # Buscar en mapeo
        for key, code in self.TYPE_MAPPING.items():
            if key in tipo_lower:
                return code
        
        # Si no encuentra coincidencia, intentar extraer número
        numbers = re.findall(r'\d+', str(tipo_str))
        if numbers:
            return int(numbers[0])
        
        return 33  # Default
    
    def _parse_date(self, date_str: Any) -> date:
        """
        Convierte string de fecha a objeto date.
        
        Args:
            date_str: String de fecha
            
        Returns:
            date object
        """
        if not date_str:
            return date.today()
        
        if isinstance(date_str, date):
            return date_str
        
        if isinstance(date_str, datetime):
            return date_str.date()
        
        # Formatos comunes de fecha del SII
        date_formats = [
            '%d/%m/%Y',
            '%d-%m-%Y', 
            '%Y-%m-%d',
            '%d/%m/%y',
            '%d-%m-%y'
        ]
        
        date_str = str(date_str).strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        logger.warning(f"No se pudo parsear fecha: {date_str}, usando fecha actual")
        return date.today()
    
    def _parse_amount(self, amount_str: Any) -> float:
        """
        Convierte string de monto a float.
        
        Args:
            amount_str: String o número del monto
            
        Returns:
            float del monto
        """
        if not amount_str:
            return 0.0
        
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        
        # Limpiar string de monto
        clean_amount = str(amount_str).replace('$', '').replace('.', '').replace(',', '.').strip()
        
        try:
            return float(clean_amount)
        except ValueError:
            logger.warning(f"No se pudo parsear monto: {amount_str}, usando 0.0")
            return 0.0
    
    def _generate_track_id(self, folio: Any) -> str:
        """
        Genera un track_id único para el documento.
        
        Args:
            folio: Folio del documento
            
        Returns:
            Track ID único
        """
        timestamp = int(datetime.now().timestamp())
        folio_str = str(folio) if folio else 'NA'
        return f"TRK{timestamp}{folio_str}"