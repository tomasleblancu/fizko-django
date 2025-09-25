"""
Agente General: servicios del SII, FAQ oficiales, información de empresa, contabilidad general
"""
from typing import Dict, Any, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from django.conf import settings

from .tools import (
    search_sii_faqs,
    get_sii_faq_categories,
    search_sii_faqs_by_category,
    ask_sii_question
)

# Importar herramientas mejoradas
from .enhanced_tools import (
    enhanced_search_sii_faqs,
    intelligent_sii_assistant,
    batch_sii_queries,
    get_sii_search_analytics,
    provide_search_feedback
)

# Importar herramienta de información del taxpayer
from ..dte.tools_context import get_taxpayer_information_secured, set_user_context


# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class SIIAgent:
    """Agente General: servicios del SII, FAQ oficiales, información de empresa, contabilidad general"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Herramientas disponibles para el agente (incluyendo versiones mejoradas)
        self.tools = [
            # Herramientas originales (mantener compatibilidad)
            search_sii_faqs,
            get_sii_faq_categories,
            search_sii_faqs_by_category,
            ask_sii_question,
            # Herramientas mejoradas con búsqueda vectorial avanzada
            enhanced_search_sii_faqs,
            intelligent_sii_assistant,
            batch_sii_queries,
            get_sii_search_analytics,
            provide_search_feedback,
            # Herramienta de información del contribuyente/empresa
            get_taxpayer_information_secured
        ]

        # Crear agente React con herramientas
        self.agent = create_react_agent(
            self.llm,
            self.tools
        )

    def run(self, state: AgentState) -> Dict:
        """Ejecuta el agente General con capacidades de SII, FAQ y información de empresa"""
        try:
            # Establecer contexto del usuario desde metadata
            metadata = state.get("metadata", {})
            user_id = metadata.get("user_id")

            # Pasar todo el contexto del usuario
            set_user_context(user_id, metadata)
            # Agregar mensaje del sistema con contexto general
            system_message = SystemMessage(content="""Eres un contador experto en el Servicio de Impuestos Internos (SII) de Chile.

            HERRAMIENTAS DISPONIBLES:
            - get_taxpayer_information_secured: Información completa de la empresa del usuario
            - enhanced_search_sii_faqs: Busca en FAQs oficiales del SII
            - intelligent_sii_assistant: Asistente SII completo

            REGLAS CRÍTICAS:
            - Para "mi empresa", "empresa", "socios", "actividades": USA get_taxpayer_information_secured INMEDIATAMENTE
            - Para consultas SII específicas: USA enhanced_search_sii_faqs
            - Para saludos simples: responde brevemente (máximo 1 línea)
            - Respuestas DIRECTAS y CONCISAS (máximo 2-3 líneas)
            - NUNCA expliques capacidades o listes lo que puedes hacer
            - NUNCA pidas RUT o información que ya tienes""")

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
                fallback_message = AIMessage(content="No pude procesar tu consulta sobre el SII. Por favor, reformula tu pregunta.")
                return {
                    "messages": [fallback_message],
                    "next_agent": "supervisor"
                }

        except Exception as e:
            from langchain_core.messages import AIMessage
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in SIIAgent: {e}")

            error_message = AIMessage(content="Hubo un error al procesar tu consulta sobre el SII. Intenta nuevamente.")
            return {
                "messages": [error_message],
                "next_agent": "supervisor"
            }