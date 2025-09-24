from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from .models import WhatsAppMessage, WhatsAppConversation, WebhookEvent


@receiver(post_save, sender=WhatsAppMessage)
def update_conversation_on_message(sender, instance, created, **kwargs):
    """
    Actualiza la conversación cuando se crea o actualiza un mensaje
    """
    if created:
        conversation = instance.conversation
        
        # Actualizar contadores
        conversation.message_count += 1
        
        # Si es un mensaje entrante, incrementar contador de no leídos
        if instance.direction == 'inbound' and instance.status == 'received':
            conversation.unread_count += 1
        
        # Actualizar última actividad
        conversation.last_active_at = timezone.now()
        conversation.status = 'active'
        
        conversation.save(update_fields=['message_count', 'unread_count', 'last_active_at', 'status'])


@receiver(post_save, sender=WebhookEvent)
def log_webhook_processing(sender, instance, created, **kwargs):
    """
    Log del procesamiento de webhooks para monitoreo
    """
    if not created:
        # Solo logear cambios de estado
        if instance.processing_status == 'processed':
            print(f"✅ Webhook procesado: {instance.event_type} - {instance.idempotency_key}")
        elif instance.processing_status == 'failed':
            print(f"❌ Error procesando webhook: {instance.event_type} - {instance.error_message}")


@receiver(post_delete, sender=WhatsAppMessage)
def update_conversation_on_message_delete(sender, instance, **kwargs):
    """
    Actualiza contadores de conversación cuando se elimina un mensaje
    """
    conversation = instance.conversation
    if conversation.message_count > 0:
        conversation.message_count -= 1
        conversation.save(update_fields=['message_count'])