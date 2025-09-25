"""
Supervisor mejorado con sistema de memoria avanzada integrado
"""
from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from django.conf import settings
import asyncio
import logging
import time
from datetime import datetime
import uuid

# Importar componentes optimizados
from .hybrid_router import get_hybrid_router
from .agent_executor import AgentExecutor
from .memory import advanced_memory_system, UserProfile, ConversationEvent

# Importar agentes
from .agents import TaxAgent, DTEAgent, SIIAgent, GeneralAgent

logger = logging.getLogger(__name__)


# Estado compartido mejorado con memoria
class EnhancedAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]
    user_id: str
    conversation_id: str
    memory_context: Dict[str, Any]


class MemoryEnhancedSupervisor:
    """Supervisor con sistema de memoria avanzada"""

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

        # Sistemas optimizados
        self.hybrid_router = get_hybrid_router()
        self.agent_executor = AgentExecutor(self.agents)
        self.memory_system = advanced_memory_system

        # Configurar timeouts con memoria
        self.agent_executor.set_agent_timeout("sii", 50.0)  # Más tiempo por memoria + FAISS
        self.agent_executor.set_agent_timeout("dte", 40.0)  # Más tiempo por memoria + BD
        self.agent_executor.set_agent_timeout("tax", 30.0)
        self.agent_executor.set_agent_timeout("general", 25.0)

        # Estadísticas del supervisor mejorado
        self.supervisor_stats = {
            'conversations_with_memory': 0,
            'context_injections': 0,
            'memory_synchronizations': 0,
            'context_summaries_generated': 0,
            'start_time': datetime.now()
        }

    async def route_with_memory(self, state: EnhancedAgentState) -> str:
        """Routing híbrido con contexto de memoria"""
        try:
            user_id = state.get("user_id")
            conversation_id = state.get("conversation_id")

            # Extraer última consulta del usuario
            user_message = None
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                logger.warning("No se encontró mensaje del usuario")
                return "general"

            # Obtener perfil del usuario para contexto de routing
            user_profile = self.memory_system.get_user_profile(user_id)

            # Preparar metadata enriquecida con memoria
            routing_metadata = {
                **state.get("metadata", {}),
                "user_profile": user_profile.to_dict() if user_profile else None,
                "conversation_context": state.get("memory_context", {})
            }

            # Usar router híbrido con contexto de memoria
            routing_decision = self.hybrid_router.route(user_message, routing_metadata)

            selected_agent = routing_decision['selected_agent']

            # Registrar evento en memoria
            if user_profile:
                # Actualizar agentes frecuentemente usados
                if selected_agent not in user_profile.frequently_used_agents:
                    user_profile.frequently_used_agents.append(selected_agent)
                user_profile.last_activity = datetime.now()
                self.memory_system.update_user_profile(user_profile)

            # Registrar evento de routing en memoria del agente
            memory_manager = self.memory_system.get_memory_manager(
                selected_agent, user_id, conversation_id
            )

            memory_manager.add_event(
                event_type='routing_decision',
                content=f"Usuario consultó: {user_message[:100]}...",
                metadata={
                    'routing_method': routing_decision['method_used'],
                    'confidence': routing_decision['confidence']
                },
                importance=0.6
            )

            # Actualizar metadata del estado con información de routing
            state['metadata']['routing_info'] = routing_decision
            state['metadata']['selected_agent'] = selected_agent

            logger.info(f"Routing con memoria: {selected_agent} "
                       f"(method: {routing_decision['method_used']}, "
                       f"confidence: {routing_decision['confidence']:.2f})")

            return selected_agent

        except Exception as e:
            logger.error(f"Error en routing con memoria: {e}")
            return "general"

    def run(self, state: EnhancedAgentState) -> Dict:
        """Ejecuta supervisor con memoria"""
        # Asegurar que el estado tenga los campos necesarios
        if 'user_id' not in state:
            state['user_id'] = 'anonymous'
        if 'conversation_id' not in state:
            state['conversation_id'] = str(uuid.uuid4())

        # Usar routing asíncrono (convertir a sync si es necesario)
        try:
            # Para compatibilidad con LangGraph, usar versión sync del routing
            next_agent = asyncio.get_event_loop().run_until_complete(
                self.route_with_memory(state)
            )
        except RuntimeError:
            # Si no hay event loop, crear uno nuevo
            import asyncio
            next_agent = asyncio.run(self.route_with_memory(state))

        return {"next_agent": next_agent}

    def execute_agent_with_memory(self, agent_key: str, state: EnhancedAgentState) -> Dict[str, Any]:
        """Ejecuta agente con contexto de memoria inyectado"""
        try:
            user_id = state.get("user_id", "anonymous")
            conversation_id = state.get("conversation_id", str(uuid.uuid4()))

            # 1. Inyectar contexto de memoria seguro
            original_messages = state.get("messages", [])

            contextualized_messages = self.memory_system.inject_secure_context(
                agent_name=agent_key,
                user_id=user_id,
                conversation_id=conversation_id,
                base_messages=list(original_messages)
            )

            # Crear estado modificado con contexto de memoria
            memory_enhanced_state = {
                **state,
                "messages": contextualized_messages
            }

            self.supervisor_stats['context_injections'] += 1

            # 2. Ejecutar agente con timeout y fallback
            execution_result = self.agent_executor.execute_agent(
                agent_key, memory_enhanced_state, enable_fallback=True
            )

            # 3. Procesar resultado y actualizar memoria
            if execution_result.get('success') and execution_result.get('messages'):
                # Obtener gestor de memoria para este agente
                memory_manager = self.memory_system.get_memory_manager(
                    agent_key, user_id, conversation_id
                )

                # Agregar mensajes a la memoria del agente
                for message in execution_result['messages']:
                    if isinstance(message, (HumanMessage, AIMessage)):
                        memory_manager.add_message(message, importance=0.7)

                # Registrar evento de ejecución exitosa
                memory_manager.add_event(
                    event_type='agent_execution',
                    content=f"Agente {agent_key} ejecutado exitosamente",
                    metadata={
                        'execution_time': execution_result.get('execution_time', 0),
                        'fallback_used': execution_result.get('fallback_used', False)
                    },
                    importance=0.8
                )

                # Verificar si necesita sincronización con otros agentes
                self._check_memory_synchronization(
                    agent_key, user_id, conversation_id, execution_result
                )

            # 4. Verificar si necesita compresión de memoria
            self._check_memory_compression(agent_key, user_id, conversation_id)

            return execution_result

        except Exception as e:
            logger.error(f"Error ejecutando {agent_key} con memoria: {e}")

            # Registrar error en memoria si es posible
            try:
                memory_manager = self.memory_system.get_memory_manager(
                    agent_key, user_id, conversation_id
                )
                memory_manager.add_event(
                    event_type='execution_error',
                    content=f"Error ejecutando {agent_key}: {str(e)}",
                    importance=0.9
                )
            except:
                pass

            # Retornar error estándar
            return {
                'messages': [AIMessage(content="Error procesando solicitud con memoria.")],
                'next_agent': 'supervisor',
                'success': False,
                'error': str(e)
            }

    def _check_memory_synchronization(self, agent_key: str, user_id: str,
                                    conversation_id: str, execution_result: Dict):
        """Verifica si se necesita sincronización de memoria entre agentes"""
        try:
            # Lógica para determinar cuándo sincronizar
            metadata = execution_result.get('metadata', {})
            routing_info = metadata.get('routing_info', {})

            # Sincronizar si el agente maneja información relevante para otros
            sync_scenarios = {
                'dte': ['tax', 'sii'],  # DTEs afectan impuestos y SII
                'tax': ['dte'],         # Impuestos relacionados con documentos
                'sii': ['dte', 'tax'],  # SII afecta documentos e impuestos
            }

            if agent_key in sync_scenarios:
                target_agents = sync_scenarios[agent_key]

                shared_info = {
                    'source_agent': agent_key,
                    'execution_time': execution_result.get('execution_time'),
                    'confidence': routing_info.get('confidence', 0.5),
                    'summary': f"Información actualizada desde {agent_key}"
                }

                self.memory_system.synchronize_agents_memory(
                    user_id, conversation_id, agent_key, target_agents, shared_info
                )

                self.supervisor_stats['memory_synchronizations'] += 1

        except Exception as e:
            logger.error(f"Error en sincronización de memoria: {e}")

    async def _check_memory_compression(self, agent_key: str, user_id: str, conversation_id: str):
        """Verifica si se necesita compresión de memoria"""
        try:
            memory_manager = self.memory_system.get_memory_manager(
                agent_key, user_id, conversation_id
            )

            # Comprimir si hay muchos mensajes sin resumen reciente
            if (len(memory_manager.short_term_memory) >= 15 and
                not memory_manager.context_summary):

                await self.memory_system.compress_agent_memory(
                    agent_key, user_id, conversation_id
                )

                self.supervisor_stats['context_summaries_generated'] += 1

        except Exception as e:
            logger.error(f"Error en compresión de memoria: {e}")

    def create_user_profile(self, user_id: str, company_ids: List[str] = None,
                          expertise_level: str = "beginner",
                          preferences: Dict[str, Any] = None) -> UserProfile:
        """Crea perfil de usuario para personalización"""
        user_profile = UserProfile(
            user_id=user_id,
            company_ids=company_ids or [],
            preferences=preferences or {},
            expertise_level=expertise_level,
            frequently_used_agents=[],
            last_activity=datetime.now(),
            security_context={'authenticated': True}
        )

        self.memory_system.update_user_profile(user_profile)
        return user_profile

    def get_memory_enhanced_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas completas incluyendo memoria"""
        base_stats = {
            'supervisor': self.supervisor_stats,
            'routing': self.hybrid_router.get_routing_stats(),
            'execution': self.agent_executor.get_execution_stats(),
            'memory_system': self.memory_system.get_system_memory_stats()
        }

        # Calcular métricas avanzadas
        memory_stats = base_stats['memory_system']
        total_conversations = self.supervisor_stats['conversations_with_memory']

        enhanced_metrics = {
            'memory_efficiency': {
                'avg_context_injections_per_conversation': (
                    self.supervisor_stats['context_injections'] / max(total_conversations, 1)
                ),
                'memory_compression_rate': (
                    self.supervisor_stats['context_summaries_generated'] / max(total_conversations, 1)
                ),
                'cross_agent_sync_rate': (
                    self.supervisor_stats['memory_synchronizations'] / max(total_conversations, 1)
                )
            },
            'personalization_metrics': {
                'users_with_profiles': base_stats['memory_system']['total_user_profiles'],
                'avg_memory_age_days': memory_stats.get('avg_memory_age_days', 0)
            }
        }

        return {
            **base_stats,
            'enhanced_metrics': enhanced_metrics
        }

    async def cleanup_system_memory(self, days_threshold: int = 30):
        """Limpia memoria antigua del sistema"""
        return self.memory_system.cleanup_old_memory(days_threshold)


class MemoryEnhancedMultiAgentSystem:
    """Sistema multi-agente con memoria avanzada"""

    def __init__(self):
        self.supervisor = MemoryEnhancedSupervisor()
        self.graph = self._build_enhanced_graph()

    def _build_enhanced_graph(self) -> StateGraph:
        """Construye grafo con soporte para memoria avanzada"""
        workflow = StateGraph(EnhancedAgentState)

        # Nodo supervisor con memoria
        workflow.add_node("supervisor", self.supervisor.run)

        # Nodos de agentes con memoria
        for agent_name in self.supervisor.agents.keys():
            workflow.add_node(
                agent_name,
                lambda state, agent=agent_name: self.supervisor.execute_agent_with_memory(agent, state)
            )

        # Flujo del grafo
        workflow.add_edge(START, "supervisor")

        def route_condition(state: EnhancedAgentState) -> str:
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

        # Volver al supervisor después de cada agente
        for agent_name in self.supervisor.agents.keys():
            workflow.add_edge(agent_name, "supervisor")

        return workflow.compile()

    def process_with_memory(self, message: str, user_id: str,
                          conversation_id: Optional[str] = None,
                          user_profile: Optional[UserProfile] = None,
                          metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Procesa mensaje con sistema de memoria completo"""
        start_time = time.time()

        try:
            # Generar conversation_id si no se proporciona
            if not conversation_id:
                conversation_id = f"{user_id}_{int(time.time())}"

            # Crear o actualizar perfil de usuario
            if user_profile:
                self.supervisor.memory_system.update_user_profile(user_profile)
            elif not self.supervisor.memory_system.get_user_profile(user_id):
                # Crear perfil básico si no existe
                self.supervisor.create_user_profile(user_id)

            self.supervisor.supervisor_stats['conversations_with_memory'] += 1

            logger.info(f"Procesando con memoria: user={user_id}, conv={conversation_id}")

            # Estado inicial mejorado
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "next_agent": "",
                "metadata": metadata or {},
                "user_id": user_id,
                "conversation_id": conversation_id,
                "memory_context": {}
            }

            # Ejecutar workflow con memoria
            result = self.graph.invoke(initial_state)

            processing_time = time.time() - start_time

            # Extraer información completa de respuesta
            response_data = {
                'success': True,
                'response': self._extract_final_response(result),
                'processing_time': processing_time,
                'conversation_id': conversation_id,
                'user_id': user_id,
                'routing_info': result.get('metadata', {}).get('routing_info', {}),
                'agent_execution_info': self._extract_execution_info(result),
                'memory_stats': self._get_conversation_memory_stats(user_id, conversation_id)
            }

            logger.info(f"Procesado con memoria en {processing_time:.2f}s")

            return response_data

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error procesando con memoria: {e}")

            return {
                'success': False,
                'response': "Error procesando solicitud con sistema de memoria.",
                'error': str(e),
                'processing_time': processing_time,
                'conversation_id': conversation_id,
                'user_id': user_id
            }

    def _extract_final_response(self, result: Dict) -> str:
        """Extrae respuesta final del resultado"""
        if result and result.get("messages"):
            for msg in reversed(result["messages"]):
                if isinstance(msg, AIMessage) and msg.content.strip():
                    return msg.content
        return "No se pudo procesar la consulta con el sistema de memoria."

    def _extract_execution_info(self, result: Dict) -> Dict[str, Any]:
        """Extrae información de ejecución"""
        return {
            'agent_used': result.get('agent_used', 'unknown'),
            'success': result.get('success', False),
            'fallback_used': result.get('fallback_used', False),
            'execution_time': result.get('execution_time', 0.0),
            'memory_context_used': bool(result.get('memory_context'))
        }

    def _get_conversation_memory_stats(self, user_id: str, conversation_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de memoria para la conversación"""
        stats = {}
        for agent_name in self.supervisor.agents.keys():
            memory_manager = self.supervisor.memory_system.get_memory_manager(
                agent_name, user_id, conversation_id
            )
            stats[agent_name] = memory_manager.get_memory_stats()

        return stats

    def get_enhanced_system_status(self) -> Dict[str, Any]:
        """Estado completo del sistema con memoria"""
        return {
            'system_type': 'memory_enhanced_multi_agent',
            'version': '3.0',
            'features_enabled': [
                'hybrid_routing',
                'advanced_memory_system',
                'per_agent_memory',
                'context_compression',
                'memory_synchronization',
                'user_personalization',
                'secure_context_injection',
                'timeout_protection',
                'comprehensive_monitoring'
            ],
            'stats': self.supervisor.get_memory_enhanced_stats(),
            'uptime_hours': (
                datetime.now() - self.supervisor.supervisor_stats['start_time']
            ).total_seconds() / 3600
        }


# Instancia global del sistema con memoria avanzada
memory_enhanced_multi_agent_system = MemoryEnhancedMultiAgentSystem()