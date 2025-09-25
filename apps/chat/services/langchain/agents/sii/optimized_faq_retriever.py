"""
Sistema de recuperación optimizado para FAQs del SII con:
- Carga incremental
- Cache de embeddings
- Persistencia de índice FAISS
- Batching optimizado
- Monitorización detallada
"""
import os
import json
import hashlib
import pickle
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class OptimizedSIIFAQRetriever:
    """Sistema de recuperación optimizado para FAQs del SII"""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY,
            chunk_size=1000,  # Optimizado para batching
        )
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Paths para persistencia
        self.base_dir = os.path.dirname(__file__)
        self.faiss_index_path = os.path.join(self.base_dir, 'faiss_index')
        self.metadata_cache_path = os.path.join(self.base_dir, 'metadata_cache.pkl')

        # Estado interno
        self.vectorstore = None
        self.qa_chain = None
        self.faqs_loaded = False
        self.document_hashes = set()
        self.last_update = None

        # Estadísticas de optimización
        self.stats = {
            'total_documents': 0,
            'new_documents_processed': 0,
            'cached_embeddings_used': 0,
            'faiss_index_loaded': False,
            'last_optimization_time': None
        }

        # Inicializar sistema
        self._initialize_system()

    def _hash_content(self, content: str) -> str:
        """Genera hash SHA-256 para contenido"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _get_faq_file_path(self) -> str:
        """Obtiene la ruta del archivo de FAQs corregido"""
        fixed_file = os.path.join(self.base_dir, 'faqs_sii_fixed.json')
        original_file = os.path.join(self.base_dir, 'faqs_sii.json')

        if os.path.exists(fixed_file):
            return fixed_file
        return original_file

    def _load_metadata_cache(self) -> Dict[str, Any]:
        """Carga caché de metadatos desde disco"""
        try:
            if os.path.exists(self.metadata_cache_path):
                with open(self.metadata_cache_path, 'rb') as f:
                    metadata = pickle.load(f)
                    logger.info(f"Cache de metadatos cargado: {len(metadata.get('hashes', set()))} documentos")
                    return metadata
        except Exception as e:
            logger.warning(f"Error cargando cache de metadatos: {e}")

        return {
            'hashes': set(),
            'last_file_hash': None,
            'last_update': None,
            'document_count': 0
        }

    def _save_metadata_cache(self, metadata: Dict[str, Any]):
        """Guarda caché de metadatos a disco"""
        try:
            with open(self.metadata_cache_path, 'wb') as f:
                pickle.dump(metadata, f)
            logger.info(f"Cache de metadatos guardado: {len(metadata.get('hashes', set()))} documentos")
        except Exception as e:
            logger.error(f"Error guardando cache de metadatos: {e}")

    def _get_file_hash(self, file_path: str) -> str:
        """Obtiene hash del archivo completo para detectar cambios"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculando hash de archivo: {e}")
            return None

    def _load_existing_vectorstore(self) -> bool:
        """Intenta cargar vectorstore FAISS existente"""
        try:
            if os.path.exists(self.faiss_index_path):
                self.vectorstore = FAISS.load_local(
                    self.faiss_index_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True  # Necesario para FAISS
                )
                logger.info("Índice FAISS cargado desde disco")
                self.stats['faiss_index_loaded'] = True
                return True
        except Exception as e:
            logger.warning(f"No se pudo cargar índice FAISS existente: {e}")

        return False

    def _save_vectorstore(self):
        """Guarda vectorstore FAISS a disco"""
        try:
            if self.vectorstore:
                self.vectorstore.save_local(self.faiss_index_path)
                logger.info("Índice FAISS guardado a disco")
        except Exception as e:
            logger.error(f"Error guardando índice FAISS: {e}")

    def _load_and_process_faqs(self) -> List[Document]:
        """Carga y procesa FAQs con detección de cambios incrementales"""
        faq_file = self._get_faq_file_path()

        if not os.path.exists(faq_file):
            logger.error(f"Archivo de FAQs no encontrado: {faq_file}")
            return []

        # Cargar cache de metadatos
        metadata_cache = self._load_metadata_cache()
        current_file_hash = self._get_file_hash(faq_file)

        # Si el archivo no cambió, no hay nada que hacer
        if (current_file_hash == metadata_cache.get('last_file_hash') and
            self.vectorstore is not None):
            logger.info("Archivo FAQs sin cambios, usando índice existente")
            self.document_hashes = metadata_cache.get('hashes', set())
            self.stats['total_documents'] = metadata_cache.get('document_count', 0)
            return []

        logger.info("Detectados cambios en archivo FAQs, procesando...")

        # Cargar FAQs desde JSON
        try:
            with open(faq_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error cargando JSON: {e}")
            return []

        # Determinar estructura
        if isinstance(data, dict) and 'faqs' in data:
            faqs_data = data['faqs']
        elif isinstance(data, list):
            faqs_data = data
        else:
            logger.error("Estructura de FAQ no reconocida")
            return []

        # Procesar documentos incrementalmente
        new_documents = []
        existing_hashes = metadata_cache.get('hashes', set())
        current_hashes = set()

        for i, faq in enumerate(faqs_data):
            # Crear contenido combinado
            content = f"Pregunta: {faq.get('question', '')}\n\nRespuesta: {faq.get('answer', '')}"
            content_hash = self._hash_content(content)
            current_hashes.add(content_hash)

            # Solo procesar documentos nuevos
            if content_hash not in existing_hashes:
                metadata = {
                    'category': faq.get('category', 'Sin categoría'),
                    'subtopic': faq.get('subtopic', 'Sin subtema'),
                    'question': faq.get('question', ''),
                    'source': 'SII FAQ',
                    'content_hash': content_hash,
                    'document_id': i
                }

                doc = Document(
                    page_content=content,
                    metadata=metadata
                )
                new_documents.append(doc)

        # Actualizar estadísticas
        self.stats['new_documents_processed'] = len(new_documents)
        self.stats['total_documents'] = len(faqs_data)
        self.document_hashes = current_hashes

        # Guardar metadatos actualizados
        updated_metadata = {
            'hashes': current_hashes,
            'last_file_hash': current_file_hash,
            'last_update': datetime.now().isoformat(),
            'document_count': len(faqs_data)
        }
        self._save_metadata_cache(updated_metadata)

        logger.info(f"Procesados {len(new_documents)} documentos nuevos de {len(faqs_data)} totales")
        return new_documents

    def _create_or_update_vectorstore(self, new_documents: List[Document]):
        """Crea o actualiza vectorstore con documentos nuevos"""
        if not new_documents:
            logger.info("No hay documentos nuevos para procesar")
            return

        start_time = datetime.now()

        try:
            # Generar embeddings en lotes para eficiencia
            logger.info(f"Generando embeddings para {len(new_documents)} documentos...")

            if self.vectorstore is None:
                # Crear nuevo vectorstore
                self.vectorstore = FAISS.from_documents(
                    new_documents,
                    self.embeddings
                )
                logger.info("Nuevo vectorstore FAISS creado")
            else:
                # Agregar documentos al vectorstore existente
                self.vectorstore.add_documents(new_documents)
                logger.info(f"Agregados {len(new_documents)} documentos al vectorstore existente")

            # Guardar a disco
            self._save_vectorstore()

            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats['last_optimization_time'] = processing_time
            logger.info(f"Vectorstore actualizado en {processing_time:.2f} segundos")

        except Exception as e:
            logger.error(f"Error actualizando vectorstore: {e}")
            raise

    def _create_qa_chain(self):
        """Crea cadena QA con retriever optimizado"""
        if not self.vectorstore:
            logger.error("Vectorstore no disponible para crear QA chain")
            return

        try:
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vectorstore.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": 3}
                ),
                return_source_documents=True
            )
            logger.info("QA Chain creado correctamente")
        except Exception as e:
            logger.error(f"Error creando QA chain: {e}")

    def _initialize_system(self):
        """Inicializa el sistema completo de forma optimizada"""
        start_time = datetime.now()
        logger.info("Iniciando sistema optimizado de FAQs del SII...")

        try:
            # Paso 1: Intentar cargar índice existente
            if self._load_existing_vectorstore():
                # Cargar metadatos para sincronizar estado
                metadata_cache = self._load_metadata_cache()
                self.document_hashes = metadata_cache.get('hashes', set())
                self.stats['total_documents'] = metadata_cache.get('document_count', 0)

            # Paso 2: Procesar cambios incrementales
            new_documents = self._load_and_process_faqs()

            # Paso 3: Actualizar vectorstore si hay cambios
            if new_documents or self.vectorstore is None:
                self._create_or_update_vectorstore(new_documents)

            # Paso 4: Crear/actualizar QA chain
            self._create_qa_chain()

            # Marcar como cargado exitosamente
            if self.vectorstore and self.qa_chain:
                self.faqs_loaded = True
                self.last_update = datetime.now()

                total_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Sistema optimizado inicializado en {total_time:.2f} segundos")
                logger.info(f"Estadísticas: {self.stats}")
            else:
                logger.error("Falló la inicialización del sistema")

        except Exception as e:
            logger.error(f"Error en inicialización del sistema: {e}")
            self.faqs_loaded = False

    def search_faqs(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """Busca FAQs usando vectorstore optimizado"""
        if not self.faqs_loaded or not self.vectorstore:
            return {
                'success': False,
                'error': 'Sistema de FAQs no inicializado',
                'results': []
            }

        try:
            docs = self.vectorstore.similarity_search_with_score(
                query,
                k=max_results
            )

            results = []
            for doc, score in docs:
                results.append({
                    'category': doc.metadata.get('category', ''),
                    'subtopic': doc.metadata.get('subtopic', ''),
                    'question': doc.metadata.get('question', ''),
                    'answer': doc.page_content.split('Respuesta: ')[-1] if 'Respuesta: ' in doc.page_content else doc.page_content,
                    'similarity_score': float(1 - score) if score < 1 else 0.0,
                    'document_id': doc.metadata.get('document_id')
                })

            return {
                'success': True,
                'query': query,
                'results': results,
                'total_found': len(results),
                'stats': self.get_performance_stats()
            }

        except Exception as e:
            logger.error(f"Error en búsqueda FAQ: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    def ask_question(self, question: str) -> Dict[str, Any]:
        """Genera respuesta usando QA chain optimizada"""
        if not self.faqs_loaded or not self.qa_chain:
            return {
                'success': False,
                'error': 'Sistema de QA no inicializado',
                'answer': ''
            }

        try:
            result = self.qa_chain.invoke({
                "query": question
            })

            source_docs = []
            if 'source_documents' in result:
                for doc in result['source_documents']:
                    source_docs.append({
                        'category': doc.metadata.get('category', ''),
                        'subtopic': doc.metadata.get('subtopic', ''),
                        'question': doc.metadata.get('question', ''),
                        'document_id': doc.metadata.get('document_id'),
                        'relevance': 'high'
                    })

            return {
                'success': True,
                'question': question,
                'answer': result['result'],
                'source_documents': source_docs,
                'sources_count': len(source_docs),
                'stats': self.get_performance_stats()
            }

        except Exception as e:
            logger.error(f"Error en QA chain: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': ''
            }

    def get_categories(self) -> Dict[str, Any]:
        """Obtiene categorías desde vectorstore optimizado"""
        if not self.vectorstore:
            return {
                'success': False,
                'error': 'Sistema no inicializado',
                'categories': {}
            }

        try:
            all_docs = list(self.vectorstore.docstore._dict.values())

            categories = {}
            for doc in all_docs:
                category = doc.metadata.get('category', 'Sin categoría')
                subtopic = doc.metadata.get('subtopic', 'Sin subtema')

                if category not in categories:
                    categories[category] = {
                        'subtopics': set(),
                        'total_faqs': 0
                    }

                categories[category]['subtopics'].add(subtopic)
                categories[category]['total_faqs'] += 1

            # Convertir sets a listas
            formatted_categories = {}
            for category, data in categories.items():
                formatted_categories[category] = {
                    'subtopics': list(data['subtopics']),
                    'total_faqs': data['total_faqs']
                }

            return {
                'success': True,
                'categories': formatted_categories,
                'total_categories': len(formatted_categories),
                'total_faqs': sum(data['total_faqs'] for data in categories.values()),
                'stats': self.get_performance_stats()
            }

        except Exception as e:
            logger.error(f"Error obteniendo categorías: {e}")
            return {
                'success': False,
                'error': str(e),
                'categories': {}
            }

    def get_performance_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de performance del sistema"""
        return {
            **self.stats,
            'faqs_loaded': self.faqs_loaded,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'vectorstore_ready': self.vectorstore is not None,
            'qa_chain_ready': self.qa_chain is not None
        }

    def force_refresh(self):
        """Fuerza actualización completa del sistema"""
        logger.info("Forzando actualización completa del sistema...")

        # Limpiar cache y estado
        if os.path.exists(self.metadata_cache_path):
            os.remove(self.metadata_cache_path)

        # Reinicializar sistema
        self.vectorstore = None
        self.qa_chain = None
        self.faqs_loaded = False
        self.document_hashes = set()

        self._initialize_system()


# Instancia global singleton optimizada
_optimized_faq_retriever = None

def get_optimized_faq_retriever() -> OptimizedSIIFAQRetriever:
    """Obtiene la instancia optimizada del retriever (singleton)"""
    global _optimized_faq_retriever
    if _optimized_faq_retriever is None:
        _optimized_faq_retriever = OptimizedSIIFAQRetriever()
    return _optimized_faq_retriever