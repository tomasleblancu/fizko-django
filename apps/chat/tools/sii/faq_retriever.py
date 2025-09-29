"""
Retriever optimizado para FAQs del SII usando JSONLoader y FAISS
"""
import os
import json
from typing import List, Dict, Any, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import JSONLoader
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SIIFAQRetriever:
    """Sistema de recuperación optimizado para FAQs del SII"""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.vectorstore = None
        self.qa_chain = None
        self.faqs_loaded = False
        self._load_and_index_faqs()

    def _get_faq_file_path(self) -> str:
        """Obtiene la ruta del archivo de FAQs corregido"""
        base_dir = os.path.dirname(__file__)
        fixed_file = os.path.join(base_dir, 'faqs_sii_fixed.json')
        original_file = os.path.join(base_dir, 'faqs_sii.json')

        # Preferir el archivo corregido si existe
        if os.path.exists(fixed_file):
            return fixed_file
        return original_file

    def _load_documents_from_json(self) -> List[Document]:
        """Carga documentos usando JSONLoader con el esquema apropiado"""
        faq_file = self._get_faq_file_path()

        if not os.path.exists(faq_file):
            logger.error(f"Archivo de FAQs no encontrado: {faq_file}")
            return []

        try:
            # Primero verificar la estructura del JSON
            with open(faq_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            documents = []

            # Determinar si es estructura nueva (con metadata) o antigua
            if isinstance(data, dict) and 'faqs' in data:
                faqs_data = data['faqs']
            elif isinstance(data, list):
                faqs_data = data
            else:
                logger.error("Estructura de FAQ no reconocida")
                return []

            # Crear documentos manualmente para mejor control
            for faq in faqs_data:
                # Combinar question y answer para contexto completo
                content = f"Pregunta: {faq.get('question', '')}\n\nRespuesta: {faq.get('answer', '')}"

                metadata = {
                    'category': faq.get('category', 'Sin categoría'),
                    'subtopic': faq.get('subtopic', 'Sin subtema'),
                    'question': faq.get('question', ''),
                    'source': 'SII FAQ'
                }

                doc = Document(
                    page_content=content,
                    metadata=metadata
                )
                documents.append(doc)

            logger.info(f"Cargados {len(documents)} documentos FAQ")
            return documents

        except Exception as e:
            logger.error(f"Error cargando documentos JSON: {e}")
            return []

    def _load_and_index_faqs(self):
        """Carga e indexa los FAQs usando FAISS"""
        try:
            documents = self._load_documents_from_json()

            if not documents:
                logger.error("No se pudieron cargar los documentos FAQ")
                return

            # Crear vectorstore FAISS
            self.vectorstore = FAISS.from_documents(
                documents=documents,
                embedding=self.embeddings
            )

            # Crear cadena de recuperación QA
            self.qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vectorstore.as_retriever(
                    search_type="similarity",
                    search_kwargs={"k": 3}  # Top 3 documentos más relevantes
                ),
                return_source_documents=True
            )

            self.faqs_loaded = True
            logger.info("Sistema de recuperación FAQ inicializado correctamente")

        except Exception as e:
            logger.error(f"Error inicializando sistema FAQ: {e}")
            self.faqs_loaded = False

    def search_faqs(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """
        Busca FAQs usando retrieval vectorizado

        Args:
            query: Consulta del usuario
            max_results: Número máximo de resultados

        Returns:
            Dict con resultados de la búsqueda
        """
        if not self.faqs_loaded or not self.vectorstore:
            return {
                'success': False,
                'error': 'Sistema de FAQs no inicializado',
                'results': []
            }

        try:
            # Usar el retriever directamente para obtener documentos similares
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
                    'similarity_score': float(1 - score) if score < 1 else 0.0  # Convertir distancia a similitud
                })

            return {
                'success': True,
                'query': query,
                'results': results,
                'total_found': len(results)
            }

        except Exception as e:
            logger.error(f"Error en búsqueda FAQ: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }

    def ask_question(self, question: str) -> Dict[str, Any]:
        """
        Hace una pregunta usando la cadena QA completa

        Args:
            question: Pregunta del usuario

        Returns:
            Dict con la respuesta generada
        """
        if not self.faqs_loaded or not self.qa_chain:
            return {
                'success': False,
                'error': 'Sistema de QA no inicializado',
                'answer': ''
            }

        try:
            # Usar la cadena QA para generar respuesta contextual
            result = self.qa_chain.invoke({
                "query": question
            })

            # Extraer documentos fuente
            source_docs = []
            if 'source_documents' in result:
                for doc in result['source_documents']:
                    source_docs.append({
                        'category': doc.metadata.get('category', ''),
                        'subtopic': doc.metadata.get('subtopic', ''),
                        'question': doc.metadata.get('question', ''),
                        'relevance': 'high'  # FAISS ya filtró los más relevantes
                    })

            return {
                'success': True,
                'question': question,
                'answer': result['result'],
                'source_documents': source_docs,
                'sources_count': len(source_docs)
            }

        except Exception as e:
            logger.error(f"Error en QA chain: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': ''
            }

    def get_categories(self) -> Dict[str, Any]:
        """Obtiene todas las categorías disponibles"""
        if not self.vectorstore:
            return {
                'success': False,
                'error': 'Sistema no inicializado',
                'categories': {}
            }

        try:
            # Obtener todos los documentos del vectorstore
            all_docs = self.vectorstore.docstore._dict.values()

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
                'total_faqs': sum(data['total_faqs'] for data in categories.values())
            }

        except Exception as e:
            logger.error(f"Error obteniendo categorías: {e}")
            return {
                'success': False,
                'error': str(e),
                'categories': {}
            }


# Instancia global singleton
_faq_retriever = None

def get_faq_retriever() -> SIIFAQRetriever:
    """Obtiene la instancia del retriever (singleton)"""
    global _faq_retriever
    if _faq_retriever is None:
        _faq_retriever = SIIFAQRetriever()
    return _faq_retriever