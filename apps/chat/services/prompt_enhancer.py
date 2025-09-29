"""
Servicio para perfeccionar prompts usando IA
"""
import logging
from typing import Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


class PromptEnhancer:
    """
    Servicio que usa IA para mejorar y perfeccionar prompts de agentes
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",  # Usar el mejor modelo para esta tarea
            temperature=0.3,  # Un poco de creatividad pero controlada
            openai_api_key=settings.OPENAI_API_KEY
        ) if hasattr(settings, 'OPENAI_API_KEY') else None

    def enhance_prompt(
        self,
        original_content: str,
        prompt_type: str = 'system',
        agent_type: str = 'general',
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, str]:
        """
        Perfecciona un prompt usando IA

        Args:
            original_content: Contenido original del prompt
            prompt_type: Tipo de prompt (system, instruction, example, context)
            agent_type: Tipo de agente (dte, sii, general, etc.)
            context: Contexto adicional sobre el agente y su propósito

        Returns:
            Tuple[bool, str, str]: (success, enhanced_content, explanation)
        """
        if not self.llm:
            return False, original_content, "OpenAI API no está configurada"

        try:
            # Construir prompt de perfeccionamiento específico según el tipo
            enhancement_prompt = self._build_enhancement_prompt(
                original_content, prompt_type, agent_type, context
            )

            logger.info(f"Perfeccionando prompt de tipo '{prompt_type}' para agente '{agent_type}'")

            # Llamar a la IA
            response = self.llm.invoke([
                {"role": "user", "content": enhancement_prompt}
            ])

            enhanced_content = response.content.strip()

            # Extraer contenido mejorado y explicación
            if "PROMPT MEJORADO:" in enhanced_content and "EXPLICACIÓN:" in enhanced_content:
                parts = enhanced_content.split("EXPLICACIÓN:")
                improved_prompt = parts[0].replace("PROMPT MEJORADO:", "").strip()
                explanation = parts[1].strip() if len(parts) > 1 else "Prompt mejorado exitosamente"
            else:
                # Si no sigue el formato esperado, usar toda la respuesta como prompt mejorado
                improved_prompt = enhanced_content
                explanation = "Prompt perfeccionado usando IA"

            logger.info("Prompt perfeccionado exitosamente")
            return True, improved_prompt, explanation

        except Exception as e:
            logger.error(f"Error perfeccionando prompt: {e}")
            return False, original_content, f"Error perfeccionando prompt: {str(e)}"

    def _build_enhancement_prompt(
        self,
        original_content: str,
        prompt_type: str,
        agent_type: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Construye el prompt de perfeccionamiento según el tipo y contexto
        """
        # Información base sobre tipos de agente
        agent_descriptions = {
            'dte': 'especializado en Documentos Tributarios Electrónicos chilenos (facturas, boletas, notas de crédito/débito)',
            'sii': 'especializado en servicios del Servicio de Impuestos Internos de Chile, información tributaria y contabilidad',
            'general': 'asistente general que maneja consultas diversas con enfoque en el mercado chileno',
            'support': 'agente de soporte técnico que ayuda a usuarios con problemas y consultas',
            'sales': 'agente de ventas que ayuda con consultas comerciales y promoción de productos'
        }

        agent_description = agent_descriptions.get(agent_type, 'asistente de propósito general')

        # Información sobre tipos de prompt
        prompt_type_guidance = {
            'system_prompt': 'Define la personalidad, rol y comportamiento fundamental del agente de IA',
            'context_instructions': 'Proporciona instrucciones específicas sobre contexto y situaciones particulares',
            'instruction': 'Proporciona directivas específicas sobre cómo debe comportarse el agente en situaciones particulares',
            'example': 'Muestra casos de uso y respuestas modelo para que el agente aprenda interacciones ideales',
            'constraint': 'Define límites y reglas estrictas sobre lo que el agente NO debe hacer o decir',
            'template': 'Crea formatos de respuesta reutilizables con {variables} para datos dinámicos',
            'fallback': 'Define respuestas de seguridad cuando algo falla o no se entiende la consulta',
            'knowledge': 'Proporciona información especializada del dominio o contexto específico del negocio'
        }

        type_guidance = prompt_type_guidance.get(prompt_type, 'prompt genérico')

        # Contexto adicional si está disponible
        context_info = ""
        if context:
            if context.get('agent_name'):
                context_info += f"- Nombre del agente: {context['agent_name']}\n"
            if context.get('agent_description'):
                context_info += f"- Descripción: {context['agent_description']}\n"
            if context.get('specific_requirements'):
                context_info += f"- Requisitos específicos: {context['specific_requirements']}\n"

        # Instrucciones específicas por tipo de prompt
        type_specific_instructions = {
            'system_prompt': """
- Mejora la definición del rol y personalidad ya establecidos
- Clarifica el tono y estilo de comunicación descrito por el usuario
- Reorganiza las capacidades y limitaciones ya mencionadas
- Estructura mejor las reglas de comportamiento existentes
- Mejora la redacción de los objetivos ya definidos""",
            'context_instructions': """
- Reorganiza las instrucciones contextuales ya proporcionadas
- Clarifica las situaciones específicas ya mencionadas
- Mejora la estructura de las condiciones ya establecidas
- Ajusta la redacción de los procedimientos ya descritos
- Organiza mejor las excepciones contextuales ya listadas""",
            'instruction': """
- Reorganiza las instrucciones existentes en orden lógico
- Convierte frases en imperativos claros solo si ya están implícitos
- Mejora la claridad de las condiciones que ya están escritas
- Estructura mejor las excepciones mencionadas por el usuario""",
            'example': """
- Mejora la estructura de los ejemplos ya proporcionados
- Clarifica los diálogos existentes sin agregar nuevos
- Reorganiza las variaciones ya mencionadas
- Mejora la redacción de las prácticas ya descritas""",
            'constraint': """
- Reorganiza las prohibiciones ya listadas para mayor claridad
- Mejora la redacción de las consecuencias ya mencionadas
- Clarifica los límites ya establecidos por el usuario
- Estructura mejor las alternativas ya proporcionadas""",
            'template': """
- Organiza mejor el formato de variables ya definidas
- Clarifica las instrucciones de uso ya escritas
- Mejora la definición de variables existentes
- Reestructura los ejemplos ya proporcionados por el usuario""",
            'fallback': """
- Reorganiza los tipos de errores ya mencionados
- Mejora la redacción de los pasos ya descritos
- Ajusta el tono manteniendo el mensaje original
- Estructura mejor las alternativas ya listadas""",
            'knowledge': """
- Reorganiza la información ya proporcionada en orden lógico
- Mejora la estructura del contenido existente
- Clarifica las referencias ya mencionadas
- Organiza mejor para consulta sin agregar datos nuevos"""
        }

        specific_instructions = type_specific_instructions.get(prompt_type, "")

        return f"""Mejora este prompt de tipo "{prompt_type}" para un agente {agent_type} ({agent_description}).

TIPO DE PROMPT: {prompt_type.upper()}
Propósito: {type_guidance}

PROMPT ORIGINAL:
{original_content}

CONTEXTO DEL AGENTE:
{context_info if context_info else "- Agente especializado en el mercado chileno"}

INSTRUCCIONES GENERALES:
- SOLO mejora y reordena el contenido que ya escribió el usuario
- NO agregues información nueva, ejemplos adicionales o conocimientos externos
- Mantén EXACTAMENTE la misma intención y alcance original
- Mejora la claridad y estructura del texto existente
- Corrige gramática, ortografía y fluidez del texto
- Reorganiza oraciones para mejor comprensión
- NO uses formato markdown, emojis ni símbolos especiales
- NO agregues títulos con ### o **
- Escribe de forma directa y simple
- IMPORTANTE: Solo retoca lo que YA está escrito

INSTRUCCIONES ESPECÍFICAS PARA TIPO "{prompt_type.upper()}":
{specific_instructions}

RECORDATORIO IMPORTANTE:
Tu trabajo es ÚNICAMENTE retocar, reorganizar y clarificar lo que el usuario ya escribió.
NO inventes, agregues o expandas el contenido. Solo mejora la redacción y estructura existente.

FORMATO DE RESPUESTA:
PROMPT MEJORADO:
[Prompt perfeccionado aquí - sin formato especial - SOLO contenido retocado del original]

EXPLICACIÓN:
[Explica qué reorganizaste, clarificaste o mejoraste del texto original - sin formato especial]"""

    def suggest_prompt_improvements(self, agent_type: str, current_prompts: list) -> Dict[str, Any]:
        """
        Sugiere mejoras generales para el conjunto de prompts de un agente
        """
        if not self.llm:
            return {'success': False, 'message': 'OpenAI API no está configurada'}

        try:
            analysis_prompt = f"""Analiza el siguiente conjunto de prompts para un agente de tipo '{agent_type}' y sugiere mejoras:

PROMPTS ACTUALES:
{chr(10).join([f"- {p.get('type', 'unknown')}: {p.get('content', '')[:100]}..." for p in current_prompts])}

Proporciona:
1. Análisis de coherencia entre prompts
2. Identificación de gaps o redundancias
3. Sugerencias específicas de mejora
4. Recomendaciones de prompts adicionales que podrían ser útiles

Responde en formato JSON con las claves: analysis, gaps, suggestions, recommendations"""

            response = self.llm.invoke([
                {"role": "user", "content": analysis_prompt}
            ])

            return {
                'success': True,
                'analysis': response.content,
                'agent_type': agent_type
            }

        except Exception as e:
            logger.error(f"Error analizando prompts: {e}")
            return {
                'success': False,
                'message': f"Error analizando prompts: {str(e)}"
            }


