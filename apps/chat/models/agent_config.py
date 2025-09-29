"""
Modelos para configuración de agentes LangChain
"""
import json
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from apps.companies.models import Company


class AgentConfig(models.Model):
    """Configuración básica de un agente"""

    AGENT_TYPES = [
        ('sii', 'Agente SII'),
        ('dte', 'Agente DTE'),
        ('general', 'Agente General'),
        ('onboarding', 'Agente Onboarding'),
        ('supervisor', 'Supervisor'),
    ]

    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('testing', 'En Pruebas'),
    ]

    name = models.CharField(max_length=100, verbose_name="Nombre del Agente")
    agent_type = models.CharField(
        max_length=20,
        choices=AGENT_TYPES,
        verbose_name="Tipo de Agente"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="Estado"
    )

    # Configuración del modelo
    model_name = models.CharField(
        max_length=50,
        default='gpt-4.1-nano',
        verbose_name="Modelo de IA"
    )
    temperature = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(2.0)],
        verbose_name="Temperatura"
    )
    max_tokens = models.IntegerField(
        default=2000,
        validators=[MinValueValidator(1), MaxValueValidator(8000)],
        verbose_name="Máximo de Tokens",
        blank=True,
        null=True
    )

    # Sistema de prompts
    system_prompt = models.TextField(
        verbose_name="Prompt del Sistema",
        help_text="Instrucciones principales que definen el comportamiento del agente"
    )
    context_instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name="Instrucciones de Contexto",
        help_text="Instrucciones específicas sobre el contexto y situación"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_agent_configs'
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='agent_configs',
        blank=True,
        null=True,
        verbose_name="Empresa"
    )

    # Configuración avanzada (JSON)
    advanced_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuración Avanzada",
        help_text="Configuración adicional en formato JSON"
    )

    class Meta:
        verbose_name = "Configuración de Agente"
        verbose_name_plural = "Configuraciones de Agentes"
        unique_together = ['agent_type', 'company']
        ordering = ['agent_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_agent_type_display()})"

    def is_active(self):
        return self.status == 'active'

    def get_full_config(self):
        """Retorna la configuración completa del agente"""
        return {
            'name': self.name,
            'agent_type': self.agent_type,
            'model_name': self.model_name,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'system_prompt': self.system_prompt,
            'context_instructions': self.context_instructions,
            'advanced_config': self.advanced_config,
            'status': self.status
        }


class AgentPrompt(models.Model):
    """Plantillas de prompts para agentes"""

    PROMPT_TYPES = [
        ('instruction', 'Instrucción'),
        ('example', 'Ejemplo'),
        ('constraint', 'Restricción'),
        ('template', 'Plantilla'),
        ('fallback', 'Respaldo'),
        ('knowledge', 'Conocimiento Específico'),
    ]

    agent_config = models.ForeignKey(
        AgentConfig,
        on_delete=models.CASCADE,
        related_name='prompts'
    )
    prompt_type = models.CharField(
        max_length=20,
        choices=PROMPT_TYPES,
        verbose_name="Tipo de Prompt"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre del Prompt"
    )
    content = models.TextField(
        verbose_name="Contenido del Prompt"
    )
    variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Variables Disponibles",
        help_text="Lista de variables que pueden ser usadas en el prompt"
    )

    # Configuración
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )
    priority = models.IntegerField(
        default=0,
        verbose_name="Prioridad",
        help_text="Orden de aplicación (mayor número = mayor prioridad)"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_prompts'
    )

    class Meta:
        verbose_name = "Prompt de Agente"
        verbose_name_plural = "Prompts de Agentes"
        ordering = ['-priority', 'prompt_type', 'name']
        unique_together = ['agent_config', 'prompt_type', 'name']

    def __str__(self):
        return f"{self.agent_config.name} - {self.name} ({self.get_prompt_type_display()})"

    def render(self, context=None):
        """Renderiza el prompt con las variables del contexto"""
        if not context:
            return self.content

        content = self.content
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            content = content.replace(placeholder, str(value))

        return content


