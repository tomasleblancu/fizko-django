from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router para ViewSets
router = DefaultRouter()
router.register('configs', views.WhatsAppConfigViewSet, basename='whatsapp-config')
router.register('conversations', views.WhatsAppConversationViewSet, basename='whatsapp-conversation')
router.register('messages', views.WhatsAppMessageViewSet, basename='whatsapp-message')
router.register('templates', views.MessageTemplateViewSet, basename='message-template')
router.register('webhook-events', views.WebhookEventViewSet, basename='webhook-event')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Webhook endpoint
    path('webhook/', views.WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    
    # Utility endpoints
    path('send-message/', views.SendMessageView.as_view(), name='send-message'),
    path('send-template/', views.SendTemplateView.as_view(), name='send-template'),
    path('conversation/<uuid:conversation_id>/mark-read/', 
         views.MarkConversationReadView.as_view(), name='mark-conversation-read'),
]