# Función helper para usar desde views
def enhance_prompt_content(
    content: str,
    prompt_type: str = 'system',
    agent_type: str = 'general',
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Helper function para perfeccionar un prompt desde las vistas
    """
    enhancer = PromptEnhancer()
    success, enhanced_content, explanation = enhancer.enhance_prompt(
        content, prompt_type, agent_type, context
    )

    return {
        'success': success,
        'original_content': content,
        'enhanced_content': enhanced_content,
        'explanation': explanation,
        'improvement_percentage': _calculate_improvement_score(content, enhanced_content) if success else 0
    }


def _calculate_improvement_score(original: str, enhanced: str) -> int:
    """
    Calcula un score aproximado de mejora basado en longitud y estructura
    """
    try:
        # Factores de mejora simples
        length_factor = min(len(enhanced) / max(len(original), 1), 2.0)  # Max 2x
        structure_factor = 1.0

        # Detectar mejoras estructurales
        if '###' in enhanced or '**' in enhanced or len(enhanced.split('\n')) > len(original.split('\n')):
            structure_factor = 1.2

        # Detectar especificidad (palabras técnicas)
        technical_words = ['específicamente', 'debe', 'siempre', 'nunca', 'formato', 'ejemplo']
        enhanced_technical = sum(1 for word in technical_words if word in enhanced.lower())
        original_technical = sum(1 for word in technical_words if word in original.lower())

        specificity_factor = 1.0 + (enhanced_technical - original_technical) * 0.1

        # Score final (0-100)
        improvement_score = min(int((length_factor * structure_factor * specificity_factor - 1) * 100), 100)
        return max(improvement_score, 5)  # Mínimo 5% si hay algún cambio

    except Exception:
        return 15  # Score por defecto