"""
Sistema Supervisor Avanzado con Seguridad, Memoria y Monitoreo Integrado
Utiliza todos los sistemas implementados: seguridad, memoria, monitoreo, routing híbrido
"""

from typing import Dict, List, Any, Optional, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from django.conf import settings
import logging
import asyncio
from datetime import datetime
import json

# Importar agentes
from .agents import DTEAgent, GeneralAgent
from .agents.onboarding.agent import OnboardingAgent

# Importar sistemas avanzados
from .security import (
    get_privilege_manager, get_context_controller, get_sandbox_manager,
    get_input_validator, get_security_monitor, get_compliance_manager,
    initialize_security_system, ResourceType, PermissionLevel
)

from .monitoring import (
    get_structured_logger, get_metrics_collector, get_tracing_system,
    get_alerting_system, get_quality_analyzer, get_monitoring_system
)

from .memory import (
    advanced_memory_system, ConversationEvent
)

from .hybrid_router import HybridRouter

logger = logging.getLogger(__name__)


# Estado avanzado del agente con contexto completo
class AdvancedAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]
    # Contextos de seguridad y sesión
    session_id: Optional[str]
    user_id: Optional[str]
    ip_address: Optional[str]
    # Contexto de memoria
    conversation_memory: Optional[Dict[str, Any]]
    agent_context: Optional[Dict[str, Any]]
    # Estado de calidad y monitoreo
    quality_metrics: Optional[Dict[str, Any]]
    security_events: Optional[List[Dict[str, Any]]]


