from rest_framework import serializers
from .models import (
    Task, TaskCategory, TaskComment, TaskAttachment, TaskLog, TaskDependency,
    Process, ProcessTemplate, ProcessTask, ProcessExecution
)


class TaskCategorySerializer(serializers.ModelSerializer):
    """Serializer para categorías de tareas"""
    
    class Meta:
        model = TaskCategory
        fields = [
            'id', 'name', 'description', 'color', 'icon', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaskDependencySerializer(serializers.ModelSerializer):
    """Serializer para dependencias de tareas"""
    
    predecessor_title = serializers.CharField(source='predecessor.title', read_only=True)
    successor_title = serializers.CharField(source='successor.title', read_only=True)
    
    class Meta:
        model = TaskDependency
        fields = [
            'id', 'predecessor', 'successor', 'dependency_type', 'lag_days',
            'predecessor_title', 'successor_title', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaskCommentSerializer(serializers.ModelSerializer):
    """Serializer para comentarios de tareas"""
    
    class Meta:
        model = TaskComment
        fields = [
            'id', 'task', 'user_email', 'comment', 'is_internal',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'user_email']


class TaskAttachmentSerializer(serializers.ModelSerializer):
    """Serializer para archivos adjuntos de tareas"""
    
    file_size_human = serializers.ReadOnlyField()
    
    class Meta:
        model = TaskAttachment
        fields = [
            'id', 'task', 'file', 'filename', 'file_size', 'file_size_human',
            'content_type', 'uploaded_by', 'description',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'uploaded_by', 'file_size', 'content_type']


class TaskLogSerializer(serializers.ModelSerializer):
    """Serializer para logs de tareas"""
    
    class Meta:
        model = TaskLog
        fields = [
            'id', 'task', 'level', 'message', 'details', 'created_at'
        ]
        read_only_fields = ['created_at']


class TaskSerializer(serializers.ModelSerializer):
    """Serializer principal para tareas"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    company_full_rut = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    # Relaciones incluidas
    comments = TaskCommentSerializer(many=True, read_only=True)
    attachments = TaskAttachmentSerializer(many=True, read_only=True)
    logs = TaskLogSerializer(many=True, read_only=True)
    
    # Dependencias
    predecessor_dependencies = TaskDependencySerializer(many=True, read_only=True)
    successor_dependencies = TaskDependencySerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'task_type', 'category', 'category_name',
            'company_rut', 'company_dv', 'company_full_rut',
            'assigned_to', 'created_by', 'status', 'priority',
            'due_date', 'started_at', 'completed_at',
            'progress_percentage', 'estimated_duration', 'actual_duration',
            'task_data', 'result_data', 'error_message',
            'is_recurring', 'recurrence_pattern', 'next_run',
            'is_overdue', 'created_at', 'updated_at',
            'comments', 'attachments', 'logs',
            'predecessor_dependencies', 'successor_dependencies'
        ]
        read_only_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'actual_duration']


class CreateTaskSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear tareas"""
    
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'task_type', 'category',
            'company_rut', 'company_dv', 'assigned_to',
            'priority', 'due_date', 'estimated_duration',
            'task_data', 'is_recurring', 'recurrence_pattern'
        ]
    
    def validate_assigned_to(self, value):
        """Validar que el usuario asignado existe"""
        if value:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(email=value).exists():
                raise serializers.ValidationError("El usuario asignado no existe")
        return value
    
    def validate(self, data):
        """Validaciones adicionales"""
        # Si es recurrente, debe tener patrón
        if data.get('is_recurring') and not data.get('recurrence_pattern'):
            raise serializers.ValidationError(
                "Las tareas recurrentes deben tener un patrón de recurrencia"
            )
        
        return data


class TaskSummarySerializer(serializers.ModelSerializer):
    """Serializer resumido para listados y referencias"""
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'task_type', 'category_name', 'status', 'priority',
            'progress_percentage', 'due_date', 'is_overdue', 'created_at'
        ]


