"""
Servicio para sincronizar formularios desde SII a la base de datos local
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ..models import TaxForm, TaxFormTemplate
from apps.companies.models import Company

logger = logging.getLogger(__name__)


class FormsSyncService:
    """
    Servicio para sincronizar formularios tributarios desde SII
    """

    def sync_forms_from_sii(
        self,
        formularios: List[Dict[str, Any]],
        company_rut: str,
        company_dv: str,
        form_type: str = 'f29'
    ) -> Dict[str, int]:
        """
        Sincroniza lista de formularios desde SII a la base de datos local.

        Args:
            formularios: Lista de formularios obtenidos desde SII
            company_rut: RUT de la empresa sin DV
            company_dv: Dígito verificador
            form_type: Tipo de formulario (f29, f3323, etc.)

        Returns:
            Dict con contadores de creados, actualizados y errores
        """
        logger.info(f"🔄 Iniciando sincronización de {len(formularios)} formularios {form_type.upper()}")
        logger.info(f"   Empresa: {company_rut}-{company_dv}")

        # Contadores
        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []
        created_form_ids = []
        updated_form_ids = []

        # Obtener Company
        company = self._get_company(company_rut, company_dv)
        if not company:
            raise ValueError(f"Company not found for RUT {company_rut}-{company_dv}")

        # Obtener o crear template
        template = self._get_or_create_template(form_type)

        for formulario in formularios:
            try:
                with transaction.atomic():
                    result = self._create_or_update_form(
                        formulario_data=formulario,
                        company=company,
                        company_rut=company_rut,
                        company_dv=company_dv,
                        template=template
                    )

                    if result['action'] == 'created':
                        created_count += 1
                        created_form_ids.append(result['form'].id)
                    elif result['action'] == 'updated':
                        updated_count += 1
                        updated_form_ids.append(result['form'].id)

                    logger.debug(f"   ✅ Formulario {result['folio']}: {result['action']}")

            except Exception as e:
                error_count += 1
                error_msg = f"Error procesando formulario {formulario.get('folio', 'UNKNOWN')}: {str(e)}"
                logger.error(f"   ❌ {error_msg}")
                errors.append(error_msg)

        logger.info(f"✅ Sincronización completada:")
        logger.info(f"   - Creados: {created_count}")
        logger.info(f"   - Actualizados: {updated_count}")
        logger.info(f"   - Errores: {error_count}")

        return {
            'created_count': created_count,
            'updated_count': updated_count,
            'error_count': error_count,
            'errors': errors,
            'created_form_ids': created_form_ids,
            'updated_form_ids': updated_form_ids
        }

    def _create_or_update_form(
        self,
        formulario_data: Dict[str, Any],
        company: Company,
        company_rut: str,
        company_dv: str,
        template: TaxFormTemplate
    ) -> Dict[str, Any]:
        """
        Crea o actualiza un formulario en la base de datos.

        Args:
            formulario_data: Datos del formulario desde SII
            company: Instancia de Company
            company_rut: RUT de la empresa (legacy)
            company_dv: Dígito verificador (legacy)
            template: Template del formulario

        Returns:
            Dict con información del resultado
        """
        # Extraer datos básicos
        sii_folio = formulario_data.get('folio', '')
        tax_period = self._extract_tax_period(formulario_data)

        # Buscar formulario existente - priorizar búsqueda por company
        existing_form = TaxForm.objects.filter(
            company=company,
            template=template,
            sii_folio=sii_folio
        ).first()

        # Fallback a búsqueda legacy si no se encuentra por company
        if not existing_form:
            existing_form = TaxForm.objects.filter(
                company_rut=company_rut,
                company_dv=company_dv.upper(),
                template=template,
                sii_folio=sii_folio
            ).first()

        # Convertir datos SII a formato TaxForm
        form_data = self._convert_sii_to_taxform_data(formulario_data)

        if existing_form:
            # Actualizar formulario existente
            for field, value in form_data.items():
                setattr(existing_form, field, value)
            # Asegurar que tenga referencia a company
            if not existing_form.company:
                existing_form.company = company
            existing_form.save()

            logger.debug(f"📝 Formulario actualizado: {sii_folio}")
            return {
                'action': 'updated',
                'form': existing_form,
                'folio': sii_folio
            }
        else:
            # Crear nuevo formulario
            new_form = TaxForm.objects.create(
                company=company,
                company_rut=company_rut,  # Legacy field
                company_dv=company_dv.upper(),  # Legacy field
                template=template,
                tax_period=tax_period,
                sii_folio=sii_folio,
                **form_data
            )

            logger.debug(f"➕ Formulario creado: {sii_folio}")
            return {
                'action': 'created',
                'form': new_form,
                'folio': sii_folio
            }

    def _convert_sii_to_taxform_data(self, formulario_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convierte datos del formato SII al formato TaxForm.

        Campos reales del SII:
        - folio: str (e.g., "7904207766")
        - period: str (e.g., "2024-01")
        - contributor: str (e.g., "77794858-K")
        - submission_date: str (e.g., "09/05/2024")
        - status: str (e.g., "Vigente")
        - amount: int (e.g., 42443)

        Args:
            formulario_data: Datos del formulario desde SII

        Returns:
            Dict con datos convertidos para TaxForm
        """
        # Extraer año y mes del período
        tax_year, tax_month = self._extract_year_month(formulario_data)

        # Determinar estado basado en datos SII
        status = self._determine_status(formulario_data)

        # Extraer montos - el campo se llama 'amount'
        total_tax_due = self._extract_decimal_value(formulario_data, 'amount')

        # Extraer fechas - el campo se llama 'submission_date'
        submission_date = self._extract_datetime(formulario_data, 'submission_date')

        return {
            'tax_year': tax_year,
            'tax_month': tax_month,
            'status': status,
            'due_date': None,  # No viene en los datos del SII
            'submission_date': submission_date,
            'form_data': formulario_data,  # Almacenar datos originales como JSON
            'total_tax_due': total_tax_due,
            'total_paid': 0,  # No viene en los datos del SII
            'balance_due': total_tax_due,  # Asumir que todo está pendiente
            'sii_response': {
                'extracted_at': timezone.now().isoformat(),
                'source': 'buscar_formularios',
                'original_data': formulario_data
            }
        }

    def _extract_tax_period(self, formulario_data: Dict[str, Any]) -> str:
        """Extrae el período tributario en formato YYYY-MM"""
        year, month = self._extract_year_month(formulario_data)
        if month:
            return f"{year}-{month:02d}"
        return str(year)

    def _extract_year_month(self, formulario_data: Dict[str, Any]) -> tuple:
        """Extrae año y mes del formulario usando el campo 'period'"""
        # El campo real del SII es 'period' en formato "YYYY-MM"
        period = formulario_data.get('period', '')

        if period and '-' in period:
            parts = period.split('-')
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else None
        else:
            # Fallback si no tiene el formato esperado
            year = datetime.now().year
            month = None

        return year, month

    def _determine_status(self, formulario_data: Dict[str, Any]) -> str:
        """Determina el estado del formulario basado en datos SII"""
        # El campo del SII es 'status', mapear a nuestros estados
        sii_status = formulario_data.get('status', '').lower()
        submission_date = formulario_data.get('submission_date')

        if 'vigente' in sii_status and submission_date:
            return 'submitted'  # Presentado y vigente
        elif submission_date:
            return 'accepted'   # Presentado
        else:
            return 'draft'      # No presentado

    def _extract_decimal_value(self, data: Dict[str, Any], field: str) -> Optional[Decimal]:
        """Extrae un valor decimal de los datos"""
        value = data.get(field)
        if value is not None:
            try:
                return Decimal(str(value))
            except:
                pass
        return None

    def _extract_date(self, data: Dict[str, Any], field: str):
        """Extrae una fecha de los datos"""
        value = data.get(field)
        if value:
            try:
                if isinstance(value, str):
                    # Intentar parsear diferentes formatos de fecha
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                        try:
                            return datetime.strptime(value, fmt).date()
                        except ValueError:
                            continue
                elif hasattr(value, 'date'):
                    return value.date()
            except:
                pass
        return None

    def _extract_datetime(self, data: Dict[str, Any], field: str):
        """Extrae un datetime de los datos usando el formato del SII (DD/MM/YYYY)"""
        value = data.get(field)
        if value:
            try:
                if isinstance(value, str):
                    # El SII usa formato "DD/MM/YYYY"
                    dt = datetime.strptime(value, '%d/%m/%Y')
                    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                elif hasattr(value, 'isoformat'):
                    return value
            except ValueError as e:
                logger.warning(f"No se pudo parsear fecha '{value}': {e}")
        return None

    def _get_or_create_template(self, form_type: str) -> TaxFormTemplate:
        """
        Obtiene o crea el template para el tipo de formulario.

        Args:
            form_type: Tipo de formulario (f29, f3323, etc.)

        Returns:
            TaxFormTemplate instance
        """
        template, created = TaxFormTemplate.objects.get_or_create(
            form_code=form_type.upper(),
            defaults={
                'name': self._get_form_name(form_type),
                'form_type': form_type.lower(),
                'description': f'Template para formulario {form_type.upper()}',
                'form_structure': self._get_default_structure(form_type),
                'validation_rules': {},
                'calculation_rules': {}
            }
        )

        if created:
            logger.info(f"📋 Template creado para formulario {form_type.upper()}")

        return template

    def _get_form_name(self, form_type: str) -> str:
        """Retorna el nombre completo del formulario"""
        names = {
            'f29': 'Formulario 29 - Declaración Mensual IVA',
            'f3323': 'Formulario 3323 - Pago Provisional Mensual Renta',
            'f50': 'Formulario 50 - Declaración Anual Renta',
            'f22': 'Formulario 22 - Declaración Anual Renta'
        }
        return names.get(form_type.lower(), f'Formulario {form_type.upper()}')

    def _get_default_structure(self, form_type: str) -> Dict[str, Any]:
        """Retorna la estructura por defecto del formulario"""
        if form_type.lower() == 'f29':
            return {
                'sections': [
                    {
                        'name': 'datos_generales',
                        'fields': ['periodo', 'rut', 'razon_social']
                    },
                    {
                        'name': 'iva',
                        'fields': ['iva_debito', 'iva_credito', 'impuesto_total']
                    },
                    {
                        'name': 'pagos',
                        'fields': ['total_pagado', 'saldo_favor', 'saldo_diferencia']
                    }
                ]
            }
        return {'sections': []}

    def _get_company(self, company_rut: str, company_dv: str) -> Optional[Company]:
        """
        Obtiene la instancia de Company basada en RUT.
        Normaliza el dígito verificador y hace búsqueda case-insensitive.

        Args:
            company_rut: RUT sin dígito verificador
            company_dv: Dígito verificador

        Returns:
            Company instance o None si no se encuentra
        """
        # Normalizar dígito verificador a mayúscula
        company_dv = company_dv.upper()
        full_rut = f"{company_rut}-{company_dv}"

        try:
            # Buscar por tax_id completo (case-insensitive)
            return Company.objects.get(tax_id__iexact=full_rut)
        except Company.DoesNotExist:
            try:
                # Buscar sin puntos en el RUT (formato normalizado)
                normalized_rut = f"{company_rut.replace('.', '')}-{company_dv}"
                return Company.objects.get(tax_id__iexact=normalized_rut)
            except Company.DoesNotExist:
                # Último intento: buscar con variaciones de caso
                try:
                    # Probar con dígito verificador en minúscula
                    lower_rut = f"{company_rut}-{company_dv.lower()}"
                    return Company.objects.get(tax_id__iexact=lower_rut)
                except Company.DoesNotExist:
                    logger.warning(f"Company not found for RUT {full_rut} (tried variations: {normalized_rut}, {lower_rut})")
                    return None
        except Company.MultipleObjectsReturned:
            # En caso de múltiples, tomar el primero
            logger.warning(f"Multiple companies found for RUT {full_rut}, taking first")
            return Company.objects.filter(tax_id__iexact=full_rut).first()