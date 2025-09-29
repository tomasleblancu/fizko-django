"""
Modelos para gestión de archivos de contexto para agentes
"""
import os
import uuid
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from apps.core.models import TimeStampedModel


def context_file_upload_path(instance, filename):
    """
    Genera ruta de almacenamiento para archivos de contexto
    Estructura: media/context_files/{agent_type}/{agent_id}/{uuid}_{filename}
    """
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4()}_{filename}"
    return f"context_files/{instance.agent_config.agent_type}/{instance.agent_config.id}/{new_filename}"


class ContextFile(TimeStampedModel):
    """
    Modelo para archivos de contexto que pueden ser asignados a agentes
    """
    FILE_TYPES = [
        ('json', 'JSON'),
        ('txt', 'Text'),
        ('docx', 'Word Document'),
        ('pdf', 'PDF'),
    ]

    STATUS_CHOICES = [
        ('uploaded', 'Subido'),
        ('processing', 'Procesando'),
        ('processed', 'Procesado'),
        ('error', 'Error'),
    ]

    # Información básica del archivo
    name = models.CharField(max_length=255, help_text="Nombre descriptivo del archivo")
    description = models.TextField(blank=True, help_text="Descripción del contenido del archivo")
    file = models.FileField(
        upload_to=context_file_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['json', 'txt', 'docx', 'pdf'])],
        help_text="Archivo de contexto (JSON, TXT, DOCX, PDF)"
    )
    file_type = models.CharField(max_length=10, choices=FILE_TYPES)
    file_size = models.PositiveIntegerField(help_text="Tamaño del archivo en bytes")

    # Contenido procesado
    extracted_content = models.TextField(
        blank=True,
        help_text="Contenido extraído del archivo para usar como contexto"
    )
    content_summary = models.TextField(
        blank=True,
        help_text="Resumen automático del contenido"
    )

    # Estado del procesamiento
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    processing_error = models.TextField(blank=True, help_text="Error durante el procesamiento")

    # Asociación con agente
    agent_config = models.ForeignKey(
        'chat.AgentConfig',
        on_delete=models.CASCADE,
        related_name='context_files',
        help_text="Agente al que pertenece este archivo"
    )

    # Metadatos adicionales
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadatos adicionales (páginas, palabras, etc.)"
    )

    # Control de usuario
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_context_files'
    )

    class Meta:
        db_table = 'chat_context_files'
        verbose_name = 'Archivo de Contexto'
        verbose_name_plural = 'Archivos de Contexto'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['agent_config', 'status']),
            models.Index(fields=['file_type']),
            models.Index(fields=['uploaded_by']),
        ]

    def __str__(self):
        return f"{self.name} ({self.file_type}) - {self.agent_config.name}"

    def save(self, *args, **kwargs):
        # Auto-detectar tipo de archivo si no está definido
        if not self.file_type and self.file:
            ext = self.file.name.split('.')[-1].lower()
            if ext in ['json', 'txt', 'docx', 'pdf']:
                self.file_type = ext

        # Obtener tamaño del archivo
        if self.file and not self.file_size:
            self.file_size = self.file.size

        super().save(*args, **kwargs)

    @property
    def file_size_human(self):
        """Retorna el tamaño del archivo en formato legible"""
        bytes_size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    @property
    def is_processed(self):
        """Indica si el archivo ha sido procesado exitosamente"""
        return self.status == 'processed' and bool(self.extracted_content)

    @property
    def content_preview(self):
        """Retorna una vista previa del contenido extraído"""
        if self.extracted_content:
            return self.extracted_content[:200] + "..." if len(self.extracted_content) > 200 else self.extracted_content
        return "No hay contenido extraído"


class AgentContextAssignment(TimeStampedModel):
    """
    Modelo para gestionar qué archivos de contexto están activos para un agente
    """
    agent_config = models.ForeignKey(
        'chat.AgentConfig',
        on_delete=models.CASCADE,
        related_name='active_context_assignments'
    )
    context_file = models.ForeignKey(
        'ContextFile',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Si este archivo está actualmente activo para el agente"
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text="Prioridad del archivo (mayor número = mayor prioridad)"
    )
    context_instructions = models.TextField(
        blank=True,
        help_text="Instrucciones específicas sobre cómo usar este archivo como contexto"
    )

    class Meta:
        db_table = 'chat_agent_context_assignments'
        verbose_name = 'Asignación de Contexto'
        verbose_name_plural = 'Asignaciones de Contexto'
        ordering = ['-priority', '-created_at']
        unique_together = [['agent_config', 'context_file']]
        indexes = [
            models.Index(fields=['agent_config', 'is_active']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        status = "Activo" if self.is_active else "Inactivo"
        return f"{self.agent_config.name} - {self.context_file.name} ({status})"


class ContextFileProcessingLog(TimeStampedModel):
    """
    Log de procesamiento de archivos de contexto
    """
    context_file = models.ForeignKey(
        'ContextFile',
        on_delete=models.CASCADE,
        related_name='processing_logs'
    )
    action = models.CharField(max_length=50, help_text="Acción realizada (upload, extract, summarize, etc.)")
    status = models.CharField(
        max_length=20,
        choices=[
            ('started', 'Iniciado'),
            ('completed', 'Completado'),
            ('failed', 'Fallido'),
        ]
    )
    details = models.TextField(blank=True, help_text="Detalles del procesamiento")
    execution_time = models.DurationField(null=True, blank=True, help_text="Tiempo de ejecución")

    class Meta:
        db_table = 'chat_context_file_processing_logs'
        verbose_name = 'Log de Procesamiento'
        verbose_name_plural = 'Logs de Procesamiento'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.context_file.name} - {self.action} ({self.status})"