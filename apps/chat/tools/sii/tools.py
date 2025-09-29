"""
Herramientas especializadas para SII con sistema de recuperación optimizado
"""
import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from .faq_retriever import get_faq_retriever

logger = logging.getLogger(__name__)


@tool
def search_sii_faqs(
    query: str,
    max_results: int = 3
) -> Dict[str, Any]:
    """
    Busca en las preguntas frecuentes oficiales del SII usando búsqueda vectorizada FAISS.

    Args:
        query: Pregunta o consulta sobre temas del SII
        max_results: Máximo número de FAQs a retornar (default: 3)

    Returns:
        Dict con FAQs relevantes encontradas
    """
    try:
        retriever = get_faq_retriever()
        return retriever.search_faqs(query, max_results)

    except Exception as e:
        logger.error(f"Error en search_sii_faqs: {e}")
        return {
            'success': False,
            'query': query,
            'error': str(e),
            'results': []
        }


@tool
def get_sii_faq_categories() -> Dict[str, Any]:
    """
    Obtiene todas las categorías y subtemas disponibles en los FAQs del SII.

    Returns:
        Dict con categorías organizadas por subtemas
    """
    try:
        retriever = get_faq_retriever()
        return retriever.get_categories()

    except Exception as e:
        logger.error(f"Error obteniendo categorías: {e}")
        return {
            'success': False,
            'error': str(e),
            'categories': {}
        }


@tool
def search_sii_faqs_by_category(
    category: str,
    subtopic: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Busca FAQs del SII por categoría específica usando el sistema de recuperación optimizado.

    Args:
        category: Categoría de FAQs (ej: "Certificado Digital")
        subtopic: Subtema opcional dentro de la categoría
        limit: Máximo número de FAQs a retornar

    Returns:
        Dict con FAQs de la categoría especificada
    """
    try:
        # Construir query de búsqueda basada en categoría y subtema
        search_query = f"categoría {category}"
        if subtopic:
            search_query += f" subtema {subtopic}"

        retriever = get_faq_retriever()

        # Usar búsqueda vectorizada para encontrar FAQs relevantes
        search_results = retriever.search_faqs(search_query, limit)

        if not search_results.get('success'):
            return search_results

        # Filtrar resultados que realmente coincidan con la categoría
        filtered_results = []
        for faq in search_results.get('results', []):
            if category.lower() in faq.get('category', '').lower():
                if not subtopic or subtopic.lower() in faq.get('subtopic', '').lower():
                    filtered_results.append(faq)

        return {
            'success': True,
            'category': category,
            'subtopic': subtopic,
            'results': filtered_results[:limit],
            'total_found': len(filtered_results),
            'showing': len(filtered_results[:limit])
        }

    except Exception as e:
        logger.error(f"Error buscando por categoría: {e}")
        return {
            'success': False,
            'error': str(e),
            'results': []
        }


@tool
def ask_sii_question(question: str) -> Dict[str, Any]:
    """
    Hace una pregunta específica al sistema de FAQs del SII usando cadena QA con retrieval.

    Esta herramienta genera respuestas contextualizada basada en los FAQs oficiales del SII.

    Args:
        question: Pregunta específica sobre el SII

    Returns:
        Dict con respuesta generada y documentos fuente
    """
    try:
        retriever = get_faq_retriever()
        return retriever.ask_question(question)

    except Exception as e:
        logger.error(f"Error en ask_sii_question: {e}")
        return {
            'success': False,
            'error': str(e),
            'answer': ''
        }