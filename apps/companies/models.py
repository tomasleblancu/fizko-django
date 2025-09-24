from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
from apps.core.models import TimeStampedModel


class Company(TimeStampedModel):
    """
    Modelo de empresa - solo contiene datos configurables por el usuario.
    Los datos del SII están en el modelo TaxPayer relacionado.
    """
    # Nota: La relación con TaxPayer ahora está en el modelo TaxPayer
    # TaxPayer.company apunta a esta Company
    
    # Identificación básica (duplicada para compatibilidad)
    tax_id = models.CharField(max_length=20, unique=True, help_text="RUT con formato XX.XXX.XXX-X")
    
    # Datos configurables por el usuario en onboarding
    business_name = models.CharField(max_length=255, help_text="Nombre comercial elegido por el usuario")
    display_name = models.CharField(max_length=255, blank=True, help_text="Nombre a mostrar en la aplicación")
    
    # Contacto personalizable por el usuario
    email = models.EmailField(help_text="Email principal de contacto")
    billing_email = models.EmailField(blank=True, help_text="Email para facturación")
    accounting_email = models.EmailField(blank=True, help_text="Email para contabilidad")
    mobile_phone = models.CharField(max_length=20, blank=True, help_text="Teléfono de contacto")
    website = models.URLField(blank=True, help_text="Sitio web de la empresa")
    
    # Configuración de la aplicación
    electronic_biller = models.BooleanField(default=True, help_text="¿Emite documentos electrónicos?")
    preferred_currency = models.CharField(max_length=3, default='CLP', help_text="Moneda preferida")
    time_zone = models.CharField(max_length=50, default='America/Santiago', help_text="Zona horaria")
    
    # Configuración tributaria personalizable
    person_company = models.CharField(
        max_length=50, 
        choices=[
            ('PERSONA', 'Persona Natural'),
            ('EMPRESA', 'Empresa/Persona Jurídica'),
        ],
        default='EMPRESA',
        help_text="Clasificación para la aplicación"
    )
    
    # Configuración de la cuenta
    is_active = models.BooleanField(default=True)
    login_tries = models.IntegerField(default=0)
    logo = models.ImageField(upload_to='companies/logos/', blank=True, null=True)
    
    # Configuración de notificaciones
    notify_new_documents = models.BooleanField(default=True)
    notify_tax_deadlines = models.BooleanField(default=True)
    notify_system_updates = models.BooleanField(default=True)
    
    # Timestamps de registro
    record_created_at = models.DateTimeField(null=True, blank=True)
    record_updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'companies'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'
        ordering = ['business_name']
        
    def __str__(self):
        return f"{self.display_name or self.business_name} ({self.tax_id})"
    
    @property
    def name(self):
        """Nombre a mostrar - compatibilidad con código existente"""
        return self.display_name or self.business_name or (self.taxpayer.razon_social if hasattr(self, 'taxpayer') else '')
    
    @property
    def full_rut(self):
        """Retorna RUT formateado desde el taxpayer"""
        return self.taxpayer.full_rut if hasattr(self, 'taxpayer') else self.tax_id
    
    @property
    def razon_social(self):
        """Razón social oficial del SII"""
        return self.taxpayer.razon_social if hasattr(self, 'taxpayer') else ''
    
    @property
    def sii_address(self):
        """Dirección registrada en el SII"""
        return self.taxpayer.formatted_address if hasattr(self, 'taxpayer') else ''
    
    @property
    def activity_description(self):
        """Descripción de actividad económica del SII"""
        return self.taxpayer.actividad_description if hasattr(self, 'taxpayer') else ''
    
    @property
    def activity_start_date(self):
        """Fecha de inicio de actividades del SII"""
        return self.taxpayer.fecha_inicio_actividades if hasattr(self, 'taxpayer') else None
    
    @property
    def is_verified_with_sii(self):
        """¿Los datos están verificados con el SII?"""
        return self.taxpayer.is_verified if hasattr(self, 'taxpayer') else False
    
    def get_contact_email(self, purpose='general'):
        """Obtiene el email apropiado según el propósito"""
        if purpose == 'billing' and self.billing_email:
            return self.billing_email
        elif purpose == 'accounting' and self.accounting_email:
            return self.accounting_email
        else:
            return self.email
    
    def sync_taxpayer_data(self):
        """Sincroniza algunos datos básicos desde el taxpayer"""
        if hasattr(self, 'taxpayer') and self.taxpayer:
            # Si no tiene display_name, usar la razón social del SII
            if not self.display_name:
                self.display_name = self.taxpayer.razon_social

            # Clasificación automática basada en tipo de contribuyente
            # TODO: Implementar is_persona_juridica en TaxPayer model
            # Por ahora, usar person_company si ya está definido, sino default a EMPRESA
            if not self.person_company:
                self.person_company = 'EMPRESA'  # Default para empresas
    
    def get_sii_credentials(self):
        """Obtiene las credenciales del SII almacenadas para esta empresa"""
        try:
            return self.taxpayer_sii_credentials
        except AttributeError:
            return None
    
    def has_sii_credentials(self):
        """Verifica si la empresa tiene credenciales del SII almacenadas"""
        credentials = self.get_sii_credentials()
        return credentials is not None and credentials.is_credentials_valid
    
    def sync_with_sii(self, user=None):
        """Sincroniza los datos de la empresa con el SII usando credenciales almacenadas"""
        if not self.has_sii_credentials():
            raise ValueError("No se encontraron credenciales válidas del SII para esta empresa")
        
        credentials = self.get_sii_credentials()
        
        try:
            from apps.sii.services import create_sii_service
            password = credentials.get_password()
            
            sii_service = create_sii_service(
                tax_id=self.tax_id, 
                password=password, 
                use_real=True
            )
            
            try:
                sii_service.authenticate()
                contribuyente_data = sii_service.consultar_contribuyente()
                
                # Actualizar datos del taxpayer
                if self.taxpayer:
                    self.taxpayer.sync_from_sii_data(contribuyente_data)
                    self.taxpayer.save()
                    
                    # Sincronizar modelos relacionados que necesitan la company
                    self.taxpayer._sync_address_from_sii(contribuyente_data, company=self)
                    self.taxpayer._sync_activity_from_sii(contribuyente_data, company=self)
                
                # Actualizar última verificación de credenciales
                from django.utils import timezone
                credentials.last_verified = timezone.now()
                credentials.verification_failures = 0
                credentials.save()
                
                # Sincronizar algunos datos de la company
                self.sync_taxpayer_data()
                self.save()
                
                return {
                    'status': 'success',
                    'message': 'Sincronización con SII exitosa',
                    'data': contribuyente_data
                }
                
            finally:
                if hasattr(sii_service, 'close'):
                    sii_service.close()
                    
        except Exception as e:
            # Incrementar fallos de verificación
            credentials.verification_failures += 1
            credentials.save()

            raise ValueError(f"Error sincronizando con SII: {str(e)}")


