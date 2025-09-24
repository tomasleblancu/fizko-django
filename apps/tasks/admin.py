from django.contrib import admin
from .models import (
    TaskCategory, Task, TaskDependency, TaskComment, TaskAttachment, TaskLog, TaskSchedule,
    Process, ProcessTemplate, ProcessTask, ProcessExecution
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
