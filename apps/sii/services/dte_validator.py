"""
Validador de DTEs (Documentos Tributarios Electrónicos)
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DTEValidator:
    """
    Validador para Documentos Tributarios Electrónicos.
    Verifica que los DTEs cumplan con los requisitos mínimos.
    """
    
    # Tipos de documento válidos según el SII
    VALID_DOCUMENT_TYPES = {
        33, 34, 35, 38, 39, 40, 43, 45, 46, 48, 52, 
        56, 60, 61, 110, 111, 112, 
        # Tipos como strings también son válidos
        '33', '34', '35', '38', '39', '40', '43', '45', '46', '48', '52',
        '56', '60', '61', '110', '111', '112'
    }
    
    def __init__(self):
        """Inicializa el validador"""
        self.last_error = None
    
    def validate(self, dte_data: Any) -> bool:
        """
        Valida que un DTE tenga la estructura y datos mínimos requeridos.
        
        Args:
            dte_data: Datos del DTE a validar
            
        Returns:
            True si es válido, False si no lo es
        """
        self.last_error = None
        
        # Validar que sea un diccionario
        if not isinstance(dte_data, dict):
            self.last_error = f"DTE debe ser un diccionario, recibido: {type(dte_data)}"
            return False
        
        # Validar que no esté vacío
        if not dte_data:
            self.last_error = "DTE está vacío"
            return False
        
        # Detectar formato del DTE (API vs RPA)
        is_api_format = 'detNroDoc' in dte_data
        is_rpa_format = 'folio' in dte_data
        
        if not is_api_format and not is_rpa_format:
            self.last_error = "DTE no tiene formato reconocible (ni API ni RPA)"
            return False
        
        # Validar campos según formato
        if is_api_format:
            return self._validate_api_format(dte_data)
        else:
            return self._validate_rpa_format(dte_data)
    
    def _validate_api_format(self, dte_data: Dict) -> bool:
        """
        Valida un DTE en formato API del SII.
        
        Args:
            dte_data: Datos del DTE en formato API
            
        Returns:
            True si es válido, False si no lo es
        """
        # Campos mínimos requeridos para formato API
        required_fields = ['detNroDoc']  # Folio es el mínimo indispensable
        
        for field in required_fields:
            if field not in dte_data:
                self.last_error = f"Campo requerido '{field}' no encontrado en DTE formato API"
                return False
        
        # Validar folio
        folio = dte_data.get('detNroDoc')
        if not self._validate_folio(folio):
            return False
        
        # Validar tipo de documento si existe
        tipo_doc = dte_data.get('detTipoDoc') or dte_data.get('codTDoc')
        if tipo_doc and not self._validate_tipo_documento(tipo_doc):
            return False
        
        # Validar montos si existen
        if not self._validate_montos_api(dte_data):
            return False
        
        # Validar RUT emisor/receptor si es documento recibido
        tipo_operacion = dte_data.get('tipo_operacion', 'recibidos')
        if tipo_operacion == 'recibidos':
            rut_emisor = dte_data.get('detRutDoc')
            if rut_emisor and not self._validate_rut_numerico(rut_emisor):
                self.last_error = f"RUT emisor inválido: {rut_emisor}"
                return False
        
        return True
    
    def _validate_rpa_format(self, dte_data: Dict) -> bool:
        """
        Valida un DTE en formato RPA (procesado).
        
        Args:
            dte_data: Datos del DTE en formato RPA
            
        Returns:
            True si es válido, False si no lo es
        """
        # Campos mínimos requeridos para formato RPA
        required_fields = ['folio']
        
        for field in required_fields:
            if field not in dte_data:
                self.last_error = f"Campo requerido '{field}' no encontrado en DTE formato RPA"
                return False
        
        # Validar folio
        folio = dte_data.get('folio')
        if not self._validate_folio(folio):
            return False
        
        # Validar tipo de documento si existe
        tipo_doc = dte_data.get('tipo_documento')
        if tipo_doc and not self._validate_tipo_documento_string(tipo_doc):
            return False
        
        # Validar RUT emisor si existe
        rut_emisor = dte_data.get('rut_emisor')
        if rut_emisor and not self._validate_rut_formato_chileno(rut_emisor):
            self.last_error = f"RUT emisor inválido: {rut_emisor}"
            return False
        
        # Validar montos si existen
        if not self._validate_montos_rpa(dte_data):
            return False
        
        return True
    
    def _validate_folio(self, folio: Any) -> bool:
        """
        Valida que el folio sea válido.
        
        Args:
            folio: Número de folio del documento
            
        Returns:
            True si es válido, False si no lo es
        """
        if folio is None:
            # Permitir None, será manejado después
            return True
        
        # Convertir a entero si es posible
        try:
            folio_int = int(folio)
            if folio_int < 0:
                self.last_error = f"Folio no puede ser negativo: {folio}"
                return False
            return True
        except (ValueError, TypeError):
            # Si no es convertible a entero, verificar que al menos sea string no vacío
            if isinstance(folio, str) and folio.strip():
                return True
            self.last_error = f"Folio inválido: {folio}"
            return False
    
    def _validate_tipo_documento(self, tipo_doc: Any) -> bool:
        """
        Valida que el tipo de documento sea válido (formato numérico).
        
        Args:
            tipo_doc: Código del tipo de documento
            
        Returns:
            True si es válido, False si no lo es
        """
        if tipo_doc is None:
            # Permitir None, se usará default después
            return True
        
        # Convertir a entero si es posible
        try:
            tipo_int = int(tipo_doc)
            # No validar contra lista específica, permitir cualquier tipo numérico
            # El SII puede agregar nuevos tipos
            return True
        except (ValueError, TypeError):
            self.last_error = f"Tipo de documento inválido: {tipo_doc}"
            return False
    
    def _validate_tipo_documento_string(self, tipo_doc: Any) -> bool:
        """
        Valida que el tipo de documento sea válido (formato string).
        
        Args:
            tipo_doc: Descripción del tipo de documento
            
        Returns:
            True si es válido, False si no lo es
        """
        if tipo_doc is None:
            return True
        
        # Aceptar cualquier string no vacío
        if isinstance(tipo_doc, str) and tipo_doc.strip():
            return True
        
        # También aceptar números
        if isinstance(tipo_doc, (int, float)):
            return True
        
        self.last_error = f"Tipo de documento inválido: {tipo_doc}"
        return False
    
    def _validate_rut_numerico(self, rut: Any) -> bool:
        """
        Valida un RUT en formato numérico (sin DV).
        
        Args:
            rut: RUT en formato numérico
            
        Returns:
            True si es válido, False si no lo es
        """
        if rut is None:
            return True
        
        try:
            rut_int = int(rut)
            # RUT debe ser positivo y menor a 100 millones
            if rut_int <= 0 or rut_int >= 100000000:
                return False
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_rut_formato_chileno(self, rut: str) -> bool:
        """
        Valida un RUT en formato chileno (XXXXXXXX-X).
        
        Args:
            rut: RUT en formato chileno
            
        Returns:
            True si es válido, False si no lo es
        """
        if not rut:
            return True
        
        # Verificar formato básico
        if not isinstance(rut, str):
            return False
        
        # Debe tener un guión
        if '-' not in rut:
            return False
        
        parts = rut.split('-')
        if len(parts) != 2:
            return False
        
        # Validar parte numérica
        try:
            rut_num = int(parts[0])
            if rut_num <= 0 or rut_num >= 100000000:
                return False
        except ValueError:
            return False
        
        # Validar DV (debe ser un carácter)
        dv = parts[1]
        if len(dv) != 1:
            return False
        
        # DV puede ser número o K
        if not (dv.isdigit() or dv.upper() == 'K'):
            return False
        
        return True
    
    def _validate_montos_api(self, dte_data: Dict) -> bool:
        """
        Valida los montos en formato API.
        
        Args:
            dte_data: Datos del DTE
            
        Returns:
            True si son válidos, False si no lo son
        """
        monto_fields = ['detMntNeto', 'detMntIVA', 'detMntTotal']
        
        for field in monto_fields:
            if field in dte_data:
                monto = dte_data[field]
                if not self._validate_monto(monto):
                    self.last_error = f"Monto inválido en {field}: {monto}"
                    return False
        
        # Validar coherencia de montos si todos están presentes
        if all(field in dte_data for field in monto_fields):
            try:
                neto = float(dte_data['detMntNeto'] or 0)
                iva = float(dte_data['detMntIVA'] or 0)
                total = float(dte_data['detMntTotal'] or 0)
                
                # El total debe ser aproximadamente neto + iva
                # Permitir pequeñas diferencias por redondeo
                expected_total = neto + iva
                if abs(total - expected_total) > 1:
                    logger.warning(f"⚠️ Montos potencialmente inconsistentes: Neto={neto}, IVA={iva}, Total={total}")
                    # No fallar, solo advertir
            except (ValueError, TypeError):
                pass  # Ignorar errores de conversión
        
        return True
    
    def _validate_montos_rpa(self, dte_data: Dict) -> bool:
        """
        Valida los montos en formato RPA.
        
        Args:
            dte_data: Datos del DTE
            
        Returns:
            True si son válidos, False si no lo son
        """
        monto_fields = ['monto_neto', 'monto_iva', 'monto_total']
        
        for field in monto_fields:
            if field in dte_data:
                monto = dte_data[field]
                if not self._validate_monto(monto):
                    self.last_error = f"Monto inválido en {field}: {monto}"
                    return False
        
        return True
    
    def _validate_monto(self, monto: Any) -> bool:
        """
        Valida que un monto sea válido.
        
        Args:
            monto: Monto a validar
            
        Returns:
            True si es válido, False si no lo es
        """
        if monto is None:
            return True  # Permitir None, será 0
        
        try:
            monto_float = float(monto)
            # Los montos pueden ser negativos (notas de crédito)
            return True
        except (ValueError, TypeError):
            # Si es string, intentar limpiar y convertir
            if isinstance(monto, str):
                # Remover símbolos de moneda y separadores
                clean_monto = monto.replace('$', '').replace('.', '').replace(',', '.')
                try:
                    float(clean_monto)
                    return True
                except ValueError:
                    return False
            return False
    
    def get_last_error(self) -> Optional[str]:
        """
        Obtiene el último error de validación.
        
        Returns:
            Mensaje del último error o None si no hay error
        """
        return self.last_error