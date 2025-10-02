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
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.CASCADE,
        related_name='processes',
        help_text="Empresa a la que pertenece este proceso",
        null=True,  # Temporal para migración
        blank=True
    )
    company_rut = models.CharField(max_length=12)
    company_dv = models.CharField(max_length=1)

    # Estado del proceso
    status = models.CharField(max_length=20, choices=PROCESS_STATUS, default='active')

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

    # Recurrencia
    is_recurring = models.BooleanField(default=False, help_text="Si este proceso se repite automáticamente")
    recurrence_type = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral'),
            ('annual', 'Anual'),
            ('custom', 'Personalizado'),
        ],
        blank=True,
        null=True,
        help_text="Tipo de recurrencia"
    )
    recurrence_config = models.JSONField(
        default=dict,
        help_text="Configuración de recurrencia: intervalos, fechas base, etc."
    )
    next_occurrence_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha en que se debe generar el siguiente proceso"
    )
    recurrence_source = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recurring_instances',
        help_text="Proceso padre del cual se generó este por recurrencia"
    )

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

    def fail_process(self, error_message=""):
        """Marca el proceso como fallido"""
        from django.utils import timezone
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.save()

    def complete_process(self):
        """Completa el proceso y genera el siguiente si es recurrente"""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        # Si es recurrente, programar la generación del siguiente
        if self.is_recurring and self.recurrence_type:
            self._schedule_next_occurrence()

    def _schedule_next_occurrence(self):
        """Programa la generación del siguiente proceso recurrente"""
        if not self.is_recurring:
            return

        # COMENTADO: No generar inmediatamente el siguiente proceso
        # Los procesos recurrentes se deben generar SOLO cuando el actual se completa
        #
        # Para procesos futuros programados (no mensual), se puede implementar esto:
        # if self.recurrence_type != 'monthly':
        #     next_date = self._calculate_next_occurrence_date()
        #     if next_date:
        #         from .tasks import create_recurring_process
        #         create_recurring_process.apply_async(
        #             args=[self.id],
        #             eta=next_date
        #         )

    def _calculate_next_occurrence_date(self):
        """Calcula la fecha del siguiente proceso"""
        from dateutil.relativedelta import relativedelta
        from django.utils import timezone

        if not self.completed_at:
            return None

        base_date = self.completed_at
        config = self.recurrence_config

        if self.recurrence_type == 'monthly':
            # Para F29: generar el proceso del siguiente mes
            period_month = config.get('period_month')
            period_year = config.get('period_year')

            if period_month and period_year:
                # Calcular siguiente período
                next_month = period_month + 1
                next_year = period_year

                if next_month > 12:
                    next_month = 1
                    next_year += 1

                # El proceso se debe crear unos días antes del vencimiento
                # F29 vence el día 12 del mes siguiente al período
                from datetime import datetime
                next_process_date = datetime(next_year, next_month, 5)  # Crear el 5 del mes
                return timezone.make_aware(next_process_date)

        elif self.recurrence_type == 'quarterly':
            return base_date + relativedelta(months=3)
        elif self.recurrence_type == 'annual':
            return base_date + relativedelta(years=1)
        elif self.recurrence_type == 'custom':
            # Usar configuración personalizada
            days = config.get('interval_days', 30)
            return base_date + relativedelta(days=days)

        return None

    def generate_next_occurrence(self):
        """Genera el siguiente proceso en la serie recurrente"""
        if not self.is_recurring:
            return None

        # Calcular datos del siguiente período
        next_period_data = self._calculate_next_period_data()

        # Crear el nuevo proceso
        next_process = Process.objects.create(
            name=next_period_data['name'],
            description=next_period_data['description'],
            process_type=self.process_type,
            company_rut=self.company_rut,
            company_dv=self.company_dv,
            created_by=self.created_by,
            assigned_to=self.assigned_to,
            due_date=next_period_data['due_date'],
            config_data=next_period_data['config_data'],
            is_recurring=self.is_recurring,
            recurrence_type=self.recurrence_type,
            recurrence_config=self.recurrence_config,
            recurrence_source=self,
            status='active'
        )

        # Copiar las tareas del proceso original
        self._copy_tasks_to_next_process(next_process, next_period_data)

        return next_process

    def _calculate_next_period_data(self):
        """Calcula los datos específicos del siguiente período"""
        config = self.recurrence_config

        if self.recurrence_type == 'monthly':
            # Para procesos mensuales como F29
            current_month = config.get('period_month', 1)
            current_year = config.get('period_year', 2024)

            next_month = current_month + 1
            next_year = current_year

            if next_month > 12:
                next_month = 1
                next_year += 1

            # Calcular fecha de vencimiento (F29 vence el 12 del mes siguiente)
            from datetime import datetime
            from django.utils import timezone
            due_date = timezone.make_aware(datetime(next_year, next_month + 1 if next_month < 12 else 1, 12))
            if next_month == 12:  # Si es diciembre, vence en enero del siguiente año
                due_date = timezone.make_aware(datetime(next_year + 1, 1, 12))

            return {
                'name': f"F29 {next_month:02d}-{next_year} - {self.company_rut}-{self.company_dv}",
                'description': f"Declaración F29 para el período {next_month:02d}/{next_year}",
                'due_date': due_date,
                'config_data': {
                    **config,
                    'period_month': next_month,
                    'period_year': next_year,
                    'period': f"{next_year}-{next_month:02d}"
                }
            }

        # Agregar más tipos de recurrencia según necesidad
        return {}

    def _copy_tasks_to_next_process(self, next_process, period_data):
        """Copia las tareas del proceso actual al siguiente"""
        from datetime import timedelta

        for process_task in self.process_tasks.all():
            # Crear nueva tarea basada en la original
            new_task = Task.objects.create(
                title=self._update_task_title_for_period(process_task.task.title, period_data),
                description=process_task.task.description,
                task_type=process_task.task.task_type,
                company_rut=self.company_rut,
                company_dv=self.company_dv,
                assigned_to=self.assigned_to,
                created_by=self.created_by,
                status='pending',
                task_data={
                    **process_task.task.task_data,
                    **period_data['config_data']
                }
            )

            # Calcular fecha límite para esta tarea
            task_due_date = self._calculate_task_due_date(process_task, next_process)
            if task_due_date:
                new_task.due_date = task_due_date
                new_task.save()

            # Crear la relación ProcessTask
            ProcessTask.objects.create(
                process=next_process,
                task=new_task,
                execution_order=process_task.execution_order,
                execution_conditions=process_task.execution_conditions,
                is_optional=process_task.is_optional,
                can_run_parallel=process_task.can_run_parallel,
                context_data=process_task.context_data,
                due_date_offset_days=process_task.due_date_offset_days,
                due_date_from_previous=process_task.due_date_from_previous,
                absolute_due_date=process_task.absolute_due_date
            )

    def _update_task_title_for_period(self, original_title, period_data):
        """Actualiza el título de la tarea para el nuevo período"""
        config = period_data['config_data']
        period = config.get('period', '')

        # Reemplazar referencias de período en el título
        if 'F29' in original_title and period:
            return original_title.replace('F29', f"F29 {period}")

        return f"{original_title} - {period}" if period else original_title

    def _calculate_task_due_date(self, process_task, next_process):
        """Calcula la fecha límite para una tarea específica"""
        from datetime import timedelta

        # Si tiene fecha absoluta, usarla
        if process_task.absolute_due_date:
            return process_task.absolute_due_date

        # Si tiene offset desde inicio del proceso
        if process_task.due_date_offset_days and next_process.start_date:
            return next_process.start_date + timedelta(days=process_task.due_date_offset_days)

        # Si depende de la tarea anterior
        if process_task.due_date_from_previous:
            previous_task = next_process.process_tasks.filter(
                execution_order__lt=process_task.execution_order
            ).order_by('-execution_order').first()

            if previous_task and previous_task.task.due_date:
                return previous_task.task.due_date + timedelta(days=process_task.due_date_from_previous)

        # Por defecto, usar la fecha límite del proceso
        return next_process.due_date


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

    # Fechas límite específicas para esta tarea en el proceso
    due_date_offset_days = models.IntegerField(
        null=True,
        blank=True,
        help_text="Días desde el inicio del proceso para calcular fecha límite"
    )
    due_date_from_previous = models.IntegerField(
        null=True,
        blank=True,
        help_text="Días desde completación de tarea anterior para calcular fecha límite"
    )
    absolute_due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha límite absoluta para esta tarea (sobrescribe cálculos)"
    )

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


