"""
Supervisor optimizado con routing híbrido, fallback y monitorización avanzada
"""
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from django.conf import settings
import logging
import time
from datetime import datetime

# Importar sistema híbrido
from .hybrid_router import get_hybrid_router
from .agent_executor import AgentExecutor

# Importar agentes
from .agents import TaxAgent, DTEAgent, SIIAgent, GeneralAgent

logger = logging.getLogger(__name__)


# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class OptimizedSupervisor:
    """Supervisor optimizado con routing híbrido y sistema de fallback"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Inicializar agentes
        self.agents = {
            "tax": TaxAgent(),
            "dte": DTEAgent(),
            "sii": SIIAgent(),
            "general": GeneralAgent()
        }

        # Inicializar sistemas de optimización
        self.hybrid_router = get_hybrid_router()
        self.agent_executor = AgentExecutor(self.agents)

        # Configuraciones de timeout por agente
        self.agent_executor.set_agent_timeout("sii", 45.0)  # SII puede tomar más tiempo por FAISS
        self.agent_executor.set_agent_timeout("dte", 35.0)  # DTE puede requerir consultas BD
        self.agent_executor.set_agent_timeout("tax", 25.0)
        self.agent_executor.set_agent_timeout("general", 20.0)

        # Estadísticas del supervisor
        self.supervisor_stats = {
            'total_conversations': 0,
            'routing_decisions': {},
            'avg_conversation_time': 0.0,
            'user_satisfaction_feedback': [],
            'start_time': datetime.now()
        }

    def route(self, state: AgentState) -> str:
        """Routing híbrido optimizado"""
        try:
            # Extraer última consulta del usuario
            user_message = None
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                logger.warning("No se encontró mensaje del usuario")
                return "general"

            # Usar router híbrido
            routing_decision = self.hybrid_router.route(
                user_message,
                metadata=state.get("metadata", {})
            )

            # Registrar decisión para estadísticas
            selected_agent = routing_decision['selected_agent']
            if selected_agent not in self.supervisor_stats['routing_decisions']:
                self.supervisor_stats['routing_decisions'][selected_agent] = 0
            self.supervisor_stats['routing_decisions'][selected_agent] += 1

            # Agregar información de routing al metadata para el agente
            if 'metadata' not in state:
                state['metadata'] = {}

            state['metadata']['routing_info'] = {
                'decision': routing_decision,
                'confidence': routing_decision['confidence'],
                'method': routing_decision['method_used']
            }

            logger.info(f"Routing decision: {selected_agent} "
                       f"(method: {routing_decision['method_used']}, "
                       f"confidence: {routing_decision['confidence']:.2f})")

            return selected_agent

        except Exception as e:
            logger.error(f"Error en routing optimizado: {e}")
            return "general"  # Fallback seguro

    def run(self, state: AgentState) -> Dict:
        """Ejecuta la lógica del supervisor optimizado"""
        next_agent = self.route(state)
        return {"next_agent": next_agent}

    def execute_agent_with_fallback(self, agent_key: str, state: AgentState) -> Dict[str, Any]:
        """Ejecuta agente con sistema de fallback robusto"""
        return self.agent_executor.execute_agent(agent_key, state, enable_fallback=True)

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas completas del sistema"""
        return {
            'supervisor': self.supervisor_stats,
            'routing': self.hybrid_router.get_routing_stats(),
            'execution': self.agent_executor.get_execution_stats(),
            'system_health': self._get_system_health()
        }

    def _get_system_health(self) -> Dict[str, Any]:
        """Evalúa la salud general del sistema"""
        routing_stats = self.hybrid_router.get_routing_stats()
        execution_stats = self.agent_executor.get_execution_stats()

        return {
            'routing_success_rate': routing_stats.get('success_rate', 0.0),
            'execution_success_rate': execution_stats.get('success_rate', 0.0),
            'average_response_time': execution_stats.get('avg_response_time', 0.0),
            'fallback_usage_rate': execution_stats.get('fallback_rate', 0.0),
            'system_status': self._determine_system_status(routing_stats, execution_stats)
        }

    def _determine_system_status(self, routing_stats: Dict, execution_stats: Dict) -> str:
        """Determina el estado general del sistema"""
        routing_success = routing_stats.get('success_rate', 0.0)
        execution_success = execution_stats.get('success_rate', 0.0)
        fallback_rate = execution_stats.get('fallback_rate', 0.0)

        if routing_success > 0.9 and execution_success > 0.95 and fallback_rate < 0.05:
            return "excellent"
        elif routing_success > 0.8 and execution_success > 0.9 and fallback_rate < 0.1:
            return "good"
        elif routing_success > 0.7 and execution_success > 0.85 and fallback_rate < 0.15:
            return "fair"
        else:
            return "needs_attention"

    def save_conversation_feedback(self, conversation_id: str, user_rating: float,
                                 routing_decision: Dict[str, Any], actual_resolution: str):
        """Guarda feedback de conversación para mejora continua"""
        feedback = {
            'conversation_id': conversation_id,
            'timestamp': datetime.now().isoformat(),
            'user_rating': user_rating,
            'routing_decision': routing_decision,
            'actual_resolution': actual_resolution,
            'was_routing_correct': routing_decision['selected_agent'] == actual_resolution
        }

        # Guardar en router híbrido para análisis
        self.hybrid_router.save_routing_feedback(
            routing_decision,
            actual_resolution,
            user_rating
        )

        # Registrar en estadísticas del supervisor
        self.supervisor_stats['user_satisfaction_feedback'].append(feedback)

        logger.info(f"Feedback guardado para conversación {conversation_id}: rating={user_rating}")


