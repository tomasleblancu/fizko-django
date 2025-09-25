"""
Herramientas optimizadas para SII con sistema de recuperación mejorado
"""
import logging
from typing import Dict, Any, Optional
from langchain_core.tools import tool
from .optimized_faq_retriever import get_optimized_faq_retriever

logger = logging.getLogger(__name__)


@tool
def search_sii_faqs_optimized(
    query: str,
    max_results: int = 3
) -> Dict[str, Any]:
    """
    Busca en las preguntas frecuentes oficiales del SII usando sistema optimizado con:
    - Carga incremental de documentos
    - Cache de embeddings
    - Persistencia de índice FAISS
    - Monitorización de performance

    Args:
        query: Pregunta o consulta sobre temas del SII
        max_results: Máximo número de FAQs a retornar (default: 3)

    Returns:
        Dict con FAQs relevantes y estadísticas de performance
    """
    try:
        retriever = get_optimized_faq_retriever()
        result = retriever.search_faqs(query, max_results)

        # Agregar información de optimización al resultado
        if result.get('success'):
            result['optimization_info'] = {
                'system_type': 'optimized_faiss',
                'cache_enabled': True,
                'incremental_loading': True,
                'persistent_index': True
            }

        return result

    except Exception as e:
        logger.error(f"Error en search_sii_faqs_optimized: {e}")
        return {
            'success': False,
            'query': query,
            'error': str(e),
            'results': []
        }


@tool
def ask_sii_question_optimized(question: str) -> Dict[str, Any]:
    """
    Hace una pregunta específica al sistema optimizado de FAQs del SII.

    Utiliza RetrievalQA chain con vectorstore FAISS optimizado para generar
    respuestas contextualizadas basadas en los FAQs oficiales.

    Args:
        question: Pregunta específica sobre el SII

    Returns:
        Dict con respuesta generada, documentos fuente y estadísticas
    """
    try:
        retriever = get_optimized_faq_retriever()
        result = retriever.ask_question(question)

        # Agregar información del sistema
        if result.get('success'):
            result['optimization_info'] = {
                'system_type': 'optimized_qa_chain',
                'retrieval_method': 'faiss_similarity',
                'response_quality': 'enhanced'
            }

        return result

    except Exception as e:
        logger.error(f"Error en ask_sii_question_optimized: {e}")
        return {
            'success': False,
            'error': str(e),
            'answer': ''
        }


@tool
def get_sii_faq_categories_optimized() -> Dict[str, Any]:
    """
    Obtiene todas las categorías y subtemas disponibles en los FAQs del SII
    usando el sistema optimizado.

    Returns:
        Dict con categorías organizadas, estadísticas y performance info
    """
    try:
        retriever = get_optimized_faq_retriever()
        result = retriever.get_categories()

        # Agregar información del sistema optimizado
        if result.get('success'):
            result['optimization_info'] = {
                'system_type': 'optimized_categories',
                'data_source': 'vectorstore_metadata',
                'real_time': True
            }

        return result

    except Exception as e:
        logger.error(f"Error obteniendo categorías optimizadas: {e}")
        return {
            'success': False,
            'error': str(e),
            'categories': {}
        }


@tool
def search_sii_faqs_by_category_optimized(
    category: str,
    subtopic: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Busca FAQs del SII por categoría específica usando el sistema optimizado.

    Args:
        category: Categoría de FAQs (ej: "Certificado Digital")
        subtopic: Subtema opcional dentro de la categoría
        limit: Máximo número de FAQs a retornar

    Returns:
        Dict con FAQs filtrados de la categoría especificada
    """
    try:
        # Construir query optimizada
        search_query = f"categoría {category}"
        if subtopic:
            search_query += f" subtema {subtopic}"

        retriever = get_optimized_faq_retriever()
        search_results = retriever.search_faqs(search_query, limit)

        if not search_results.get('success'):
            return search_results

        # Filtrar resultados por categoría con mayor precisión
        filtered_results = []
        for faq in search_results.get('results', []):
            category_match = category.lower() in faq.get('category', '').lower()
            subtopic_match = (not subtopic or
                            subtopic.lower() in faq.get('subtopic', '').lower())

            if category_match and subtopic_match:
                filtered_results.append(faq)

        return {
            'success': True,
            'category': category,
            'subtopic': subtopic,
            'results': filtered_results[:limit],
            'total_found': len(filtered_results),
            'showing': len(filtered_results[:limit]),
            'optimization_info': {
                'system_type': 'optimized_category_search',
                'filtering_method': 'vector_similarity + metadata',
                'precision': 'high'
            },
            'stats': search_results.get('stats', {})
        }

    except Exception as e:
        logger.error(f"Error buscando por categoría optimizada: {e}")
        return {
            'success': False,
            'error': str(e),
            'results': []
        }


@tool
def get_sii_system_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas detalladas del sistema optimizado de FAQs del SII.

    Útil para monitorización, debugging y análisis de performance.

    Returns:
        Dict con estadísticas completas del sistema
    """
    try:
        retriever = get_optimized_faq_retriever()
        stats = retriever.get_performance_stats()

        return {
            'success': True,
            'system_stats': stats,
            'optimization_features': {
                'incremental_loading': True,
                'embedding_cache': True,
                'faiss_persistence': True,
                'batch_processing': True,
                'hash_based_change_detection': True
            },
            'performance_benefits': {
                'faster_startup': 'Documents only processed when changed',
                'reduced_api_calls': 'Embeddings cached and reused',
                'persistent_index': 'FAISS index saved/loaded from disk',
                'memory_efficient': 'Incremental updates instead of full reload'
            }
        }

    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del sistema: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@tool
def refresh_sii_faqs_optimized() -> Dict[str, Any]:
    """
    Fuerza actualización completa del sistema de FAQs del SII.

    Útil cuando se detectan problemas o se quiere forzar recarga completa.

    Returns:
        Dict con resultado de la actualización
    """
    try:
        retriever = get_optimized_faq_retriever()
        retriever.force_refresh()

        # Obtener estadísticas después de la actualización
        stats = retriever.get_performance_stats()

        return {
            'success': True,
            'message': 'Sistema de FAQs actualizado completamente',
            'stats_after_refresh': stats,
            'actions_performed': [
                'Cache de metadatos limpiado',
                'Índice FAISS reconstruido',
                'Documentos reprocesados',
                'QA Chain reinicializada'
            ]
        }

    except Exception as e:
        logger.error(f"Error en actualización forzada: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': 'Falló la actualización del sistema'
        }