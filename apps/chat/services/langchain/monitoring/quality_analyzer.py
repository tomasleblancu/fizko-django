"""
Sistema de Análisis de Feedback y Calidad Automático
Evalúa automáticamente la calidad de respuestas y recopila feedback
"""

import time
import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .tracing_system import get_tracing_system
from .metrics_collector import get_metrics_collector


@dataclass
class QualityMetrics:
    """Métricas de calidad agregadas"""
    avg_response_quality: float
    avg_user_satisfaction: float
    avg_response_time: float
    success_rate: float
    total_interactions: int
    quality_distribution: Dict[str, int]  # excellent, good, fair, poor
    common_issues: List[str]
    improvement_suggestions: List[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class InteractionQuality:
    """Calidad de una interacción individual"""
    conversation_id: str
    agent_name: str
    timestamp: float
    user_query: str
    agent_response: str
    response_time: float

    # Métricas automáticas (0-100)
    relevance_score: Optional[float] = None
    coherence_score: Optional[float] = None
    completeness_score: Optional[float] = None
    accuracy_score: Optional[float] = None

    # Feedback del usuario (1-5)
    user_rating: Optional[float] = None
    user_comments: Optional[str] = None

    # Análisis automático
    detected_issues: List[str] = field(default_factory=list)
    quality_category: Optional[str] = None  # excellent, good, fair, poor
    improvement_suggestions: List[str] = field(default_factory=list)

    def get_overall_quality_score(self) -> float:
        """Calcula puntuación general de calidad (0-100)"""
        auto_scores = [
            score for score in [
                self.relevance_score,
                self.coherence_score,
                self.completeness_score,
                self.accuracy_score
            ] if score is not None
        ]

        if auto_scores:
            auto_avg = sum(auto_scores) / len(auto_scores)
        else:
            auto_avg = 50.0  # Default neutral

        # Incorporar rating del usuario si está disponible
        if self.user_rating:
            user_score = (self.user_rating / 5.0) * 100  # Convertir 1-5 a 0-100
            # Dar más peso al feedback del usuario
            return (auto_avg * 0.4) + (user_score * 0.6)

        return auto_avg

    def categorize_quality(self) -> str:
        """Categoriza calidad basada en puntuación general"""
        score = self.get_overall_quality_score()

        if score >= 80:
            return "excellent"
        elif score >= 65:
            return "good"
        elif score >= 50:
            return "fair"
        else:
            return "poor"


class AutoQualityEvaluator:
    """Evaluador automático de calidad usando LLM"""

    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

    async def evaluate_interaction(
        self,
        user_query: str,
        agent_response: str,
        agent_name: str = "unknown"
    ) -> Dict[str, Any]:
        """Evalúa automáticamente la calidad de una interacción"""

        system_prompt = """Eres un experto evaluador de calidad para sistemas de IA conversacional especializada en tributación chilena.

Tu tarea es evaluar una interacción entre un usuario y un agente especializado, calificando en una escala de 0-100:

1. RELEVANCIA: ¿La respuesta aborda directamente la pregunta del usuario?
2. COHERENCIA: ¿La respuesta es lógica y bien estructurada?
3. COMPLETITUD: ¿La respuesta proporciona información suficiente?
4. PRECISIÓN: ¿La información es correcta y específica para el contexto chileno?

También identifica:
- PROBLEMAS detectados en la respuesta
- SUGERENCIAS de mejora específicas

Responde ÚNICAMENTE en formato JSON válido:
{
  "relevance_score": 85,
  "coherence_score": 90,
  "completeness_score": 75,
  "accuracy_score": 80,
  "detected_issues": ["Falta información sobre plazos"],
  "improvement_suggestions": ["Incluir fechas específicas", "Agregar ejemplos prácticos"],
  "overall_assessment": "La respuesta es buena pero podría ser más específica"
}"""

        user_prompt = f"""
AGENTE: {agent_name}

CONSULTA DEL USUARIO:
{user_query}

RESPUESTA DEL AGENTE:
{agent_response}

Evalúa esta interacción según los criterios especificados:"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # Parsear respuesta JSON
            evaluation = json.loads(response.content.strip())

            # Validar que tiene los campos requeridos
            required_fields = ["relevance_score", "coherence_score", "completeness_score", "accuracy_score"]
            for field in required_fields:
                if field not in evaluation:
                    evaluation[field] = 50.0  # Default neutral

            return evaluation

        except Exception as e:
            # Fallback en caso de error
            return {
                "relevance_score": 50.0,
                "coherence_score": 50.0,
                "completeness_score": 50.0,
                "accuracy_score": 50.0,
                "detected_issues": [f"Error en evaluación automática: {str(e)}"],
                "improvement_suggestions": ["Revisar manualmente esta interacción"],
                "overall_assessment": "Evaluación automática falló"
            }


class QualityAnalyzer:
    """Sistema central de análisis de calidad y feedback"""

    def __init__(self):
        self.evaluator = AutoQualityEvaluator()
        self.interactions: deque = deque(maxlen=1000)  # Últimas 1000 interacciones
        self.user_feedback: deque = deque(maxlen=500)  # Últimos 500 feedback

        # Patrones comunes de problemas
        self.issue_patterns = {
            "incomplete_response": [
                r"no puedo.*ayudarte",
                r"información.*insuficiente",
                r"contacta.*soporte"
            ],
            "irrelevant_response": [
                r"no.*relacionado",
                r"tema.*diferente",
                r"consulta.*específica"
            ],
            "technical_error": [
                r"error.*sistema",
                r"falló.*búsqueda",
                r"tiempo.*agotado"
            ],
            "unclear_response": [
                r"puede.*ser",
                r"depende.*caso",
                r"consultar.*experto"
            ]
        }

    async def analyze_interaction(
        self,
        conversation_id: str,
        agent_name: str,
        user_query: str,
        agent_response: str,
        response_time: float,
        metadata: Dict[str, Any] = None
    ) -> InteractionQuality:
        """Analiza calidad de una interacción"""

        # Crear objeto de calidad base
        quality = InteractionQuality(
            conversation_id=conversation_id,
            agent_name=agent_name,
            timestamp=time.time(),
            user_query=user_query[:500],  # Truncar para storage
            agent_response=agent_response[:1000],
            response_time=response_time
        )

        # Evaluación automática
        try:
            evaluation = await self.evaluator.evaluate_interaction(
                user_query, agent_response, agent_name
            )

            quality.relevance_score = evaluation.get("relevance_score", 50.0)
            quality.coherence_score = evaluation.get("coherence_score", 50.0)
            quality.completeness_score = evaluation.get("completeness_score", 50.0)
            quality.accuracy_score = evaluation.get("accuracy_score", 50.0)
            quality.detected_issues = evaluation.get("detected_issues", [])
            quality.improvement_suggestions = evaluation.get("improvement_suggestions", [])

        except Exception as e:
            quality.detected_issues.append(f"Error en evaluación: {str(e)}")

        # Análisis de patrones
        quality.detected_issues.extend(self._detect_pattern_issues(agent_response))

        # Categorizar calidad
        quality.quality_category = quality.categorize_quality()

        # Almacenar interacción
        self.interactions.append(quality)

        return quality

    def add_user_feedback(
        self,
        conversation_id: str,
        user_rating: float,
        user_comments: str = ""
    ):
        """Agrega feedback del usuario"""

        # Buscar interacción correspondiente
        for interaction in reversed(self.interactions):
            if interaction.conversation_id == conversation_id:
                interaction.user_rating = user_rating
                interaction.user_comments = user_comments[:500]  # Truncar

                # Re-categorizar con feedback del usuario
                interaction.quality_category = interaction.categorize_quality()
                break

        # También almacenar feedback por separado
        feedback_entry = {
            "conversation_id": conversation_id,
            "rating": user_rating,
            "comments": user_comments,
            "timestamp": time.time()
        }
        self.user_feedback.append(feedback_entry)

    def get_quality_metrics(self, hours: int = 24) -> QualityMetrics:
        """Obtiene métricas de calidad agregadas"""
        cutoff_time = time.time() - (hours * 3600)

        # Filtrar interacciones recientes
        recent_interactions = [
            i for i in self.interactions
            if i.timestamp >= cutoff_time
        ]

        if not recent_interactions:
            return QualityMetrics(
                avg_response_quality=0,
                avg_user_satisfaction=0,
                avg_response_time=0,
                success_rate=0,
                total_interactions=0,
                quality_distribution={},
                common_issues=[],
                improvement_suggestions=[]
            )

        # Calcular métricas
        quality_scores = [i.get_overall_quality_score() for i in recent_interactions]
        avg_quality = sum(quality_scores) / len(quality_scores)

        # Satisfacción del usuario
        user_ratings = [i.user_rating for i in recent_interactions if i.user_rating]
        avg_satisfaction = (sum(user_ratings) / len(user_ratings)) if user_ratings else 0

        # Tiempo de respuesta
        response_times = [i.response_time for i in recent_interactions]
        avg_response_time = sum(response_times) / len(response_times)

        # Tasa de éxito (interacciones sin problemas graves)
        successful_interactions = [
            i for i in recent_interactions
            if i.get_overall_quality_score() >= 60
        ]
        success_rate = len(successful_interactions) / len(recent_interactions)

        # Distribución de calidad
        quality_dist = defaultdict(int)
        for interaction in recent_interactions:
            category = interaction.quality_category or "unknown"
            quality_dist[category] += 1

        # Problemas comunes
        all_issues = []
        for interaction in recent_interactions:
            all_issues.extend(interaction.detected_issues)

        issue_counts = defaultdict(int)
        for issue in all_issues:
            issue_counts[issue] += 1

        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        common_issues = [issue for issue, count in common_issues]

        # Sugerencias de mejora
        all_suggestions = []
        for interaction in recent_interactions:
            all_suggestions.extend(interaction.improvement_suggestions)

        suggestion_counts = defaultdict(int)
        for suggestion in all_suggestions:
            suggestion_counts[suggestion] += 1

        top_suggestions = sorted(suggestion_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        top_suggestions = [suggestion for suggestion, count in top_suggestions]

        return QualityMetrics(
            avg_response_quality=round(avg_quality, 2),
            avg_user_satisfaction=round(avg_satisfaction, 2),
            avg_response_time=round(avg_response_time, 3),
            success_rate=round(success_rate, 3),
            total_interactions=len(recent_interactions),
            quality_distribution=dict(quality_dist),
            common_issues=common_issues,
            improvement_suggestions=top_suggestions
        )

    def get_agent_quality_report(self, agent_name: str = None, hours: int = 24) -> Dict[str, Any]:
        """Obtiene reporte de calidad por agente"""
        cutoff_time = time.time() - (hours * 3600)

        # Filtrar interacciones
        interactions = [
            i for i in self.interactions
            if i.timestamp >= cutoff_time and (not agent_name or i.agent_name == agent_name)
        ]

        if not interactions:
            return {"message": "No data available for specified criteria"}

        # Agrupar por agente
        agent_stats = defaultdict(list)
        for interaction in interactions:
            agent_stats[interaction.agent_name].append(interaction)

        agent_reports = {}
        for agent, agent_interactions in agent_stats.items():
            quality_scores = [i.get_overall_quality_score() for i in agent_interactions]
            user_ratings = [i.user_rating for i in agent_interactions if i.user_rating]

            agent_reports[agent] = {
                "total_interactions": len(agent_interactions),
                "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 2),
                "avg_user_rating": round(sum(user_ratings) / len(user_ratings), 2) if user_ratings else 0,
                "quality_distribution": self._get_quality_distribution(agent_interactions),
                "most_common_issues": self._get_top_issues(agent_interactions, 3),
                "avg_response_time": round(
                    sum(i.response_time for i in agent_interactions) / len(agent_interactions), 3
                )
            }

        return {
            "time_range_hours": hours,
            "agents": agent_reports if not agent_name else agent_reports.get(agent_name, {}),
            "total_interactions": len(interactions)
        }

    def get_feedback_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """Analiza feedback de usuarios"""
        cutoff_time = time.time() - (hours * 3600)

        recent_feedback = [
            f for f in self.user_feedback
            if f["timestamp"] >= cutoff_time
        ]

        if not recent_feedback:
            return {"message": "No user feedback available"}

        ratings = [f["rating"] for f in recent_feedback]
        comments = [f["comments"] for f in recent_feedback if f["comments"]]

        # Análisis de sentimientos básico en comentarios
        positive_keywords = ["bueno", "excelente", "útil", "claro", "rápido", "preciso"]
        negative_keywords = ["malo", "lento", "confuso", "error", "incompleto", "difícil"]

        sentiment_scores = []
        for comment in comments:
            comment_lower = comment.lower()
            positive_count = sum(1 for word in positive_keywords if word in comment_lower)
            negative_count = sum(1 for word in negative_keywords if word in comment_lower)

            if positive_count > negative_count:
                sentiment_scores.append(1)
            elif negative_count > positive_count:
                sentiment_scores.append(-1)
            else:
                sentiment_scores.append(0)

        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0

        return {
            "time_range_hours": hours,
            "total_feedback_entries": len(recent_feedback),
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "rating_distribution": self._get_rating_distribution(ratings),
            "avg_sentiment": round(avg_sentiment, 2),
            "comments_with_text": len(comments),
            "sample_comments": comments[:5]  # Primeros 5 comentarios como muestra
        }

    def _detect_pattern_issues(self, response_text: str) -> List[str]:
        """Detecta problemas basados en patrones predefinidos"""
        detected_issues = []
        response_lower = response_text.lower()

        for issue_type, patterns in self.issue_patterns.items():
            for pattern in patterns:
                if re.search(pattern, response_lower):
                    detected_issues.append(issue_type)
                    break  # Solo agregar cada tipo una vez

        return detected_issues

    def _get_quality_distribution(self, interactions: List[InteractionQuality]) -> Dict[str, int]:
        """Obtiene distribución de calidad"""
        distribution = defaultdict(int)
        for interaction in interactions:
            category = interaction.quality_category or "unknown"
            distribution[category] += 1
        return dict(distribution)

    def _get_top_issues(self, interactions: List[InteractionQuality], limit: int) -> List[str]:
        """Obtiene problemas más comunes"""
        issue_counts = defaultdict(int)
        for interaction in interactions:
            for issue in interaction.detected_issues:
                issue_counts[issue] += 1

        top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return [issue for issue, count in top_issues[:limit]]

    def _get_rating_distribution(self, ratings: List[float]) -> Dict[str, int]:
        """Obtiene distribución de ratings"""
        distribution = defaultdict(int)
        for rating in ratings:
            if rating >= 4.5:
                distribution["5_stars"] += 1
            elif rating >= 3.5:
                distribution["4_stars"] += 1
            elif rating >= 2.5:
                distribution["3_stars"] += 1
            elif rating >= 1.5:
                distribution["2_stars"] += 1
            else:
                distribution["1_star"] += 1

        return dict(distribution)


# Instancia global del analizador de calidad
_global_quality_analyzer: Optional[QualityAnalyzer] = None


def get_quality_analyzer() -> QualityAnalyzer:
    """Obtiene instancia global del analizador de calidad"""
    global _global_quality_analyzer

    if _global_quality_analyzer is None:
        _global_quality_analyzer = QualityAnalyzer()

    return _global_quality_analyzer