# Serializers para Procesos

class ProcessTemplateSerializer(serializers.ModelSerializer):
    """Serializer para plantillas de procesos"""

    class Meta:
        model = ProcessTemplate
        fields = [
            'id', 'name', 'description', 'process_type', 'template_data',
            'is_active', 'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class ProcessTaskSerializer(serializers.ModelSerializer):
    """Serializer para tareas de procesos"""

    task_title = serializers.CharField(source='task.title', read_only=True)
    task_status = serializers.CharField(source='task.status', read_only=True)
    task_type = serializers.CharField(source='task.task_type', read_only=True)

    class Meta:
        model = ProcessTask
        fields = [
            'id', 'process', 'task', 'task_title', 'task_status', 'task_type',
            'execution_order', 'execution_conditions', 'is_optional',
            'can_run_parallel', 'context_data', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class ProcessExecutionSerializer(serializers.ModelSerializer):
    """Serializer para ejecuciones de procesos"""

    process_name = serializers.CharField(source='process.name', read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    duration = serializers.ReadOnlyField()

    class Meta:
        model = ProcessExecution
        fields = [
            'id', 'process', 'process_name', 'status', 'started_at', 'completed_at',
            'execution_context', 'current_step', 'total_steps', 'completed_steps',
            'failed_steps', 'last_error', 'error_count', 'progress_percentage', 'duration'
        ]
        read_only_fields = ['started_at', 'progress_percentage', 'duration']


class ProcessSerializer(serializers.ModelSerializer):
    """Serializer principal para procesos"""

    company_full_rut = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    current_step = serializers.SerializerMethodField()

    # Tareas del proceso
    process_tasks = ProcessTaskSerializer(many=True, read_only=True)

    # Ejecuciones del proceso
    executions = ProcessExecutionSerializer(many=True, read_only=True)

    class Meta:
        model = Process
        fields = [
            'id', 'name', 'description', 'process_type', 'status',
            'company_rut', 'company_dv', 'company_full_rut',
            'created_by', 'assigned_to', 'is_template', 'parent_process',
            'start_date', 'due_date', 'completed_at', 'config_data',
            'progress_percentage', 'is_overdue', 'current_step',
            'created_at', 'updated_at',
            'process_tasks', 'executions'
        ]
        read_only_fields = ['created_at', 'updated_at', 'start_date', 'completed_at']

    def get_current_step(self, obj):
        """Obtiene información del paso actual"""
        current = obj.current_step
        if current:
            return {
                'task_title': current.task.title,
                'task_status': current.task.status,
                'execution_order': current.execution_order,
                'is_optional': current.is_optional
            }
        return None


class CreateProcessSerializer(serializers.ModelSerializer):
    """Serializer simplificado para crear procesos"""

    class Meta:
        model = Process
        fields = [
            'name', 'description', 'process_type', 'company_rut', 'company_dv',
            'assigned_to', 'due_date', 'config_data', 'is_template', 'parent_process'
        ]

    def validate(self, data):
        """Validaciones adicionales"""
        # Validar formato RUT básico
        company_rut = data.get('company_rut')
        company_dv = data.get('company_dv')

        if company_rut and not company_rut.isdigit():
            raise serializers.ValidationError("El RUT debe contener solo números")

        if company_dv and len(company_dv) != 1:
            raise serializers.ValidationError("El DV debe ser un solo carácter")

        return data


class ProcessSummarySerializer(serializers.ModelSerializer):
    """Serializer resumido para listados de procesos"""

    company_full_rut = serializers.ReadOnlyField()
    progress_percentage = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Process
        fields = [
            'id', 'name', 'process_type', 'status', 'company_full_rut',
            'progress_percentage', 'due_date', 'is_overdue', 'task_count', 'created_at'
        ]

    def get_task_count(self, obj):
        """Cuenta de tareas en el proceso"""
        return obj.process_tasks.count()