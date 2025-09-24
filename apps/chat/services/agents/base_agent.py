from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Tuple
from django.utils import timezone
from dataclasses import dataclass


@dataclass
class AgentResponse:
    """
    Respuesta generada por un agente
    """
    message: str
    confidence: float  # 0.0 - 1.0
    agent_name: str
    metadata: Dict = None
    should_escalate: bool = False
    next_action: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MessageContext:
    """
    Contexto de un mensaje para los agentes
    """
    message_content: str
    sender_id: str
    conversation_id: str
    company_id: str
    message_history: List[Dict] = None
    sender_info: Dict = None
    conversation_metadata: Dict = None
    company_info: Dict = None
    timestamp: timezone.datetime = None

    def __post_init__(self):
        if self.message_history is None:
            self.message_history = []
        if self.sender_info is None:
            self.sender_info = {}
        if self.conversation_metadata is None:
            self.conversation_metadata = {}
        if self.company_info is None:
            self.company_info = {}
        if self.timestamp is None:
            self.timestamp = timezone.now()


class BaseAgent(ABC):
    """
    Clase base para todos los agentes de chat
    """

    def __init__(self, name: str, priority: int = 5, confidence_threshold: float = 0.5):
        self.name = name
        self.priority = priority
        self.confidence_threshold = confidence_threshold
        self.is_active = True

    @abstractmethod
    def can_handle(self, context: MessageContext) -> bool:
        """
        Determina si este agente puede manejar el mensaje

        Args:
            context: Contexto del mensaje

        Returns:
            True si el agente puede manejar el mensaje
        """
        pass

    @abstractmethod
    def generate_response(self, context: MessageContext) -> Optional[AgentResponse]:
        """
        Genera una respuesta para el mensaje

        Args:
            context: Contexto del mensaje

        Returns:
            AgentResponse o None si no puede generar respuesta
        """
        pass

    def get_confidence_score(self, context: MessageContext) -> float:
        """
        Calcula el score de confianza para manejar este mensaje

        Args:
            context: Contexto del mensaje

        Returns:
            Score de confianza (0.0 - 1.0)
        """
        return 0.5  # Implementación por defecto

    def pre_process_message(self, context: MessageContext) -> MessageContext:
        """
        Pre-procesamiento del mensaje antes de generar respuesta

        Args:
            context: Contexto original

        Returns:
            Contexto modificado
        """
        return context

    def post_process_response(self, response: AgentResponse, context: MessageContext) -> AgentResponse:
        """
        Post-procesamiento de la respuesta antes de enviarla

        Args:
            response: Respuesta original
            context: Contexto del mensaje

        Returns:
            Respuesta modificada
        """
        return response

    def validate_response(self, response: AgentResponse) -> bool:
        """
        Valida que la respuesta sea apropiada

        Args:
            response: Respuesta a validar

        Returns:
            True si la respuesta es válida
        """
        return (
            response is not None and
            response.message and
            len(response.message.strip()) > 0 and
            0.0 <= response.confidence <= 1.0
        )

    def get_agent_info(self) -> Dict:
        """
        Retorna información del agente

        Returns:
            Dict con información del agente
        """
        return {
            'name': self.name,
            'priority': self.priority,
            'confidence_threshold': self.confidence_threshold,
            'is_active': self.is_active,
            'type': self.__class__.__name__
        }

    def enable(self):
        """Activa el agente"""
        self.is_active = True

    def disable(self):
        """Desactiva el agente"""
        self.is_active = False


class RuleBasedAgent(BaseAgent):
    """
    Agente basado en reglas de patrones
    """

    def __init__(self, name: str, patterns: List[str], response_template: str,
                 priority: int = 5, conditions: Dict = None, variables: Dict = None):
        super().__init__(name, priority)
        self.patterns = [pattern.lower() for pattern in patterns]
        self.response_template = response_template
        self.conditions = conditions or {}
        self.variables = variables or {}

    def can_handle(self, context: MessageContext) -> bool:
        """Verifica si los patrones coinciden con el mensaje"""
        if not self.is_active:
            return False

        content = context.message_content.lower().strip()

        # Verificar patrones
        pattern_match = any(
            any(word in content for word in pattern.split())
            for pattern in self.patterns
        )

        if not pattern_match:
            return False

        # Verificar condiciones adicionales
        return self._check_conditions(context)

    def _check_conditions(self, context: MessageContext) -> bool:
        """Verifica condiciones adicionales del agente"""
        # Condición de horario comercial
        if 'business_hours_only' in self.conditions:
            now = timezone.now().time()
            start_time = timezone.now().replace(hour=9, minute=0).time()
            end_time = timezone.now().replace(hour=18, minute=0).time()
            is_business_hours = start_time <= now <= end_time

            if self.conditions['business_hours_only'] and not is_business_hours:
                return False
            elif not self.conditions['business_hours_only'] and is_business_hours:
                return False

        # Condición de longitud mínima del mensaje
        if 'min_message_length' in self.conditions:
            min_length = self.conditions['min_message_length']
            if len(context.message_content.strip()) < min_length:
                return False

        # Condición de palabras prohibidas
        if 'forbidden_words' in self.conditions:
            forbidden = self.conditions['forbidden_words']
            content_lower = context.message_content.lower()
            if any(word.lower() in content_lower for word in forbidden):
                return False

        return True

    def generate_response(self, context: MessageContext) -> Optional[AgentResponse]:
        """Genera respuesta basada en template y variables"""
        if not self.can_handle(context):
            return None

        try:
            # Variables del sistema
            system_vars = {
                'company_name': context.company_info.get('name', 'Nuestra empresa'),
                'sender_name': context.sender_info.get('name', 'Cliente'),
                'current_time': timezone.now().strftime('%H:%M'),
                'current_date': timezone.now().strftime('%d/%m/%Y'),
                'day_of_week': timezone.now().strftime('%A'),
            }

            # Combinar todas las variables
            all_vars = {**system_vars, **self.variables}

            # Reemplazar variables en el template
            message = self.response_template
            for var, value in all_vars.items():
                message = message.replace(f'{{{var}}}', str(value))

            # Calcular confianza basada en coincidencia de patrones
            confidence = self.get_confidence_score(context)

            return AgentResponse(
                message=message,
                confidence=confidence,
                agent_name=self.name,
                metadata={
                    'patterns_matched': self._get_matched_patterns(context),
                    'variables_used': list(all_vars.keys())
                }
            )

        except Exception as e:
            print(f"Error generating response in {self.name}: {e}")
            return None

    def get_confidence_score(self, context: MessageContext) -> float:
        """Calcula confianza basada en número de patrones coincidentes"""
        content = context.message_content.lower().strip()
        matched_patterns = 0

        for pattern in self.patterns:
            if pattern == ".*":  # Patrón comodín
                matched_patterns += 0.5
            elif all(word in content for word in pattern.split()):
                matched_patterns += 1
            elif any(word in content for word in pattern.split()):
                matched_patterns += 0.5

        # Normalizar a 0-1
        max_possible = len(self.patterns)
        if max_possible == 0:
            return 0.5

        confidence = min(matched_patterns / max_possible, 1.0)
        return max(confidence, 0.1)  # Mínimo de confianza

    def _get_matched_patterns(self, context: MessageContext) -> List[str]:
        """Obtiene los patrones que coincidieron"""
        content = context.message_content.lower().strip()
        matched = []

        for pattern in self.patterns:
            if pattern == ".*":
                matched.append(pattern)
            elif any(word in content for word in pattern.split()):
                matched.append(pattern)

        return matched