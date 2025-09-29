import json
import uuid
from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import TimeStampedModel


class WhatsAppConfig(TimeStampedModel):
    """
    Configuración de WhatsApp Business API (Kapso)
    """
    company = models.OneToOneField(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='whatsapp_config',
        help_text="Empresa asociada"
    )
    
    # Identificadores de Kapso
    config_id = models.CharField(max_length=255, unique=True, help_text="ID de configuración en Kapso")
    phone_number_id = models.CharField(max_length=255, help_text="ID del número de teléfono en WhatsApp Business")
    business_account_id = models.CharField(max_length=255, help_text="ID de la cuenta de negocio")
    
    # Información del número
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+\d{1,15}$', 'Formato: +1234567890')],
        help_text="Número de teléfono con formato internacional"
    )
    display_phone_number = models.CharField(max_length=30, help_text="Número formateado para mostrar")
    display_name = models.CharField(max_length=100, help_text="Nombre a mostrar en WhatsApp")
    
    # Estado y configuración
    is_active = models.BooleanField(default=True)
    is_coexistence = models.BooleanField(default=False, help_text="¿Permite coexistencia con WhatsApp Business?")
    webhook_verified_at = models.DateTimeField(null=True, blank=True)
    
    # API Credentials
    api_token = models.CharField(max_length=500, help_text="Token de API de Kapso")
    webhook_secret = models.CharField(max_length=255, help_text="Secreto para validar webhooks")
    
    # Configuración de mensajes
    enable_auto_responses = models.BooleanField(default=True)
    business_hours_start = models.TimeField(default='09:00')
    business_hours_end = models.TimeField(default='18:00')
    
    class Meta:
        db_table = 'whatsapp_configs'
        verbose_name = 'WhatsApp Configuration'
        verbose_name_plural = 'WhatsApp Configurations'
    
    def __str__(self):
        return f"{self.company.name} - {self.display_phone_number}"


class WhatsAppConversation(TimeStampedModel):
    """
    Conversaciones de WhatsApp con clientes
    """
    STATUS_CHOICES = [
        ('active', 'Activa'),
        ('ended', 'Terminada'),
        ('archived', 'Archivada'),
    ]
    
    # Identificadores
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_id = models.CharField(max_length=255, unique=True, help_text="ID de conversación en Kapso")
    
    # Relaciones
    whatsapp_config = models.ForeignKey(
        WhatsAppConfig,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='whatsapp_conversations'
    )
    
    # Información del contacto
    phone_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r'^\+\d{1,15}$', 'Formato: +1234567890')],
        help_text="Número del cliente"
    )
    contact_name = models.CharField(max_length=100, blank=True, help_text="Nombre del contacto")
    
    # Estado de la conversación
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_active_at = models.DateTimeField(auto_now_add=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True, help_text="Etiquetas para clasificar la conversación")
    
    # Métricas
    message_count = models.PositiveIntegerField(default=0)
    unread_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'whatsapp_conversations'
        verbose_name = 'WhatsApp Conversation'
        verbose_name_plural = 'WhatsApp Conversations'
        ordering = ['-last_active_at']
        indexes = [
            models.Index(fields=['whatsapp_config', 'status']),
            models.Index(fields=['company', 'phone_number']),
            models.Index(fields=['last_active_at']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} - {self.contact_name or 'Sin nombre'}"


class WhatsAppMessage(TimeStampedModel):
    """
    Mensajes de WhatsApp enviados y recibidos
    """
    MESSAGE_TYPES = [
        ('text', 'Texto'),
        ('image', 'Imagen'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('voice', 'Nota de voz'),
        ('document', 'Documento'),
        ('location', 'Ubicación'),
        ('contact', 'Contacto'),
        ('interactive', 'Interactivo'),
        ('template', 'Plantilla'),
        ('reaction', 'Reacción'),
        ('system', 'Sistema'),
    ]
    
    DIRECTION_CHOICES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]
    
    STATUS_CHOICES = [
        ('received', 'Recibido'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('read', 'Leído'),
        ('failed', 'Fallido'),
        ('pending', 'Pendiente'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('failed', 'Error'),
    ]
    
    # Identificadores
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_id = models.CharField(max_length=255, unique=True, help_text="ID del mensaje en Kapso")
    whatsapp_message_id = models.CharField(max_length=255, blank=True, help_text="ID del mensaje en WhatsApp")
    
    # Relaciones
    conversation = models.ForeignKey(
        WhatsAppConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='whatsapp_messages'
    )
    
    # Contenido del mensaje
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    content = models.TextField(help_text="Contenido del mensaje")
    
    # Información adicional por tipo de mensaje
    message_type_data = models.JSONField(default=dict, blank=True)
    has_media = models.BooleanField(default=False)
    media_data = models.JSONField(default=dict, blank=True)
    
    # Estado del mensaje
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Respuesta automática
    is_auto_response = models.BooleanField(default=False)
    triggered_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='auto_responses',
        help_text="Mensaje que generó esta respuesta automática"
    )
    
    class Meta:
        db_table = 'whatsapp_messages'
        verbose_name = 'WhatsApp Message'
        verbose_name_plural = 'WhatsApp Messages'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['conversation', 'direction']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['message_type', 'direction']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        direction_symbol = "→" if self.direction == 'outbound' else "←"
        return f"{direction_symbol} {self.conversation.phone_number}: {self.content[:50]}..."


class WebhookEvent(TimeStampedModel):
    """
    Registro de eventos de webhooks recibidos de Kapso
    """
    EVENT_TYPES = [
        ('whatsapp.message.received', 'Mensaje Recibido'),
        ('whatsapp.message.sent', 'Mensaje Enviado'),
        ('whatsapp.conversation.created', 'Conversación Creada'),
        ('whatsapp.conversation.ended', 'Conversación Terminada'),
        ('whatsapp.message.delivered', 'Mensaje Entregado'),
        ('whatsapp.message.read', 'Mensaje Leído'),
        ('whatsapp.message.failed', 'Mensaje Fallido'),
        ('unknown', 'Tipo Desconocido'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('failed', 'Error'),
        ('ignored', 'Ignorado'),
    ]
    
    # Identificadores
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True, help_text="Clave de idempotencia del webhook")
    
    # Información del evento
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, null=True, blank=True, default='unknown')
    webhook_signature = models.CharField(max_length=255, help_text="Firma HMAC del webhook")
    
    # Relaciones (pueden ser null si el evento no está asociado a una entidad específica)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='webhook_events'
    )
    conversation = models.ForeignKey(
        WhatsAppConversation,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='webhook_events'
    )
    message = models.ForeignKey(
        WhatsAppMessage,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='webhook_events'
    )
    
    # Datos del webhook
    raw_payload = models.JSONField(help_text="Payload completo del webhook")
    processed_data = models.JSONField(default=dict, blank=True, help_text="Datos procesados del webhook")
    
    # Estado del procesamiento
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    processing_attempts = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Información de errores
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(default=dict, blank=True)
    
    # Flags especiales
    is_test = models.BooleanField(default=False, help_text="¿Es un webhook de prueba?")
    is_batch = models.BooleanField(default=False, help_text="¿Es un webhook con múltiples mensajes?")
    batch_size = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'webhook_events'
        verbose_name = 'Webhook Event'
        verbose_name_plural = 'Webhook Events'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'processing_status']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['processing_status', 'created_at']),
            models.Index(fields=['is_test']),
        ]
    
    def __str__(self):
        status_symbol = {
            'pending': '⏳',
            'processing': '⚙️',
            'processed': '✅',
            'failed': '❌',
            'ignored': '🚫'
        }.get(self.processing_status, '❓')
        
        return f"{status_symbol} {self.get_event_type_display()} - {self.created_at.strftime('%H:%M:%S')}"


