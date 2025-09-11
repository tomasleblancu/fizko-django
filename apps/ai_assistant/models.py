from django.db import models
from apps.core.models import TimeStampedModel

class ChatSession(TimeStampedModel):
    """
    Sesiones de chat con el asistente AI
    """
    user_email = models.EmailField()
    company_rut = models.CharField(max_length=12, blank=True)
    company_dv = models.CharField(max_length=1, blank=True)
    session_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'ai_chat_sessions'
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Chat {self.session_id} - {self.user_email}"


class ChatMessage(TimeStampedModel):
    """
    Mensajes del chat con AI
    """
    MESSAGE_TYPES = [
        ('user', 'Usuario'),
        ('assistant', 'Asistente'),
        ('system', 'Sistema'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, help_text="Metadatos adicionales del mensaje")
    tokens_used = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'ai_chat_messages'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}..."


class AIUsageLog(TimeStampedModel):
    """
    Log de uso de IA
    """
    user_email = models.EmailField()
    company_rut = models.CharField(max_length=12, blank=True)
    company_dv = models.CharField(max_length=1, blank=True)
    feature = models.CharField(max_length=50, help_text="Función de IA utilizada")
    tokens_used = models.IntegerField()
    cost = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    
    class Meta:
        db_table = 'ai_usage_logs'
        verbose_name = 'AI Usage Log'
        verbose_name_plural = 'AI Usage Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.feature} - {self.tokens_used} tokens"