class AdvancedSupervisor:
    """Supervisor avanzado con seguridad, memoria y monitoreo integrado"""

    def __init__(self):
        # Inicializar LLM
        self.llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Inicializar sistemas
        self._initialize_systems()

        # Inicializar agentes
        self.agents = {
            "dte": DTEAgent(),
            "general": GeneralAgent(),
            "onboarding": OnboardingAgent()
        }

        # Router híbrido
        self.hybrid_router = HybridRouter()

        # Prompt mejorado
        self.routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un supervisor inteligente que coordina agentes especializados en contabilidad y tributación chilena.

            AGENTES DISPONIBLES:
            🆕 onboarding: Para usuarios NO AUTENTICADOS que necesitan registrarse
            📄 dte: EXCLUSIVAMENTE documentos electrónicos (facturas, boletas, notas de crédito/débito, DTEs)
            💼 general: Para usuarios AUTENTICADOS - información de empresa, SII, contabilidad, saludos

            INSTRUCCIONES:
            1. Analiza la consulta considerando el contexto de la conversación
            2. Si hay memoria previa, úsala para tomar mejores decisiones
            3. Considera la seguridad y permisos del usuario
            4. Responde SOLO con el nombre del agente o END

            REGLAS CRÍTICAS:
            - USA "onboarding" SOLO cuando el usuario NO está autenticado y solicita registro/crear cuenta
            - USA "dte" SOLO para documentos electrónicos específicos
            - USA "general" para usuarios autenticados con otras consultas
            - Verifica SIEMPRE si el usuario está autenticado

            Ejemplos:
            "Quiero crear una cuenta" → onboarding
            "Mostrar mis facturas" → dte
            "¿Qué sabes de mi empresa?" → general
            "Hola" → general
            "Gracias, eso es todo" → END
            """),
            MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="memory_context", optional=True)
        ])

    def _initialize_systems(self):
        """Inicializa todos los sistemas avanzados"""
        try:
            # Inicializar sistema de seguridad
            security_result = initialize_security_system()
            logger.info(f"Sistema de seguridad: {security_result['status']}")

            # Obtener instancias de sistemas
            self.privilege_manager = get_privilege_manager()
            self.context_controller = get_context_controller()
            self.security_monitor = get_security_monitor()
            self.compliance_manager = get_compliance_manager()
            self.input_validator = get_input_validator()

            # Sistema de monitoreo
            self.monitoring_system = get_monitoring_system()
            self.structured_logger = get_structured_logger("advanced_supervisor")
            self.metrics_collector = get_metrics_collector()
            self.tracing_system = get_tracing_system()
            self.quality_analyzer = get_quality_analyzer()

            # Sistema de memoria
            self.memory_system = advanced_memory_system

            logger.info("Todos los sistemas avanzados inicializados correctamente")

        except Exception as e:
            logger.error(f"Error inicializando sistemas avanzados: {e}")
            # Usar versiones básicas como fallback
            self.privilege_manager = None
            self.security_monitor = None
            self.memory_system = None

    async def create_secure_session(self, user_id: Optional[str], ip_address: Optional[str] = None) -> str:
        """Crea sesión segura para el usuario"""
        try:
            if self.privilege_manager:
                session_id = self.privilege_manager.create_agent_session(
                    "supervisor_agent", user_id, {"ip_address": ip_address}
                )
                self.structured_logger.info(
                    "Sesión segura creada",
                    session_id=session_id,
                    user_id=user_id,
                    event_type="session_created"
                )
                return session_id
            else:
                # Fallback: generar ID simple
                import uuid
                return str(uuid.uuid4())[:16]
        except Exception as e:
            logger.error(f"Error creando sesión segura: {e}")
            import uuid
            return str(uuid.uuid4())[:16]

    async def validate_and_sanitize_input(self, user_input: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """Valida y sanitiza entrada del usuario"""
        try:
            if self.input_validator and self.security_monitor:
                # Validación con security monitor
                validation_result = self.security_monitor.validate_user_input(
                    user_input, user_id, session_id
                )

                if not validation_result["is_safe"]:
                    self.structured_logger.warning(
                        "Entrada bloqueada por seguridad",
                        user_input=user_input[:100],
                        issues=validation_result["issues"],
                        session_id=session_id,
                        event_type="input_blocked"
                    )
                    return {
                        "is_safe": False,
                        "sanitized_input": "",
                        "issues": validation_result["issues"]
                    }

                return {
                    "is_safe": True,
                    "sanitized_input": validation_result["sanitized_input"],
                    "issues": []
                }
            else:
                # Fallback: usar solo input validator
                validation_result = self.input_validator.validate_input(user_input)
                return {
                    "is_safe": validation_result.result.value != "blocked",
                    "sanitized_input": validation_result.sanitized_input,
                    "issues": validation_result.issues_found
                }
        except Exception as e:
            logger.error(f"Error en validación de entrada: {e}")
            return {
                "is_safe": True,  # Fallback permisivo
                "sanitized_input": user_input,
                "issues": []
            }

    async def get_conversation_memory(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Obtiene memoria de la conversación"""
        try:
            if self.memory_system:
                # Obtener memoria del agente supervisor
                supervisor_memory = self.memory_system.get_agent_memory("supervisor_agent")

                # Obtener contexto de conversación
                context = supervisor_memory.get_conversation_context(session_id, max_events=10)

                return {
                    "conversation_context": context,
                    "user_profile": supervisor_memory.get_user_profile(user_id),
                    "recent_topics": supervisor_memory.get_recent_topics(session_id, hours=1)
                }
            else:
                return {"conversation_context": [], "user_profile": {}, "recent_topics": []}
        except Exception as e:
            logger.error(f"Error obteniendo memoria: {e}")
            return {"conversation_context": [], "user_profile": {}, "recent_topics": []}

    async def route_with_hybrid_system(self, state: AdvancedAgentState) -> str:
        """Usa el router híbrido para decidir el agente"""
        try:
            # Extraer última consulta del usuario
            user_message = ""
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                return "general"

            # VERIFICAR ESTADO DE AUTENTICACIÓN
            user_id = state.get("user_id")
            is_authenticated = user_id is not None and user_id != "anonymous"

            # Usar router híbrido
            routing_result = self.hybrid_router.route(user_message, state.get("metadata", {}))
            selected_agent = routing_result.get("selected_agent", "general")

            # OVERRIDE DE ROUTING BASADO EN AUTENTICACIÓN Y NECESIDAD DE ONBOARDING
            if selected_agent == "onboarding":
                if not is_authenticated:
                    # Usuario no autenticado no puede hacer onboarding (necesita cuenta primero)
                    selected_agent = "general"
                    logger.info(f"Usuario no autenticado redirigido de onboarding a general (necesita cuenta)")
                else:
                    # Usuario autenticado: verificar si realmente necesita onboarding
                    needs_onboarding = self._check_user_needs_onboarding(user_id)
                    if not needs_onboarding:
                        selected_agent = "general"
                        logger.info(f"Usuario {user_id} ya completó onboarding, redirigido a general")
                    else:
                        logger.info(f"Usuario {user_id} necesita onboarding, mantener routing")
            elif is_authenticated and selected_agent in ["dte", "general"]:
                # Verificar si el mensaje sugiere necesidad de onboarding y usuario lo necesita
                onboarding_keywords = ["onboarding", "configurar empresa", "crear empresa", "completar registro"]
                if any(keyword in user_message.lower() for keyword in onboarding_keywords):
                    needs_onboarding = self._check_user_needs_onboarding(user_id)
                    if needs_onboarding:
                        selected_agent = "onboarding"
                        logger.info(f"Usuario {user_id} redirigido a onboarding (necesita completarlo)")
                    else:
                        logger.info(f"Usuario {user_id} ya completó onboarding, mantener en {selected_agent}")

            # Log de routing
            self.structured_logger.info(
                "Decisión de routing",
                query=user_message,
                selected_agent=selected_agent,
                method=routing_result.get("method_used"),
                confidence=routing_result.get("confidence", 0),
                is_authenticated=is_authenticated,
                user_id=user_id,
                session_id=state.get("session_id"),
                event_type="agent_routing"
            )

            return selected_agent

        except Exception as e:
            logger.error(f"Error en routing híbrido: {e}")
            return "general"

    def _check_user_needs_onboarding(self, user_id: str) -> bool:
        """Verifica si el usuario necesita completar onboarding consultando directamente la DB"""
        import threading

        # Crear un result container para thread-safe communication
        result = {'needs_onboarding': True, 'error': None}

        def sync_check():
            try:
                from django.contrib.auth import get_user_model
                from apps.onboarding.models import UserOnboarding

                User = get_user_model()
                user = User.objects.get(id=user_id)
                user_email = user.email

                # Verificar si existe un registro de finalización
                finalized_step = UserOnboarding.objects.filter(
                    user_email=user_email,
                    step__name='finalized',
                    status='completed'
                ).first()

                # El onboarding solo está completado si fue finalizado explícitamente
                is_completed = finalized_step is not None
                needs_onboarding = not is_completed

                logger.info(f"Usuario {user_id} ({user_email}): needs_onboarding={needs_onboarding}, is_finalized={is_completed}")
                result['needs_onboarding'] = needs_onboarding

            except Exception as e:
                logger.error(f"Error verificando necesidad de onboarding para usuario {user_id}: {e}")
                result['error'] = str(e)
                result['needs_onboarding'] = True  # Safe default

        # Ejecutar en thread separado para evitar problemas de contexto async
        thread = threading.Thread(target=sync_check)
        thread.start()
        thread.join(timeout=5.0)  # 5 second timeout

        if thread.is_alive():
            logger.error(f"Timeout verificando onboarding para usuario {user_id}")
            return True  # Safe default

        return result['needs_onboarding']

    async def prepare_secure_context(self, state: AdvancedAgentState, agent_name: str) -> Dict[str, Any]:
        """Prepara contexto seguro para el agente"""
        try:
            if self.context_controller:
                # Extraer datos relevantes del estado
                context_data = {
                    "messages": [msg.dict() for msg in state["messages"][-5:]],  # Últimos 5 mensajes
                    "metadata": state.get("metadata", {}),
                    "conversation_memory": state.get("conversation_memory", {}),
                    "timestamp": datetime.now().isoformat()
                }

                # Preparar contexto seguro con anonimización
                secure_context = self.context_controller.prepare_secure_context(
                    state.get("session_id", ""), agent_name, context_data, "agent_context"
                )

                return secure_context
            else:
                return {"data": [], "anonymization_applied": False}

        except Exception as e:
            logger.error(f"Error preparando contexto seguro: {e}")
            return {"data": [], "anonymization_applied": False}

    async def record_conversation_event(self, state: AdvancedAgentState, event_type: str, content: str):
        """Registra evento en el sistema de memoria"""
        try:
            if self.memory_system:
                supervisor_memory = self.memory_system.get_agent_memory("supervisor_agent")

                event = ConversationEvent(
                    timestamp=datetime.now(),
                    event_type=event_type,
                    agent="supervisor_agent",
                    content=content,
                    metadata={
                        "session_id": state.get("session_id"),
                        "user_id": state.get("user_id"),
                        "next_agent": state.get("next_agent")
                    }
                )

                supervisor_memory.add_conversation_event(
                    state.get("session_id", ""), event
                )
        except Exception as e:
            logger.error(f"Error registrando evento de conversación: {e}")

    async def run(self, state: AdvancedAgentState) -> Dict[str, Any]:
        """Ejecuta la lógica avanzada del supervisor"""
        try:
            # Iniciar traza si el sistema está disponible
            trace_context = None
            if self.tracing_system:
                trace_context = self.tracing_system.start_conversation_trace(
                    conversation_id=state.get("session_id", ""),
                    user_id=state.get("user_id"),
                    metadata=state.get("metadata", {})
                )

            # Si ya hay respuesta de agente, verificar calidad y terminar
            if state.get("next_agent") == "supervisor" and len(state["messages"]) >= 2:
                # Analizar calidad de la respuesta si está disponible
                if self.quality_analyzer and len(state["messages"]) >= 2:
                    last_human_msg = None
                    last_ai_msg = None

                    for msg in reversed(state["messages"]):
                        if isinstance(msg, AIMessage) and not last_ai_msg:
                            last_ai_msg = msg.content
                        elif isinstance(msg, HumanMessage) and not last_human_msg:
                            last_human_msg = msg.content

                    if last_human_msg and last_ai_msg:
                        # Análisis de calidad asíncrono
                        asyncio.create_task(self._analyze_response_quality(
                            state.get("session_id", ""),
                            state.get("next_agent", ""),
                            last_human_msg,
                            last_ai_msg
                        ))

                return {"next_agent": "END"}

            # Obtener memoria de conversación
            memory_context = await self.get_conversation_memory(
                state.get("session_id", ""), state.get("user_id", "")
            )
            state["conversation_memory"] = memory_context

            # Usar router híbrido para decisión
            next_agent = await self.route_with_hybrid_system(state)

            # Registrar evento de routing
            await self.record_conversation_event(
                state, "agent_routing", f"Routed to {next_agent}"
            )

            # Registrar métricas
            if self.metrics_collector:
                self.metrics_collector.record_routing_decision(
                    next_agent, "hybrid", 0.9, 0.1  # Confidence values
                )

            return {
                "next_agent": next_agent,
                "conversation_memory": memory_context
            }

        except Exception as e:
            logger.error(f"Error en supervisor avanzado: {e}")
            return {"next_agent": "general"}

    async def _analyze_response_quality(self, session_id: str, agent_name: str,
                                      user_query: str, agent_response: str):
        """Analiza calidad de respuesta de forma asíncrona"""
        try:
            if self.quality_analyzer:
                quality_result = await self.quality_analyzer.analyze_interaction(
                    conversation_id=session_id,
                    agent_name=agent_name,
                    user_query=user_query,
                    agent_response=agent_response,
                    response_time=1.0  # Tiempo simulado
                )

                self.structured_logger.info(
                    "Análisis de calidad completado",
                    session_id=session_id,
                    agent_name=agent_name,
                    quality_score=quality_result.get_overall_quality_score(),
                    event_type="quality_analysis"
                )
        except Exception as e:
            logger.error(f"Error en análisis de calidad: {e}")


