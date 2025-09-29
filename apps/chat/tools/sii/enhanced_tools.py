"""
Herramientas SII Mejoradas con Búsqueda Vectorial Avanzada

Integra el nuevo sistema de búsqueda vectorial con todas las mejoras:
- Filtrado por metadatos
- Re-ranking con LLM
- Monitorización de calidad
- Búsquedas en batch
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from langchain.tools import tool

from .enhanced_vectorial_search import get_enhanced_vectorial_system

logger = logging.getLogger(__name__)


@tool
async def enhanced_search_sii_faqs(
    query: str,
    max_results: int = 5,
    category_filter: str = None,
    use_smart_filtering: bool = True,
    enable_reranking: bool = True
) -> Dict[str, Any]:
    """
    Busca FAQs del SII con sistema vectorial avanzado

    Args:
        query: Consulta del usuario sobre temas del SII
        max_results: Número máximo de resultados (1-10)
        category_filter: Filtro manual por categoría específica
        use_smart_filtering: Usar filtrado automático inteligente
        enable_reranking: Usar re-ranking con LLM para mejor relevancia

    Returns:
        Dict con resultados, métricas y metadatos de búsqueda
    """
    try:
        system = get_enhanced_vectorial_system()

        # Preparar filtros
        category_list = [category_filter] if category_filter else None

        # Realizar búsqueda avanzada
        search_result = await system.enhanced_search(
            query=query,
            k=max_results,
            use_llm_rerank=enable_reranking,
            auto_filter=use_smart_filtering,
            category_filter=category_list
        )

        # Formatear respuesta para el agente
        formatted_results = []
        for doc in search_result["results"]:
            formatted_results.append({
                "question": doc.metadata.get("question", ""),
                "answer": doc.metadata.get("answer", ""),
                "category": doc.metadata.get("category", ""),
                "subtopic": doc.metadata.get("subtopic", ""),
                "relevance_info": "Resultado re-rankeado por LLM" if search_result.get("reranked") else "Resultado por similitud vectorial"
            })

        return {
            "success": True,
            "results": formatted_results,
            "search_metadata": {
                "total_candidates_found": search_result["total_found"],
                "results_returned": len(formatted_results),
                "categories_used": search_result.get("filtered_by", []),
                "reranking_applied": search_result.get("reranked", False),
                "response_time_seconds": search_result["response_time"],
                "auto_filtering_used": search_result["search_metadata"]["auto_filter_used"]
            },
            "query_processed": query
        }

    except Exception as e:
        logger.error(f"Error en búsqueda avanzada SII: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": [],
            "fallback_message": "Error en búsqueda avanzada, intenta con una consulta más específica"
        }


@tool
async def intelligent_sii_assistant(
    user_question: str,
    context_categories: List[str] = None,
    include_related_topics: bool = True
) -> Dict[str, Any]:
    """
    Asistente SII inteligente que combina búsqueda vectorial con respuesta contextualizada

    Args:
        user_question: Pregunta del usuario sobre tributación chilena
        context_categories: Categorías específicas para enfocar la búsqueda
        include_related_topics: Incluir temas relacionados en la respuesta

    Returns:
        Dict con respuesta completa y contexto adicional
    """
    try:
        system = get_enhanced_vectorial_system()

        # Búsqueda principal con re-ranking
        main_search = await system.enhanced_search(
            query=user_question,
            k=3,
            use_llm_rerank=True,
            auto_filter=True,
            category_filter=context_categories
        )

        # Búsqueda de temas relacionados si está habilitado
        related_results = []
        if include_related_topics and main_search["results"]:
            # Extraer categorías de los resultados principales
            main_categories = list(set([
                doc.metadata.get("category", "")
                for doc in main_search["results"]
                if doc.metadata.get("category")
            ]))

            if main_categories:
                related_search = await system.enhanced_search(
                    query=user_question,
                    k=2,
                    use_llm_rerank=False,
                    auto_filter=False,
                    category_filter=main_categories
                )
                related_results = related_search["results"]

        # Formatear respuesta completa
        main_answers = []
        for doc in main_search["results"]:
            main_answers.append({
                "question": doc.metadata.get("question", ""),
                "answer": doc.metadata.get("answer", ""),
                "category": doc.metadata.get("category", ""),
                "subtopic": doc.metadata.get("subtopic", ""),
                "relevance": "Principal"
            })

        related_answers = []
        for doc in related_results:
            related_answers.append({
                "question": doc.metadata.get("question", ""),
                "answer": doc.metadata.get("answer", ""),
                "category": doc.metadata.get("category", ""),
                "subtopic": doc.metadata.get("subtopic", ""),
                "relevance": "Relacionado"
            })

        return {
            "success": True,
            "user_question": user_question,
            "main_answers": main_answers,
            "related_topics": related_answers,
            "categories_covered": list(set([
                ans["category"] for ans in main_answers + related_answers
                if ans["category"]
            ])),
            "search_performance": {
                "main_search_time": main_search["response_time"],
                "total_faqs_analyzed": main_search["total_found"],
                "intelligent_filtering_used": main_search["search_metadata"]["auto_filter_used"]
            },
            "recommendations": {
                "follow_up_questions": _generate_follow_up_questions(main_answers),
                "related_categories": list(set([ans["category"] for ans in related_answers]))
            }
        }

    except Exception as e:
        logger.error(f"Error en asistente SII inteligente: {e}")
        return {
            "success": False,
            "error": str(e),
            "fallback_message": "No pude procesar tu consulta. Intenta ser más específico sobre el tema tributario."
        }


@tool
async def batch_sii_queries(
    questions: List[str],
    enable_smart_features: bool = True
) -> Dict[str, Any]:
    """
    Procesa múltiples consultas SII en batch para mayor eficiencia

    Args:
        questions: Lista de preguntas sobre temas del SII
        enable_smart_features: Habilitar filtrado inteligente y re-ranking

    Returns:
        Dict con resultados para cada consulta y métricas agregadas
    """
    try:
        system = get_enhanced_vectorial_system()

        # Procesar consultas en batch
        batch_results = await system.batch_search(
            queries=questions,
            k=3,
            use_llm_rerank=enable_smart_features,
            auto_filter=enable_smart_features
        )

        # Formatear resultados
        formatted_batch = []
        total_response_time = 0
        total_results_found = 0

        for i, result in enumerate(batch_results):
            if "error" not in result:
                formatted_results = []
                for doc in result["results"]:
                    formatted_results.append({
                        "question": doc.metadata.get("question", ""),
                        "answer": doc.metadata.get("answer", ""),
                        "category": doc.metadata.get("category", ""),
                        "subtopic": doc.metadata.get("subtopic", "")
                    })

                formatted_batch.append({
                    "query_index": i,
                    "original_query": questions[i],
                    "results": formatted_results,
                    "categories_found": result.get("filtered_by", []),
                    "response_time": result["response_time"]
                })

                total_response_time += result["response_time"]
                total_results_found += result["total_found"]
            else:
                formatted_batch.append({
                    "query_index": i,
                    "original_query": questions[i],
                    "error": result["error"],
                    "results": []
                })

        return {
            "success": True,
            "batch_results": formatted_batch,
            "batch_statistics": {
                "total_queries": len(questions),
                "successful_queries": len([r for r in batch_results if "error" not in r]),
                "failed_queries": len([r for r in batch_results if "error" in r]),
                "average_response_time": total_response_time / len(questions) if questions else 0,
                "total_faqs_analyzed": total_results_found,
                "smart_features_enabled": enable_smart_features
            },
            "processing_time": sum([r.get("response_time", 0) for r in batch_results if "response_time" in r])
        }

    except Exception as e:
        logger.error(f"Error en batch processing: {e}")
        return {
            "success": False,
            "error": str(e),
            "batch_results": []
        }


@tool
def get_sii_search_analytics() -> Dict[str, Any]:
    """
    Obtiene análisis y métricas del sistema de búsqueda SII

    Returns:
        Dict con estadísticas completas del sistema de búsqueda
    """
    try:
        system = get_enhanced_vectorial_system()
        metrics = system.get_search_metrics()

        return {
            "success": True,
            "system_analytics": {
                "performance_metrics": {
                    "total_queries_processed": metrics["total_queries"],
                    "average_response_time": metrics["avg_response_time"],
                    "queries_with_filtering": metrics["filtered_vs_unfiltered"]["filtered"],
                    "queries_without_filtering": metrics["filtered_vs_unfiltered"]["unfiltered"]
                },
                "content_metrics": {
                    "total_faqs_available": metrics["vectorstore_stats"]["total_documents"],
                    "embedding_dimensions": metrics["vectorstore_stats"]["embedding_dimension"],
                    "categories_supported": metrics["categories_available"]
                },
                "usage_patterns": {
                    "most_queried_categories": dict(sorted(
                        metrics["category_distribution"].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]),
                    "average_user_satisfaction": metrics["avg_user_rating"],
                    "total_feedback_entries": len(metrics.get("last_feedback", []))
                },
                "system_health": {
                    "cache_status": metrics["cache_status"],
                    "last_updated": metrics["last_updated"]
                }
            }
        }

    except Exception as e:
        logger.error(f"Error obteniendo analytics: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "No se pudieron obtener las métricas del sistema"
        }


@tool
def provide_search_feedback(
    original_query: str,
    relevance_rating: float,
    feedback_comments: str = ""
) -> Dict[str, Any]:
    """
    Permite proporcionar feedback sobre la calidad de las búsquedas

    Args:
        original_query: La consulta original realizada
        relevance_rating: Puntuación de relevancia (1.0 = muy mala, 5.0 = excelente)
        feedback_comments: Comentarios adicionales sobre la búsqueda

    Returns:
        Dict confirmando el registro del feedback
    """
    try:
        system = get_enhanced_vectorial_system()

        # Validar rating
        if not (1.0 <= relevance_rating <= 5.0):
            return {
                "success": False,
                "error": "El rating debe estar entre 1.0 y 5.0"
            }

        # Registrar feedback
        system.provide_feedback(
            query=original_query,
            relevance_score=relevance_rating,
            comments=feedback_comments
        )

        return {
            "success": True,
            "message": "Feedback registrado exitosamente",
            "feedback_summary": {
                "query": original_query[:100],
                "rating": relevance_rating,
                "has_comments": bool(feedback_comments.strip())
            }
        }

    except Exception as e:
        logger.error(f"Error registrando feedback: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _generate_follow_up_questions(main_answers: List[Dict[str, Any]]) -> List[str]:
    """Genera preguntas de seguimiento basadas en las respuestas principales"""
    follow_ups = []
    categories_seen = set()

    for answer in main_answers:
        category = answer.get("category", "")
        if category and category not in categories_seen:
            categories_seen.add(category)

            # Generar pregunta de seguimiento basada en la categoría
            if "certificado" in category.lower():
                follow_ups.append("¿Cómo renuevo mi certificado digital?")
            elif "factura" in category.lower():
                follow_ups.append("¿Qué hacer si hay errores en una factura electrónica?")
            elif "formulario 29" in category.lower() or "iva" in category.lower():
                follow_ups.append("¿Cuáles son las fechas de vencimiento del F29?")
            elif "renta" in category.lower():
                follow_ups.append("¿Cómo calcular el impuesto a la renta?")
            elif "inicio" in category.lower():
                follow_ups.append("¿Qué documentos necesito para iniciar actividades?")

    return follow_ups[:3]  # Máximo 3 preguntas de seguimiento