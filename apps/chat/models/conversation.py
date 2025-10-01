"""
Models for managing chat conversations and message history
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):
    """
    Represents a chat conversation with an agent
    """
    CONVERSATION_STATUS = [
        ('active', 'Activa'),
        ('ended', 'Finalizada'),
        ('archived', 'Archivada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_conversations',
        null=True,
        blank=True
    )
    agent_name = models.CharField(max_length=100, help_text="Nombre del agente asignado")
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Título generado automáticamente basado en el primer mensaje"
    )
    status = models.CharField(
        max_length=20,
        choices=CONVERSATION_STATUS,
        default='active'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata adicional como configuración del agente, contexto, etc."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'chat_conversation'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['status', '-updated_at']),
        ]

    def __str__(self):
        title = self.title or f"Conversación con {self.agent_name}"
        return f"{title} ({self.id})"

    def save(self, *args, **kwargs):
        # Auto-generate title if not set and we have messages
        if not self.title and hasattr(self, 'messages') and self.messages.exists():
            first_message = self.messages.filter(role='user').first()
            if first_message:
                # Take first 50 chars as title
                self.title = first_message.content[:50] + ("..." if len(first_message.content) > 50 else "")

        super().save(*args, **kwargs)


class ConversationMessage(models.Model):
    """
    Individual messages within a conversation
    """
    MESSAGE_ROLES = [
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
        ('system', 'Sistema'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=MESSAGE_ROLES)
    content = models.TextField()
    agent_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nombre del agente que generó la respuesta (para mensajes de assistant)"
    )
    token_count = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata adicional como tiempo de respuesta, modelo usado, etc."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_conversation_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role', 'created_at']),
        ]

    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{self.role}: {preview}"