class AdvancedMultiAgentSystem:
    """Sistema multi-agente avanzado con todos los sistemas integrados"""

    def __init__(self):
        self.supervisor = AdvancedSupervisor()
        self.graph = self._build_graph()

        # Logger estructurado
        self.logger = get_structured_logger("multi_agent_system")

        # Sistema de monitoreo
        self.monitoring = get_monitoring_system()

    def _build_graph(self) -> StateGraph:
        """Construye el grafo avanzado de flujo de trabajo"""
        workflow = StateGraph(AdvancedAgentState)

        # Agregar nodos
        workflow.add_node("supervisor", self._wrap_supervisor_node)

        # Agregar agentes con wrapping de seguridad
        for agent_name, agent in self.supervisor.agents.items():
            workflow.add_node(agent_name, self._wrap_agent_node(agent_name, agent))

        # Flujo principal
        workflow.add_edge(START, "supervisor")

        # Routing condicional
        def route_condition(state: AdvancedAgentState) -> str:
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

        # Agentes regresan al supervisor
        for agent_name in self.supervisor.agents.keys():
            workflow.add_edge(agent_name, "supervisor")

        return workflow.compile()

    async def _wrap_supervisor_node(self, state: AdvancedAgentState) -> Dict[str, Any]:
        """Wrapper del supervisor con monitoreo"""
        try:
            result = await self.supervisor.run(state)
            return result
        except Exception as e:
            self.logger.error("Error en nodo supervisor", error=str(e), event_type="supervisor_error")
            return {"next_agent": "general"}

    def _wrap_agent_node(self, agent_name: str, agent):
        """Wrapper de agentes con sandboxing y monitoreo"""
        async def wrapped_node(state: AdvancedAgentState) -> Dict[str, Any]:
            try:
                # Preparar contexto seguro
                secure_context = await self.supervisor.prepare_secure_context(state, agent_name)

                # Ejecutar agente con monitoreo
                if self.monitoring:
                    async with self.monitoring.monitor_agent_execution(
                        agent_name=agent_name,
                        input_messages=state["messages"],
                        user_id=state.get("user_id"),
                        conversation_id=state.get("session_id")
                    ):
                        # Ejecutar agente (síncronamente)
                        result = agent.run(state)
                        return result
                else:
                    # Fallback sin monitoreo
                    result = agent.run(state)
                    return result

            except Exception as e:
                self.logger.error(f"Error en agente {agent_name}", error=str(e), event_type="agent_error")
                # Respuesta de error segura
                error_message = AIMessage(content="Lo siento, ocurrió un error procesando tu consulta. Por favor intenta nuevamente.")
                return {"messages": [error_message]}

        return wrapped_node

    async def process_async(self, message: str, user_id: Optional[str] = None,
                          ip_address: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Procesa mensaje de forma asíncrona con todos los sistemas integrados"""
        session_id = None

        try:
            # Crear sesión segura
            session_id = await self.supervisor.create_secure_session(user_id, ip_address)

            # Validar y sanitizar entrada
            validation_result = await self.supervisor.validate_and_sanitize_input(
                message, session_id, user_id or "anonymous"
            )

            if not validation_result["is_safe"]:
                return "Tu mensaje contiene elementos que no puedo procesar por seguridad. Por favor, reformúlalo."

            sanitized_message = validation_result["sanitized_input"]

            self.logger.info(
                "Procesando mensaje",
                user_message=sanitized_message[:100],
                session_id=session_id,
                user_id=user_id,
                event_type="message_processing_start"
            )

            # Estado inicial avanzado
            initial_state = AdvancedAgentState(
                messages=[HumanMessage(content=sanitized_message)],
                next_agent="",
                metadata=metadata or {},
                session_id=session_id,
                user_id=user_id,
                ip_address=ip_address,
                conversation_memory=None,
                agent_context=None,
                quality_metrics=None,
                security_events=None
            )

            # Ejecutar workflow con monitoreo
            if self.monitoring:
                async with self.monitoring.monitor_conversation(session_id, user_id, ip_address):
                    result = await self.graph.ainvoke(initial_state)
            else:
                result = await self.graph.ainvoke(initial_state)

            # Extraer respuesta final
            response = self._extract_final_response(result)

            self.logger.info(
                "Mensaje procesado exitosamente",
                session_id=session_id,
                response_length=len(response),
                event_type="message_processing_complete"
            )

            return response

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error procesando mensaje en advanced_supervisor: {str(e)}")
            logger.error(f"Stack trace: {error_trace}")
            self.logger.error(
                "Error procesando mensaje",
                error=str(e),
                session_id=session_id,
                event_type="message_processing_error"
            )
            return "Ocurrió un error al procesar tu consulta. Por favor, intenta nuevamente."

    def process(self, message: str, user_id: Optional[str] = None,
               ip_address: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Procesa mensaje (interfaz síncrona para compatibilidad)"""
        try:
            # Ejecutar versión asíncrona
            return asyncio.run(self.process_async(message, user_id, ip_address, metadata))
        except Exception as e:
            self.logger.error("Error en proceso síncrono", error=str(e), event_type="sync_process_error")
            return "Error procesando la consulta."

    def _extract_final_response(self, result: Dict) -> str:
        """Extrae la respuesta final del resultado"""
        try:
            if result and result.get("messages"):
                # Buscar la última respuesta AI
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage) and msg.content.strip():
                        return msg.content

            return "No pude procesar tu consulta. Por favor, intenta reformularla."

        except Exception as e:
            self.logger.error("Error extrayendo respuesta", error=str(e), event_type="response_extraction_error")
            return "Error interno procesando la respuesta."

    def get_system_status(self) -> Dict[str, Any]:
        """Obtiene estado completo del sistema"""
        try:
            from .security import get_security_system_status

            return {
                "timestamp": datetime.now().isoformat(),
                "supervisor": "advanced",
                "agents_available": len(self.supervisor.agents),
                "systems_status": {
                    "security": get_security_system_status(),
                    "monitoring": "active" if self.monitoring else "inactive",
                    "memory": "active" if self.supervisor.memory_system else "inactive",
                    "routing": "hybrid"
                }
            }
        except Exception as e:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "status": "error"
            }


# Instancia global del sistema avanzado
advanced_multi_agent_system = AdvancedMultiAgentSystem()