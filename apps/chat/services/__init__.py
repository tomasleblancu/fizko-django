# Servicios de chat modularizados
# Imports comentados para evitar circular imports durante startup de Celery
# Los imports se hacen de forma lazy en views.py

# from .chat_service import chat_service, ChatService
# from .langchain.supervisor import multi_agent_system
# from .whatsapp.whatsapp_processor import WhatsAppProcessor
# from .whatsapp.kapso_service import KapsoAPIService

__all__ = [
    # "chat_service",
    # "ChatService",
    # "multi_agent_system",
    # "WhatsAppProcessor",
    # "KapsoAPIService"
]
