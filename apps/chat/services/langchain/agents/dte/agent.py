"""
Agente especializado en documentos tributarios electrónicos con herramientas
"""
from typing import Dict, Any, TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from django.conf import settings

from .tools_context import (
    get_document_types_info_secured,
    validate_dte_code_secured,
    search_documents_by_criteria_secured,
    get_document_stats_summary_secured,
    calculate_dte_tax_impact_secured,
    get_recent_documents_summary_secured,
    get_taxpayer_information_secured,
    set_user_context
)


# Estado compartido entre agentes
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class DTEAgent:
    """Agente especializado en documentos tributarios electrónicos con herramientas"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-5-nano",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Herramientas disponibles para el agente DTE (EXCLUSIVAMENTE documentos electrónicos)
        self.tools = [
            get_document_types_info_secured,
            validate_dte_code_secured,
            search_documents_by_criteria_secured,
            get_document_stats_summary_secured,
            calculate_dte_tax_impact_secured,
            get_recent_documents_summary_secured
        ]

        # Crear agente React con herramientas
        self.agent = create_react_agent(
            self.llm,
            self.tools
        )

    def run(self, state: AgentState) -> Dict:
        """Ejecuta el agente DTE con capacidades de herramientas restringidas por usuario"""
        try:
            from langchain_core.messages import SystemMessage

            # Establecer contexto completo del usuario desde metadata
            metadata = state.get("metadata", {})
            user_id = metadata.get("user_id")

            # Pasar todo el contexto del usuario, incluyendo las empresas
            set_user_context(user_id, metadata)

            # Agregar mensaje del sistema con contexto específico del DTE
            system_message = SystemMessage(content="""Eres un experto en Documentos Tributarios Electrónicos (DTE) de Chile con acceso a herramientas especializadas.

            COMPORTAMIENTO PROACTIVO:
            - YA tienes acceso automático a los documentos de las empresas del usuario
            - NUNCA pidas el RUT de la empresa ni información adicional
            - USA directamente las herramientas para consultar documentos
            - Si el usuario pregunta sobre documentos, facturas, boletas, etc., BUSCA inmediatamente

            TIPOS DE DOCUMENTOS DTE:
            - Factura Electrónica (33): Ventas afectas a IVA 19%
            - Factura Exenta (34): Ventas exentas de IVA
            - Boleta Electrónica (39): Consumidor final
            - Nota de Crédito (61): Anulaciones y devoluciones
            - Nota de Débito (56): Cargos adicionales
            - Guía de Despacho (52): Traslado de mercancías
            - Factura de Exportación (110): Exportaciones

            DIRECCIÓN DE DOCUMENTOS (document_direction):
            - EMITIDO: Documentos que la empresa emite (facturas de venta, boletas emitidas)
            - RECIBIDO: Documentos que la empresa recibe (facturas de compra, gastos)

            DIFERENCIAS CRÍTICAS:
            - Factura EMITIDA: Venta de la empresa (ingreso, genera IVA débito fiscal)
            - Factura RECIBIDA: Compra de la empresa (gasto, genera IVA crédito fiscal)
            - Siempre distinguir entre documentos emitidos vs recibidos en análisis

            HERRAMIENTAS - ÚSALAS PROACTIVAMENTE:
            - get_document_stats_summary_secured: Para estadísticas generales de documentos (USAR PRIMERO para contexto)
            - get_recent_documents_summary_secured: Para documentos recientes y detalles específicos
            - search_documents_by_criteria_secured: Para búsquedas con criterios específicos
            - calculate_dte_tax_impact_secured: Para cálculos tributarios de DTEs
            - validate_dte_code_secured: Para validar códigos DTE
            - get_document_types_info_secured: Para información de tipos de documentos

            FLUJO DE TRABAJO AUTOMÁTICO:
            1. Usuario pregunta sobre documentos → USA inmediatamente get_document_stats_summary_secured
            2. Si necesita más detalles → USA get_recent_documents_summary_secured
            3. Si necesita búsqueda específica → USA search_documents_by_criteria_secured
            4. Para cálculos de IVA o impacto tributario → USA calculate_dte_tax_impact_secured
            5. NUNCA pidas RUT, fechas, o información adicional a menos que sea absolutamente necesario

            RESPUESTAS:
            - Concisas y directas (máximo 3-4 líneas)
            - Con datos específicos de los documentos encontrados
            - Incluye números, montos, fechas cuando disponibles""")

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
                fallback_message = AIMessage(content="No pude procesar tu consulta sobre DTEs. Por favor, reformula tu pregunta.")
                return {
                    "messages": [fallback_message],
                    "next_agent": "supervisor"
                }
        except Exception as e:
            from langchain_core.messages import AIMessage
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error in DTEAgent: {e}")

            error_message = AIMessage(content="Hubo un error al procesar tu consulta sobre DTEs. Intenta nuevamente.")
            return {
                "messages": [error_message],
                "next_agent": "supervisor"
            }