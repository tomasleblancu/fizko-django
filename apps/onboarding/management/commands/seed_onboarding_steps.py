from django.core.management.base import BaseCommand
from apps.onboarding.models import OnboardingStep


class Command(BaseCommand):
    help = 'Seed onboarding steps based on existing data'

    def handle(self, *args, **options):
        steps_data = [
            {
                'name': 'welcome',
                'title': 'Bienvenida',
                'description': 'Paso de bienvenida al sistema Fizko',
                'step_order': 1,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'welcome',
                    'show_progress': True,
                    'allow_skip': False
                }
            },
            {
                'name': 'profile',
                'title': 'Perfil Personal',
                'description': 'Información personal del usuario',
                'step_order': 2,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'form',
                    'fields': ['first_name', 'last_name', 'phone'],
                    'show_progress': True,
                    'allow_skip': False
                }
            },
            {
                'name': 'company',
                'title': 'Información de Empresa',
                'description': 'Datos de la empresa del usuario',
                'step_order': 3,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'form',
                    'fields': ['company_name', 'rut', 'address'],
                    'show_progress': True,
                    'allow_skip': False
                }
            },
            {
                'name': 'business',
                'title': 'Información del Negocio',
                'description': 'Detalles específicos del negocio',
                'step_order': 4,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'form',
                    'fields': ['business_type', 'industry', 'employees_count'],
                    'show_progress': True,
                    'allow_skip': False
                }
            }
        ]

        created_count = 0
        updated_count = 0

        for step_data in steps_data:
            step, created = OnboardingStep.objects.get_or_create(
                name=step_data['name'],
                defaults=step_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created step: {step.name} - {step.title}')
                )
            else:
                # Update existing step
                for field, value in step_data.items():
                    if field != 'name':  # Don't update the name field
                        setattr(step, field, value)
                step.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated step: {step.name} - {step.title}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nOnboarding steps seeded successfully!'
                f'\nCreated: {created_count} steps'
                f'\nUpdated: {updated_count} steps'
                f'\nTotal: {OnboardingStep.objects.count()} steps'
            )
        )