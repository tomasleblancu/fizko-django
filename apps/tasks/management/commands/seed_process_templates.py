"""
Django management command to seed process templates for Chilean tax processes
"""

import json
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.tasks.models import ProcessTemplate, TaskCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seeds process templates for common Chilean tax processes (F29, F22, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing templates before seeding',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)

        try:
            with transaction.atomic():
                # Clear existing templates if requested
                if options.get('clear'):
                    self.stdout.write(self.style.WARNING('Clearing existing templates...'))
                    ProcessTemplate.objects.all().delete()
                    TaskCategory.objects.all().delete()

                # Create task categories
                self._create_task_categories()

                # Seed process templates
                self._seed_f29_monthly_template()
                self._seed_f22_annual_template()
                self._seed_document_sync_template()
                self._seed_iva_purchase_books_template()
                self._seed_iva_sales_books_template()
                self._seed_f3323_template()

                self.stdout.write(self.style.SUCCESS('✅ Process templates seeded successfully!'))

                # Show summary
                template_count = ProcessTemplate.objects.count()
                category_count = TaskCategory.objects.count()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSummary:\n'
                        f'- Task Categories: {category_count}\n'
                        f'- Process Templates: {template_count}'
                    )
                )

        except Exception as e:
            raise CommandError(f'Error seeding templates: {str(e)}')

    def _create_task_categories(self):
        """Create standard task categories"""
        categories = [
            {
                'name': 'Tributario',
                'description': 'Tareas relacionadas con declaraciones y pagos de impuestos',
                'color': '#4CAF50',
                'icon': 'receipt_long'
            },
            {
                'name': 'Documentos',
                'description': 'Gestión y procesamiento de documentos tributarios electrónicos',
                'color': '#2196F3',
                'icon': 'description'
            },
            {
                'name': 'Sincronización',
                'description': 'Tareas de sincronización con el SII',
                'color': '#FF9800',
                'icon': 'sync'
            },
            {
                'name': 'Revisión',
                'description': 'Tareas de revisión y aprobación manual',
                'color': '#9C27B0',
                'icon': 'task_alt'
            },
            {
                'name': 'Pagos',
                'description': 'Gestión de pagos y cobranzas',
                'color': '#F44336',
                'icon': 'payments'
            },
            {
                'name': 'Análisis',
                'description': 'Análisis y reportes financieros',
                'color': '#00BCD4',
                'icon': 'analytics'
            }
        ]

        for cat_data in categories:
            category, created = TaskCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'color': cat_data['color'],
                    'icon': cat_data['icon'],
                    'is_active': True
                }
            )
            if created and self.verbose:
                self.stdout.write(f"  ✓ Created category: {category.name}")

    def _seed_f29_monthly_template(self):
        """Seed template for F29 monthly tax declaration"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Sincronizar documentos del período',
                    'description': 'Descarga automática de facturas emitidas y recibidas desde el SII',
                    'task_type': 'automatic',
                    'category': 'Sincronización',
                    'estimated_duration_hours': 1,
                    'due_date_offset_days': -10,  # 10 días antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 2,
                    'title': 'Procesar documentos tributarios',
                    'description': 'Clasificación y cálculo automático de IVA de compras y ventas',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 2,
                    'due_date_from_previous': 1,  # 1 día después de la tarea anterior
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 3,
                    'title': 'Generar borrador F29',
                    'description': 'Generación automática del formulario F29 con los datos procesados',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 1,
                    'due_date_offset_days': -7,  # 7 días antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False,
                    'execution_conditions': {
                        'previous_task_status': 'completed'
                    }
                },
                {
                    'order': 4,
                    'title': 'Revisar y ajustar F29',
                    'description': 'Revisión manual del formulario generado y ajustes necesarios',
                    'task_type': 'manual',
                    'category': 'Revisión',
                    'estimated_duration_hours': 4,
                    'due_date_offset_days': -5,  # 5 días antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Aprobar F29 para envío',
                    'description': 'Aprobación final del contribuyente antes del envío al SII',
                    'task_type': 'manual',
                    'category': 'Revisión',
                    'estimated_duration_hours': 1,
                    'due_date_offset_days': -3,  # 3 días antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False,
                    'execution_conditions': {
                        'previous_task_status': 'completed'
                    }
                },
                {
                    'order': 6,
                    'title': 'Enviar F29 al SII',
                    'description': 'Envío automático de la declaración al Servicio de Impuestos Internos',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -1,  # 1 día antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False,
                    'execution_conditions': {
                        'previous_task_status': 'completed',
                        'require_approval': True
                    }
                },
                {
                    'order': 7,
                    'title': 'Gestionar pago F29',
                    'description': 'Coordinación del pago de impuestos si corresponde',
                    'task_type': 'manual',
                    'category': 'Pagos',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': 0,  # El día del vencimiento
                    'optional': True,  # Opcional porque puede no haber impuesto a pagar
                    'can_run_parallel': False
                },
                {
                    'order': 8,
                    'title': 'Archivar comprobantes',
                    'description': 'Archivo de comprobantes de declaración y pago',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 0.5,
                    'due_date_from_previous': 1,
                    'optional': False,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'form_type': 'f29',
                'recurrence': 'monthly',
                'due_day': 12,  # F29 vence el día 12 de cada mes
                'auto_generate': True,
                'notification_days': [10, 5, 3, 1],  # Días antes del vencimiento para notificar
                'requires_sii_credentials': True,
                'supports_auto_submission': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='F29 - Declaración Mensual IVA',
            process_type='tax_monthly',
            defaults={
                'description': (
                    'Proceso mensual para la declaración y pago del Formulario 29 (IVA). '
                    'Incluye sincronización de documentos, cálculo automático, revisión '
                    'y envío al SII. Vence el día 12 de cada mes.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created F29 monthly template'))
        elif self.verbose:
            self.stdout.write('  - F29 template already exists')

    def _seed_f22_annual_template(self):
        """Seed template for F22 annual tax declaration"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Recopilar información anual',
                    'description': 'Consolidación de toda la información tributaria del año',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 8,
                    'due_date_offset_days': -60,  # 2 meses antes del vencimiento
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 2,
                    'title': 'Revisar consistencia F29',
                    'description': 'Verificación de que todos los F29 del año estén correctos',
                    'task_type': 'automatic',
                    'category': 'Análisis',
                    'estimated_duration_hours': 4,
                    'due_date_from_previous': 3,
                    'optional': False,
                    'can_run_parallel': True
                },
                {
                    'order': 3,
                    'title': 'Calcular depreciación activos',
                    'description': 'Cálculo de depreciación de activos fijos para el período',
                    'task_type': 'manual',
                    'category': 'Tributario',
                    'estimated_duration_hours': 6,
                    'due_date_offset_days': -45,
                    'optional': False,
                    'can_run_parallel': True
                },
                {
                    'order': 4,
                    'title': 'Preparar balance tributario',
                    'description': 'Elaboración del balance general con ajustes tributarios',
                    'task_type': 'manual',
                    'category': 'Tributario',
                    'estimated_duration_hours': 16,
                    'due_date_offset_days': -30,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Calcular RLI',
                    'description': 'Determinación de la Renta Líquida Imponible',
                    'task_type': 'manual',
                    'category': 'Tributario',
                    'estimated_duration_hours': 8,
                    'due_date_offset_days': -20,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 6,
                    'title': 'Generar borrador F22',
                    'description': 'Generación del formulario F22 con todos los datos',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': -15,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 7,
                    'title': 'Revisión contador externo',
                    'description': 'Revisión y validación por contador externo si aplica',
                    'task_type': 'manual',
                    'category': 'Revisión',
                    'estimated_duration_hours': 24,
                    'due_date_offset_days': -10,
                    'optional': True,
                    'can_run_parallel': False
                },
                {
                    'order': 8,
                    'title': 'Aprobar F22',
                    'description': 'Aprobación final del contribuyente',
                    'task_type': 'manual',
                    'category': 'Revisión',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': -5,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 9,
                    'title': 'Enviar F22 al SII',
                    'description': 'Envío de la declaración anual de renta',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 1,
                    'due_date_offset_days': -2,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 10,
                    'title': 'Gestionar pago/devolución',
                    'description': 'Gestión del pago de impuestos o solicitud de devolución',
                    'task_type': 'manual',
                    'category': 'Pagos',
                    'estimated_duration_hours': 4,
                    'due_date_offset_days': 0,
                    'optional': False,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'form_type': 'f22',
                'recurrence': 'annual',
                'due_month': 4,  # Abril
                'due_day': 30,  # 30 de abril
                'auto_generate': True,
                'notification_days': [60, 30, 15, 7, 3, 1],
                'requires_sii_credentials': True,
                'requires_external_accountant': False,  # Depende del contribuyente
                'supports_auto_submission': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='F22 - Declaración Anual de Renta',
            process_type='tax_annual',
            defaults={
                'description': (
                    'Proceso anual para la preparación y presentación del Formulario 22 '
                    '(Declaración de Renta). Incluye consolidación de información anual, '
                    'cálculos tributarios, revisión y envío al SII. Vence el 30 de abril.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created F22 annual template'))
        elif self.verbose:
            self.stdout.write('  - F22 template already exists')

    def _seed_document_sync_template(self):
        """Seed template for periodic document synchronization"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Sincronizar facturas emitidas',
                    'description': 'Descarga de facturas emitidas desde el SII',
                    'task_type': 'automatic',
                    'category': 'Sincronización',
                    'estimated_duration_hours': 0.5,
                    'optional': False,
                    'can_run_parallel': True
                },
                {
                    'order': 2,
                    'title': 'Sincronizar facturas recibidas',
                    'description': 'Descarga de facturas recibidas desde el SII',
                    'task_type': 'automatic',
                    'category': 'Sincronización',
                    'estimated_duration_hours': 0.5,
                    'optional': False,
                    'can_run_parallel': True
                },
                {
                    'order': 3,
                    'title': 'Procesar y clasificar documentos',
                    'description': 'Clasificación automática de documentos por tipo y categoría',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 1,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 4,
                    'title': 'Detectar inconsistencias',
                    'description': 'Identificación de documentos faltantes o con errores',
                    'task_type': 'automatic',
                    'category': 'Análisis',
                    'estimated_duration_hours': 0.5,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Generar reporte de sincronización',
                    'description': 'Reporte con resumen de documentos procesados',
                    'task_type': 'automatic',
                    'category': 'Análisis',
                    'estimated_duration_hours': 0.25,
                    'optional': False,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'sync_type': 'full',
                'recurrence': 'weekly',
                'day_of_week': 1,  # Lunes
                'auto_generate': True,
                'notification_on_errors': True,
                'requires_sii_credentials': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='Sincronización Semanal de Documentos',
            process_type='document_sync',
            defaults={
                'description': (
                    'Proceso automatizado para sincronizar documentos tributarios '
                    'con el SII. Se ejecuta semanalmente para mantener actualizada '
                    'la información de facturas emitidas y recibidas.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created Document Sync template'))
        elif self.verbose:
            self.stdout.write('  - Document Sync template already exists')

    def _seed_iva_purchase_books_template(self):
        """Seed template for IVA purchase books"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Descargar libro de compras SII',
                    'description': 'Descarga del libro de compras desde el portal del SII',
                    'task_type': 'automatic',
                    'category': 'Sincronización',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -8,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 2,
                    'title': 'Validar facturas de compra',
                    'description': 'Verificación de validez y consistencia de facturas',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 1,
                    'due_date_from_previous': 1,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 3,
                    'title': 'Clasificar gastos',
                    'description': 'Clasificación de gastos por categoría contable',
                    'task_type': 'manual',
                    'category': 'Tributario',
                    'estimated_duration_hours': 3,
                    'due_date_offset_days': -5,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 4,
                    'title': 'Calcular IVA crédito fiscal',
                    'description': 'Cálculo del IVA crédito fiscal del período',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -4,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Generar informe libro de compras',
                    'description': 'Generación del informe detallado del libro de compras',
                    'task_type': 'automatic',
                    'category': 'Análisis',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -3,
                    'optional': False,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'book_type': 'purchases',
                'recurrence': 'monthly',
                'due_day': 10,
                'auto_generate': True,
                'requires_sii_credentials': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='Libro de Compras Mensual',
            process_type='custom',
            defaults={
                'description': (
                    'Proceso mensual para gestionar el libro de compras. '
                    'Incluye descarga desde el SII, validación de facturas, '
                    'clasificación de gastos y cálculo del IVA crédito fiscal.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created IVA Purchase Books template'))
        elif self.verbose:
            self.stdout.write('  - IVA Purchase Books template already exists')

    def _seed_iva_sales_books_template(self):
        """Seed template for IVA sales books"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Descargar libro de ventas SII',
                    'description': 'Descarga del libro de ventas desde el portal del SII',
                    'task_type': 'automatic',
                    'category': 'Sincronización',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -8,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 2,
                    'title': 'Validar facturas emitidas',
                    'description': 'Verificación de facturas, boletas y notas emitidas',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 1,
                    'due_date_from_previous': 1,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 3,
                    'title': 'Conciliar con sistema de facturación',
                    'description': 'Conciliación con el sistema interno de facturación',
                    'task_type': 'manual',
                    'category': 'Tributario',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': -5,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 4,
                    'title': 'Calcular IVA débito fiscal',
                    'description': 'Cálculo del IVA débito fiscal del período',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -4,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Generar informe libro de ventas',
                    'description': 'Generación del informe detallado del libro de ventas',
                    'task_type': 'automatic',
                    'category': 'Análisis',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -3,
                    'optional': False,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'book_type': 'sales',
                'recurrence': 'monthly',
                'due_day': 10,
                'auto_generate': True,
                'requires_sii_credentials': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='Libro de Ventas Mensual',
            process_type='custom',
            defaults={
                'description': (
                    'Proceso mensual para gestionar el libro de ventas. '
                    'Incluye descarga desde el SII, validación de documentos emitidos, '
                    'conciliación y cálculo del IVA débito fiscal.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created IVA Sales Books template'))
        elif self.verbose:
            self.stdout.write('  - IVA Sales Books template already exists')

    def _seed_f3323_template(self):
        """Seed template for F3323 simplified tax regime"""

        template_data = {
            'tasks': [
                {
                    'order': 1,
                    'title': 'Recopilar ingresos del trimestre',
                    'description': 'Consolidación de todos los ingresos del período trimestral',
                    'task_type': 'automatic',
                    'category': 'Documentos',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': -15,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 2,
                    'title': 'Validar requisitos régimen Pro Pyme',
                    'description': 'Verificación del cumplimiento de requisitos para el régimen',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 1,
                    'due_date_from_previous': 1,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 3,
                    'title': 'Calcular base imponible',
                    'description': 'Determinación de la base imponible según régimen Pro Pyme',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 1,
                    'due_date_offset_days': -12,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 4,
                    'title': 'Generar borrador F3323',
                    'description': 'Generación automática del formulario F3323',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -10,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 5,
                    'title': 'Revisar y aprobar F3323',
                    'description': 'Revisión y aprobación del formulario por el contribuyente',
                    'task_type': 'manual',
                    'category': 'Revisión',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': -5,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 6,
                    'title': 'Enviar F3323 al SII',
                    'description': 'Envío de la declaración trimestral Pro Pyme',
                    'task_type': 'automatic',
                    'category': 'Tributario',
                    'estimated_duration_hours': 0.5,
                    'due_date_offset_days': -1,
                    'optional': False,
                    'can_run_parallel': False
                },
                {
                    'order': 7,
                    'title': 'Gestionar pago F3323',
                    'description': 'Gestión del pago de impuestos trimestrales',
                    'task_type': 'manual',
                    'category': 'Pagos',
                    'estimated_duration_hours': 2,
                    'due_date_offset_days': 0,
                    'optional': True,
                    'can_run_parallel': False
                }
            ],
            'config': {
                'form_type': 'f3323',
                'recurrence': 'quarterly',
                'quarters': {
                    'Q1': {'months': [1, 2, 3], 'due_month': 4, 'due_day': 20},
                    'Q2': {'months': [4, 5, 6], 'due_month': 7, 'due_day': 20},
                    'Q3': {'months': [7, 8, 9], 'due_month': 10, 'due_day': 20},
                    'Q4': {'months': [10, 11, 12], 'due_month': 1, 'due_day': 20}
                },
                'auto_generate': True,
                'notification_days': [15, 7, 3, 1],
                'requires_sii_credentials': True,
                'supports_auto_submission': True
            }
        }

        template, created = ProcessTemplate.objects.get_or_create(
            name='F3323 - Declaración Trimestral Pro Pyme',
            process_type='custom',
            defaults={
                'description': (
                    'Proceso trimestral para contribuyentes acogidos al régimen Pro Pyme. '
                    'Incluye recopilación de ingresos, validación de requisitos, '
                    'cálculos y envío del Formulario 3323. Vence el día 20 del mes '
                    'siguiente al término del trimestre.'
                ),
                'template_data': template_data,
                'is_active': True,
                'created_by': 'system'
            }
        )

        if created and self.verbose:
            self.stdout.write(self.style.SUCCESS('  ✓ Created F3323 Pro Pyme template'))
        elif self.verbose:
            self.stdout.write('  - F3323 template already exists')