from rest_framework import serializers
from .models import Task, TaskCategory, TaskComment, TaskAttachment, TaskLog, TaskDependency


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