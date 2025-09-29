from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Importar las APIs movidas desde sii
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
    TestSupervisorView
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
    # PANEL DE ADMINISTRACIÓN DE AGENTES
    # ============================================================================

    # Dashboard principal
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # ============================================================================
    # GESTIÓN DE AGENTES
    # ============================================================================

    # CRUD de agentes
    path('agents/', views.agent_list, name='agent_list'),
    path('agents/create/', views.agent_create, name='agent_create'),
    path('agents/<int:agent_id>/', views.agent_detail, name='agent_detail'),
    path('agents/<int:agent_id>/edit/', views.agent_edit, name='agent_edit'),

    # Herramientas de agentes
    path('agents/<int:agent_id>/tools/', views.agent_tools, name='agent_tools'),
    path('agents/<int:agent_id>/tools/assign/', views.assign_tool_to_agent, name='assign_tool_to_agent'),
    path('agents/<int:agent_id>/tools/<int:assignment_id>/remove/', views.remove_tool_from_agent, name='remove_tool_from_agent'),

    # Prompts de agentes
    path('agents/<int:agent_id>/prompts/create/', views.create_prompt, name='create_prompt'),

    # Testing de agentes
    path('agents/<int:agent_id>/test/', views.test_agent, name='test_agent'),

    # API para perfeccionamiento de prompts
    path('agents/<int:agent_id>/enhance-prompt/', views.enhance_prompt_api, name='enhance_prompt_api'),

    # API para gestión de prompts
    path('agents/<int:agent_id>/prompts/<int:prompt_id>/delete/', views.delete_prompt_api, name='delete_prompt_api'),
    path('agents/<int:agent_id>/prompts/<int:prompt_id>/toggle/', views.toggle_prompt_api, name='toggle_prompt_api'),

    # ============================================================================
    # ARCHIVOS DE CONTEXTO
    # ============================================================================

    # Gestión de archivos de contexto por agente
    path('agents/<int:agent_id>/context/', views.agent_context_files, name='agent_context_files'),
    path('agents/<int:agent_id>/context/upload/', views.upload_context_file, name='upload_context_file'),
    path('agents/<int:agent_id>/context/<int:file_id>/assign/', views.assign_context_file, name='assign_context_file'),
    path('agents/<int:agent_id>/context/<int:file_id>/remove/', views.remove_context_file, name='remove_context_file'),
    path('agents/<int:agent_id>/context/<int:file_id>/toggle/', views.toggle_context_file, name='toggle_context_file'),

    # Gestión general de archivos
    path('context-files/', views.context_files_list, name='context_files_list'),
    path('context-files/<int:file_id>/', views.context_file_detail, name='context_file_detail'),
    path('context-files/<int:file_id>/reprocess/', views.reprocess_context_file, name='reprocess_context_file'),

    # ============================================================================
    # BIBLIOTECA DE HERRAMIENTAS
    # ============================================================================

    path('tools/', views.tools_library, name='tools_library'),
    path('tools/<str:tool_name>/', views.tool_detail, name='tool_detail'),

    # ============================================================================
    # API ENDPOINTS (desde sii/api)
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
]