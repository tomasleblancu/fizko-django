from django.db import models
from apps.core.models import TimeStampedModel

class TaskCategory(TimeStampedModel):
    """
    Categorías de tareas
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Color hexadecimal")
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'task_categories'
        verbose_name = 'Task Category'
        verbose_name_plural = 'Task Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Task(TimeStampedModel):
    """
    Tareas del sistema
    """
    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('normal', 'Normal'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
        ('failed', 'Fallida'),
    ]
    
    TASK_TYPES = [
        ('manual', 'Manual'),
        ('automatic', 'Automática'),
        ('scheduled', 'Programada'),
        ('recurring', 'Recurrente'),
    ]
    
    # Identificación
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='manual')
    category = models.ForeignKey(TaskCategory, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Asignación
    company_rut = models.CharField(max_length=12, blank=True)
    company_dv = models.CharField(max_length=1, blank=True)
    assigned_to = models.CharField(max_length=255, blank=True, help_text="Email del usuario asignado")
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")
    
    # Estado y prioridad
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # Fechas
    due_date = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Progreso
    progress_percentage = models.IntegerField(default=0, help_text="Porcentaje de progreso 0-100")
    estimated_duration = models.DurationField(null=True, blank=True)
    actual_duration = models.DurationField(null=True, blank=True)
    
    # Datos específicos
    task_data = models.JSONField(default=dict, help_text="Datos específicos de la tarea")
    result_data = models.JSONField(default=dict, help_text="Resultados de la ejecución")
    error_message = models.TextField(blank=True)
    
    # Recurrencia
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.JSONField(default=dict, help_text="Patrón de recurrencia")
    next_run = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tasks'
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company_rut', 'company_dv']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['due_date']),
            models.Index(fields=['task_type']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def is_overdue(self):
        """Verifica si la tarea está vencida"""
        if self.status in ['completed', 'cancelled'] or not self.due_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.due_date
    
    @property
    def company_full_rut(self):
        if self.company_rut and self.company_dv:
            return f"{self.company_rut}-{self.company_dv}"
        return ""
    
    def start_task(self):
        """Inicia la ejecución de la tarea"""
        from django.utils import timezone
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
    
    def complete_task(self, result_data=None):
        """Completa la tarea"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100
        if self.started_at:
            self.actual_duration = self.completed_at - self.started_at
        if result_data:
            self.result_data = result_data
        self.save()
    
    def fail_task(self, error_message=""):
        """Marca la tarea como fallida"""
        from django.utils import timezone
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        if self.started_at:
            self.actual_duration = self.completed_at - self.started_at
        self.save()


class TaskDependency(TimeStampedModel):
    """
    Dependencias entre tareas
    """
    DEPENDENCY_TYPES = [
        ('finish_to_start', 'Finalizar para Iniciar'),
        ('start_to_start', 'Iniciar para Iniciar'),
        ('finish_to_finish', 'Finalizar para Finalizar'),
        ('start_to_finish', 'Iniciar para Finalizar'),
    ]
    
    predecessor = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='successor_dependencies')
    successor = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='predecessor_dependencies')
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPES, default='finish_to_start')
    lag_days = models.IntegerField(default=0, help_text="Días de retraso/adelanto")
    
    class Meta:
        db_table = 'task_dependencies'
        verbose_name = 'Task Dependency'
        verbose_name_plural = 'Task Dependencies'
        unique_together = ['predecessor', 'successor']
    
    def __str__(self):
        return f"{self.predecessor.title} -> {self.successor.title}"


class TaskComment(TimeStampedModel):
    """
    Comentarios en tareas
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user_email = models.EmailField()
    comment = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Solo visible para el equipo interno")
    
    class Meta:
        db_table = 'task_comments'
        verbose_name = 'Task Comment'
        verbose_name_plural = 'Task Comments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.title} - Comentario por {self.user_email}"


class TaskAttachment(TimeStampedModel):
    """
    Archivos adjuntos a tareas
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='tasks/attachments/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="Tamaño en bytes")
    content_type = models.CharField(max_length=100)
    uploaded_by = models.EmailField()
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'task_attachments'
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task.title} - {self.filename}"
    
    @property
    def file_size_human(self):
        """Tamaño del archivo en formato legible"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class Process(TimeStampedModel):
    """
    Proceso completo que agrupa múltiples tareas relacionadas
    """
    PROCESS_STATUS = [
        ('draft', 'Borrador'),
        ('active', 'Activo'),
        ('paused', 'Pausado'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
    ]

    PROCESS_TYPES = [
        ('tax_monthly', 'Declaración Mensual'),
        ('tax_annual', 'Declaración Anual'),
        ('document_sync', 'Sincronización Documentos'),
        ('sii_integration', 'Integración SII'),
        ('custom', 'Personalizado'),
    ]

    # Identificación
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    process_type = models.CharField(max_length=50, choices=PROCESS_TYPES)

    # Asociación a empresa
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)

    # Estado del proceso
    status = models.CharField(max_length=20, choices=PROCESS_STATUS, default='draft')

    # Configuración
    is_template = models.BooleanField(default=False)
    parent_process = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)

    # Usuario responsable
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")
    assigned_to = models.CharField(max_length=255, blank=True, help_text="Email del usuario responsable")

    # Fechas importantes
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Configuración del proceso
    config_data = models.JSONField(default=dict, help_text="Configuración específica del proceso")

    class Meta:
        db_table = 'processes'
        verbose_name = 'Process'
        verbose_name_plural = 'Processes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company_rut', 'company_dv']),
            models.Index(fields=['status', 'process_type']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def progress_percentage(self):
        """Calcula progreso basado en tareas completadas"""
        tasks = self.process_tasks.all()
        if not tasks.exists():
            return 0
        completed = tasks.filter(task__status='completed').count()
        return int((completed / tasks.count()) * 100)

    @property
    def current_step(self):
        """Obtiene el paso actual del proceso"""
        return self.process_tasks.filter(
            task__status__in=['pending', 'in_progress']
        ).order_by('execution_order').first()

    @property
    def is_overdue(self):
        """Verifica si el proceso está vencido"""
        if self.status in ['completed', 'cancelled'] or not self.due_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.due_date

    @property
    def company_full_rut(self):
        if self.company_rut and self.company_dv:
            return f"{self.company_rut}-{self.company_dv}"
        return ""

    def start_process(self):
        """Inicia la ejecución del proceso"""
        from django.utils import timezone
        self.status = 'active'
        self.start_date = timezone.now()
        self.save()

    def complete_process(self):
        """Completa el proceso"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def fail_process(self, error_message=""):
        """Marca el proceso como fallido"""
        from django.utils import timezone
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.save()