# ============================================================================
# SISTEMA DE GESTIÓN DE PROCESOS TRIBUTARIOS
# ============================================================================

class CompanySegment(TimeStampedModel):
    """
    Segmentación de empresas para asignación automática de procesos tributarios
    """
    SEGMENT_TYPES = [
        ('size', 'Por Tamaño'),
        ('industry', 'Por Actividad Económica'),
        ('tax_regime', 'Por Régimen Tributario'),
        ('revenue', 'Por Ingresos'),
        ('custom', 'Personalizado'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del Segmento")
    description = models.TextField(blank=True, verbose_name="Descripción")
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPES, verbose_name="Tipo de Segmento")

    # Criterios de segmentación (JSON)
    criteria = models.JSONField(
        default=dict,
        help_text="Criterios de segmentación en formato JSON. "
                  "Ejemplo: {'size': {'min_employees': 10, 'max_employees': 50}, 'tax_regime': ['14A', '14B']}"
    )

    # Estado
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    # Metadata
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")

    class Meta:
        db_table = 'company_segments'
        verbose_name = 'Segmento de Empresas'
        verbose_name_plural = 'Segmentos de Empresas'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_segment_type_display()})"

    def get_matching_companies(self):
        """Retorna las empresas que cumplen con los criterios de este segmento"""
        from apps.companies.models import Company
        from apps.taxpayers.models import TaxPayer

        # Por ahora retorna las que tienen el segmento asignado explícitamente
        # TODO: Implementar evaluación dinámica de criterios
        return TaxPayer.objects.filter(company_segment=self).select_related('company')

    def evaluate_company(self, company):
        """Evalúa si una empresa cumple con los criterios del segmento"""
        if not self.criteria:
            return False

        # TODO: Implementar lógica de evaluación de criterios
        # Por ahora retorna False, se implementará en el servicio
        return False


