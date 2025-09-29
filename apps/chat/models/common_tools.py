"""
Sistema de herramientas comunes reutilizables para agentes
"""
import json
from django.db import models
from django.conf import settings
from apps.companies.models import Company


class ToolCategory(models.Model):
    """Categorías de herramientas disponibles"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descripción"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Icono",
        help_text="Nombre del icono (ej: database, search, calculator)"
    )
    color = models.CharField(
        max_length=7,
        default="#6B7280",
        verbose_name="Color",
        help_text="Color hexadecimal (ej: #3B82F6)"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Categoría de Herramienta"
        verbose_name_plural = "Categorías de Herramientas"
        ordering = ['name']

    def __str__(self):
        return self.name

    def tools_count(self):
        return self.common_tools.count()


class CommonTool(models.Model):
    """Herramientas comunes reutilizables"""

    TOOL_TYPES = [
        ('function', 'Función Python'),
        ('api', 'API Externa'),
        ('database', 'Consulta Base de Datos'),
        ('file', 'Procesamiento de Archivos'),
        ('calculation', 'Cálculo'),
        ('search', 'Búsqueda'),
        ('validation', 'Validación'),
        ('integration', 'Integración'),
    ]

    PARAMETER_TYPES = [
        ('string', 'Texto'),
        ('integer', 'Número Entero'),
        ('float', 'Número Decimal'),
        ('boolean', 'Verdadero/Falso'),
        ('array', 'Lista'),
        ('object', 'Objeto'),
        ('file', 'Archivo'),
        ('date', 'Fecha'),
    ]

    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    display_name = models.CharField(
        max_length=200,
        verbose_name="Nombre a Mostrar"
    )
    description = models.TextField(verbose_name="Descripción")
    category = models.ForeignKey(
        ToolCategory,
        on_delete=models.CASCADE,
        related_name='common_tools'
    )

    # Configuración técnica
    tool_type = models.CharField(
        max_length=20,
        choices=TOOL_TYPES,
        verbose_name="Tipo de Herramienta"
    )
    function_path = models.CharField(
        max_length=500,
        verbose_name="Ruta de la Función",
        help_text="Ruta completa a la función (ej: apps.chat.tools.search_documents)"
    )

    # Configuración de parámetros
    parameters_schema = models.JSONField(
        default=dict,
        verbose_name="Esquema de Parámetros",
        help_text="Definición JSON de los parámetros que acepta la herramienta"
    )
    required_parameters = models.JSONField(
        default=list,
        verbose_name="Parámetros Requeridos",
        help_text="Lista de parámetros obligatorios"
    )

    # Configuración de respuesta
    response_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Esquema de Respuesta",
        help_text="Formato esperado de la respuesta"
    )

    # Configuración de seguridad
    requires_authentication = models.BooleanField(
        default=True,
        verbose_name="Requiere Autenticación"
    )
    company_scope = models.BooleanField(
        default=True,
        verbose_name="Limitado por Empresa",
        help_text="Si la herramienta debe estar limitada al contexto de la empresa"
    )
    allowed_roles = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Roles Permitidos",
        help_text="Lista de roles que pueden usar esta herramienta"
    )

    # Estado y configuración
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    is_system = models.BooleanField(
        default=False,
        verbose_name="Herramienta del Sistema",
        help_text="Herramientas del sistema no pueden ser eliminadas"
    )
    max_calls_per_session = models.IntegerField(
        default=100,
        verbose_name="Máximo de Llamadas por Sesión"
    )

    # Documentación
    usage_examples = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ejemplos de Uso",
        help_text="Ejemplos de cómo usar la herramienta"
    )
    documentation_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="URL de Documentación"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_common_tools'
    )

    # Estadísticas
    usage_count = models.IntegerField(default=0, verbose_name="Contador de Uso")
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Último Uso"
    )

    class Meta:
        verbose_name = "Herramienta Común"
        verbose_name_plural = "Herramientas Comunes"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.display_name} ({self.category.name})"

    def get_function(self):
        """Importa y retorna la función de la herramienta"""
        try:
            module_path, function_name = self.function_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[function_name])
            return getattr(module, function_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"No se pudo importar la función {self.function_path}: {e}")

    def validate_parameters(self, parameters):
        """Valida los parámetros según el esquema"""
        # Verificar parámetros requeridos
        for required_param in self.required_parameters:
            if required_param not in parameters:
                raise ValueError(f"Parámetro requerido faltante: {required_param}")

        # Validar tipos según esquema
        for param_name, param_value in parameters.items():
            if param_name in self.parameters_schema:
                expected_type = self.parameters_schema[param_name].get('type')
                if not self._validate_parameter_type(param_value, expected_type):
                    raise ValueError(
                        f"Tipo incorrecto para parámetro {param_name}. "
                        f"Esperado: {expected_type}"
                    )

        return True

    def _validate_parameter_type(self, value, expected_type):
        """Valida el tipo de un parámetro específico"""
        type_validators = {
            'string': lambda v: isinstance(v, str),
            'integer': lambda v: isinstance(v, int),
            'float': lambda v: isinstance(v, (int, float)),
            'boolean': lambda v: isinstance(v, bool),
            'array': lambda v: isinstance(v, list),
            'object': lambda v: isinstance(v, dict),
            'file': lambda v: hasattr(v, 'read'),  # File-like object
        }

        validator = type_validators.get(expected_type)
        return validator(value) if validator else True

    def increment_usage(self):
        """Incrementa el contador de uso"""
        from django.utils import timezone
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])


class AgentToolAssignment(models.Model):
    """Asignación de herramientas comunes a agentes específicos"""

    agent_config = models.ForeignKey(
        'AgentConfig',
        on_delete=models.CASCADE,
        related_name='tool_assignments'
    )
    common_tool = models.ForeignKey(
        CommonTool,
        on_delete=models.CASCADE,
        related_name='agent_assignments'
    )

    # Configuración específica para este agente
    is_enabled = models.BooleanField(default=True, verbose_name="Habilitada")
    custom_parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Parámetros Personalizados",
        help_text="Parámetros específicos para este agente"
    )
    priority = models.IntegerField(
        default=0,
        verbose_name="Prioridad",
        help_text="Orden de preferencia en caso de herramientas similares"
    )

    # Limitaciones específicas
    max_calls_override = models.IntegerField(
        blank=True,
        null=True,
        verbose_name="Límite de Llamadas (Override)",
        help_text="Anula el límite global para este agente"
    )

    # Metadatos
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tool_assignments'
    )

    class Meta:
        verbose_name = "Asignación de Herramienta"
        verbose_name_plural = "Asignaciones de Herramientas"
        unique_together = ['agent_config', 'common_tool']
        ordering = ['-priority', 'common_tool__name']

    def __str__(self):
        return f"{self.agent_config.name} -> {self.common_tool.display_name}"

    def get_effective_max_calls(self):
        """Retorna el límite efectivo de llamadas"""
        return (self.max_calls_override
                if self.max_calls_override is not None
                else self.common_tool.max_calls_per_session)


class ToolUsageLog(models.Model):
    """Log de uso de herramientas para auditoría"""

    agent_config = models.ForeignKey(
        'AgentConfig',
        on_delete=models.CASCADE,
        related_name='tool_usage_logs'
    )
    common_tool = models.ForeignKey(
        CommonTool,
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tool_usage_logs',
        blank=True,
        null=True
    )

    # Detalles de la ejecución
    session_id = models.CharField(
        max_length=100,
        verbose_name="ID de Sesión"
    )
    parameters_used = models.JSONField(
        default=dict,
        verbose_name="Parámetros Utilizados"
    )
    response_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Datos de Respuesta"
    )

    # Resultado
    success = models.BooleanField(verbose_name="Exitoso")
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Mensaje de Error"
    )
    execution_time_ms = models.IntegerField(
        verbose_name="Tiempo de Ejecución (ms)"
    )

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="Dirección IP"
    )

    class Meta:
        verbose_name = "Log de Uso de Herramienta"
        verbose_name_plural = "Logs de Uso de Herramientas"
        ordering = ['-created_at']

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.common_tool.display_name} - {self.created_at}"