from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router para ViewSets
router = DefaultRouter()
# TEMP: Comentado mientras se arreglan los ViewSets
# router.register('configs', views.WhatsAppConfigViewSet, basename='whatsapp-config')
# router.register('conversations', views.WhatsAppConversationViewSet, basename='whatsapp-conversation')
# router.register('messages', views.WhatsAppMessageViewSet, basename='whatsapp-message')
# router.register('templates', views.MessageTemplateViewSet, basename='message-template')
# router.register('webhook-events', views.WebhookEventViewSet, basename='webhook-event')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),

    # Webhook para recibir mensajes de WhatsApp desde Kapso
    path('webhook/', views.WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    # path('send-message/', views.SendMessageView.as_view(), name='send-message'),
    # path('send-template/', views.SendTemplateView.as_view(), name='send-template'),
    # path('conversation/<uuid:conversation_id>/mark-read/',
    #      views.MarkConversationReadView.as_view(), name='mark-conversation-read'),
    path('test-response/', views.TestResponseView.as_view(), name='test-response'),
    path('test-supervisor/', views.TestSupervisorView.as_view(), name='test-supervisor'),
    # path('response-rules/', views.ResponseRulesView.as_view(), name='response-rules'),
    # path('response-analytics/', views.ResponseAnalyticsView.as_view(), name='response-analytics'),
]