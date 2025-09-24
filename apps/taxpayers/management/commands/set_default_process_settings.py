from django.core.management.base import BaseCommand
from apps.taxpayers.models import TaxPayer


class Command(BaseCommand):
    help = 'Configura los procesos por defecto para todos los TaxPayers existentes que no tengan configuración'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar actualización incluso si ya tienen configuración'
        )

    def handle(self, *args, **options):
        force = options['force']

        # Configuración por defecto: todas las empresas necesitan F29 y F22
        default_settings = {
            'f29_monthly': True,
            'f22_annual': True,
            'f3323_quarterly': False  # Solo para empresas Pro-Pyme
        }

        if force:
            # Actualizar todos los TaxPayers
            taxpayers = TaxPayer.objects.all()
            msg = "Actualizando configuración de procesos para TODOS los TaxPayers"
        else:
            # Solo actualizar TaxPayers sin configuración
            taxpayers = TaxPayer.objects.filter(
                setting_procesos__isnull=True
            ) | TaxPayer.objects.filter(
                setting_procesos={}
            )
            msg = "Configurando procesos por defecto para TaxPayers sin configuración"

        self.stdout.write(msg)
        self.stdout.write(f"TaxPayers a actualizar: {taxpayers.count()}")

        updated_count = 0
        for taxpayer in taxpayers:
            try:
                # Aplicar configuración por defecto
                taxpayer.update_process_settings(default_settings)
                updated_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ {taxpayer.razon_social or taxpayer.tax_id}: Configuración aplicada'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {taxpayer.razon_social or taxpayer.tax_id}: Error - {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Resumen:'
                f'\n  - TaxPayers encontrados: {taxpayers.count()}'
                f'\n  - TaxPayers actualizados: {updated_count}'
                f'\n  - Configuración aplicada: {default_settings}'
            )
        )