"""
Comando para crear templates de formularios tributarios por defecto
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.forms.models import TaxFormTemplate


class Command(BaseCommand):
    help = 'Crea templates de formularios tributarios por defecto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--form-type',
            type=str,
            help='Tipo específico de formulario a crear (f29, f3323, etc.)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Fuerza la recreación de templates existentes',
        )

    def handle(self, *args, **options):
        form_type = options.get('form_type')
        force = options.get('force', False)

        if form_type:
            self._create_template(form_type, force)
        else:
            self._create_all_templates(force)

    def _create_all_templates(self, force=False):
        """Crea todos los templates por defecto"""
        self.stdout.write(self.style.SUCCESS('🚀 Creando templates de formularios...'))

        templates = ['f29', 'f3323', 'f50', 'f22', 'f1924', 'f1923']

        for template_type in templates:
            self._create_template(template_type, force)

        self.stdout.write(self.style.SUCCESS('✅ Templates creados exitosamente'))

    def _create_template(self, form_type, force=False):
        """Crea un template específico"""
        form_code = form_type.upper()

        # Verificar si ya existe
        existing = TaxFormTemplate.objects.filter(form_code=form_code).first()
        if existing and not force:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Template {form_code} ya existe. Usa --force para sobrescribir.')
            )
            return

        with transaction.atomic():
            if existing and force:
                existing.delete()
                self.stdout.write(f'🗑️  Template {form_code} eliminado')

            template_data = self._get_template_data(form_type)

            template = TaxFormTemplate.objects.create(**template_data)

            self.stdout.write(
                self.style.SUCCESS(f'✅ Template {form_code} creado: {template.name}')
            )

    def _get_template_data(self, form_type):
        """Retorna datos del template según el tipo"""
        templates_data = {
            'f29': {
                'form_code': 'F29',
                'name': 'Formulario 29 - Declaración Mensual IVA',
                'description': 'Declaración mensual de IVA para empresas chilenas',
                'form_type': 'f29',
                'form_structure': {
                    'sections': [
                        {
                            'name': 'datos_generales',
                            'title': 'Datos Generales',
                            'fields': [
                                {'code': 'periodo', 'name': 'Período Tributario', 'type': 'text'},
                                {'code': 'rut', 'name': 'RUT', 'type': 'text'},
                                {'code': 'razon_social', 'name': 'Razón Social', 'type': 'text'}
                            ]
                        },
                        {
                            'name': 'ventas_iva',
                            'title': 'Ventas y Servicios Gravados con IVA',
                            'fields': [
                                {'code': 'ventas_netas', 'name': 'Ventas Netas', 'type': 'decimal'},
                                {'code': 'iva_debito', 'name': 'IVA Débito Fiscal', 'type': 'decimal'}
                            ]
                        },
                        {
                            'name': 'compras_iva',
                            'title': 'Compras Gravadas con IVA',
                            'fields': [
                                {'code': 'compras_netas', 'name': 'Compras Netas', 'type': 'decimal'},
                                {'code': 'iva_credito', 'name': 'IVA Crédito Fiscal', 'type': 'decimal'}
                            ]
                        },
                        {
                            'name': 'liquidacion',
                            'title': 'Liquidación del Impuesto',
                            'fields': [
                                {'code': 'impuesto_total', 'name': 'Total Impuesto Determinado', 'type': 'decimal'},
                                {'code': 'pagos_previos', 'name': 'Pagos Provisionales', 'type': 'decimal'},
                                {'code': 'saldo_diferencia', 'name': 'Saldo a Pagar/Favor', 'type': 'decimal'}
                            ]
                        }
                    ]
                },
                'validation_rules': {
                    'required_fields': ['periodo', 'rut'],
                    'calculation_checks': [
                        'iva_debito = ventas_netas * 0.19',
                        'iva_credito <= compras_netas * 0.19'
                    ]
                },
                'calculation_rules': {
                    'iva_debito': 'ventas_netas * 0.19',
                    'iva_credito': 'compras_netas * 0.19',
                    'impuesto_total': 'iva_debito - iva_credito',
                    'saldo_diferencia': 'impuesto_total - pagos_previos'
                }
            },
            'f3323': {
                'form_code': 'F3323',
                'name': 'Formulario 3323 - Pago Provisional Mensual Renta',
                'description': 'Pago provisional mensual obligatorio de impuesto a la renta',
                'form_type': 'f3323',
                'form_structure': {
                    'sections': [
                        {
                            'name': 'datos_generales',
                            'title': 'Datos Generales',
                            'fields': [
                                {'code': 'periodo', 'name': 'Mes Comercial', 'type': 'text'},
                                {'code': 'rut', 'name': 'RUT', 'type': 'text'}
                            ]
                        },
                        {
                            'name': 'ingresos',
                            'title': 'Ingresos del Mes',
                            'fields': [
                                {'code': 'ingresos_brutos', 'name': 'Ingresos Brutos', 'type': 'decimal'},
                                {'code': 'factor_actualizacion', 'name': 'Factor de Actualización', 'type': 'decimal'}
                            ]
                        }
                    ]
                }
            },
            'f50': {
                'form_code': 'F50',
                'name': 'Formulario 50 - Declaración Anual Renta',
                'description': 'Declaración anual de impuesto a la renta',
                'form_type': 'f50',
                'form_structure': {'sections': []}
            },
            'f22': {
                'form_code': 'F22',
                'name': 'Formulario 22 - Declaración Anual Renta',
                'description': 'Declaración anual de impuesto a la renta',
                'form_type': 'f22',
                'form_structure': {'sections': []}
            },
            'f1924': {
                'form_code': 'F1924',
                'name': 'Formulario 1924 - Solicitud de Devolución',
                'description': 'Solicitud de devolución de impuestos',
                'form_type': 'f1924',
                'form_structure': {'sections': []}
            },
            'f1923': {
                'form_code': 'F1923',
                'name': 'Formulario 1923 - Declaración Jurada',
                'description': 'Declaración jurada anual',
                'form_type': 'f1923',
                'form_structure': {'sections': []}
            }
        }

        return templates_data.get(form_type.lower(), {
            'form_code': form_type.upper(),
            'name': f'Formulario {form_type.upper()}',
            'description': f'Template para formulario {form_type.upper()}',
            'form_type': form_type.lower(),
            'form_structure': {'sections': []},
            'validation_rules': {},
            'calculation_rules': {}
        })