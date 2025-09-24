from django.core.management.base import BaseCommand
from django.db import transaction
from apps.companies.models import Company
from apps.chat.fixtures import create_default_templates, create_chile_specific_templates


class Command(BaseCommand):
    help = 'Crea plantillas por defecto de WhatsApp para empresas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de empresa específica. Si no se proporciona, se crean para todas las empresas.',
        )
        parser.add_argument(
            '--chile-specific',
            action='store_true',
            help='Crear solo plantillas específicas de Chile',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar recreación de plantillas existentes',
        )
    
    def handle(self, *args, **options):
        company_id = options.get('company_id')
        chile_specific = options.get('chile_specific', False)
        force = options.get('force', False)
        
        if company_id:
            try:
                companies = [Company.objects.get(id=company_id)]
                self.stdout.write(f"Procesando empresa ID: {company_id}")
            except Company.DoesNotExist:
                self.stderr.write(f"Empresa con ID {company_id} no existe")
                return
        else:
            companies = Company.objects.all()
            self.stdout.write(f"Procesando {companies.count()} empresas")
        
        total_created = 0
        
        for company in companies:
            self.stdout.write(f"\nProcesando empresa: {company.name}")
            
            try:
                with transaction.atomic():
                    if chile_specific:
                        templates = create_chile_specific_templates(company)
                    else:
                        templates = create_default_templates(company)
                        # También crear las específicas de Chile
                        chile_templates = create_chile_specific_templates(company)
                        templates.extend(chile_templates)
                    
                    created_count = len(templates)
                    total_created += created_count
                    
                    if created_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"✅ {created_count} plantillas creadas para {company.name}")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"⚠️ No se crearon plantillas nuevas para {company.name}")
                        )
                        
            except Exception as e:
                self.stderr.write(f"❌ Error procesando {company.name}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 Proceso completado. {total_created} plantillas creadas en total.")
        )