class ProcessTemplateConfig(TimeStampedModel):
    """
    Configuración avanzada de plantillas de procesos tributarios
    Similar a AgentConfig pero para procesos
    """
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('testing', 'En Pruebas'),
    ]

    # Identificación
    name = models.CharField(max_length=255, verbose_name="Nombre de la Plantilla")
    description = models.TextField(blank=True, verbose_name="Descripción")
    process_type = models.CharField(max_length=50, choices=Process.PROCESS_TYPES, verbose_name="Tipo de Proceso")

    # Estado
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name="Estado")
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    # Configuración de recurrencia por defecto
    default_recurrence_type = models.CharField(
        max_length=20,
        choices=Process._meta.get_field('recurrence_type').choices,
        blank=True,
        null=True,
        verbose_name="Recurrencia por Defecto"
    )
    default_recurrence_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuración de Recurrencia",
        help_text="Configuración de recurrencia por defecto para procesos creados con esta plantilla"
    )

    # Configuración de la plantilla
    template_config = models.JSONField(
        default=dict,
        verbose_name="Configuración de la Plantilla",
        help_text="Configuración completa de la plantilla: estructura, variables, valores por defecto"
    )

    # Variables disponibles
    available_variables = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Variables Disponibles",
        help_text="Lista de variables que pueden ser usadas en esta plantilla"
    )

    # Valores por defecto
    default_values = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Valores por Defecto",
        help_text="Valores por defecto para las variables de la plantilla"
    )

    # Estadísticas de uso
    usage_count = models.IntegerField(default=0, verbose_name="Veces Utilizado")
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name="Último Uso")

    # Metadata
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")

    class Meta:
        db_table = 'process_template_configs'
        verbose_name = 'Configuración de Plantilla de Proceso'
        verbose_name_plural = 'Configuraciones de Plantillas de Procesos'
        ordering = ['process_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_process_type_display()})"

    def is_available(self):
        """Verifica si la plantilla está disponible para uso"""
        return self.is_active and self.status == 'active'

    def increment_usage(self):
        """Incrementa el contador de uso"""
        from django.utils import timezone
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])


