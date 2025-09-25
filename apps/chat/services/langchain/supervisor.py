"""
Sistema Supervisor con LangGraph para gestión multi-agente
"""
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from django.conf import settings
import logging

# Importar agentes desde archivos separados
from .agents.dte.agent import DTEAgent
from .agents.sii.agent import SIIAgent as GeneralAgent
from .agents.onboarding.agent import OnboardingAgent

logger = logging.getLogger(__name__)

# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class Supervisor:
    """Supervisor que coordina los agentes especializados"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            temperature=0.1,  # Temperatura baja para decisiones consistentes
            openai_api_key=settings.OPENAI_API_KEY
        )

        self.agents = {
            "dte": DTEAgent(),
            "general": GeneralAgent(),
            "onboarding": OnboardingAgent()
        }

        self.routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un supervisor que decide qué agente especializado debe responder.

            Agentes disponibles:
            - onboarding: Para usuarios NO AUTENTICADOS que necesitan registrarse
            - dte: EXCLUSIVAMENTE para documentos electrónicos (facturas, boletas, notas de crédito/débito, DTEs, timbrajes)
            - general: Para usuarios AUTENTICADOS - información de empresa, socios, actividades, impuestos, F29, SII, contabilidad general, saludos
            - END: Si la conversación está completa

            REGLAS DE ROUTING CRÍTICAS:

            USA "onboarding" SOLO cuando:
            - Usuario NO está autenticado/identificado
            - Solicita crear cuenta, registrarse, o hacer onboarding
            - Pregunta sobre cómo empezar a usar Fizko
            - Es un usuario completamente nuevo

            USA "dte" SOLO para usuarios AUTENTICADOS que preguntan sobre:
            - Facturas electrónicas, boletas, notas de crédito/débito
            - Documentos tributarios específicos (DTEs)
            - Timbrajes y autorizaciones de documentos

            USA "general" para usuarios AUTENTICADOS que preguntan sobre:
            - "¿Qué sabes de mi empresa?" → general
            - "Información de mi empresa" → general
            - "Mis socios", "actividades económicas" → general
            - Preguntas sobre impuestos, F29, SII → general
            - Saludos, consultas generales → general

            IMPORTANTE: Verifica SIEMPRE si el usuario está autenticado antes de decidir.

            Responde SOLO con: onboarding, dte, general, o END"""),
            MessagesPlaceholder(variable_name="messages")
        ])

    def route(self, state: AgentState) -> str:
        """Decide qué agente debe manejar la consulta"""
        # Si ya hay una respuesta del agente, terminar
        if state.get("next_agent") == "supervisor":
            # Verificar si la última respuesta es de un agente
            if len(state["messages"]) >= 2:
                logger.info("Terminando conversación - respuesta del agente recibida")
                return "END"

        # Obtener último mensaje para logging
        last_message = state["messages"][-1].content if state["messages"] else "No message"
        logger.info(f"Routing mensaje: '{last_message}'")

        # Decidir el próximo agente
        chain = self.routing_prompt | self.llm
        result = chain.invoke({"messages": state["messages"]})

        agent_name = result.content.strip().lower()
        logger.info(f"Supervisor decidió: '{agent_name}'")

        if agent_name in self.agents:
            logger.info(f"Redirigiendo a agente: {agent_name}")
            return agent_name
        elif agent_name == "end":
            logger.info("Terminando conversación")
            return "END"
        else:
            logger.info(f"Agente no reconocido '{agent_name}', usando general por defecto")
            return "general"  # Por defecto usar el agente general

    def run(self, state: AgentState) -> Dict:
        """Ejecuta la lógica del supervisor"""
        next_agent = self.route(state)
        return {"next_agent": next_agent}

class MultiAgentSystem:
    """Sistema multi-agente con supervisor"""

    def __init__(self):
        self.supervisor = Supervisor()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construye el grafo de flujo de trabajo"""
        workflow = StateGraph(AgentState)

        # Agregar nodos
        workflow.add_node("supervisor", self.supervisor.run)

        for agent_name, agent in self.supervisor.agents.items():
            workflow.add_node(agent_name, agent.run)

        # Definir el flujo - agregar edge desde START al supervisor
        workflow.add_edge(START, "supervisor")

        # Agregar edges condicionales desde el supervisor
        def route_condition(state: AgentState) -> str:
            return state.get("next_agent", "END")

        workflow.add_conditional_edges(
            "supervisor",
            route_condition,
            {
                "onboarding": "onboarding",
                "dte": "dte",
                "general": "general",
                "END": END
            }
        )

        # Los agentes vuelven al supervisor
        for agent_name in self.supervisor.agents.keys():
            workflow.add_edge(agent_name, "supervisor")

        return workflow.compile()

    def process(self, message: str, metadata: Optional[Dict] = None) -> str:
        """Procesa un mensaje a través del sistema multi-agente"""
        try:
            logger.info(f"Procesando mensaje: {message}")

            initial_state = {
                "messages": [HumanMessage(content=message)],
                "next_agent": "",
                "metadata": metadata or {}
            }

            logger.info(f"Estado inicial: {initial_state}")

            # Ejecutar el workflow
            result = self.graph.invoke(initial_state)
            logger.info(f"Resultado del grafo: {result}")

            # Extraer la respuesta final
            if result and result.get("messages"):
                # La última mensaje debe ser la respuesta del agente
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        logger.info(f"Respuesta encontrada: {msg.content}")
                        return msg.content

            logger.warning("No se encontró respuesta AI en los mensajes")
            return "No pude procesar tu consulta. Por favor, intenta reformularla."

        except Exception as e:
            logger.error(f"Error en MultiAgentSystem: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return "Ocurrió un error al procesar tu consulta. Por favor, intenta nuevamente."

# Instancia global del sistema
multi_agent_system = MultiAgentSystem()

# SISTEMA AVANZADO (RECOMENDADO)
# Importar y usar el sistema avanzado con todos los componentes integrados
try:
    from .advanced_supervisor import advanced_multi_agent_system

    # Función de conveniencia para usar el sistema avanzado
    def process_with_advanced_system(message: str, user_id: str = None,
                                   ip_address: str = None, metadata: dict = None) -> str:
        """
        Procesa mensaje con el sistema avanzado que incluye:
        - Seguridad y validación de entradas
        - Gestión de privilegios y sesiones
        - Memoria de conversación avanzada
        - Monitoreo y trazabilidad completa
        - Cumplimiento normativo chileno
        - Router híbrido optimizado
        """
        return advanced_multi_agent_system.process(message, user_id, ip_address, metadata)

    # Alias para compatibilidad y facilidad de uso
    process_secure = process_with_advanced_system

    logger.info("Sistema multi-agente avanzado cargado correctamente")

except ImportError as e:
    logger.warning(f"Sistema avanzado no disponible: {e}")

    # Fallback al sistema básico
    def process_with_advanced_system(message: str, user_id: str = None,
                                   ip_address: str = None, metadata: dict = None) -> str:
        """Fallback al sistema básico si el avanzado no está disponible"""
        return multi_agent_system.process(message, metadata)

    process_secure = process_with_advanced_system