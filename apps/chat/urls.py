"""
URLs para la app chat - Solo API endpoints
Las vistas web fueron migradas a apps.internal
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Importar las APIs de WhatsApp desde sii
from apps.sii.api.chat_api import (
    WhatsAppConfigViewSet,
    WhatsAppConversationViewSet,
    WhatsAppMessageViewSet,
    MessageTemplateViewSet,
    WebhookEventViewSet,
    WhatsAppWebhookView,
    SendMessageView,
    SendTemplateView,
    MarkConversationReadView,
    ResponseAnalyticsView,
    TestResponseView,
    TestSupervisorView,
    ConversationHistoryView,
    ConversationDetailView
)

app_name = 'chat'

# Router para ViewSets de API
router = DefaultRouter()
router.register('api/configs', WhatsAppConfigViewSet, basename='whatsapp-config')
router.register('api/conversations', WhatsAppConversationViewSet, basename='whatsapp-conversation')
router.register('api/messages', WhatsAppMessageViewSet, basename='whatsapp-message')
router.register('api/templates', MessageTemplateViewSet, basename='message-template')
router.register('api/webhook-events', WebhookEventViewSet, basename='webhook-event')

urlpatterns = [
    # ============================================================================
    # API ENDPOINTS (WhatsApp)
    # ============================================================================

    # Include router URLs para APIs
    path('', include(router.urls)),

    # Webhook de WhatsApp
    path('webhook/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),

    # Envío de mensajes
    path('send-message/', SendMessageView.as_view(), name='send-message'),
    path('send-template/', SendTemplateView.as_view(), name='send-template'),
    path('conversation/<uuid:conversation_id>/mark-read/', MarkConversationReadView.as_view(), name='mark-conversation-read'),

    # Testing y análisis
    path('test-response/', TestResponseView.as_view(), name='test-response'),
    path('test-supervisor/', TestSupervisorView.as_view(), name='test-supervisor'),
    path('response-analytics/', ResponseAnalyticsView.as_view(), name='response-analytics'),

    # Gestión de conversaciones persistentes
    path('conversations/', ConversationHistoryView.as_view(), name='conversation-history'),
    path('conversations/<uuid:conversation_id>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:conversation_id>/archive/', ConversationHistoryView.as_view(), name='conversation-archive'),
]
