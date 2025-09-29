"""
Agente LangChain dinámico que replica el comportamiento de DTEAgent/SIIAgent
pero carga configuración desde el modelo AgentConfig
"""
from typing import Dict, Any, TypedDict, Annotated, Sequence, List
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langchain.tools import tool
from django.conf import settings
import importlib
import logging


# Estado compartido entre agentes (igual que sistema actual)
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_agent: str
    metadata: Dict[str, Any]


class DynamicLangChainAgent:
    """
    Agente LangChain dinámico que se comporta exactamente igual que DTEAgent/SIIAgent
    pero carga su configuración desde el modelo AgentConfig
    """

    def __init__(self, agent_config_id: int):
        # Configurar logger primero
        self.logger = logging.getLogger(__name__)

        # Cargar configuración desde base de datos
        try:
            from apps.chat.models import AgentConfig
            self.config = AgentConfig.objects.select_related('model_config').get(id=agent_config_id)
        except Exception as e:
            raise ValueError(f"AgentConfig con ID {agent_config_id} no encontrado: {e}")

        # Configurar LLM desde AgentConfig (igual que agentes actuales)
        self.llm = ChatOpenAI(
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Cargar herramientas asignadas desde base de datos
        self.tools = self._load_tools_from_db()

        # Crear agente React (exactamente igual que sistema actual)
        if self.tools:
            self.agent = create_react_agent(self.llm, self.tools)
        else:
            # Si no hay herramientas, crear agente básico
            self.agent = None

    def _load_tools_from_db(self) -> List:
        """Carga herramientas desde AgentToolAssignment y las convierte a LangChain tools"""
        from apps.chat.models import AgentToolAssignment

        tools = []
        assignments = AgentToolAssignment.objects.filter(
            agent_config=self.config,
            is_enabled=True
        ).select_related('common_tool')

        for assignment in assignments:
            try:
                tool_func = self._convert_common_tool_to_langchain(assignment.common_tool)
                if tool_func:
                    tools.append(tool_func)
                    print(f"🔧 Herramienta cargada: {assignment.common_tool.display_name}")
            except Exception as e:
                self.logger.error(f"Error cargando herramienta {assignment.common_tool.name}: {e}")

        return tools

    def _convert_common_tool_to_langchain(self, common_tool):
        """Convierte un CommonTool a una herramienta LangChain"""
        try:
            # Importar función dinámicamente desde function_path
            module_path, function_name = common_tool.function_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            tool_function = getattr(module, function_name)

            # Crear herramienta LangChain usando el decorador @tool
            @tool(description=common_tool.description)
            def dynamic_tool(**kwargs):
                """Wrapper dinámico para herramienta CommonTool"""
                try:
                    # Verificar si es una herramienta LangChain (con invoke) o función Python normal
                    if hasattr(tool_function, 'invoke'):
                        # Es una herramienta LangChain, usar invoke con dict
                        result = tool_function.invoke(kwargs)
                    else:
                        # Es una función Python normal, usar llamada directa
                        result = tool_function(**kwargs)

                    self.logger.info(f"✅ Herramienta {common_tool.name} ejecutada exitosamente")
                    return result
                except Exception as e:
                    self.logger.error(f"❌ Error en herramienta {common_tool.name}: {e}")
                    return f"Error ejecutando {common_tool.name}: {str(e)}"

            # Establecer el nombre manualmente
            dynamic_tool.name = common_tool.name
            return dynamic_tool

        except Exception as e:
            self.logger.error(f"Error convirtiendo herramienta {common_tool.name}: {e}")
            return None

    def _create_system_message(self) -> SystemMessage:
        """Crea el SystemMessage usando la configuración del AgentConfig"""
        # Usar system_prompt de la configuración
        system_content = self.config.system_prompt

        # Agregar context_instructions si existen
        if self.config.context_instructions:
            system_content += f"\\n\\n{self.config.context_instructions}"

        # Agregar prompts adicionales activos (CRÍTICO: Esto faltaba!)
        additional_prompts = self._load_additional_prompts()
        if additional_prompts:
            system_content += f"\\n\\n{additional_prompts}"

        # Agregar contenido de archivos de contexto
        context_content = self._load_context_files_content()
        if context_content:
            system_content += f"\\n\\n{context_content}"

        # Agregar información de herramientas disponibles (como en agentes actuales)
        if self.tools:
            tools_info = "\\n\\nHERRAMIENTAS DISPONIBLES:\\n"
            for tool in self.tools:
                tools_info += f"- {tool.name}: {tool.description}\\n"
            system_content += tools_info

        return SystemMessage(content=system_content)

    def _load_additional_prompts(self) -> str:
        """Carga todos los prompts adicionales activos (instructions, constraints, examples, etc.)"""
        try:
            from apps.chat.models import AgentPrompt

            # Obtener prompts activos ordenados por tipo y fecha de creación
            prompts = AgentPrompt.objects.filter(
                agent_config=self.config,
                is_active=True
            ).order_by('prompt_type', 'created_at')

            if not prompts.exists():
                return ""

            # Organizar prompts por tipo para mejor estructura
            prompt_sections = []

            # Mapeo de tipos a títulos legibles
            type_titles = {
                'instruction': 'INSTRUCCIONES ADICIONALES',
                'constraint': 'RESTRICCIONES IMPORTANTES',
                'example': 'EJEMPLOS DE COMPORTAMIENTO',
                'template': 'PLANTILLAS DE RESPUESTA',
                'fallback': 'RESPUESTAS DE RESPALDO',
                'knowledge': 'CONOCIMIENTO ESPECÍFICO'
            }

            # Agrupar por tipo
            current_type = None
            for prompt in prompts:
                if prompt.prompt_type != current_type:
                    current_type = prompt.prompt_type
                    title = type_titles.get(current_type, current_type.upper())
                    prompt_sections.append(f"\\n{title}:")
                    prompt_sections.append("=" * len(title))

                # Agregar contenido del prompt
                prompt_sections.append(f"\\n{prompt.content}")

            return "\\n".join(prompt_sections)

        except Exception as e:
            self.logger.error(f"Error cargando prompts adicionales: {e}")
            return ""

    def _load_context_files_content(self) -> str:
        """Carga el contenido de todos los archivos de contexto activos para este agente"""
        try:
            from apps.chat.models import AgentContextAssignment

            # Obtener asignaciones activas ordenadas por prioridad
            assignments = AgentContextAssignment.objects.filter(
                agent_config=self.config,
                is_active=True,
                context_file__status='processed'
            ).select_related('context_file').order_by('-priority', '-created_at')

            if not assignments.exists():
                return ""

            context_sections = []
            context_sections.append("CONTEXTO ADICIONAL:")
            context_sections.append("=" * 50)

            for assignment in assignments:
                context_file = assignment.context_file

                # Agregar información del archivo
                file_header = f"\\n📄 ARCHIVO: {context_file.name} ({context_file.file_type.upper()})"
                if context_file.description:
                    file_header += f"\\n📝 DESCRIPCIÓN: {context_file.description}"

                if assignment.context_instructions:
                    file_header += f"\\n🔍 INSTRUCCIONES: {assignment.context_instructions}"

                context_sections.append(file_header)
                context_sections.append("-" * 40)

                # Agregar contenido del archivo
                if context_file.extracted_content:
                    # Limitar contenido para evitar tokens excesivos
                    content = context_file.extracted_content
                    if len(content) > 3000:  # Limitar a ~3000 caracteres por archivo
                        content = content[:3000] + "\\n... [contenido truncado]"

                    context_sections.append(content)
                    context_sections.append("")  # Línea en blanco entre archivos

                self.logger.info(f"📎 Archivo de contexto cargado: {context_file.name}")

            return "\\n".join(context_sections)

        except Exception as e:
            self.logger.error(f"Error cargando archivos de contexto: {e}")
            return ""

    def run(self, state: AgentState) -> Dict:
        """
        Método principal que replica exactamente el comportamiento de DTEAgent.run()
        """
        try:
            # Establecer contexto del usuario desde metadata (igual que agentes actuales)
            metadata = state.get("metadata", {})
            user_id = metadata.get("user_id")

            # Si hay herramientas que requieren contexto de usuario, establecerlo
            self._set_user_context_if_needed(user_id, metadata)

            # Crear mensaje del sistema usando configuración de BD
            system_message = self._create_system_message()

            # Preparar mensajes incluyendo el contexto del sistema
            messages = [system_message] + state["messages"]

            if self.agent:
                # Usar agente React con herramientas (igual que sistema actual)
                response = self.agent.invoke({"messages": messages})

                # Extraer el último mensaje de respuesta (misma lógica que agentes actuales)
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
                # Si no hay herramientas, respuesta directa del LLM
                response = self.llm.invoke(messages)
                return {
                    "messages": [response],
                    "next_agent": "supervisor"
                }

        except Exception as e:
            # Manejo de errores igual que agentes actuales
            import traceback
            self.logger.error(f"Error in DynamicLangChainAgent {self.config.name}: {e}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            error_message = AIMessage(
                content=f"Hubo un error al procesar tu consulta con el agente {self.config.name}: {str(e)}"
            )
            return {
                "messages": [error_message],
                "next_agent": "supervisor"
            }

    def _set_user_context_if_needed(self, user_id, metadata):
        """Establece contexto de usuario para herramientas que lo necesiten"""
        try:
            # Buscar si hay herramientas que requieren contexto de usuario
            # (como las herramientas de DTE que usan set_user_context)
            for assignment in self.config.tool_assignments.filter(is_enabled=True):
                function_path = assignment.common_tool.function_path

                # Si es una herramienta que necesita contexto de usuario
                if 'tools_context' in function_path:
                    try:
                        # Importar set_user_context si existe
                        module_path = function_path.rsplit('.', 1)[0]
                        module = importlib.import_module(module_path)
                        if hasattr(module, 'set_user_context'):
                            set_user_context = getattr(module, 'set_user_context')
                            set_user_context(user_id, metadata)
                            break
                    except:
                        pass  # Si no se puede establecer contexto, continuar
        except Exception as e:
            self.logger.warning(f"No se pudo establecer contexto de usuario: {e}")

    def get_config_summary(self) -> Dict[str, Any]:
        """Retorna resumen de la configuración del agente"""
        return {
            "agent_id": self.config.id,
            "name": self.config.name,
            "agent_type": self.config.agent_type,
            "model_name": self.config.model_name,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "tools_count": len(self.tools),
            "status": self.config.status,
            "created_at": self.config.created_at.isoformat() if self.config.created_at else None
        }


def create_dynamic_agent(agent_config_id: int) -> DynamicLangChainAgent:
    """Factory function para crear agentes dinámicos desde AgentConfig"""
    return DynamicLangChainAgent(agent_config_id)