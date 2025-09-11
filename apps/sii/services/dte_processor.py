"""
Procesador de DTEs (Documentos Tributarios Electrónicos)
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from django.db import transaction

from apps.companies.models import Company
from apps.documents.models import Document, DocumentType
from ..models import SIISyncLog

logger = logging.getLogger(__name__)


class DTEProcessor:
    """
    Procesador especializado para DTEs.
    Maneja la lógica de procesamiento, validación y almacenamiento.
    """
    
    def __init__(self, company: Company):
        """
        Inicializa el procesador de DTEs.
        
        Args:
            company: Empresa propietaria de los documentos
        """
        self.company = company
        self.validator = None
        self.mapper = None
        
        # Inicializar validador y mapper
        self._initialize_dependencies()
    
    def _initialize_dependencies(self):
        """Inicializa las dependencias del procesador"""
        from .dte_validator import DTEValidator
        from .dte_mapper import DTEMapper
        
        self.validator = DTEValidator()
        self.mapper = DTEMapper(self.company)
    
    def process_batch(
        self,
        dtes: List[Dict], 
        sync_log: Optional[SIISyncLog] = None
    ) -> Dict[str, Any]:
        """
        Procesa un lote de DTEs.
        
        Args:
            dtes: Lista de DTEs a procesar
            sync_log: Log de sincronización (opcional)
            
        Returns:
            Dict con estadísticas del procesamiento
        """
        results = {
            'processed': 0,
            'created': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }
        
        if not dtes:
            logger.info("📊 No hay DTEs para procesar")
            return results
        
        logger.info(f"📊 Procesando lote de {len(dtes)} DTEs para empresa {self.company.tax_id}")
        
        # Procesar cada DTE individualmente para evitar que un error rompa todo
        for dte_data in dtes:
            try:
                self._process_single_dte(dte_data, results)
            except Exception as e:
                results['errors'] += 1
                error_msg = f"Error procesando DTE: {str(e)}"
                results['error_details'].append(error_msg)
                logger.error(error_msg)
                
                # Log información del DTE problemático para debugging
                if dte_data and isinstance(dte_data, dict):
                    folio = dte_data.get('detNroDoc') or dte_data.get('folio', 'N/A')
                    tipo = dte_data.get('detTipoDoc') or dte_data.get('tipo_documento', 'N/A')
                    logger.error(f"   DTE problemático - Folio: {folio}, Tipo: {tipo}")
        
        logger.info(f"✅ Procesamiento completado: {results['created']} creados, {results['updated']} actualizados, {results['errors']} errores")
        
        return results
    
    def _process_single_dte(
        self,
        dte_data: Dict,
        results: Dict
    ):
        """
        Procesa un DTE individual.
        
        Args:
            dte_data: Datos del DTE
            results: Dict para acumular resultados
            
        Raises:
            Exception: Si hay error en el procesamiento
        """
        # Validar DTE
        if not self.validator.validate(dte_data):
            raise ValueError(f"DTE inválido: {self.validator.get_last_error()}")
        
        # Mapear datos del DTE
        dte_fields = self.mapper.map_to_document(dte_data)
        
        # Guardar en base de datos con transacción atómica
        with transaction.atomic():
            # Buscar DTE existente
            existing = self._find_existing_document(dte_fields)
            
            if existing:
                # Actualizar documento existente
                self._update_document(existing, dte_fields)
                results['updated'] += 1
                logger.debug(f"📝 DTE actualizado: Folio {dte_fields.get('folio')}, Tipo {dte_fields.get('document_type')}")
            else:
                # Crear nuevo documento
                self._create_document(dte_fields)
                results['created'] += 1
                logger.debug(f"🆕 DTE creado: Folio {dte_fields.get('folio')}, Tipo {dte_fields.get('document_type')}")
        
        results['processed'] += 1
    
    def _find_existing_document(self, dte_fields: Dict) -> Optional[Document]:
        """
        Busca un documento existente con los mismos identificadores únicos.
        
        Args:
            dte_fields: Campos del documento
            
        Returns:
            Document si existe, None si no existe
        """
        try:
            # Los campos únicos según la constraint son:
            # issuer_company_rut, issuer_company_dv, document_type, folio
            return Document.objects.filter(
                issuer_company_rut=dte_fields['issuer_company_rut'],
                issuer_company_dv=dte_fields['issuer_company_dv'],
                document_type=dte_fields['document_type'],
                folio=dte_fields['folio']
            ).first()
        except Exception as e:
            logger.warning(f"⚠️ Error buscando documento existente: {e}")
            return None
    
    def _update_document(self, document: Document, dte_fields: Dict):
        """
        Actualiza un documento existente con nuevos datos.
        
        Args:
            document: Documento a actualizar
            dte_fields: Nuevos campos del documento
        """
        # Actualizar todos los campos excepto los de auditoría
        fields_to_skip = ['id', 'created_at', 'updated_at', 'sync_log']
        
        for field, value in dte_fields.items():
            if field not in fields_to_skip and hasattr(document, field):
                setattr(document, field, value)
        
        # Guardar cambios
        document.save()
    
    def _create_document(self, dte_fields: Dict) -> Document:
        """
        Crea un nuevo documento en la base de datos.
        
        Args:
            dte_fields: Campos del documento
            
        Returns:
            Document creado
        """
        return Document.objects.create(**dte_fields)