"""
Sistema de búsqueda vectorial simplificado para FAQs del SII
Versión simplificada que usa el retriever básico como fallback
"""

import logging
from typing import Dict, Any, List, Optional
from .faq_retriever import get_faq_retriever

logger = logging.getLogger(__name__)


class EnhancedVectorialSystem:
    """
    Sistema de búsqueda vectorial simplificado que usa el retriever básico
    """

    def __init__(self):
        self.retriever = get_faq_retriever()
        logger.info("EnhancedVectorialSystem iniciado con retriever básico")

    def search(
        self,
        query: str,
        max_results: int = 5,
        category_filter: str = None,
        use_smart_filtering: bool = True,
        enable_reranking: bool = True
    ) -> Dict[str, Any]:
        """
        Búsqueda simplificada usando el retriever básico
        """
        try:
            # Usar el retriever básico con los resultados solicitados
            result = self.retriever.search(query, max_results=max_results)

            # Agregar información de que es una búsqueda simplificada
            if isinstance(result, dict):
                result["search_type"] = "simplified"
                result["enhanced_features"] = "disabled (fallback mode)"

            return result

        except Exception as e:
            logger.error(f"Error en búsqueda simplificada: {e}")
            return {
                "success": False,
                "error": str(e),
                "search_type": "simplified",
                "results": []
            }

    async def asearch(self, *args, **kwargs):
        """Versión async que llama a la versión sync"""
        return self.search(*args, **kwargs)


# Instancia global
_enhanced_system = None


def get_enhanced_vectorial_system():
    """
    Obtiene la instancia del sistema vectorial mejorado (versión simplificada)
    """
    global _enhanced_system
    if _enhanced_system is None:
        _enhanced_system = EnhancedVectorialSystem()
    return _enhanced_system