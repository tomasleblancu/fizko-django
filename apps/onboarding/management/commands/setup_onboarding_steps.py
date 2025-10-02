from django.core.management.base import BaseCommand
from apps.onboarding.models import OnboardingStep


class Command(BaseCommand):
    help = 'Setup or update onboarding steps in the database'

    def handle(self, *args, **options):
        self.stdout.write('🔧 Setting up onboarding steps...\n')

        steps_config = [
            {
                'name': 'user_info',
                'title': 'Información Personal',
                'description': 'Información básica del usuario',
                'step_order': 1,
                'is_required': True,
                'is_active': False,  # Deprecated
                'step_config': {}
            },
            {
                'name': 'business_info',
                'title': 'Información del Negocio',
                'description': 'Detalles sobre el tipo de negocio y operaciones',
                'step_order': 1,
                'is_required': True,
                'is_active': True,
                'step_config': {}
            },
            {
                'name': 'company',
                'title': 'Credenciales SII',
                'description': 'Credenciales y datos de la empresa en el SII',
                'step_order': 2,
                'is_required': True,
                'is_active': True,
                'step_config': {}
            },
            {
                'name': 'process_settings',
                'title': 'Configuración de Procesos',
                'description': 'Configuración de procesos tributarios',
                'step_order': 4,
                'is_required': True,
                'is_active': False,  # Optional
                'step_config': {}
            },
            {
                'name': 'finalized',
                'title': 'Onboarding Finalizado',
                'description': 'Onboarding completado exitosamente',
                'step_order': 999,
                'is_required': True,
                'is_active': False,  # Internal only
                'step_config': {}
            }
        ]

        created_count = 0
        updated_count = 0

        for step_data in steps_config:
            step, created = OnboardingStep.objects.update_or_create(
                name=step_data['name'],
                defaults={
                    'title': step_data['title'],
                    'description': step_data['description'],
                    'step_order': step_data['step_order'],
                    'is_required': step_data['is_required'],
                    'is_active': step_data['is_active'],
                    'step_config': step_data['step_config']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ Created: {step.name} - {step.title}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  🔄 Updated: {step.name} - {step.title}')
                )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'✅ Setup complete!'))
        self.stdout.write(f'   Created: {created_count}')
        self.stdout.write(f'   Updated: {updated_count}')
        self.stdout.write(f'   Total:   {OnboardingStep.objects.count()}')

        # Show current steps
        self.stdout.write('\n📝 Current steps:')
        for step in OnboardingStep.objects.all().order_by('step_order'):
            active_marker = '✓' if step.is_active else '✗'
            self.stdout.write(
                f'   [{active_marker}] {step.step_order}. {step.name} - {step.title}'
            )
