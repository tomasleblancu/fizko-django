from django.core.management.base import BaseCommand
from apps.onboarding.models import OnboardingStep


class Command(BaseCommand):
    help = 'Seed onboarding steps based on existing data'

    def handle(self, *args, **options):
        steps_data = [
            {
                'name': 'business_info',
                'title': 'Información del Negocio',
                'description': 'Detalles sobre la empresa y tipo de negocio',
                'step_order': 1,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'form',
                    'fields': ['business_name', 'business_type', 'industry', 'employees_count', 'monthly_income'],
                    'show_progress': True,
                    'allow_skip': False
                }
            },
            {
                'name': 'company',
                'title': 'Credenciales SII',
                'description': 'Conexión con el Servicio de Impuestos Internos para automatizar la gestión tributaria',
                'step_order': 2,
                'is_required': True,
                'is_active': True,
                'step_config': {
                    'type': 'form',
                    'fields': ['tax_id', 'password', 'email', 'mobile_phone'],
                    'show_progress': True,
                    'allow_skip': False,
                    'sensitive': True,
                    'description': 'Estos datos se utilizan para conectar con el SII y sincronizar automáticamente documentos tributarios'
                }
            }
        ]

        created_count = 0
        updated_count = 0
        deactivated_count = 0

        # First, deactivate old steps that are no longer needed
        old_step_names = ['welcome', 'profile', 'business', 'process_settings', 'user_info']
        old_steps = OnboardingStep.objects.filter(name__in=old_step_names)
        for old_step in old_steps:
            old_step.is_active = False
            old_step.save()
            deactivated_count += 1
            self.stdout.write(
                self.style.WARNING(f'Deactivated old step: {old_step.name} - {old_step.title}')
            )

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
                f'\nDeactivated: {deactivated_count} steps'
                f'\nActive steps: {OnboardingStep.objects.filter(is_active=True).count()}'
                f'\nTotal steps: {OnboardingStep.objects.count()}'
            )
        )