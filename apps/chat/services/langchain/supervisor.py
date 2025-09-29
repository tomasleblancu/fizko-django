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

# Importar sistema de agentes dinámicos
from apps.chat.agents import create_dte_agent, create_sii_agent

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
            model="gpt-4.1-nano",
            temperature=0.1,  # Temperatura baja para decisiones consistentes
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Cargar agentes dinámicamente desde BD (con fallback a legacy)
        self.agents = self._load_agents_from_db()
        self.routing_prompt = self._build_dynamic_routing_prompt()

        logger.info(f"Supervisor inicializado con {len(self.agents)} agentes: {list(self.agents.keys())}")

    def _load_agents_from_db(self) -> Dict[str, Any]:
        """Carga agentes dinámicamente desde la base de datos"""
        agents = {}

        try:
            from apps.chat.models import AgentConfig
            from apps.chat.agents.dynamic_langchain_agent import DynamicLangChainAgent

            # Obtener agentes activos de la BD
            db_agents = AgentConfig.objects.filter(status='active').order_by('created_at')

            logger.info(f"Encontrados {db_agents.count()} agentes activos en BD")

            for agent_config in db_agents:
                try:
                    # Crear agente dinámico desde configuración de BD
                    dynamic_agent = DynamicLangChainAgent(agent_config.id)

                    # Usar nombre del agente como clave (convertir a minúsculas para consistencia)
                    agent_key = agent_config.name.lower().replace(' ', '_')
                    agents[agent_key] = dynamic_agent

                    logger.info(f"✅ Agente dinámico cargado: {agent_key} (tipo: {agent_config.agent_type})")

                except Exception as e:
                    logger.error(f"❌ Error cargando agente {agent_config.name}: {e}")
                    continue

            # Si no hay agentes en BD, usar sistema legacy como fallback
            if not agents:
                logger.warning("No hay agentes activos en BD, usando sistema legacy")
                agents = {
                    "dte": create_dte_agent(),
                    "general": create_sii_agent()
                }
                logger.info("✅ Agentes legacy cargados como fallback")

        except Exception as e:
            logger.error(f"Error cargando agentes desde BD: {e}")
            logger.info("Fallback a sistema legacy")
            agents = {
                "dte": create_dte_agent(),
                "general": create_sii_agent()
            }

        return agents

    def _build_dynamic_routing_prompt(self) -> ChatPromptTemplate:
        """Construye el prompt de routing dinámicamente basado en agentes disponibles"""
        try:
            from apps.chat.models import AgentConfig

            # Obtener información de agentes para prompt dinámico
            agent_descriptions = []
            agent_names = []

            # Si tenemos agentes de BD, usar su configuración
            db_agents = AgentConfig.objects.filter(status='active').order_by('created_at')

            if db_agents.exists():
                logger.info("Construyendo prompt dinámico desde agentes de BD")

                for agent_config in db_agents:
                    agent_key = agent_config.name.lower().replace(' ', '_')
                    agent_names.append(agent_key)

                    # Mapeo de tipos a descripciones específicas
                    type_descriptions = {
                        'dte': 'EXCLUSIVAMENTE para documentos tributarios electrónicos (facturas, boletas, notas de crédito/débito, DTEs, timbrajes)',
                        'sii': 'Para información de empresa, servicios SII, impuestos, F29, contabilidad, consultas tributarias generales',
                        'general': 'Para consultas generales, saludos, información básica y temas no especializados',
                        'support': 'Para soporte técnico, problemas del sistema y ayuda con la plataforma',
                        'sales': 'Para consultas comerciales, información de productos y ventas'
                    }

                    description = type_descriptions.get(
                        agent_config.agent_type,
                        f"Agente especializado en {agent_config.agent_type}"
                    )

                    if agent_config.description:
                        description += f" - {agent_config.description}"

                    agent_descriptions.append(f"- {agent_key}: {description}")

            else:
                # Fallback a descripciones legacy
                logger.info("Construyendo prompt legacy (no hay agentes en BD)")
                agent_names = ["dte", "general"]
                agent_descriptions = [
                    "- dte: EXCLUSIVAMENTE para documentos electrónicos (facturas, boletas, notas de crédito/débito, DTEs, timbrajes)",
                    "- general: Para información de empresa, socios, actividades, impuestos, F29, SII, contabilidad general, saludos, usuarios nuevos y consultas generales"
                ]

            # Construir prompt dinámico
            agents_list = "\\n            ".join(agent_descriptions)
            agents_options = ", ".join(agent_names) + ", o END"

            routing_system_message = f"""Eres un supervisor que decide qué agente especializado debe responder.

            Agentes disponibles:
            {agents_list}
            - END: Si la conversación está completa

            REGLAS DE ROUTING:
            - Analiza cuidadosamente el tipo de consulta
            - Selecciona el agente más apropiado según su especialización
            - Usa END solo si la conversación está verdaderamente completa

            Responde SOLO con: {agents_options}"""

            return ChatPromptTemplate.from_messages([
                ("system", routing_system_message),
                MessagesPlaceholder(variable_name="messages")
            ])

        except Exception as e:
            logger.error(f"Error construyendo prompt dinámico: {e}")
            # Fallback a prompt estático
            return ChatPromptTemplate.from_messages([
                ("system", """Eres un supervisor que decide qué agente especializado debe responder.

                Agentes disponibles:
                - dte: EXCLUSIVAMENTE para documentos electrónicos (facturas, boletas, notas de crédito/débito, DTEs, timbrajes)
                - general: Para información de empresa, socios, actividades, impuestos, F29, SII, contabilidad general, saludos, usuarios nuevos y consultas generales
                - END: Si la conversación está completa

                Responde SOLO con: dte, general, o END"""),
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

    def get_agents_info(self) -> Dict[str, Any]:
        """Retorna información de los agentes disponibles para metadata"""
        agents_info = {
            'agents_available': list(self.agents.keys()),
            'agents_count': len(self.agents),
            'agents_source': 'database' if self._has_db_agents() else 'legacy',
            'agents_details': []
        }

        try:
            from apps.chat.models import AgentConfig

            # Si tenemos agentes de BD, incluir detalles
            if self._has_db_agents():
                db_agents = AgentConfig.objects.filter(status='active').order_by('created_at')
                for agent_config in db_agents:
                    agent_key = agent_config.name.lower().replace(' ', '_')
                    agents_info['agents_details'].append({
                        'key': agent_key,
                        'name': agent_config.name,
                        'type': agent_config.agent_type,
                        'description': agent_config.description or '',
                        'model': agent_config.model_name,
                        'temperature': agent_config.temperature
                    })
            else:
                # Información legacy
                agents_info['agents_details'] = [
                    {'key': 'dte', 'name': 'DTE Agent', 'type': 'dte', 'description': 'Documentos tributarios electrónicos'},
                    {'key': 'general', 'name': 'SII Agent', 'type': 'sii', 'description': 'Consultas generales SII'}
                ]

        except Exception as e:
            logger.error(f"Error obteniendo información de agentes: {e}")

        return agents_info

    def _has_db_agents(self) -> bool:
        """Verifica si los agentes actuales provienen de la BD"""
        try:
            from apps.chat.models import AgentConfig
            return AgentConfig.objects.filter(status='active').exists()
        except:
            return False

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

        # Agregar edges condicionales desde el supervisor (dinámico)
        def route_condition(state: AgentState) -> str:
            return state.get("next_agent", "END")

        # Construir mapping dinámico de agentes
        agent_mapping = {agent_name: agent_name for agent_name in self.supervisor.agents.keys()}
        agent_mapping["END"] = END

        workflow.add_conditional_edges(
            "supervisor",
            route_condition,
            agent_mapping
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

    def get_agents_info(self) -> Dict[str, Any]:
        """Retorna información detallada de los agentes para APIs"""
        return self.supervisor.get_agents_info()

# Instancia global del sistema
multi_agent_system = MultiAgentSystem()

# SISTEMA DINÁMICO SIMPLE
def process_with_advanced_system(message: str, user_id: str = None,
                               ip_address: str = None, metadata: dict = None) -> str:
    """
    Procesa mensaje con el sistema multi-agente dinámico
    """
    return multi_agent_system.process(message, metadata)

# Alias para compatibilidad
process_secure = process_with_advanced_system