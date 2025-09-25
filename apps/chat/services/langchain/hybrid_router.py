"""
Sistema de Routing Híbrido Avanzado para Supervisor Multi-Agente

Combina:
- Reglas basadas en palabras clave
- Routing semántico con embeddings
- LLM para casos ambiguos
- Feedback loop y monitorización
- Sistema de fallback y timeouts
"""
import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from django.conf import settings
from django.core.cache import cache
import numpy as np
import logging

logger = logging.getLogger(__name__)


class HybridRouter:
    """Router híbrido con reglas, embeddings y LLM"""

    def __init__(self):
        # Modelos
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Configuración de agentes
        self.agents_config = {
            "onboarding": {
                "name": "OnboardingAgent",
                "keywords": [
                    "registrarse", "crear cuenta", "registro", "nueva cuenta",
                    "empezar", "comenzar", "onboarding", "como uso fizko",
                    "nuevo usuario", "primera vez", "signup", "sign up"
                ],
                "description": "Agente para registro y onboarding de nuevos usuarios no autenticados",
                "examples": [
                    "Quiero crear una cuenta",
                    "¿Cómo me registro?",
                    "Soy nuevo en Fizko",
                    "¿Cómo empiezo a usar Fizko?"
                ]
            },
            "dte": {
                "name": "DTEAgent",
                "keywords": [
                    "factura", "boleta", "nota de credito", "nota de debito",
                    "dte", "documento", "electronico", "emision", "folio",
                    "timbre", "xml", "pdf", "mis documentos", "ventas", "compras"
                ],
                "description": "Especializado en Documentos Tributarios Electrónicos, facturas, boletas y notas",
                "examples": [
                    "Mostrar mis facturas del mes",
                    "¿Cómo emito una boleta electrónica?",
                    "Ver documentos de enero 2024",
                    "¿Qué es una nota de crédito?"
                ]
            },
            "general": {
                "name": "GeneralAgent",
                "keywords": [
                    # Servicios SII
                    "certificado digital", "clave tributaria", "portal", "misii", "sii",
                    "tramite", "solicitud", "peticion", "fiscalizacion",
                    "mandatario", "representante", "codigo provisorio", "habilitacion",
                    "avaluo", "contribucion", "termino de giro", "actualizacion informacion",
                    # Tributación
                    "f29", "f3323", "impuesto", "renta", "iva", "ppm",
                    "tributacion", "tributario", "declaracion", "mensual", "anual", "formulario",
                    # Información de empresa
                    "empresa", "compañia", "socios", "actividad economica", "representantes",
                    "mi empresa", "que sabes de mi empresa", "informacion empresa",
                    # General
                    "hola", "gracias", "ayuda", "que puedes hacer",
                    "contabilidad", "balance", "estado", "general", "saludo"
                ],
                "description": "Agente general para SII, tributación, información de empresa, contabilidad y consultas generales",
                "examples": [
                    "¿Qué sabes de mi empresa?",
                    "¿Cómo declaro F29?",
                    "¿Cómo obtengo certificado digital?",
                    "Hola, ¿cómo estás?",
                    "¿Cuáles son mis socios?",
                    "¿Qué actividades económicas tengo?",
                    "¿Cómo calculo el IVA mensual?"
                ]
            }
        }

        # Cache para embeddings de ejemplos
        self.agent_embeddings = {}
        self._initialize_agent_embeddings()

        # Sistema de monitorización
        self.routing_stats = {
            'total_requests': 0,
            'rule_based_decisions': 0,
            'semantic_decisions': 0,
            'llm_decisions': 0,
            'fallback_decisions': 0,
            'confidence_scores': [],
            'response_times': []
        }

    def _initialize_agent_embeddings(self):
        """Inicializa embeddings de ejemplos para cada agente"""
        logger.info("Inicializando embeddings para routing semántico...")

        try:
            for agent_key, config in self.agents_config.items():
                # Cache key para embeddings
                cache_key = f"agent_embeddings_{agent_key}_{hashlib.md5(str(config['examples']).encode()).hexdigest()}"

                # Intentar cargar desde cache
                cached_embeddings = cache.get(cache_key)

                if cached_embeddings:
                    self.agent_embeddings[agent_key] = cached_embeddings
                    logger.info(f"Embeddings de {agent_key} cargados desde cache")
                else:
                    # Generar embeddings para ejemplos
                    examples = config['examples']
                    embeddings = self.embeddings.embed_documents(examples)
                    self.agent_embeddings[agent_key] = embeddings

                    # Cachear por 24 horas
                    cache.set(cache_key, embeddings, 60 * 60 * 24)
                    logger.info(f"Embeddings de {agent_key} generados y cacheados")

        except Exception as e:
            logger.error(f"Error inicializando embeddings: {e}")

    def _rule_based_routing(self, query: str) -> Tuple[Optional[str], float]:
        """Routing basado en reglas de palabras clave"""
        query_lower = query.lower()

        # Puntuación por agente
        agent_scores = {}

        for agent_key, config in self.agents_config.items():
            score = 0
            keywords_found = []

            for keyword in config['keywords']:
                if keyword in query_lower:
                    # Peso mayor para keywords más específicos
                    keyword_weight = 2.0 if len(keyword) > 6 else 1.0
                    score += keyword_weight
                    keywords_found.append(keyword)

            if score > 0:
                agent_scores[agent_key] = {
                    'score': score,
                    'keywords': keywords_found
                }

        if not agent_scores:
            return None, 0.0

        # Seleccionar agente con mayor puntuación
        best_agent = max(agent_scores.keys(), key=lambda x: agent_scores[x]['score'])
        max_score = agent_scores[best_agent]['score']

        # Normalizar score a 0-1
        confidence = min(max_score / 5.0, 1.0)  # Max esperado ~5 keywords

        logger.info(f"Rule-based routing: {best_agent} (confidence: {confidence:.2f}, keywords: {agent_scores[best_agent]['keywords']})")

        return best_agent, confidence

    def _semantic_routing(self, query: str, threshold: float = 0.75) -> Tuple[Optional[str], float]:
        """Routing semántico usando embeddings"""
        if not self.agent_embeddings:
            return None, 0.0

        try:
            # Generar embedding de la consulta
            query_embedding = self.embeddings.embed_query(query)
            query_embedding = np.array(query_embedding)

            # Calcular similitud con ejemplos de cada agente
            agent_similarities = {}

            for agent_key, agent_examples_embeddings in self.agent_embeddings.items():
                similarities = []

                for example_embedding in agent_examples_embeddings:
                    example_embedding = np.array(example_embedding)

                    # Similitud coseno
                    dot_product = np.dot(query_embedding, example_embedding)
                    norms = np.linalg.norm(query_embedding) * np.linalg.norm(example_embedding)
                    similarity = dot_product / norms
                    similarities.append(similarity)

                # Usar la similitud máxima para este agente
                max_similarity = max(similarities) if similarities else 0.0
                agent_similarities[agent_key] = max_similarity

            # Encontrar agente con mayor similitud
            if agent_similarities:
                best_agent = max(agent_similarities.keys(), key=lambda x: agent_similarities[x])
                confidence = agent_similarities[best_agent]

                # Solo retornar si supera el umbral
                if confidence >= threshold:
                    logger.info(f"Semantic routing: {best_agent} (confidence: {confidence:.3f})")
                    return best_agent, confidence

            return None, 0.0

        except Exception as e:
            logger.error(f"Error en routing semántico: {e}")
            return None, 0.0

    def _llm_routing(self, query: str) -> Tuple[str, float]:
        """Routing usando LLM para casos ambiguos"""
        prompt = f"""Analiza esta consulta y decide qué agente especializado debe responder.

Consulta: "{query}"

Agentes disponibles:
- OnboardingAgent: Para usuarios NO AUTENTICADOS que necesitan registrarse o crear cuenta
- DTEAgent: EXCLUSIVAMENTE documentos electrónicos (facturas, boletas, notas de crédito/débito)
- GeneralAgent: Para usuarios AUTENTICADOS - información de empresa, SII, contabilidad, saludos

Responde SOLO con el nombre del agente y un número de confianza del 0.0 al 1.0 separados por coma.
Ejemplo: "OnboardingAgent, 0.85"
"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # Parsear respuesta
            parts = content.split(',')
            if len(parts) == 2:
                agent = parts[0].strip()
                confidence = float(parts[1].strip())

                # Validar agente
                valid_agents = ["OnboardingAgent", "DTEAgent", "GeneralAgent"]
                if agent in valid_agents:
                    # Mapear a keys internas
                    agent_mapping = {
                        "OnboardingAgent": "onboarding",
                        "DTEAgent": "dte",
                        "GeneralAgent": "general"
                    }

                    internal_key = agent_mapping[agent]
                    logger.info(f"LLM routing: {internal_key} (confidence: {confidence:.2f})")
                    return internal_key, confidence

        except Exception as e:
            logger.error(f"Error en LLM routing: {e}")

        # Fallback a general
        logger.warning("LLM routing failed, usando GeneralAgent como fallback")
        return "general", 0.3

    def route(self, query: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecuta routing híbrido completo"""
        start_time = time.time()

        self.routing_stats['total_requests'] += 1

        routing_decision = {
            'query': query,
            'selected_agent': None,
            'confidence': 0.0,
            'method_used': None,
            'methods_tried': [],
            'processing_time': 0.0,
            'metadata': metadata or {}
        }

        try:
            # PASO 1: Intentar routing basado en reglas
            rule_agent, rule_confidence = self._rule_based_routing(query)
            routing_decision['methods_tried'].append({
                'method': 'rule_based',
                'agent': rule_agent,
                'confidence': rule_confidence
            })

            # Si las reglas son confiables (>0.7), usar ese resultado
            if rule_agent and rule_confidence > 0.7:
                routing_decision.update({
                    'selected_agent': rule_agent,
                    'confidence': rule_confidence,
                    'method_used': 'rule_based'
                })
                self.routing_stats['rule_based_decisions'] += 1

            else:
                # PASO 2: Intentar routing semántico
                semantic_agent, semantic_confidence = self._semantic_routing(query)
                routing_decision['methods_tried'].append({
                    'method': 'semantic',
                    'agent': semantic_agent,
                    'confidence': semantic_confidence
                })

                # Si semántico es confiable, usarlo
                if semantic_agent and semantic_confidence > 0.75:
                    routing_decision.update({
                        'selected_agent': semantic_agent,
                        'confidence': semantic_confidence,
                        'method_used': 'semantic'
                    })
                    self.routing_stats['semantic_decisions'] += 1

                else:
                    # PASO 3: Usar LLM para casos ambiguos
                    llm_agent, llm_confidence = self._llm_routing(query)
                    routing_decision['methods_tried'].append({
                        'method': 'llm',
                        'agent': llm_agent,
                        'confidence': llm_confidence
                    })

                    routing_decision.update({
                        'selected_agent': llm_agent,
                        'confidence': llm_confidence,
                        'method_used': 'llm'
                    })
                    self.routing_stats['llm_decisions'] += 1

            # Registrar estadísticas
            processing_time = time.time() - start_time
            routing_decision['processing_time'] = processing_time

            self.routing_stats['confidence_scores'].append(routing_decision['confidence'])
            self.routing_stats['response_times'].append(processing_time)

            # Log de decisión final
            logger.info(f"Routing decision: {routing_decision['selected_agent']} "
                       f"(method: {routing_decision['method_used']}, "
                       f"confidence: {routing_decision['confidence']:.2f}, "
                       f"time: {processing_time:.3f}s)")

            return routing_decision

        except Exception as e:
            logger.error(f"Error en routing híbrido: {e}")

            # Fallback de emergencia
            self.routing_stats['fallback_decisions'] += 1

            return {
                'query': query,
                'selected_agent': 'general',
                'confidence': 0.2,
                'method_used': 'emergency_fallback',
                'methods_tried': [],
                'processing_time': time.time() - start_time,
                'error': str(e)
            }

    def get_routing_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de routing"""
        avg_confidence = np.mean(self.routing_stats['confidence_scores']) if self.routing_stats['confidence_scores'] else 0.0
        avg_response_time = np.mean(self.routing_stats['response_times']) if self.routing_stats['response_times'] else 0.0

        return {
            **self.routing_stats,
            'average_confidence': float(avg_confidence),
            'average_response_time': float(avg_response_time),
            'success_rate': (self.routing_stats['total_requests'] - self.routing_stats['fallback_decisions']) / max(self.routing_stats['total_requests'], 1)
        }

    def save_routing_feedback(self, routing_decision: Dict[str, Any],
                            actual_agent_used: str,
                            user_satisfaction: Optional[float] = None):
        """Guarda feedback para mejorar el routing"""
        feedback = {
            'timestamp': datetime.now().isoformat(),
            'original_decision': routing_decision,
            'actual_agent_used': actual_agent_used,
            'user_satisfaction': user_satisfaction,
            'was_correct': routing_decision['selected_agent'] == actual_agent_used
        }

        # Guardar en archivo para análisis posterior
        feedback_file = os.path.join(
            os.path.dirname(__file__),
            'routing_feedback.jsonl'
        )

        try:
            with open(feedback_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback, ensure_ascii=False) + '\n')

            logger.info(f"Feedback guardado: {'correcto' if feedback['was_correct'] else 'incorrecto'}")

        except Exception as e:
            logger.error(f"Error guardando feedback: {e}")


# Instancia global del router híbrido
_hybrid_router = None

def get_hybrid_router() -> HybridRouter:
    """Obtiene la instancia del router híbrido (singleton)"""
    global _hybrid_router
    if _hybrid_router is None:
        _hybrid_router = HybridRouter()
    return _hybrid_router