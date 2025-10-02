from django.db import models
from apps.core.models import TimeStampedModel

class SIISession(TimeStampedModel):
    """
    Sesiones de usuario en el SII
    """
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    username = models.CharField(max_length=100)
    session_id = models.CharField(max_length=255, unique=True)
    session_token = models.TextField(blank=True)
    cookies_data = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sii_sessions'
        verbose_name = 'SII Session'
        verbose_name_plural = 'SII Sessions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.company_rut}-{self.company_dv} - {self.username}"
    
    @property
    def is_expired(self):
        """Verifica si la sesión ha expirado"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False






class SIISyncLog(TimeStampedModel):
    """
    Log de sincronización con el SII
    """
    SYNC_TYPES = [
        ('taxpayer_info', 'Información de Contribuyente'),
        ('tax_forms', 'Formularios Tributarios'),
        ('electronic_docs', 'Documentos Electrónicos'),
        ('documents', 'Documentos Tributarios'),
        ('activities', 'Actividades Económicas'),
        ('addresses', 'Direcciones'),
        ('partners', 'Socios'),
        ('representatives', 'Representantes'),
        ('stamps', 'Timbres'),
    ]
    
    STATUS_CHOICES = [
        ('running', 'En Ejecución'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('success', 'Exitoso'),
        ('error', 'Error'),
        ('partial', 'Parcial'),
    ]
    
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)
    sync_type = models.CharField(max_length=30, choices=SYNC_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    # Campos adicionales para tareas de Celery y seguimiento detallado
    task_id = models.CharField(max_length=255, blank=True, null=True)
    fecha_desde = models.DateField(blank=True, null=True)
    fecha_hasta = models.DateField(blank=True, null=True)
    user_email = models.EmailField(blank=True)
    priority = models.CharField(max_length=10, default='normal')
    description = models.CharField(max_length=500, blank=True)
    documents_processed = models.IntegerField(default=0)
    documents_created = models.IntegerField(default=0)
    documents_updated = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    results_data = models.JSONField(default=dict)

    sync_data = models.JSONField(default=dict)
    progress_percentage = models.IntegerField(default=0, help_text="Porcentaje de progreso de la sincronización")
    
    class Meta:
        db_table = 'sii_sync_logs'
        verbose_name = 'SII Sync Log'
        verbose_name_plural = 'SII Sync Logs'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['company_rut', 'company_dv']),
            models.Index(fields=['sync_type', 'status']),
            models.Index(fields=['started_at']),
            models.Index(fields=['task_id']),
        ]
    
    def __str__(self):
        return f"{self.company_rut}-{self.company_dv} - {self.get_sync_type_display()} ({self.status})"
    
    @property
    def duration(self):
        """Duración de la sincronización"""
        if self.completed_at:
            return self.completed_at - self.started_at
        from django.utils import timezone
        return timezone.now() - self.started_at
    
    @property
    def success_rate(self):
        """Tasa de éxito de la sincronización"""
        if self.records_processed == 0:
            return 0
        return ((self.records_created + self.records_updated) / self.records_processed) * 100
