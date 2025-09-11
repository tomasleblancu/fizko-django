from django.contrib import admin
from .models import TaskCategory, Task, TaskDependency, TaskComment, TaskAttachment, TaskLog, TaskSchedule

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
