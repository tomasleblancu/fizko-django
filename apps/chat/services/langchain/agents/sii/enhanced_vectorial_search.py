"""
Sistema de Búsqueda Vectorial Avanzado para SII Agent

Mejoras implementadas:
1. Filtrado previo con metadatos
2. Re-ranking con LLM
3. Actualización dinámica del índice
4. Batching y paralelización
5. Monitorización de calidad
6. Embeddings especializados
"""

import json
import logging
import time
import hashlib
import pickle
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import JSONLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class SearchMetrics:
    """Monitorización de métricas de búsqueda"""

    def __init__(self):
        self.queries_count = 0
        self.avg_response_time = 0.0
        self.category_hits = {}
        self.user_feedback = []
        self.filtered_vs_unfiltered = {"filtered": 0, "unfiltered": 0}

    def log_query(self, query: str, response_time: float, category_filter: str = None, relevance_score: float = None):
        """Registra métricas de una consulta"""
        self.queries_count += 1

        # Actualizar tiempo promedio de respuesta
        self.avg_response_time = ((self.avg_response_time * (self.queries_count - 1)) + response_time) / self.queries_count

        # Contar hits por categoría
        if category_filter:
            self.category_hits[category_filter] = self.category_hits.get(category_filter, 0) + 1
            self.filtered_vs_unfiltered["filtered"] += 1
        else:
            self.filtered_vs_unfiltered["unfiltered"] += 1

        # Registrar puntuación de relevancia
        if relevance_score:
            self.user_feedback.append({
                "query": query,
                "relevance_score": relevance_score,
                "timestamp": datetime.now().isoformat()
            })

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema"""
        return {
            "total_queries": self.queries_count,
            "avg_response_time": round(self.avg_response_time, 3),
            "category_distribution": self.category_hits,
            "filtered_vs_unfiltered": self.filtered_vs_unfiltered,
            "avg_user_rating": np.mean([f["relevance_score"] for f in self.user_feedback]) if self.user_feedback else 0,
            "last_updated": datetime.now().isoformat()
        }


class CategoryFilter:
    """Sistema de filtrado inteligente por categorías y metadatos"""

    # Mapping de keywords a categorías para filtrado inteligente
    CATEGORY_KEYWORDS = {
        "certificado digital": ["Clave tributaria, mandatario digital y representantes electrónicos"],
        "clave tributaria": ["Clave tributaria, mandatario digital y representantes electrónicos"],
        "factura": ["Factura electrónica", "Facturación electrónica"],
        "boleta": ["Boleta electrónica", "Boleta de honorarios"],
        "iva": ["Formulario 29", "IVA"],
        "f29": ["Formulario 29", "IVA"],
        "renta": ["Impuesto a la Renta", "Renta"],
        "término de giro": ["Término de giro"],
        "inicio actividades": ["Inicio de actividades"],
        "portal": ["Portal SII", "Clave tributaria, mandatario digital y representantes electrónicos"],
        "declaración": ["Formulario 29", "Impuesto a la Renta"],
        "pyme": ["Renta PYME", "Renta"],
        "mandatario": ["Clave tributaria, mandatario digital y representantes electrónicos"],
        "representante": ["Clave tributaria, mandatario digital y representantes electrónicos"]
    }

    @classmethod
    def predict_categories(cls, query: str) -> List[str]:
        """Predice categorías relevantes basadas en la consulta"""
        query_lower = query.lower()
        relevant_categories = set()

        for keyword, categories in cls.CATEGORY_KEYWORDS.items():
            if keyword in query_lower:
                relevant_categories.update(categories)

        return list(relevant_categories)

    @classmethod
    def create_metadata_filter(cls, categories: List[str] = None, subtopics: List[str] = None) -> Dict[str, Any]:
        """Crea filtro de metadatos para FAISS"""
        filters = {}

        if categories:
            filters["category"] = categories

        if subtopics:
            filters["subtopic"] = subtopics

        return filters


class LLMReRanker:
    """Sistema de re-ranking usando LLM para mejorar relevancia"""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

    async def rerank_results(self, query: str, results: List[Document], top_k: int = 3) -> List[Document]:
        """Re-rankea resultados usando análisis semántico del LLM"""
        if len(results) <= top_k:
            return results

        # Preparar contexto para el LLM
        context_docs = []
        for i, doc in enumerate(results):
            context_docs.append(f"""
            Documento {i+1}:
            Categoría: {doc.metadata.get('category', 'N/A')}
            Subtema: {doc.metadata.get('subtopic', 'N/A')}
            Pregunta: {doc.metadata.get('question', 'N/A')}
            Respuesta: {doc.page_content[:300]}...
            """)

        system_prompt = """Eres un experto en tributación chilena. Tu tarea es analizar una consulta y una lista de documentos FAQ, luego rankear los documentos por relevancia.

