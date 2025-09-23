"""
Servicio para extraer detalles completos de formularios F29 desde SII
"""
import logging
from typing import Dict, Any, Optional, List
from django.utils import timezone

from ..models import TaxForm
from apps.sii.rpa.f29.f29_service import F29Service
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class F29DetailExtractionService:
    """
    Servicio para extraer detalles completos de formularios F29 usando obtener_formulario_f29
    """

    def __init__(self, tax_id: str = None, password: str = None):
        """
        Inicializar servicio con credenciales SII

        Args:
            tax_id: RUT con formato XX.XXX.XXX-X
            password: Contraseña SII
        """
        self.tax_id = tax_id
        self.password = password

    def extract_form_details(self, tax_form: TaxForm, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Extrae los detalles completos de un formulario F29 específico.

        Args:
            tax_form: Instancia de TaxForm
            force_refresh: Si True, fuerza nueva extracción aunque ya existan detalles

        Returns:
            Dict con resultado de la extracción
        """
        logger.info(f"🔍 Extrayendo detalles F29 para folio: {tax_form.sii_folio}")

        # Verificar si ya tiene detalles y no se fuerza refresh
        if tax_form.details_extracted and not force_refresh:
            logger.info(f"  ✅ Formulario ya tiene detalles extraídos ({tax_form.details_extracted_at})")
            return {
                'status': 'already_extracted',
                'message': 'Formulario ya tiene detalles extraídos',
                'extracted_at': tax_form.details_extracted_at.isoformat() if tax_form.details_extracted_at else None,
                'method': tax_form.details_extraction_method
            }

        # Verificar que tiene folio SII
        if not tax_form.sii_folio:
            logger.warning(f"  ❌ Formulario no tiene folio SII")
            return {
                'status': 'error',
                'message': 'Formulario no tiene folio SII para extraer detalles'
            }

        # Obtener credenciales de la company si no se proporcionaron
        if not self.tax_id or not self.password:
            credentials = self._get_company_sii_credentials(tax_form.company)
            if not credentials:
                return {
                    'status': 'error',
                    'message': 'No se encontraron credenciales SII para la company'
                }
            self.tax_id, self.password = credentials

        try:
            # Crear servicio F29
            f29_service = F29Service(self.tax_id, self.password, headless=True)

            # Extraer detalles usando obtener_formulario_f29
            resultado = f29_service.obtener_formulario_f29(
                folio=tax_form.sii_folio,
                periodo=tax_form.tax_period
            )

            if resultado['status'] == 'success':
                # Formatear campos extraídos
                campos_formateados = self._format_extracted_fields(resultado.get('campos_extraidos', []))

                # Guardar detalles en el formulario
                tax_form.mark_details_extracted(
                    method='f29_rpa_service',
                    details_data={
                        'extraction_timestamp': timezone.now().isoformat(),
                        'folio': resultado['folio'],
                        'periodo': resultado['periodo'],
                        'total_campos': resultado['total_campos'],
                        'campos_extraidos': campos_formateados,
                        'campos_extraidos_raw': resultado.get('campos_extraidos', []),  # Mantener originales
                        'subtablas': resultado.get('subtablas', []),
                        'extraction_method': resultado.get('extraction_method', 'f29_rpa'),
                        'original_response': resultado
                    }
                )

                logger.info(f"  ✅ Detalles extraídos exitosamente: {resultado['total_campos']} campos")
                return {
                    'status': 'success',
                    'message': f'Detalles extraídos exitosamente: {resultado["total_campos"]} campos',
                    'folio': resultado['folio'],
                    'total_campos': resultado['total_campos'],
                    'extracted_at': tax_form.details_extracted_at.isoformat()
                }

            else:
                error_msg = resultado.get('message', 'Error desconocido')
                logger.error(f"  ❌ Error extrayendo detalles: {error_msg}")
                return {
                    'status': 'error',
                    'message': f'Error extrayendo detalles: {error_msg}'
                }

        except Exception as e:
            logger.error(f"  ❌ Excepción extrayendo detalles: {str(e)}")
            return {
                'status': 'error',
                'message': f'Excepción extrayendo detalles: {str(e)}'
            }

        finally:
            try:
                f29_service.close()
            except:
                pass

    def extract_multiple_forms_details(
        self,
        tax_forms: List[TaxForm],
        force_refresh: bool = False,
        max_forms: int = 10
    ) -> Dict[str, Any]:
        """
        Extrae detalles de múltiples formularios F29.

        Args:
            tax_forms: Lista de TaxForm instances
            force_refresh: Si True, fuerza nueva extracción aunque ya existan detalles
            max_forms: Máximo número de formularios a procesar

        Returns:
            Dict con resumen de resultados
        """
        logger.info(f"🔄 Extrayendo detalles de {len(tax_forms)} formularios (máx: {max_forms})")

        # Filtrar formularios que necesitan extracción
        if not force_refresh:
            forms_to_process = [f for f in tax_forms if f.needs_detail_extraction]
        else:
            forms_to_process = tax_forms

        # Limitar cantidad a procesar
        forms_to_process = forms_to_process[:max_forms]

        logger.info(f"  📋 Procesando {len(forms_to_process)} formularios")

        # Contadores
        success_count = 0
        error_count = 0
        already_extracted_count = 0
        results = []

        for i, tax_form in enumerate(forms_to_process, 1):
            logger.info(f"  📝 Procesando {i}/{len(forms_to_process)}: {tax_form.sii_folio}")

            resultado = self.extract_form_details(tax_form, force_refresh)

            if resultado['status'] == 'success':
                success_count += 1
            elif resultado['status'] == 'already_extracted':
                already_extracted_count += 1
            else:
                error_count += 1

            results.append({
                'form_id': tax_form.id,
                'folio': tax_form.sii_folio,
                'period': tax_form.tax_period,
                'result': resultado
            })

        logger.info(f"✅ Extracción múltiple completada:")
        logger.info(f"  - Exitosos: {success_count}")
        logger.info(f"  - Ya extraídos: {already_extracted_count}")
        logger.info(f"  - Errores: {error_count}")

        return {
            'status': 'completed',
            'total_processed': len(forms_to_process),
            'success_count': success_count,
            'error_count': error_count,
            'already_extracted_count': already_extracted_count,
            'results': results
        }

    def get_forms_needing_details(self, company: Company = None, limit: int = 50) -> List[TaxForm]:
        """
        Obtiene formularios que necesitan extracción de detalles.

        Args:
            company: Company específica (opcional)
            limit: Máximo número de formularios a retornar

        Returns:
            Lista de TaxForm que necesitan extracción
        """
        queryset = TaxForm.objects.filter(
            details_extracted=False,
            sii_folio__isnull=False,
            sii_folio__gt=''
        ).order_by('-tax_year', '-tax_month')

        if company:
            queryset = queryset.filter(company=company)

        return list(queryset[:limit])

    def _get_company_sii_credentials(self, company: Company) -> Optional[tuple]:
        """
        Obtiene credenciales SII de la company.
        Por ahora usa credenciales por defecto, en futuro podría usar company-specific.

        Args:
            company: Company instance

        Returns:
            Tuple (tax_id, password) o None si no disponible
        """
        # TODO: En futuro obtener credenciales específicas de la company
        from django.conf import settings

        tax_id = getattr(settings, 'SII_TAX_ID', '77794858-K')
        password = getattr(settings, 'SII_PASSWORD', 'SiiPfufl574@#')

        if tax_id and password:
            return (tax_id, password)

        return None

    def _format_extracted_fields(self, campos_extraidos: List[Dict]) -> List[Dict]:
        """
        Formatea los campos extraídos del F29 para almacenamiento.

        Convierte valores chilenos (ej: "1.023.785", "0,25") a formato numérico.

        Args:
            campos_extraidos: Lista de diccionarios con campos extraídos del F29

        Returns:
            Lista de campos con valores formateados
        """
        if not campos_extraidos:
            return []

        campos_formateados = []

        for campo in campos_extraidos:
            campo_formateado = campo.copy()

            # El F29Service usa 'value' en lugar de 'valor'
            valor_original = campo.get('value', campo.get('valor', ''))
            if valor_original and isinstance(valor_original, str):
                valor_formateado = self._format_chilean_value(valor_original)
                campo_formateado['value_formatted'] = valor_formateado
                campo_formateado['value_original'] = valor_original

            campos_formateados.append(campo_formateado)

        return campos_formateados

    def _format_chilean_value(self, valor: str) -> Optional[float]:
        """
        Convierte valores monetarios chilenos a float.

        Ejemplos:
        - "1.023.785" -> 1023785.0
        - "0,25" -> 0.25
        - "123.456,78" -> 123456.78
        - "" -> None
        - "N/A" -> None

        Args:
            valor: String con valor en formato chileno

        Returns:
            Float con valor numérico o None si no se puede convertir
        """
        if not valor or not isinstance(valor, str):
            return None

        # Limpiar valor
        valor = valor.strip()
        if not valor or valor.upper() in ['N/A', 'NO DISPONIBLE', '-', '']:
            return None

        try:
            # Remover separadores de miles (puntos) y convertir separador decimal (coma a punto)
            # Si tiene coma, es separador decimal
            if ',' in valor:
                # Formato: "123.456,78" -> "123456.78"
                partes = valor.split(',')
                if len(partes) == 2:
                    parte_entera = partes[0].replace('.', '')  # Quitar puntos de miles
                    parte_decimal = partes[1]
                    valor_limpio = f"{parte_entera}.{parte_decimal}"
                else:
                    return None
            else:
                # Solo puntos - pueden ser separadores de miles: "1.023.785" -> "1023785"
                # O puede ser valor simple: "123" -> "123"
                valor_limpio = valor.replace('.', '')

            return float(valor_limpio)

        except (ValueError, TypeError):
            logger.warning(f"No se pudo formatear valor: '{valor}'")
            return None