class AgentTool(models.Model):
    """Configuración de herramientas disponibles para agentes"""

    TOOL_CATEGORIES = [
        ('sii', 'SII/FAQ'),
        ('dte', 'Documentos'),
        ('company', 'Empresa'),
        ('analysis', 'Análisis'),
        ('general', 'General'),
        ('external', 'Externa'),
    ]

    agent_config = models.ForeignKey(
        AgentConfig,
        on_delete=models.CASCADE,
        related_name='tools'
    )
    tool_name = models.CharField(
        max_length=100,
        verbose_name="Nombre de la Herramienta"
    )
    tool_function = models.CharField(
        max_length=200,
        verbose_name="Función/Clase de la Herramienta",
        help_text="Ruta completa a la función o clase (ej: apps.chat.services.tools.search_sii_faqs)"
    )
    category = models.CharField(
        max_length=20,
        choices=TOOL_CATEGORIES,
        verbose_name="Categoría"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )

    # Configuración
    is_enabled = models.BooleanField(
        default=True,
        verbose_name="Habilitada"
    )
    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Parámetros",
        help_text="Parámetros específicos de configuración para la herramienta"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tools'
    )

    class Meta:
        verbose_name = "Herramienta de Agente"
        verbose_name_plural = "Herramientas de Agentes"
        ordering = ['category', 'tool_name']
        unique_together = ['agent_config', 'tool_name']

    def __str__(self):
        return f"{self.agent_config.name} - {self.tool_name}"

    def get_tool_instance(self):
        """Importa y retorna la instancia de la herramienta"""
        try:
            module_path, function_name = self.tool_function.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            tool_func = getattr(module, function_name)
            return tool_func
        except (ImportError, AttributeError) as e:
            raise ValueError(f"No se pudo importar la herramienta {self.tool_function}: {e}")


class AgentModelConfig(models.Model):
    """Configuración específica del modelo de IA para agentes"""

    agent_config = models.OneToOneField(
        AgentConfig,
        on_delete=models.CASCADE,
        related_name='model_config'
    )

    # Configuración del modelo
    top_p = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Top P"
    )
    frequency_penalty = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-2.0), MaxValueValidator(2.0)],
        verbose_name="Penalización de Frecuencia"
    )
    presence_penalty = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-2.0), MaxValueValidator(2.0)],
        verbose_name="Penalización de Presencia"
    )

    # Configuración de stop sequences
    stop_sequences = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Secuencias de Parada",
        help_text="Lista de secuencias que detendrán la generación"
    )

    # Configuración de timeouts
    timeout_seconds = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        verbose_name="Timeout (segundos)"
    )

    # Configuración de reintentos
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name="Máximo de Reintentos"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Modelo"
        verbose_name_plural = "Configuraciones de Modelos"

    def __str__(self):
        return f"Configuración de modelo para {self.agent_config.name}"

    def get_openai_params(self):
        """Retorna parámetros formateados para OpenAI"""
        return {
            'model': self.agent_config.model_name,
            'temperature': self.agent_config.temperature,
            'max_tokens': self.agent_config.max_tokens,
            'top_p': self.top_p,
            'frequency_penalty': self.frequency_penalty,
            'presence_penalty': self.presence_penalty,
            'stop': self.stop_sequences if self.stop_sequences else None,
            'timeout': self.timeout_seconds
        }


class AgentVersion(models.Model):
    """Versionado de configuraciones de agentes"""

    agent_config = models.ForeignKey(
        AgentConfig,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.CharField(
        max_length=20,
        verbose_name="Número de Versión"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción de Cambios"
    )

    # Snapshot de la configuración
    config_snapshot = models.JSONField(
        verbose_name="Snapshot de Configuración"
    )

    # Estado
    is_current = models.BooleanField(
        default=False,
        verbose_name="Versión Actual"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_versions'
    )

    class Meta:
        verbose_name = "Versión de Configuración"
        verbose_name_plural = "Versiones de Configuraciones"
        ordering = ['-created_at']
        unique_together = ['agent_config', 'version_number']

    def __str__(self):
        return f"{self.agent_config.name} v{self.version_number}"

    def make_current(self):
        """Establece esta versión como la actual"""
        # Desmarcar todas las otras versiones
        AgentVersion.objects.filter(
            agent_config=self.agent_config
        ).update(is_current=False)

        # Marcar esta como actual
        self.is_current = True
        self.save()

        # Aplicar la configuración al agente
        self.restore_config()

    def restore_config(self):
        """Restaura la configuración desde este snapshot"""
        config = self.config_snapshot
        agent = self.agent_config

        # Actualizar configuración básica
        for field, value in config.items():
            if hasattr(agent, field):
                setattr(agent, field, value)

        agent.save()