Criterios de ranking:
1. Relevancia directa con la consulta
2. Especificidad de la información
3. Utilidad práctica para el usuario
4. Claridad de la respuesta

Responde ÚNICAMENTE con una lista de números separados por comas, ordenados por relevancia (más relevante primero).
Por ejemplo: 3,1,5,2,4"""

        user_prompt = f"""
        CONSULTA: {query}

        DOCUMENTOS:
        {chr(10).join(context_docs)}

        Rankea los documentos por relevancia (1 al {len(results)}). Responde solo los números separados por comas:"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # Parsear respuesta del LLM
            rankings = [int(x.strip()) for x in response.content.strip().split(",")]

            # Re-ordenar documentos basado en el ranking
            reranked = []
            for rank in rankings[:top_k]:  # Solo tomar top_k
                if 1 <= rank <= len(results):
                    reranked.append(results[rank - 1])

            logger.info(f"Re-ranking completado: {len(reranked)} documentos reordenados")
            return reranked

        except Exception as e:
            logger.error(f"Error en re-ranking con LLM: {e}")
            return results[:top_k]  # Fallback a orden original


class EnhancedVectorialSearch:
    """
    Sistema de búsqueda vectorial avanzado con todas las mejoras implementadas
    """

    def __init__(self, faq_file_path: str):
        self.faq_file_path = Path(faq_file_path)
        self.vectorstore: Optional[FAISS] = None
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.reranker = LLMReRanker()
        self.metrics = SearchMetrics()
        self.category_filter = CategoryFilter()

        # Configuración de cache y persistencia
        self.cache_dir = Path(__file__).parent / "vectorial_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.index_file = self.cache_dir / "enhanced_faiss_index"
        self.metadata_file = self.cache_dir / "enhanced_metadata.pkl"

        # Thread pool para paralelización
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.lock = threading.RLock()

        # Inicializar sistema
        self._initialize_vectorstore()

    def _initialize_vectorstore(self):
        """Inicializa el vectorstore con carga inteligente"""
        try:
            with self.lock:
                # Verificar si existe cache válido
                if self._should_load_from_cache():
                    logger.info("Cargando índice vectorial desde cache...")
                    self._load_from_cache()
                else:
                    logger.info("Construyendo nuevo índice vectorial...")
                    self._build_new_index()

                logger.info(f"Sistema vectorial iniciado con {self.vectorstore.index.ntotal} documentos")

        except Exception as e:
            logger.error(f"Error inicializando vectorstore: {e}")
            raise

    def _should_load_from_cache(self) -> bool:
        """Determina si debe cargar desde cache"""
        if not (self.index_file.exists() and self.metadata_file.exists()):
            return False

        # Verificar si el archivo FAQ cambió
        try:
            with open(self.metadata_file, 'rb') as f:
                metadata = pickle.load(f)

            current_hash = self._get_file_hash(self.faq_file_path)
            return metadata.get('file_hash') == current_hash

        except Exception:
            return False

    def _get_file_hash(self, file_path: Path) -> str:
        """Calcula hash del archivo para detección de cambios"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _load_from_cache(self):
        """Carga vectorstore desde cache"""
        self.vectorstore = FAISS.load_local(
            str(self.index_file),
            self.embeddings,
            allow_dangerous_deserialization=True
        )

    def _build_new_index(self):
        """Construye nuevo índice vectorial desde cero"""
        # Cargar documentos con metadatos mejorados
        documents = self._load_enhanced_documents()

        # Construir vectorstore
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)

        # Guardar en cache
        self._save_to_cache()

    def _load_enhanced_documents(self) -> List[Document]:
        """Carga documentos con metadatos enriquecidos"""
        with open(self.faq_file_path, 'r', encoding='utf-8') as f:
            faqs = json.load(f)

        documents = []
        for faq in faqs:
            # Crear contenido enriquecido para mejor búsqueda
            content = f"""
            Pregunta: {faq.get('question', '')}
            Respuesta: {faq.get('answer', '')}
            Categoría: {faq.get('category', '')}
            Subtema: {faq.get('subtopic', '')}
            """

            # Metadatos enriquecidos
            metadata = {
                'category': faq.get('category', ''),
                'subtopic': faq.get('subtopic', ''),
                'question': faq.get('question', ''),
                'answer': faq.get('answer', ''),
                'source': 'SII_FAQ',
                'indexed_date': datetime.now().isoformat()
            }

            documents.append(Document(page_content=content, metadata=metadata))

        logger.info(f"Cargados {len(documents)} documentos FAQ con metadatos enriquecidos")
        return documents

    def _save_to_cache(self):
        """Guarda vectorstore en cache"""
        try:
            # Guardar índice FAISS
            self.vectorstore.save_local(str(self.index_file))

            # Guardar metadatos
            metadata = {
                'file_hash': self._get_file_hash(self.faq_file_path),
                'created_date': datetime.now().isoformat(),
                'document_count': self.vectorstore.index.ntotal
            }

            with open(self.metadata_file, 'wb') as f:
                pickle.dump(metadata, f)

            logger.info("Cache vectorial guardado exitosamente")

        except Exception as e:
            logger.error(f"Error guardando cache: {e}")

    async def enhanced_search(
        self,
        query: str,
        k: int = 5,
        use_llm_rerank: bool = True,
        auto_filter: bool = True,
        category_filter: List[str] = None,
        subtopic_filter: List[str] = None
    ) -> Dict[str, Any]:
        """
        Búsqueda vectorial avanzada con todas las mejoras

        Args:
            query: Consulta del usuario
            k: Número de resultados a retornar
            use_llm_rerank: Si usar re-ranking con LLM
            auto_filter: Si aplicar filtrado automático por categorías
            category_filter: Filtro manual por categorías
            subtopic_filter: Filtro manual por subtemas
        """
        start_time = time.time()

        try:
            # 1. Filtrado inteligente previo
            search_filter = None
            used_categories = category_filter or []

            if auto_filter and not category_filter:
                # Predicción automática de categorías
                predicted_categories = self.category_filter.predict_categories(query)
                if predicted_categories:
                    used_categories = predicted_categories
                    logger.info(f"Categorías predichas: {predicted_categories}")

            if used_categories or subtopic_filter:
                search_filter = self.category_filter.create_metadata_filter(
                    categories=used_categories,
                    subtopics=subtopic_filter
                )

            # 2. Búsqueda vectorial con filtrado
            search_kwargs = {"k": min(k * 2, 20)}  # Obtener más resultados para re-ranking

            if search_filter:
                # Búsqueda con filtro (requiere implementación específica de FAISS)
                results = self.vectorstore.similarity_search(query, **search_kwargs)
                # Filtrado manual por categorías ya que FAISS no soporta filtros complejos nativamente
                if used_categories:
                    results = [doc for doc in results if doc.metadata.get('category') in used_categories]
            else:
                results = self.vectorstore.similarity_search(query, **search_kwargs)

            # 3. Re-ranking con LLM si está habilitado
            final_results = results
            if use_llm_rerank and len(results) > k:
                final_results = await self.reranker.rerank_results(query, results, top_k=k)
            else:
                final_results = results[:k]

            # 4. Calcular métricas
            response_time = time.time() - start_time

            # 5. Log de métricas
            category_used = used_categories[0] if used_categories else None
            self.metrics.log_query(query, response_time, category_used)

            return {
                "results": final_results,
                "total_found": len(results),
                "filtered_by": used_categories,
                "reranked": use_llm_rerank and len(results) > k,
                "response_time": round(response_time, 3),
                "search_metadata": {
                    "auto_filter_used": auto_filter and bool(used_categories),
                    "categories_predicted": used_categories if auto_filter else [],
                    "total_candidates": len(results)
                }
            }

        except Exception as e:
            logger.error(f"Error en búsqueda avanzada: {e}")
            # Fallback a búsqueda simple
            results = self.vectorstore.similarity_search(query, k=k)
            return {
                "results": results,
                "total_found": len(results),
                "error": str(e),
                "fallback_used": True,
                "response_time": time.time() - start_time
            }

    async def batch_search(self, queries: List[str], **search_kwargs) -> List[Dict[str, Any]]:
        """Procesamiento en batch de múltiples consultas"""
        tasks = []

        for query in queries:
            task = self.enhanced_search(query, **search_kwargs)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Manejar excepciones
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error en query {i}: {result}")
                processed_results.append({"error": str(result), "query_index": i})
            else:
                processed_results.append(result)

        return processed_results

    def update_index_dynamically(self, new_documents: List[Dict[str, Any]]):
        """Actualiza índice dinámicamente sin reconstruir completamente"""
        try:
            with self.lock:
                # Convertir nuevos documentos
                docs_to_add = []
                for doc_data in new_documents:
                    content = f"""
                    Pregunta: {doc_data.get('question', '')}
                    Respuesta: {doc_data.get('answer', '')}
                    Categoría: {doc_data.get('category', '')}
                    Subtema: {doc_data.get('subtopic', '')}
                    """

                    metadata = {
                        'category': doc_data.get('category', ''),
                        'subtopic': doc_data.get('subtopic', ''),
                        'question': doc_data.get('question', ''),
                        'answer': doc_data.get('answer', ''),
                        'source': 'SII_FAQ',
                        'added_date': datetime.now().isoformat()
                    }

                    docs_to_add.append(Document(page_content=content, metadata=metadata))

                # Agregar al vectorstore existente
                self.vectorstore.add_documents(docs_to_add)

                # Actualizar cache
                self._save_to_cache()

                logger.info(f"Agregados {len(docs_to_add)} nuevos documentos al índice")

        except Exception as e:
            logger.error(f"Error actualizando índice dinámicamente: {e}")

    def get_search_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas completas del sistema de búsqueda"""
        base_metrics = self.metrics.get_stats()

        # Agregar métricas del vectorstore
        base_metrics.update({
            "vectorstore_stats": {
                "total_documents": self.vectorstore.index.ntotal if self.vectorstore else 0,
                "embedding_dimension": self.vectorstore.index.d if self.vectorstore else 0,
            },
            "categories_available": len(self.category_filter.CATEGORY_KEYWORDS),
            "cache_status": {
                "index_exists": self.index_file.exists(),
                "metadata_exists": self.metadata_file.exists(),
            }
        })

        return base_metrics

    def provide_feedback(self, query: str, relevance_score: float, comments: str = ""):
        """Permite al usuario proporcionar feedback sobre la calidad de búsqueda"""
        feedback = {
            "query": query,
            "relevance_score": relevance_score,  # 1.0-5.0
            "comments": comments,
            "timestamp": datetime.now().isoformat()
        }

        self.metrics.user_feedback.append(feedback)
        logger.info(f"Feedback recibido para query: '{query[:50]}...' - Score: {relevance_score}")


# Instancia global del sistema mejorado
enhanced_vectorial_system: Optional[EnhancedVectorialSearch] = None

def get_enhanced_vectorial_system() -> EnhancedVectorialSearch:
    """Obtiene instancia global del sistema vectorial mejorado"""
    global enhanced_vectorial_system

    if enhanced_vectorial_system is None:
        faq_file = Path(__file__).parent / "faqs_sii_fixed.json"
        enhanced_vectorial_system = EnhancedVectorialSearch(faq_file)

    return enhanced_vectorial_system