from django.contrib import admin
from django.utils.html import format_html
from .models import (
    TaskCategory, Task, TaskDependency, TaskComment, TaskAttachment, TaskLog, TaskSchedule,
    Process, ProcessTemplate, ProcessTask, ProcessExecution,
    CompanySegment, ProcessTemplateConfig, ProcessTemplateTask, ProcessAssignmentRule
)

@admin.register(TaskCategory)
class TaskCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'assigned_to', 'status', 'priority', 'due_date', 'is_overdue')
    list_filter = ('status', 'priority', 'task_type', 'category', 'due_date')
    search_fields = ('title', 'description', 'assigned_to', 'created_by')
    readonly_fields = ('is_overdue', 'company_full_rut', 'actual_duration')

@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ('predecessor', 'successor', 'dependency_type', 'lag_days')
    list_filter = ('dependency_type',)

@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user_email', 'is_internal', 'created_at')
    list_filter = ('is_internal', 'created_at')

@admin.register(TaskSchedule)
class TaskScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'schedule_type', 'is_active', 'next_run', 'run_count', 'is_expired')
    list_filter = ('schedule_type', 'is_active')
    readonly_fields = ('is_expired',)


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ('name', 'process_type', 'status', 'company', 'company_full_rut', 'progress_percentage', 'due_date', 'is_recurring', 'is_overdue')
    list_filter = ('status', 'process_type', 'company', 'is_template', 'is_recurring', 'recurrence_type', 'due_date')
    search_fields = ('name', 'description', 'company__name', 'company_rut', 'assigned_to', 'created_by')
    readonly_fields = ('progress_percentage', 'company_full_rut', 'is_overdue', 'current_step')
    date_hierarchy = 'due_date'

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'process_type', 'status')
        }),
        ('Empresa', {
            'fields': ('company', 'company_rut', 'company_dv', 'company_full_rut')
        }),
        ('Asignación', {
            'fields': ('created_by', 'assigned_to')
        }),
        ('Fechas', {
            'fields': ('start_date', 'due_date', 'completed_at')
        }),
        ('Recurrencia', {
            'fields': ('is_recurring', 'recurrence_type', 'recurrence_config', 'next_occurrence_date', 'recurrence_source'),
            'classes': ('collapse',)
        }),
        ('Configuración', {
            'fields': ('is_template', 'parent_process', 'config_data'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('progress_percentage', 'current_step', 'is_overdue'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProcessTemplate)
class ProcessTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'process_type', 'is_active', 'created_by', 'created_at')
    list_filter = ('process_type', 'is_active')
    search_fields = ('name', 'description', 'created_by')


class ProcessTaskInline(admin.TabularInline):
    model = ProcessTask
    extra = 0
    fields = ('task', 'execution_order', 'is_optional', 'can_run_parallel', 'due_date_offset_days', 'due_date_from_previous')
    ordering = ('execution_order',)


@admin.register(ProcessTask)
class ProcessTaskAdmin(admin.ModelAdmin):
    list_display = ('process', 'task', 'execution_order', 'is_optional', 'can_run_parallel', 'due_date_offset_days')
    list_filter = ('is_optional', 'can_run_parallel')
    search_fields = ('process__name', 'task__title')
    ordering = ('process', 'execution_order')

    fieldsets = (
        ('Básico', {
            'fields': ('process', 'task', 'execution_order')
        }),
        ('Configuración', {
            'fields': ('is_optional', 'can_run_parallel', 'execution_conditions', 'context_data')
        }),
        ('Fechas Límite', {
            'fields': ('due_date_offset_days', 'due_date_from_previous', 'absolute_due_date'),
            'description': 'Configuración de fechas límite para esta tarea en el proceso'
        }),
    )


@admin.register(ProcessExecution)
class ProcessExecutionAdmin(admin.ModelAdmin):
    list_display = ('process', 'status', 'progress_percentage', 'started_at', 'duration')
    list_filter = ('status', 'started_at')
    search_fields = ('process__name',)
    readonly_fields = ('progress_percentage', 'duration')
    date_hierarchy = 'started_at'


# ============================================================================
# ADMINISTRADORES PARA SISTEMA DE GESTIÓN DE PROCESOS TRIBUTARIOS
# ============================================================================

@admin.register(CompanySegment)
class CompanySegmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'segment_type', 'matching_companies_count', 'is_active', 'created_at']
    list_filter = ['segment_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'matching_companies_count']

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'segment_type', 'is_active')
        }),
        ('Criterios de Segmentación', {
            'fields': ('criteria',),
            'description': 'Define los criterios para asignar empresas a este segmento'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    actions = ['view_matching_companies', 'activate_segments', 'deactivate_segments']

    def matching_companies_count(self, obj):
        count = obj.get_matching_companies().count()
        return format_html('<strong>{}</strong> empresas', count)
    matching_companies_count.short_description = 'Empresas en Segmento'

    def view_matching_companies(self, request, queryset):
        # TODO: Implementar vista de empresas en segmento
        self.message_user(request, "Funcionalidad en desarrollo")
    view_matching_companies.short_description = "Ver empresas en segmento"

    def activate_segments(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} segmento(s) activado(s).")
    activate_segments.short_description = "Activar segmentos"

    def deactivate_segments(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} segmento(s) desactivado(s).")
    deactivate_segments.short_description = "Desactivar segmentos"


class ProcessTemplateTaskInline(admin.TabularInline):
    model = ProcessTemplateTask
    extra = 1
    fields = ['task_title', 'execution_order', 'priority', 'task_type', 'is_optional', 'due_date_offset_days', 'estimated_hours']
    ordering = ['execution_order']


@admin.register(ProcessTemplateConfig)
class ProcessTemplateConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'process_type', 'status_badge', 'tasks_count', 'usage_count', 'last_used_at', 'created_at']
    list_filter = ['process_type', 'status', 'is_active', 'default_recurrence_type', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['usage_count', 'last_used_at', 'created_at', 'updated_at']
    inlines = [ProcessTemplateTaskInline]

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'process_type')
        }),
        ('Estado', {
            'fields': ('status', 'is_active')
        }),
        ('Configuración de Recurrencia', {
            'fields': ('default_recurrence_type', 'default_recurrence_config'),
            'description': 'Configuración de recurrencia por defecto para procesos creados con esta plantilla'
        }),
        ('Configuración de la Plantilla', {
            'fields': ('template_config', 'available_variables', 'default_values'),
            'classes': ('collapse',),
            'description': 'Configuración avanzada y variables de la plantilla'
        }),
        ('Estadísticas de Uso', {
            'fields': ('usage_count', 'last_used_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    actions = ['activate_templates', 'deactivate_templates', 'duplicate_template', 'set_testing', 'set_active']

    def status_badge(self, obj):
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'testing': '#ffc107'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'

    def tasks_count(self, obj):
        count = obj.template_tasks.count()
        return format_html('<strong>{}</strong> tareas', count)
    tasks_count.short_description = 'Tareas'

    def activate_templates(self, request, queryset):
        count = queryset.update(is_active=True, status='active')
        self.message_user(request, f"{count} plantilla(s) activada(s).")
    activate_templates.short_description = "Activar plantillas"

    def deactivate_templates(self, request, queryset):
        count = queryset.update(is_active=False, status='inactive')
        self.message_user(request, f"{count} plantilla(s) desactivada(s).")
    deactivate_templates.short_description = "Desactivar plantillas"

    def set_testing(self, request, queryset):
        count = queryset.update(status='testing')
        self.message_user(request, f"{count} plantilla(s) marcada(s) como en pruebas.")
    set_testing.short_description = "Marcar como en pruebas"

    def set_active(self, request, queryset):
        count = queryset.update(status='active')
        self.message_user(request, f"{count} plantilla(s) marcada(s) como activas.")
    set_active.short_description = "Marcar como activas"

    def duplicate_template(self, request, queryset):
        for template in queryset:
            # Duplicar la configuración de plantilla
            new_template = ProcessTemplateConfig.objects.create(
                name=f"{template.name} (Copia)",
                description=template.description,
                process_type=template.process_type,
                status='inactive',
                is_active=False,
                default_recurrence_type=template.default_recurrence_type,
                default_recurrence_config=template.default_recurrence_config,
                template_config=template.template_config,
                available_variables=template.available_variables,
                default_values=template.default_values,
                created_by=request.user.email
            )

            # Duplicar las tareas asociadas
            for task in template.template_tasks.all():
                ProcessTemplateTask.objects.create(
                    template=new_template,
                    task_title=task.task_title,
                    task_description=task.task_description,
                    task_type=task.task_type,
                    priority=task.priority,
                    execution_order=task.execution_order,
                    is_optional=task.is_optional,
                    can_run_parallel=task.can_run_parallel,
                    due_date_offset_days=task.due_date_offset_days,
                    due_date_from_previous=task.due_date_from_previous,
                    estimated_hours=task.estimated_hours,
                    task_config=task.task_config
                )

        self.message_user(request, f"{queryset.count()} plantilla(s) duplicada(s).")
    duplicate_template.short_description = "Duplicar plantillas"


@admin.register(ProcessTemplateTask)
class ProcessTemplateTaskAdmin(admin.ModelAdmin):
    list_display = ['task_title', 'template', 'execution_order', 'priority', 'task_type', 'is_optional', 'estimated_hours']
    list_filter = ['template', 'priority', 'task_type', 'is_optional', 'can_run_parallel']
    search_fields = ['task_title', 'task_description', 'template__name']
    ordering = ['template', 'execution_order']

    fieldsets = (
        ('Información de la Tarea', {
            'fields': ('template', 'task_title', 'task_description', 'task_type', 'priority')
        }),
        ('Orden y Dependencias', {
            'fields': ('execution_order', 'depends_on', 'is_optional', 'can_run_parallel')
        }),
        ('Configuración de Plazos', {
            'fields': ('due_date_offset_days', 'due_date_from_previous', 'estimated_hours'),
            'description': 'Define los plazos y duración estimada de la tarea'
        }),
        ('Configuración Adicional', {
            'fields': ('task_config',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(ProcessAssignmentRule)
class ProcessAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ['rule_display', 'priority', 'is_valid_badge', 'auto_apply', 'created_at']
    list_filter = ['template__process_type', 'segment', 'is_active', 'auto_apply', 'priority', 'created_at']
    search_fields = ['template__name', 'segment__name']
    readonly_fields = ['created_at', 'updated_at', 'is_valid_badge']

    fieldsets = (
        ('Asignación', {
            'fields': ('template', 'segment', 'priority')
        }),
        ('Condiciones Adicionales', {
            'fields': ('conditions',),
            'classes': ('collapse',),
            'description': 'Condiciones específicas adicionales a los criterios del segmento'
        }),
        ('Vigencia', {
            'fields': ('is_active', 'auto_apply', 'start_date', 'end_date')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'is_valid_badge'),
            'classes': ('collapse',)
        })
    )

    actions = ['activate_rules', 'deactivate_rules', 'apply_to_segment']

    def rule_display(self, obj):
        return format_html(
            '<strong>{}</strong> → {}',
            obj.template.name,
            obj.segment.name
        )
    rule_display.short_description = 'Regla'

    def is_valid_badge(self, obj):
        is_valid = obj.is_valid()
        color = '#28a745' if is_valid else '#dc3545'
        text = 'Vigente' if is_valid else 'No Vigente'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            text
        )
    is_valid_badge.short_description = 'Vigencia'

    def activate_rules(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} regla(s) activada(s).")
    activate_rules.short_description = "Activar reglas"

    def deactivate_rules(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} regla(s) desactivada(s).")
    deactivate_rules.short_description = "Desactivar reglas"

    def apply_to_segment(self, request, queryset):
        # TODO: Implementar aplicación de reglas a empresas del segmento
        self.message_user(request, "Funcionalidad en desarrollo")
    apply_to_segment.short_description = "Aplicar reglas a segmento"