class MessageTemplate(TimeStampedModel):
    """
    Plantillas de mensajes para WhatsApp
    """
    TEMPLATE_TYPES = [
        ('tax_reminder', 'Recordatorio Tributario'),
        ('document_alert', 'Alerta de Documento'),
        ('payment_due', 'Vencimiento de Pago'),
        ('welcome', 'Bienvenida'),
        ('support', 'Soporte'),
        ('custom', 'Personalizado'),
    ]
    
    LANGUAGE_CHOICES = [
        ('es', 'Español'),
        ('es_CL', 'Español (Chile)'),
        ('en', 'Inglés'),
    ]
    
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='whatsapp_templates'
    )
    
    # Información de la plantilla
    name = models.CharField(max_length=100, help_text="Nombre identificatorio de la plantilla")
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='es_CL')
    
    # Contenido de la plantilla
    subject = models.CharField(max_length=200, blank=True, help_text="Asunto o título del mensaje")
    body_text = models.TextField(help_text="Texto del mensaje con variables {variable}")
    footer_text = models.CharField(max_length=60, blank=True, help_text="Pie del mensaje")
    
    # Variables disponibles
    available_variables = models.JSONField(
        default=list,
        help_text="Lista de variables disponibles para esta plantilla"
    )
    
    # Configuración
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False, help_text="¿Está aprobada por WhatsApp Business?")
    
    # Métricas de uso
    usage_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'whatsapp_message_templates'
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'
        unique_together = ['company', 'name']
        ordering = ['template_type', 'name']
    
    def __str__(self):
        return f"{self.company.name} - {self.name}"
    
    def render_message(self, variables=None):
        """
        Renderiza la plantilla con las variables proporcionadas
        """
        variables = variables or {}
        
        # Renderizar texto del cuerpo
        body = self.body_text
        for var, value in variables.items():
            body = body.replace(f'{{{var}}}', str(value))
        
        return {
            'subject': self.subject,
            'body': body,
            'footer': self.footer_text
        }