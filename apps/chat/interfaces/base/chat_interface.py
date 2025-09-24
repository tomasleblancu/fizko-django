from abc import ABC, abstractmethod
from typing import Dict, Optional, List


class ChatInterface(ABC):
    """
    Interface base para todos los servicios de chat/comunicación
    """

    @abstractmethod
    def send_message(self, recipient: str, message: str, **kwargs) -> Dict:
        """
        Envía un mensaje a un destinatario

        Args:
            recipient: Identificador del destinatario (número, email, user_id, etc.)
            message: Contenido del mensaje
            **kwargs: Parámetros adicionales específicos del servicio

        Returns:
            Dict con resultado del envío
        """
        pass

    @abstractmethod
    def process_incoming_message(self, payload: Dict, signature: str = None) -> Dict:
        """
        Procesa un mensaje entrante desde webhook o API

        Args:
            payload: Datos del mensaje entrante
            signature: Firma de seguridad (opcional)

        Returns:
            Dict con resultado del procesamiento
        """
        pass

    @abstractmethod
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict]:
        """
        Obtiene historial de conversación

        Args:
            conversation_id: ID de la conversación
            limit: Número máximo de mensajes

        Returns:
            Lista de mensajes ordenados cronológicamente
        """
        pass

    @abstractmethod
    def mark_as_read(self, conversation_id: str, message_id: str = None) -> bool:
        """
        Marca mensaje(s) como leído(s)

        Args:
            conversation_id: ID de la conversación
            message_id: ID del mensaje específico (opcional)

        Returns:
            True si fue exitoso
        """
        pass

    @abstractmethod
    def get_service_info(self) -> Dict:
        """
        Retorna información del servicio

        Returns:
            Dict con información del servicio (nombre, versión, capacidades)
        """
        pass


class ChatMessage(ABC):
    """
    Clase base para mensajes de chat
    """

    def __init__(self, message_id: str, content: str, direction: str,
                 message_type: str = 'text', metadata: Dict = None):
        self.message_id = message_id
        self.content = content
        self.direction = direction  # 'inbound' or 'outbound'
        self.message_type = message_type
        self.metadata = metadata or {}

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convierte el mensaje a diccionario"""
        pass

    @classmethod
    @abstractmethod
    def from_webhook(cls, webhook_data: Dict) -> 'ChatMessage':
        """Crea mensaje desde datos de webhook"""
        pass


class ChatConversation(ABC):
    """
    Clase base para conversaciones de chat
    """

    def __init__(self, conversation_id: str, participant_id: str,
                 status: str = 'active', metadata: Dict = None):
        self.conversation_id = conversation_id
        self.participant_id = participant_id
        self.status = status
        self.metadata = metadata or {}

    @abstractmethod
    def add_message(self, message: ChatMessage) -> bool:
        """Añade un mensaje a la conversación"""
        pass

    @abstractmethod
    def get_last_message(self) -> Optional[ChatMessage]:
        """Obtiene el último mensaje de la conversación"""
        pass

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convierte la conversación a diccionario"""
        pass