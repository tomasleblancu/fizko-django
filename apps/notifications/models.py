from django.db import models
from apps.core.models import TimeStampedModel

class Notification(TimeStampedModel):
    """
    Notificaciones del sistema
    """
    NOTIFICATION_TYPES = [
        ('info', 'Información'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
        ('success', 'Éxito'),
        ('reminder', 'Recordatorio'),
    ]
    
    user_email = models.EmailField()
    company_rut = models.CharField(max_length=12, blank=True)
    company_dv = models.CharField(max_length=1, blank=True)
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    
    # Estado
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadatos
    action_url = models.URLField(blank=True, help_text="URL de acción relacionada")
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_email', 'is_read']),
            models.Index(fields=['company_rut', 'company_dv']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user_email}"
    
    def mark_as_read(self):
        """Marca la notificación como leída"""
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class NotificationPreference(TimeStampedModel):
    """
    Preferencias de notificación por usuario
    """
    NOTIFICATION_CHANNELS = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push'),
        ('in_app', 'En la App'),
    ]
    
    user_email = models.EmailField()
    notification_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=20, choices=NOTIFICATION_CHANNELS)
    is_enabled = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
        unique_together = ['user_email', 'notification_type', 'channel']
    
    def __str__(self):
        return f"{self.user_email} - {self.notification_type} via {self.get_channel_display()}"