class ProcessTemplate(TimeStampedModel):
    """
    Plantillas reutilizables de procesos
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    process_type = models.CharField(max_length=50, choices=Process.PROCESS_TYPES)
    template_data = models.JSONField(default=dict, help_text="Configuración de la plantilla")
    is_active = models.BooleanField(default=True)
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")

    class Meta:
        db_table = 'process_templates'
        verbose_name = 'Process Template'
        verbose_name_plural = 'Process Templates'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_process_type_display()})"


class ProcessTask(TimeStampedModel):
    """
    Relación entre procesos y tareas con metadata adicional
    """
    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='process_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_processes')

    # Orden de ejecución
    execution_order = models.IntegerField(default=0)

    # Condiciones para ejecutar esta tarea
    execution_conditions = models.JSONField(default=dict, help_text="Condiciones para ejecutar la tarea")

    # Es opcional en el proceso?
    is_optional = models.BooleanField(default=False)

    # Se ejecuta en paralelo con otras tareas?
    can_run_parallel = models.BooleanField(default=False)

    # Datos específicos para esta tarea en el contexto del proceso
    context_data = models.JSONField(default=dict, help_text="Datos de contexto para la tarea")

    class Meta:
        db_table = 'process_tasks'
        verbose_name = 'Process Task'
        verbose_name_plural = 'Process Tasks'
        unique_together = ['process', 'task']
        ordering = ['execution_order']

    def __str__(self):
        return f"{self.process.name} -> {self.task.title}"


class ProcessExecution(TimeStampedModel):
    """
    Instancia de ejecución de un proceso con seguimiento detallado
    """
    EXECUTION_STATUS = [
        ('running', 'Ejecutándose'),
        ('paused', 'Pausado'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
        ('cancelled', 'Cancelado'),
    ]

    process = models.ForeignKey(Process, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=20, choices=EXECUTION_STATUS, default='running')

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Contexto de ejecución
    execution_context = models.JSONField(default=dict, help_text="Contexto global de la ejecución")
    current_step = models.IntegerField(default=0)

    # Métricas
    total_steps = models.IntegerField(default=0)
    completed_steps = models.IntegerField(default=0)
    failed_steps = models.IntegerField(default=0)

    # Error tracking
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'process_executions'
        verbose_name = 'Process Execution'
        verbose_name_plural = 'Process Executions'
        ordering = ['-started_at']

    def __str__(self):
        return f"Ejecución {self.id} - {self.process.name}"

    @property
    def progress_percentage(self):
        """Progreso de la ejecución"""
        if self.total_steps == 0:
            return 0
        return int((self.completed_steps / self.total_steps) * 100)

    @property
    def duration(self):
        """Duración de la ejecución"""
        if not self.completed_at:
            from django.utils import timezone
            return timezone.now() - self.started_at
        return self.completed_at - self.started_at


class TaskLog(TimeStampedModel):
    """
    Log de ejecución de tareas
    """
    LOG_LEVELS = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='logs')
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='info')
    message = models.TextField()
    details = models.JSONField(default=dict, help_text="Detalles adicionales")
    
    class Meta:
        db_table = 'task_logs'
        verbose_name = 'Task Log'
        verbose_name_plural = 'Task Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', 'level']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.task.title} - {self.get_level_display()}: {self.message[:50]}"


class TaskSchedule(TimeStampedModel):
    """
    Programación de tareas automáticas
    """
    SCHEDULE_TYPES = [
        ('once', 'Una vez'),
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('yearly', 'Anual'),
        ('cron', 'Expresión Cron'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPES)
    schedule_expression = models.CharField(max_length=100, help_text="Expresión de programación")
    
    # Tarea a ejecutar
    task_template = models.JSONField(help_text="Plantilla de la tarea a crear")
    
    # Estado
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    run_count = models.IntegerField(default=0)
    
    # Límites
    max_runs = models.IntegerField(null=True, blank=True, help_text="Máximo número de ejecuciones")
    end_date = models.DateTimeField(null=True, blank=True, help_text="Fecha de finalización")
    
    class Meta:
        db_table = 'task_schedules'
        verbose_name = 'Task Schedule'
        verbose_name_plural = 'Task Schedules'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_schedule_type_display()})"
    
    @property
    def is_expired(self):
        """Verifica si la programación ha expirado"""
        if self.max_runs and self.run_count >= self.max_runs:
            return True
        if self.end_date:
            from django.utils import timezone
            return timezone.now() > self.end_date
        return False
