from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel

class OnboardingStep(TimeStampedModel):
    """
    Pasos del proceso de onboarding
    """
    name = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    step_order = models.IntegerField()
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Configuración del paso
    step_config = models.JSONField(default=dict, help_text="Configuración específica del paso")
    
    class Meta:
        db_table = 'onboarding_steps'
        verbose_name = 'Onboarding Step'
        verbose_name_plural = 'Onboarding Steps'
        ordering = ['step_order']
    
    def __str__(self):
        return f"{self.step_order}. {self.title}"


class UserOnboarding(TimeStampedModel):
    """
    Progreso de onboarding por usuario
    """
    STATUS_CHOICES = [
        ('not_started', 'No Iniciado'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completado'),
        ('skipped', 'Omitido'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='onboarding_steps',
        null=True,
        blank=True
    )
    user_email = models.EmailField()  # Mantener por compatibilidad, pero deprecated
    company_rut = models.CharField(max_length=12, blank=True)
    company_dv = models.CharField(max_length=1, blank=True)
    step = models.ForeignKey(OnboardingStep, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')

    # Fechas
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Datos del paso
    step_data = models.JSONField(default=dict, help_text="Datos específicos del paso")

    class Meta:
        db_table = 'user_onboarding'
        verbose_name = 'User Onboarding'
        verbose_name_plural = 'User Onboarding'
        unique_together = [['user', 'step'], ['user_email', 'step']]  # Mantener ambos por compatibilidad
        ordering = ['step__step_order']

    def __str__(self):
        return f"{self.user.email if self.user else self.user_email} - {self.step.title} ({self.get_status_display()})"
    
    def complete_step(self, step_data=None):
        """Completa el paso de onboarding"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        if step_data:
            self.step_data.update(step_data)
        self.save()


# class OnboardingProgress(models.Model):
#     """
#     Vista del progreso general de onboarding
#     DISABLED: Vista de BD no existe aún
#     """
#     user = models.OneToOneField(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.CASCADE,
#         related_name='onboarding_progress',
#         null=True,
#         blank=True
#     )
#     user_email = models.EmailField(unique=True)  # Mantener por compatibilidad, pero deprecated
#     total_steps = models.IntegerField(default=0)
#     completed_steps = models.IntegerField(default=0)
#     progress_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     is_completed = models.BooleanField(default=False)
#     last_activity = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'onboarding_progress'
#         verbose_name = 'Onboarding Progress'
#         verbose_name_plural = 'Onboarding Progress'
#         managed = False  # Será una vista de base de datos

#     def __str__(self):
#         return f"{self.user.email if self.user else self.user_email} - {self.progress_percentage}% completado"