class ProcessTemplateTask(TimeStampedModel):
    """
    Tareas predefinidas dentro de una plantilla de proceso
    Define la estructura de tareas que se crearán cuando se aplique la plantilla
    """
    TASK_TYPES = Task.TASK_TYPES
    PRIORITY_CHOICES = Task.PRIORITY_CHOICES

    template = models.ForeignKey(
        ProcessTemplateConfig,
        on_delete=models.CASCADE,
        related_name='template_tasks',
        verbose_name="Plantilla"
    )

    # Definición de la tarea
    task_title = models.CharField(max_length=255, verbose_name="Título de la Tarea")
    task_description = models.TextField(blank=True, verbose_name="Descripción")
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default='manual', verbose_name="Tipo de Tarea")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', verbose_name="Prioridad")

    # Orden y dependencias
    execution_order = models.IntegerField(default=0, verbose_name="Orden de Ejecución")
    depends_on = models.ManyToManyField(
        'self',
        symmetrical=False,
        blank=True,
        related_name='dependent_tasks',
        verbose_name="Depende de"
    )

    # Opcionalidad y paralelización
    is_optional = models.BooleanField(default=False, verbose_name="Es Opcional")
    can_run_parallel = models.BooleanField(default=False, verbose_name="Puede Ejecutarse en Paralelo")

    # Configuración de plazos
    due_date_offset_days = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Días de Plazo",
        help_text="Días desde el inicio del proceso para calcular fecha límite"
    )
    due_date_from_previous = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Días desde Tarea Anterior",
        help_text="Días desde completación de tarea anterior"
    )

    # Duración estimada
    estimated_hours = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Horas Estimadas",
        help_text="Duración estimada en horas"
    )

    # Configuración adicional
    task_config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configuración de la Tarea",
        help_text="Configuración específica de la tarea"
    )

    class Meta:
        db_table = 'process_template_tasks'
        verbose_name = 'Tarea de Plantilla'
        verbose_name_plural = 'Tareas de Plantilla'
        ordering = ['template', 'execution_order']
        unique_together = ['template', 'execution_order']

    def __str__(self):
        return f"{self.template.name} - {self.task_title}"


class ProcessAssignmentRule(TimeStampedModel):
    """
    Reglas de asignación automática de plantillas de procesos a segmentos de empresas
    """
    template = models.ForeignKey(
        ProcessTemplateConfig,
        on_delete=models.CASCADE,
        related_name='assignment_rules',
        verbose_name="Plantilla"
    )
    segment = models.ForeignKey(
        CompanySegment,
        on_delete=models.CASCADE,
        related_name='assignment_rules',
        verbose_name="Segmento"
    )

    # Condiciones adicionales
    conditions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Condiciones Adicionales",
        help_text="Condiciones específicas adicionales a los criterios del segmento"
    )

    # Prioridad
    priority = models.IntegerField(
        default=0,
        verbose_name="Prioridad",
        help_text="Orden de aplicación (mayor número = mayor prioridad)"
    )

    # Vigencia
    start_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Inicio")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Fin")

    # Estado
    is_active = models.BooleanField(default=True, verbose_name="Activo")

    # Configuración de aplicación
    auto_apply = models.BooleanField(
        default=True,
        verbose_name="Aplicar Automáticamente",
        help_text="Si se debe aplicar automáticamente cuando una empresa cumple los criterios"
    )

    # Metadata
    created_by = models.CharField(max_length=255, help_text="Email del usuario creador")

    class Meta:
        db_table = 'process_assignment_rules'
        verbose_name = 'Regla de Asignación de Procesos'
        verbose_name_plural = 'Reglas de Asignación de Procesos'
        ordering = ['-priority', 'template', 'segment']
        unique_together = ['template', 'segment']

    def __str__(self):
        return f"{self.template.name} → {self.segment.name}"

    def is_valid(self):
        """Verifica si la regla está vigente"""
        from django.utils import timezone
        now = timezone.now()

        if not self.is_active:
            return False

        if self.start_date and now < self.start_date:
            return False

        if self.end_date and now > self.end_date:
            return False

        return True

    def applies_to_company(self, company):
        """Verifica si esta regla aplica a una empresa específica"""
        if not self.is_valid():
            return False

        # Verificar si la empresa pertenece al segmento
        if not hasattr(company, 'taxpayer'):
            return False

        taxpayer = company.taxpayer
        if taxpayer.company_segment != self.segment:
            # Evaluar si cumple los criterios del segmento
            if not self.segment.evaluate_company(company):
                return False

        # TODO: Evaluar condiciones adicionales

        return True
