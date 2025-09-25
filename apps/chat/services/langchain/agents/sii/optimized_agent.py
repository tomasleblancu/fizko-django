"""
Agente SII optimizado con sistema de recuperación mejorado
"""
from typing import Dict, Any, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from django.conf import settings
import logging

from .optimized_tools import (
    search_sii_faqs_optimized,
    ask_sii_question_optimized,
    get_sii_faq_categories_optimized,
    search_sii_faqs_by_category_optimized,
    get_sii_system_stats,
    refresh_sii_faqs_optimized
)

logger = logging.getLogger(__name__)

# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class OptimizedSIIAgent:
    """Agente SII optimizado con sistema de recuperación mejorado"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Herramientas optimizadas disponibles para el agente
        self.tools = [
            search_sii_faqs_optimized,
            ask_sii_question_optimized,
            get_sii_faq_categories_optimized,
            search_sii_faqs_by_category_optimized,
            get_sii_system_stats,
            refresh_sii_faqs_optimized
        ]

        # Crear agente React con herramientas optimizadas
        self.agent = create_react_agent(
            self.llm,
            self.tools
        )

    def run(self, state: AgentState) -> Dict:
        """Ejecuta el agente SII optimizado"""
        try:
            # Sistema message optimizado con información del sistema mejorado
            system_message = SystemMessage(content="""Eres un experto en el Servicio de Impuestos Internos (SII) de Chile con acceso al sistema OPTIMIZADO de preguntas frecuentes oficiales.

            🚀 SISTEMA OPTIMIZADO DISPONIBLE:
            - **454 FAQs oficiales** con indexación FAISS ultrarrápida
            - **Carga incremental** que solo procesa cambios nuevos
            - **Cache de embeddings** para reducir costos y tiempo
            - **Persistencia de índice** para arranque instantáneo
            - **Monitorización avanzada** de performance

            📂 CATEGORÍAS DISPONIBLES (14):
            - Clave tributaria, mandatario digital y representantes electrónicos
            - Factura Electrónica (129 FAQs)
            - Boleta Electrónica de Ventas y Servicios (74 FAQs)
            - Avalúos y Contribuciones de Bienes Raíces (67 FAQs)
            - Término de Giro (32 FAQs)
            - IVA a los Servicios Profesionales y Culturales (24 FAQs)
            - Peticiones Administrativas y Otras Solicitudes (23 FAQs)
            - Impuesto a Aviones, Helicópteros, Yates y Vehículos de Alto Valor (20 FAQs)
            - Boletas de Honorarios Electrónicas (16 FAQs)
            - Y 5 categorías más especializadas

            🔧 HERRAMIENTAS OPTIMIZADAS DISPONIBLES:

            **BÚSQUEDA Y RESPUESTAS:**
            - `search_sii_faqs_optimized`: Búsqueda vectorizada ultrarrápida con estadísticas
            - `ask_sii_question_optimized`: Respuestas contextualizadas con QA Chain mejorado
            - `search_sii_faqs_by_category_optimized`: Búsqueda precisa por categoría

            **EXPLORACIÓN Y ADMINISTRACIÓN:**
            - `get_sii_faq_categories_optimized`: Explorar todas las categorías disponibles
            - `get_sii_system_stats`: Estadísticas de performance y optimización
            - `refresh_sii_faqs_optimized`: Forzar actualización completa si es necesario

            📋 INSTRUCCIONES OPTIMIZADAS:

            1. **PRIORIZA ask_sii_question_optimized** para preguntas directas que requieren respuesta elaborada
            2. **USA search_sii_faqs_optimized** para búsquedas amplias y exploración de temas
            3. **APROVECHA las estadísticas** incluidas en las respuestas para mejor contexto
            4. **El sistema es ultrarrápido** - no dudes en usar múltiples herramientas si es necesario
            5. **Información 100% oficial** del SII con sistema de última generación

            🎯 BENEFICIOS DEL SISTEMA OPTIMIZADO:
            - ⚡ **Arranque 10x más rápido** (índice persistente)
            - 💰 **Reduce costos API** (cache de embeddings)
            - 🔄 **Actualizaciones inteligentes** (solo procesa cambios)
            - 📊 **Monitorización avanzada** (estadísticas detalladas)
            - 🎯 **Mayor precisión** (FAISS optimizado)

            Responde de forma concisa (4-5 líneas) priorizando información oficial de los FAQs.""")

            # Preparar mensajes incluyendo el contexto del sistema optimizado
            messages = [system_message] + state["messages"]

            # El agente React maneja automáticamente las tool calls
            response = self.agent.invoke({"messages": messages})

            # Extraer el último mensaje de respuesta AI
            if response and response.get("messages"):
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
                fallback_message = AIMessage(
                    content="No pude procesar tu consulta sobre el SII con el sistema optimizado. Por favor, reformula tu pregunta."
                )
                return {
                    "messages": [fallback_message],
                    "next_agent": "supervisor"
                }

        except Exception as e:
            from langchain_core.messages import AIMessage

            logger.error(f"Error in OptimizedSIIAgent: {e}")

            error_message = AIMessage(
                content="Hubo un error al procesar tu consulta sobre el SII con el sistema optimizado. Intenta nuevamente."
            )
            return {
                "messages": [error_message],
                "next_agent": "supervisor"
            }

    def get_agent_info(self) -> Dict[str, Any]:
        """Información del agente optimizado"""
        return {
            "name": "OptimizedSIIAgent",
            "version": "2.0_optimized",
            "description": "Agente SII con sistema de recuperación optimizado",
            "features": [
                "Búsqueda vectorizada FAISS ultrarrápida",
                "Carga incremental de documentos",
                "Cache de embeddings persistente",
                "Monitorización avanzada de performance",
                "454 FAQs oficiales indexados",
                "RetrievalQA chain optimizado"
            ],
            "tools_count": len(self.tools),
            "optimization_benefits": {
                "startup_speed": "10x faster with persistent index",
                "api_costs": "Reduced with embedding cache",
                "memory_usage": "Efficient incremental updates",
                "search_quality": "Enhanced with FAISS optimization"
            }
        }