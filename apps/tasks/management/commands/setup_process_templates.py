"""
Command para configurar plantillas de procesos de ejemplo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.tasks.models import (
    CompanySegment,
    ProcessTemplateConfig,
    ProcessTemplateTask,
    ProcessAssignmentRule
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Configura plantillas de procesos tributarios de ejemplo'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Configurando Sistema de Gestión de Procesos ===\n'))

        # Obtener o crear usuario admin
        admin_email = 'admin@fizko.cl'
        try:
            admin_user = User.objects.filter(email=admin_email).first()
            if not admin_user:
                admin_user = User.objects.filter(is_superuser=True).first()
                if admin_user:
                    admin_email = admin_user.email
        except:
            admin_email = 'system@fizko.cl'

        # 1. Crear Segmentos de Empresas
        self.stdout.write('\n1. Creando segmentos de empresas...')

        segment_pyme, created = CompanySegment.objects.get_or_create(
            name='PYME con F29',
            defaults={
                'description': 'Pequeñas y medianas empresas con declaración mensual de IVA',
                'segment_type': 'tax_regime',
                'criteria': {
                    'tax_regime': ['f29_monthly'],
                    'size': {'min_employees': 1, 'max_employees': 50}
                },
                'is_active': True,
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Segmento: {segment_pyme.name} ({"creado" if created else "ya existe"})'))

        segment_propyme, created = CompanySegment.objects.get_or_create(
            name='Pro-Pyme con F3323',
            defaults={
                'description': 'Empresas acogidas al régimen Pro-Pyme',
                'segment_type': 'tax_regime',
                'criteria': {
                    'tax_regime': ['f3323_quarterly'],
                    'custom_conditions': ['requires_f3323']
                },
                'is_active': True,
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Segmento: {segment_propyme.name} ({"creado" if created else "ya existe"})'))

        # 2. Crear Plantilla F29
        self.stdout.write('\n2. Creando plantilla F29 mensual...')

        template_f29, created = ProcessTemplateConfig.objects.get_or_create(
            name='F29 - Declaración Mensual IVA',
            defaults={
                'description': 'Proceso completo para declaración mensual de IVA (Formulario 29)',
                'process_type': 'tax_monthly',
                'status': 'active',
                'is_active': True,
                'default_recurrence_type': 'monthly',
                'default_recurrence_config': {
                    'day_of_month': 12,  # Vencimiento día 12 de cada mes
                    'months': list(range(1, 13))
                },
                'template_config': {
                    'form_type': 'f29',
                    'auto_sync_documents': True,
                    'require_approval': True
                },
                'available_variables': ['period', 'company_name', 'rut', 'tax_year'],
                'default_values': {
                    'auto_calculate_iva': True,
                    'include_credits': True
                },
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Template: {template_f29.name} ({"creado" if created else "ya existe"})'))

        # Tareas para F29
        if created or template_f29.template_tasks.count() == 0:
            self.stdout.write('    Creando tareas...')

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Sincronizar documentos tributarios del mes',
                task_description='Sincronizar todos los DTEs (facturas, boletas, notas) del período',
                task_type='automatic',
                priority='high',
                execution_order=1,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=2,
                estimated_hours=1
            )

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Revisar libro de compras',
                task_description='Verificar que todos los documentos de compra estén registrados',
                task_type='manual',
                priority='high',
                execution_order=2,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=5,
                estimated_hours=2
            )

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Revisar libro de ventas',
                task_description='Verificar que todas las ventas estén correctamente registradas',
                task_type='manual',
                priority='high',
                execution_order=3,
                is_optional=False,
                can_run_parallel=True,
                due_date_offset_days=5,
                estimated_hours=2
            )

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Calcular IVA a pagar o retener',
                task_description='Calcular el monto de IVA según compras y ventas del período',
                task_type='automatic',
                priority='high',
                execution_order=4,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=7,
                estimated_hours=1
            )

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Completar Formulario 29',
                task_description='Completar todos los campos del F29 en el sitio del SII',
                task_type='manual',
                priority='urgent',
                execution_order=5,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=10,
                estimated_hours=1
            )

            ProcessTemplateTask.objects.create(
                template=template_f29,
                task_title='Enviar declaración al SII',
                task_description='Enviar y confirmar recepción de la declaración',
                task_type='manual',
                priority='urgent',
                execution_order=6,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=12,
                estimated_hours=1
            )

            self.stdout.write(self.style.SUCCESS('    ✓ 6 tareas creadas'))

        # 3. Crear Plantilla F22
        self.stdout.write('\n3. Creando plantilla F22 anual...')

        template_f22, created = ProcessTemplateConfig.objects.get_or_create(
            name='F22 - Declaración Anual de Renta',
            defaults={
                'description': 'Proceso completo para declaración anual de impuesto a la renta',
                'process_type': 'tax_annual',
                'status': 'active',
                'is_active': True,
                'default_recurrence_type': 'annual',
                'default_recurrence_config': {
                    'month': 4,  # Abril
                    'day': 30
                },
                'template_config': {
                    'form_type': 'f22',
                    'require_balance_sheet': True,
                    'require_approval': True
                },
                'available_variables': ['tax_year', 'company_name', 'rut'],
                'default_values': {
                    'include_previous_year_comparison': True
                },
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Template: {template_f22.name} ({"creado" if created else "ya existe"})'))

        # Tareas para F22
        if created or template_f22.template_tasks.count() == 0:
            self.stdout.write('    Creando tareas...')

            ProcessTemplateTask.objects.create(
                template=template_f22,
                task_title='Preparar balance anual',
                task_description='Consolidar toda la información contable del año',
                task_type='manual',
                priority='high',
                execution_order=1,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=30,
                estimated_hours=8
            )

            ProcessTemplateTask.objects.create(
                template=template_f22,
                task_title='Revisar gastos deducibles',
                task_description='Verificar que todos los gastos estén respaldados y sean deducibles',
                task_type='manual',
                priority='high',
                execution_order=2,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=60,
                estimated_hours=4
            )

            ProcessTemplateTask.objects.create(
                template=template_f22,
                task_title='Completar Formulario 22',
                task_description='Completar declaración anual de renta',
                task_type='manual',
                priority='urgent',
                execution_order=3,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=100,
                estimated_hours=3
            )

            ProcessTemplateTask.objects.create(
                template=template_f22,
                task_title='Enviar declaración al SII',
                task_description='Enviar y confirmar recepción de la declaración anual',
                task_type='manual',
                priority='urgent',
                execution_order=4,
                is_optional=False,
                can_run_parallel=False,
                due_date_offset_days=120,
                estimated_hours=1
            )

            self.stdout.write(self.style.SUCCESS('    ✓ 4 tareas creadas'))

        # 4. Crear Reglas de Asignación
        self.stdout.write('\n4. Creando reglas de asignación...')

        rule_f29, created = ProcessAssignmentRule.objects.get_or_create(
            template=template_f29,
            segment=segment_pyme,
            defaults={
                'priority': 100,
                'is_active': True,
                'auto_apply': True,
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Regla: {template_f29.name} → {segment_pyme.name} ({"creada" if created else "ya existe"})'))

        rule_f22, created = ProcessAssignmentRule.objects.get_or_create(
            template=template_f22,
            segment=segment_pyme,
            defaults={
                'priority': 90,
                'is_active': True,
                'auto_apply': True,
                'created_by': admin_email
            }
        )
        self.stdout.write(self.style.SUCCESS(f'  ✓ Regla: {template_f22.name} → {segment_pyme.name} ({"creada" if created else "ya existe"})'))

        # Resumen
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✅ Sistema de Gestión de Procesos configurado exitosamente!\n'))
        self.stdout.write('Resumen:')
        self.stdout.write(f'  - Segmentos creados: {CompanySegment.objects.count()}')
        self.stdout.write(f'  - Plantillas creadas: {ProcessTemplateConfig.objects.count()}')
        self.stdout.write(f'  - Tareas de plantillas: {ProcessTemplateTask.objects.count()}')
        self.stdout.write(f'  - Reglas de asignación: {ProcessAssignmentRule.objects.count()}')

        self.stdout.write('\nPróximos pasos:')
        self.stdout.write('  1. Accede al admin de Django: http://localhost:8000/admin/')
        self.stdout.write('  2. Navega a "Tasks" y explora las secciones:')
        self.stdout.write('     - Segmentos de Empresas')
        self.stdout.write('     - Configuraciones de Plantillas de Procesos')
        self.stdout.write('     - Reglas de Asignación de Procesos')
        self.stdout.write('  3. Puedes editar, duplicar o crear nuevas plantillas')
        self.stdout.write('  4. Asigna segmentos a empresas desde el admin de TaxPayers\n')
