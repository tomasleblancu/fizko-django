"""
Agente especializado en proceso de onboarding - registro y primeros pasos
"""
from typing import Dict, Any, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from django.conf import settings

from .tools import (
    get_onboarding_status,
    update_onboarding_step,
    finalize_onboarding,
    set_onboarding_context,
    get_onboarding_context
)


# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class OnboardingAgent:
    """Agente especializado en onboarding de nuevos usuarios"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Herramientas disponibles para el agente Onboarding
        self.tools = [
            get_onboarding_status,
            update_onboarding_step,
            finalize_onboarding
        ]

        # Crear agente React con herramientas
        self.agent = create_react_agent(
            self.llm,
            self.tools
        )

    def run(self, state: AgentState) -> Dict:
        """Ejecuta el agente de onboarding para usuarios no autenticados"""
        try:
            # Establecer contexto de la sesión
            metadata = state.get("metadata", {})
            session_id = metadata.get("session_id", "")
            user_id = metadata.get("user_id")  # Cambiar para que use metadata como otros agentes

            # Preparar contexto completo con user_id
            onboarding_context = {
                **metadata,
                "user_id": user_id,
                "session_id": session_id
            }

            # Pasar contexto de sesión
            set_onboarding_context(session_id, onboarding_context)

            # Agregar mensaje del sistema con contexto de onboarding
            system_message = SystemMessage(content="""Eres un especialista en onboarding de Fizko, una plataforma de contabilidad chilena.

            TU MISIÓN: Ayudar a usuarios AUTENTICADOS a completar el proceso de onboarding para crear su empresa.

            PROCESO DE ONBOARDING (4 PASOS):

            1. INFORMACIÓN PERSONAL:
            - Recopila: nombre completo, teléfono, información profesional
            - Pregunta sobre experiencia empresarial y conocimiento contable
            - USA update_onboarding_step con step=1 cuando termine

            2. INFORMACIÓN DE NEGOCIO:
            - Pregunta sobre el tipo de negocio, industria, tamaño esperado
            - Objetivos con la plataforma
            - USA update_onboarding_step con step=2 cuando termine

            3. CREDENCIALES DE EMPRESA:
            - Solicita RUT de empresa (formato XX.XXX.XXX-X)
            - Clave del SII (Servicio de Impuestos Internos)
            - Nombre/razón social de la empresa
            - USA update_onboarding_step con step=3 cuando termine
            - IMPORTANTE: Este paso verifica credenciales con el SII

            4. FINALIZACIÓN:
            - Muestra resumen de información completada
            - USA finalize_onboarding para crear la empresa oficialmente
            - Inicia sincronización con SII

            HERRAMIENTAS DISPONIBLES:
            - get_onboarding_status: Ver estado actual del onboarding
            - update_onboarding_step: Actualizar/completar un paso específico
            - finalize_onboarding: Finalizar onboarding y crear empresa

            COMPORTAMIENTO:
            - Conversacional y guía paso a paso
            - Verifica el estado actual antes de proceder
            - Explica qué está pasando en cada paso
            - Si hay errores de credenciales SII, ayuda a resolverlos
            - Respuestas concisas pero informativas

            IMPORTANTE:
            - Solo para usuarios YA AUTENTICADOS
            - El onboarding crea la empresa real con datos del SII
            - Verificar SIEMPRE el estado actual con get_onboarding_status primero""")

            # Preparar mensajes incluyendo el contexto del sistema
            messages = [system_message] + state["messages"]

            # El agente React maneja automáticamente las tool calls
            response = self.agent.invoke({"messages": messages})

            # Extraer el último mensaje de respuesta
            if response and response.get("messages"):
                # Filtrar solo las respuestas AI finales (no los tool calls internos)
                final_messages = []
                for msg in response["messages"]:
                    if hasattr(msg, 'type') and msg.type == 'ai':
                        final_messages.append(msg)

                return {
                    "messages": final_messages[-1:] if final_messages else response["messages"][-1:],
                    "next_agent": "supervisor"
                }
            else:
                # Fallback si no hay respuesta válida
                from langchain_core.messages import AIMessage
                fallback_message = AIMessage(content="No pude procesar tu solicitud de onboarding. ¿Podrías intentar nuevamente?")
                return {
                    "messages": [fallback_message],
                    "next_agent": "supervisor"
                }

        except Exception as e:
            from langchain_core.messages import AIMessage
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in OnboardingAgent: {e}")

            error_message = AIMessage(content="Hubo un error procesando tu registro. Por favor, intenta nuevamente o contacta soporte.")
            return {
                "messages": [error_message],
                "next_agent": "supervisor"
            }