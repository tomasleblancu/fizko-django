# Importar modelos originales de WhatsApp
from .whatsapp_models import (
    WhatsAppConfig,
    WhatsAppConversation,
    WhatsAppMessage,
    WebhookEvent,
    MessageTemplate
)

# Importar nuevos modelos de configuración de agentes
from .agent_config import (
    AgentConfig,
    AgentPrompt,
    AgentTool,
    AgentModelConfig,
    AgentVersion
)

# Importar modelos de herramientas comunes
from .common_tools import (
    ToolCategory,
    CommonTool,
    AgentToolAssignment,
    ToolUsageLog
)

# Importar modelos de archivos de contexto
from .context_files import (
    ContextFile,
    AgentContextAssignment,
    ContextFileProcessingLog
)

# Importar modelos de conversaciones
from .conversation import (
    Conversation,
    ConversationMessage
)

__all__ = [
    # Modelos WhatsApp
    'WhatsAppConfig',
    'WhatsAppConversation',
    'WhatsAppMessage',
    'WebhookEvent',
    'MessageTemplate',

    # Modelos de configuración de agentes
    'AgentConfig',
    'AgentPrompt',
    'AgentTool',
    'AgentModelConfig',
    'AgentVersion',

    # Modelos de herramientas comunes
    'ToolCategory',
    'CommonTool',
    'AgentToolAssignment',
    'ToolUsageLog',

    # Modelos de archivos de contexto
    'ContextFile',
    'AgentContextAssignment',
    'ContextFileProcessingLog',

    # Modelos de conversaciones
    'Conversation',
    'ConversationMessage',
]