class BackgroundTaskTracker(TimeStampedModel):
    """
    Modelo para rastrear el estado de tareas en segundo plano asociadas a una empresa.
    Usado especialmente para mostrar progreso durante el onboarding.
    """
    TASK_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('running', 'Ejecutándose'),
        ('success', 'Completada'),
        ('failed', 'Falló'),
    ]

    TASK_NAME_CHOICES = [
        ('create_processes_from_taxpayer_settings', 'Creando procesos tributarios'),
        ('sync_sii_documents_task', 'Sincronizando documentos SII'),
        ('sync_sii_documents_full_history_task', 'Sincronizando historial completo SII'),
        ('sync_all_historical_forms_task', 'Sincronizando formularios históricos'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='background_tasks',
        help_text="Empresa asociada a la tarea"
    )

    task_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="ID único de la tarea de Celery"
    )

    task_name = models.CharField(
        max_length=100,
        choices=TASK_NAME_CHOICES,
        help_text="Nombre identificativo de la tarea"
    )

    display_name = models.CharField(
        max_length=255,
        help_text="Nombre a mostrar al usuario"
    )

    status = models.CharField(
        max_length=20,
        choices=TASK_STATUS_CHOICES,
        default='pending',
        help_text="Estado actual de la tarea"
    )

    progress = models.IntegerField(
        default=0,
        help_text="Progreso de 0 a 100"
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento en que comenzó la ejecución"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Momento en que terminó la ejecución"
    )

    error_message = models.TextField(
        blank=True,
        help_text="Mensaje de error si la tarea falló"
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Información adicional sobre la tarea"
    )

    class Meta:
        db_table = 'background_task_trackers'
        verbose_name = 'Background Task Tracker'
        verbose_name_plural = 'Background Task Trackers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['task_id']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_task_name_display()} - {self.company.business_name} ({self.status})"

    @property
    def is_active(self):
        """Retorna True si la tarea está pendiente o ejecutándose"""
        return self.status in ['pending', 'running']

    @property
    def is_completed(self):
        """Retorna True si la tarea terminó (exitosa o con error)"""
        return self.status in ['success', 'failed']

    @property
    def duration(self):
        """Retorna la duración de la tarea si ya terminó"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @classmethod
    def create_for_task(cls, company, task_result, task_name, display_name, metadata=None):
        """
        Factory method para crear un tracker desde un resultado de tarea de Celery
        """
        return cls.objects.create(
            company=company,
            task_id=task_result.id,
            task_name=task_name,
            display_name=display_name,
            status='pending',
            metadata=metadata or {}
        )

    @classmethod
    def cleanup_old_completed_tasks(cls, hours_old=1):
        """
        Elimina tareas completadas más antiguas que el tiempo especificado
        """
        cutoff_time = timezone.now() - timedelta(hours=hours_old)
        old_tasks = cls.objects.filter(
            status__in=['success', 'failed'],
            completed_at__lt=cutoff_time
        )
        count = old_tasks.count()
        old_tasks.delete()
        return count

    def update_from_celery_result(self, celery_result):
        """
        Actualiza el estado del tracker basado en el resultado de Celery
        """
        if celery_result.state == 'PENDING':
            self.status = 'pending'
            self.progress = 0
        elif celery_result.state == 'PROGRESS':
            self.status = 'running'
            if not self.started_at:
                self.started_at = timezone.now()
            # Intentar extraer progreso del resultado
            if hasattr(celery_result, 'info') and isinstance(celery_result.info, dict):
                self.progress = celery_result.info.get('progress', self.progress)
        elif celery_result.state == 'SUCCESS':
            self.status = 'success'
            self.progress = 100
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif celery_result.state == 'FAILURE':
            self.status = 'failed'
            if not self.completed_at:
                self.completed_at = timezone.now()
            self.error_message = str(celery_result.info) if celery_result.info else 'Error desconocido'

        self.save()
        return self