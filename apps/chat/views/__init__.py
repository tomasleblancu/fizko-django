# Views modularizadas por dominio de negocio

# WhatsApp ViewSets
from .whatsapp import (
    WhatsAppConfigViewSet,
    WhatsAppConversationViewSet,
    WhatsAppMessageViewSet,
    MessageTemplateViewSet,
)

# Common Views (webhooks, messaging)
from .common import (
    WhatsAppWebhookView,
    WebhookEventViewSet,
    SendMessageView,
    SendTemplateView,
    MarkConversationReadView,
)

# Agent Management Views
from .agents import (
    TestResponseView,
    ResponseRulesView,
    ResponseAnalyticsView,
)

__all__ = [
    # WhatsApp
    'WhatsAppConfigViewSet',
    'WhatsAppConversationViewSet',
    'WhatsAppMessageViewSet',
    'MessageTemplateViewSet',

    # Common
    'WhatsAppWebhookView',
    'WebhookEventViewSet',
    'SendMessageView',
    'SendTemplateView',
    'MarkConversationReadView',

    # Agents
    'TestResponseView',
    'ResponseRulesView',
    'ResponseAnalyticsView',
]