from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.onboarding.models import UserOnboarding, OnboardingProgress

User = get_user_model()


class Command(BaseCommand):
    help = 'Migra los registros de onboarding para vincularlos con usuarios mediante FK'

    def handle(self, *args, **options):
        # Migrar UserOnboarding
        self.stdout.write(self.style.WARNING('\n=== Migrando UserOnboarding ==='))

        onboarding_records = UserOnboarding.objects.filter(user__isnull=True)
        total_onboarding = onboarding_records.count()
        migrated_onboarding = 0
        failed_onboarding = 0

        for record in onboarding_records:
            try:
                user = User.objects.get(email=record.user_email)
                record.user = user
                record.save(update_fields=['user'])
                migrated_onboarding += 1

                if migrated_onboarding % 10 == 0:
                    self.stdout.write(f'  Procesados: {migrated_onboarding}/{total_onboarding}')

            except User.DoesNotExist:
                failed_onboarding += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Usuario no encontrado para email: {record.user_email}')
                )
            except Exception as e:
                failed_onboarding += 1
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Error migrando {record.user_email}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ UserOnboarding migrado:'
                f'\n  - Total: {total_onboarding}'
                f'\n  - Exitosos: {migrated_onboarding}'
                f'\n  - Fallidos: {failed_onboarding}'
            )
        )

        # Migrar OnboardingProgress (si no es managed=False)
        # Como OnboardingProgress tiene managed=False, podríamos necesitar un approach diferente
        self.stdout.write(self.style.WARNING('\n=== OnboardingProgress ==='))
        self.stdout.write(
            self.style.NOTICE(
                'OnboardingProgress tiene managed=False (vista de BD).'
                '\nSi necesitas migrar este modelo, deberás actualizar la vista en la BD.'
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Migración completada!'
                f'\n  Total registros actualizados: {migrated_onboarding}'
            )
        )
