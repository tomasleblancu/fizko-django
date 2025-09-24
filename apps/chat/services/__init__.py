# Servicios de chat modularizados

from .chat_service import chat_service, ChatService
from .agents.agent_manager import agent_manager
from .whatsapp.whatsapp_processor import WhatsAppProcessor
from .whatsapp.kapso_service import KapsoAPIService

__all__ = [
    "chat_service",
    "ChatService", 
    "agent_manager",
    "WhatsAppProcessor",
    "KapsoAPIService"
]