class OptimizedMultiAgentSystem:
    """Sistema multi-agente optimizado con todas las mejoras"""

    def __init__(self):
        self.supervisor = OptimizedSupervisor()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construye el grafo optimizado de flujo de trabajo"""
        workflow = StateGraph(AgentState)

        # Agregar nodo supervisor
        workflow.add_node("supervisor", self.supervisor.run)

        # Agregar nodos de agentes con ejecución robusta
        for agent_name in self.supervisor.agents.keys():
            workflow.add_node(
                agent_name,
                lambda state, agent=agent_name: self.supervisor.execute_agent_with_fallback(agent, state)
            )

        # Definir flujo - START → supervisor
        workflow.add_edge(START, "supervisor")

        # Edges condicionales desde supervisor
        def route_condition(state: AgentState) -> str:
            return state.get("next_agent", "END")

        workflow.add_conditional_edges(
            "supervisor",
            route_condition,
            {
                "tax": "tax",
                "dte": "dte",
                "sii": "sii",
                "general": "general",
                "END": END
            }
        )

        # Los agentes vuelven al supervisor
        for agent_name in self.supervisor.agents.keys():
            workflow.add_edge(agent_name, "supervisor")

        return workflow.compile()

    def process(self, message: str, metadata: Optional[Dict] = None,
               conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Procesa un mensaje con sistema optimizado completo"""
        start_time = time.time()

        try:
            self.supervisor.supervisor_stats['total_conversations'] += 1

            logger.info(f"Procesando mensaje optimizado: {message[:100]}...")

            initial_state = {
                "messages": [HumanMessage(content=message)],
                "next_agent": "",
                "metadata": {
                    **(metadata or {}),
                    "conversation_id": conversation_id,
                    "start_time": start_time
                }
            }

            # Ejecutar workflow optimizado
            result = self.graph.invoke(initial_state)

            processing_time = time.time() - start_time

            # Extraer respuesta final con información extendida
            response_data = {
                'success': True,
                'response': self._extract_final_response(result),
                'processing_time': processing_time,
                'routing_info': result.get('metadata', {}).get('routing_info', {}),
                'agent_execution_info': self._extract_execution_info(result),
                'conversation_id': conversation_id
            }

            # Actualizar estadísticas
            self._update_conversation_stats(processing_time)

            logger.info(f"Mensaje procesado exitosamente en {processing_time:.2f}s")

            return response_data

        except Exception as e:
            processing_time = time.time() - start_time

            logger.error(f"Error en OptimizedMultiAgentSystem: {e}")

            return {
                'success': False,
                'response': "Ocurrió un error al procesar tu consulta. Por favor, intenta nuevamente.",
                'error': str(e),
                'processing_time': processing_time,
                'conversation_id': conversation_id
            }

    def _extract_final_response(self, result: Dict) -> str:
        """Extrae la respuesta final del resultado"""
        if result and result.get("messages"):
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and msg.content.strip():
                    return msg.content

        return "No pude procesar tu consulta. Por favor, intenta reformularla."

    def _extract_execution_info(self, result: Dict) -> Dict[str, Any]:
        """Extrae información de ejecución del resultado"""
        return {
            'agent_used': result.get('agent_used', 'unknown'),
            'success': result.get('success', False),
            'fallback_used': result.get('fallback_used', False),
            'execution_time': result.get('execution_time', 0.0),
            'fallback_reason': result.get('fallback_reason')
        }

    def _update_conversation_stats(self, processing_time: float):
        """Actualiza estadísticas de conversación"""
        stats = self.supervisor.supervisor_stats

        # Calcular promedio móvil del tiempo de conversación
        total_conversations = stats['total_conversations']
        current_avg = stats['avg_conversation_time']

        new_avg = ((current_avg * (total_conversations - 1)) + processing_time) / total_conversations
        stats['avg_conversation_time'] = new_avg

    def get_system_status(self) -> Dict[str, Any]:
        """Obtiene estado completo del sistema optimizado"""
        return {
            'system_type': 'optimized_multi_agent',
            'version': '2.0',
            'features_enabled': [
                'hybrid_routing',
                'semantic_search',
                'llm_fallback',
                'timeout_protection',
                'execution_fallback',
                'comprehensive_monitoring'
            ],
            'stats': self.supervisor.get_comprehensive_stats(),
            'uptime_hours': (datetime.now() - self.supervisor.supervisor_stats['start_time']).total_seconds() / 3600
        }

    def reset_all_stats(self):
        """Reinicia todas las estadísticas del sistema"""
        self.supervisor.supervisor_stats = {
            'total_conversations': 0,
            'routing_decisions': {},
            'avg_conversation_time': 0.0,
            'user_satisfaction_feedback': [],
            'start_time': datetime.now()
        }

        self.supervisor.agent_executor.reset_stats()

        # Note: No reseteamos hybrid_router stats intencionalmente
        # para mantener aprendizaje a largo plazo

        logger.info("Estadísticas del sistema reiniciadas")


# Instancia global del sistema optimizado
optimized_multi_agent_system = OptimizedMultiAgentSystem()