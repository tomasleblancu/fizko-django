"""
Sistema de Monitoreo Integrado para Multi-Agent System
Combina logging, métricas, trazabilidad, alertas, calidad y auditoría en un sistema unificado
"""

import time
import threading
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from contextlib import asynccontextmanager

from .structured_logger import get_structured_logger, get_multiagent_logger
from .metrics_collector import get_metrics_collector, track_execution_time
from .tracing_system import get_tracing_system
from .alerting_system import get_alerting_system, AlertLevel
from .quality_analyzer import get_quality_analyzer
from .audit_logger import get_audit_logger, AuditEventType, AuditLevel


class IntegratedMonitoringSystem:
    """Sistema de monitoreo integrado que coordina todos los subsistemas"""

    def __init__(self):
        # Inicializar todos los subsistemas
        self.logger = get_multiagent_logger()
        self.metrics = get_metrics_collector()
        self.tracing = get_tracing_system()
        self.alerting = get_alerting_system()
        self.quality = get_quality_analyzer()
        self.audit = get_audit_logger()

        # Estado del sistema
        self.system_started = False
        self.monitoring_tasks = []

        # Thread para updates periódicos
        self.background_thread = None
        self.running = False

    def start_monitoring(self):
        """Inicia todo el sistema de monitoreo"""
        if self.system_started:
            return

        print("🚀 Iniciando Sistema de Monitoreo Integrado...")

        # Iniciar alertas
        self.alerting.start_monitoring(check_interval_seconds=30)

        # Iniciar thread de background para métricas del sistema
        self.running = True
        self.background_thread = threading.Thread(
            target=self._background_monitoring_loop,
            daemon=True
        )
        self.background_thread.start()

        # Log de inicio
        system_logger = get_structured_logger("system")
        system_logger.info(
            "Sistema de monitoreo integrado iniciado",
            event_type="system_start",
            metadata={
                "components": ["logging", "metrics", "tracing", "alerting", "quality", "audit"],
                "version": "1.0.0"
            }
        )

        # Auditoría de inicio
        self.audit.log_system_action(
            action="monitoring_system_start",
            component="integrated_monitoring",
            details={
                "components_enabled": 6,
                "version": "1.0.0"
            }
        )

        self.system_started = True
        print("✅ Sistema de Monitoreo Integrado activo")

    def stop_monitoring(self):
        """Detiene todo el sistema de monitoreo"""
        if not self.system_started:
            return

        print("🛑 Deteniendo Sistema de Monitoreo Integrado...")

        self.running = False
        self.alerting.stop_monitoring()

        if self.background_thread:
            self.background_thread.join(timeout=5)

        # Log de parada
        system_logger = get_structured_logger("system")
        system_logger.info(
            "Sistema de monitoreo integrado detenido",
            event_type="system_stop"
        )

        self.system_started = False
        print("✅ Sistema de Monitoreo Integrado detenido")

    @asynccontextmanager
    async def monitor_conversation(
        self,
        conversation_id: str,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Context manager para monitorear una conversación completa"""

        # 1. Iniciar contexto de logging
        with self.logger.conversation_context(conversation_id, user_id):
            # 2. Iniciar traza de conversación
            conversation_trace = self.tracing.start_conversation_trace(
                conversation_id=conversation_id,
                user_id=user_id,
                metadata={"ip_address": ip_address, "user_agent": user_agent}
            )

            # 3. Log de auditoría del acceso
            session_id = f"session_{int(time.time())}"
            self.audit.log_user_access(
                user_id=user_id or "anonymous",
                action="conversation_start",
                resource=f"conversation:{conversation_id}",
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details={"conversation_id": conversation_id}
            )

            # 4. Métricas del sistema
            self.metrics.set_gauge("active_conversations", len(self.tracing.active_traces))
            self.metrics.increment_counter("conversations_total")

            start_time = time.time()

            try:
                yield self

                # Conversación exitosa
                execution_time = time.time() - start_time
                self.tracing.end_conversation_trace(conversation_id, success=True)

                # Métricas de éxito
                self.metrics.observe_histogram("conversation_duration_seconds", execution_time)
                self.metrics.increment_counter("conversations_successful_total")

                # Log de auditoría de finalización
                self.audit.log_user_access(
                    user_id=user_id or "anonymous",
                    action="conversation_end",
                    resource=f"conversation:{conversation_id}",
                    session_id=session_id,
                    result="success",
                    details={
                        "conversation_id": conversation_id,
                        "duration_seconds": execution_time
                    }
                )

            except Exception as e:
                # Conversación fallida
                execution_time = time.time() - start_time
                error_info = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_seconds": execution_time
                }

                self.tracing.end_conversation_trace(conversation_id, success=False, error_info=error_info)

                # Métricas de error
                self.metrics.increment_counter("conversations_failed_total")
                self.metrics.increment_counter("conversation_errors_total")

                # Alerta por conversación fallida
                self.alerting.create_alert(
                    name="conversation_failure",
                    level=AlertLevel.ERROR,
                    message=f"Conversación {conversation_id} falló: {str(e)}",
                    source_component="conversation_monitor",
                    metadata=error_info
                )

                # Log de auditoría de error
                self.audit.log_user_access(
                    user_id=user_id or "anonymous",
                    action="conversation_end",
                    resource=f"conversation:{conversation_id}",
                    session_id=session_id,
                    result="failure",
                    details=error_info
                )

                raise

            finally:
                # Actualizar estado del sistema
                self.metrics.set_gauge("active_conversations", len(self.tracing.active_traces))
                self.metrics.agent_states["last_activity"] = time.time()

    @asynccontextmanager
    async def monitor_agent_execution(
        self,
        agent_name: str,
        input_messages: List[Any] = None,
        user_id: str = None,
        conversation_id: str = None
    ):
        """Context manager para monitorear ejecución de agente"""

        start_time = time.time()

        # 1. Logging estructurado
        agent_logger = get_structured_logger("agents")
        agent_logger.log_agent_start(agent_name, {"user_id": user_id})

        # 2. Traza de agente
        with self.tracing.trace_agent_execution(agent_name, input_messages):
            try:
                yield

                # Ejecución exitosa
                execution_time = time.time() - start_time

                # Logging
                agent_logger.log_agent_response(
                    agent_name=agent_name,
                    response_time=execution_time,
                    success=True,
                    metadata={"user_id": user_id}
                )

                # Métricas
                self.metrics.record_agent_response_time(agent_name, execution_time, success=True)

                # Auditoría
                self.audit.log_agent_execution(
                    agent_name=agent_name,
                    user_id=user_id or "anonymous",
                    conversation_id=conversation_id or "unknown",
                    execution_time=execution_time,
                    success=True,
                    messages_processed=len(input_messages) if input_messages else 0
                )

            except Exception as e:
                # Ejecución fallida
                execution_time = time.time() - start_time

                # Logging
                agent_logger.log_error_with_traceback(
                    error=e,
                    context_message=f"Error ejecutando agente {agent_name}",
                    metadata={"user_id": user_id, "execution_time": execution_time}
                )

                # Métricas
                self.metrics.record_agent_response_time(agent_name, execution_time, success=False)

                # Alerta si hay muchos errores
                error_rate = self._calculate_agent_error_rate(agent_name)
                if error_rate > 0.2:  # >20% error rate
                    self.alerting.create_alert(
                        name="agent_high_error_rate",
                        level=AlertLevel.WARNING,
                        message=f"Agente {agent_name} tiene alta tasa de errores: {error_rate:.1%}",
                        source_component="agent_monitor",
                        affected_agents=[agent_name]
                    )

                # Auditoría
                self.audit.log_agent_execution(
                    agent_name=agent_name,
                    user_id=user_id or "anonymous",
                    conversation_id=conversation_id or "unknown",
                    execution_time=execution_time,
                    success=False,
                    messages_processed=len(input_messages) if input_messages else 0
                )

                raise

    @asynccontextmanager
    async def monitor_tool_execution(
        self,
        tool_name: str,
        agent_name: str,
        input_data: Dict[str, Any] = None,
        user_id: str = None
    ):
        """Context manager para monitorear ejecución de herramienta"""

        start_time = time.time()

        # 1. Logging
        tool_logger = get_structured_logger("tools")

        # 2. Traza
        with self.tracing.trace_tool_call(tool_name, agent_name, input_data):
            try:
                yield

                # Ejecución exitosa
                execution_time = time.time() - start_time

                # Logging
                tool_logger.log_tool_call(
                    tool_name=tool_name,
                    agent_name=agent_name,
                    execution_time=execution_time,
                    success=True,
                    metadata={"user_id": user_id}
                )

                # Métricas
                self.metrics.record_tool_execution_time(
                    tool_name, agent_name, execution_time, success=True
                )

                # Auditoría
                self.audit.log_tool_execution(
                    tool_name=tool_name,
                    agent_name=agent_name,
                    user_id=user_id or "anonymous",
                    execution_time=execution_time,
                    success=True,
                    input_data=input_data
                )

            except Exception as e:
                # Ejecución fallida
                execution_time = time.time() - start_time

                # Logging
                tool_logger.log_error_with_traceback(
                    error=e,
                    context_message=f"Error ejecutando tool {tool_name} en {agent_name}",
                    metadata={
                        "user_id": user_id,
                        "execution_time": execution_time,
                        "input_data": input_data
                    }
                )

                # Métricas
                self.metrics.record_tool_execution_time(
                    tool_name, agent_name, execution_time, success=False
                )

                # Auditoría
                self.audit.log_tool_execution(
                    tool_name=tool_name,
                    agent_name=agent_name,
                    user_id=user_id or "anonymous",
                    execution_time=execution_time,
                    success=False,
                    input_data=input_data
                )

                raise

    async def analyze_interaction_quality(
        self,
        conversation_id: str,
        agent_name: str,
        user_query: str,
        agent_response: str,
        response_time: float
    ):
        """Analiza calidad de una interacción"""

        # Análisis automático de calidad
        quality_result = await self.quality.analyze_interaction(
            conversation_id=conversation_id,
            agent_name=agent_name,
            user_query=user_query,
            agent_response=agent_response,
            response_time=response_time
        )

        # Métricas de calidad
        quality_score = quality_result.get_overall_quality_score()
        self.metrics.observe_histogram("interaction_quality_score", quality_score)

        # Alerta si calidad es muy baja
        if quality_score < 40:
            self.alerting.create_alert(
                name="low_interaction_quality",
                level=AlertLevel.WARNING,
                message=f"Interacción de baja calidad detectada: {quality_score:.1f}/100",
                source_component="quality_analyzer",
                affected_agents=[agent_name],
                metadata={
                    "conversation_id": conversation_id,
                    "quality_score": quality_score,
                    "detected_issues": quality_result.detected_issues
                }
            )

        # Auditoría de análisis de calidad
        self.audit.log_system_action(
            action="quality_analysis",
            component="quality_analyzer",
            details={
                "conversation_id": conversation_id,
                "agent_name": agent_name,
                "quality_score": quality_score,
                "quality_category": quality_result.quality_category
            }
        )

        return quality_result

    def add_user_feedback(
        self,
        conversation_id: str,
        user_rating: float,
        user_comments: str = "",
        user_id: str = None
    ):
        """Registra feedback del usuario"""

        # Registrar en analizador de calidad
        self.quality.add_user_feedback(conversation_id, user_rating, user_comments)

        # Métricas
        self.metrics.observe_histogram("user_satisfaction_rating", user_rating)

        # Logging
        feedback_logger = get_structured_logger("system")
        feedback_logger.info(
            f"Feedback recibido: {user_rating}/5.0",
            event_type="user_feedback",
            metadata={
                "conversation_id": conversation_id,
                "rating": user_rating,
                "has_comments": bool(user_comments.strip()),
                "user_id": user_id
            }
        )

        # Auditoría
        self.audit.log_user_access(
            user_id=user_id or "anonymous",
            action="provide_feedback",
            resource=f"conversation:{conversation_id}",
            details={
                "rating": user_rating,
                "comments_length": len(user_comments),
                "feedback_type": "quality_rating"
            }
        )

        # Alerta si rating muy bajo
        if user_rating <= 2.0:
            self.alerting.create_alert(
                name="poor_user_feedback",
                level=AlertLevel.WARNING,
                message=f"Feedback negativo recibido: {user_rating}/5.0",
                source_component="user_feedback",
                metadata={
                    "conversation_id": conversation_id,
                    "rating": user_rating,
                    "comments": user_comments[:200]
                }
            )

    def get_system_health_status(self) -> Dict[str, Any]:
        """Obtiene estado de salud completo del sistema"""

        # Estado de cada subsistema
        metrics_health = self.metrics.get_health_status()
        tracing_health = self.tracing.get_system_trace_summary()
        alerting_stats = self.alerting.get_alert_stats(hours=24)
        quality_metrics = self.quality.get_quality_metrics(hours=24)

        # Estado general
        overall_status = "healthy"
        issues = []

        # Verificar métricas
        if metrics_health["status"] != "healthy":
            overall_status = "degraded"
            issues.extend(metrics_health.get("issues", []))

        # Verificar alertas activas críticas
        critical_alerts = len([
            a for a in self.alerting.get_active_alerts()
            if a.level == AlertLevel.CRITICAL
        ])

        if critical_alerts > 0:
            overall_status = "unhealthy"
            issues.append(f"{critical_alerts} alertas críticas activas")

        # Verificar calidad promedio
        if quality_metrics.avg_response_quality < 60:
            if overall_status == "healthy":
                overall_status = "degraded"
            issues.append("Calidad de respuestas por debajo del promedio")

        return {
            "overall_status": overall_status,
            "issues": issues,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystems": {
                "metrics": metrics_health,
                "tracing": {
                    "status": "healthy",
                    "active_conversations": tracing_health["active_conversations"],
                    "completed_conversations": tracing_health["completed_conversations"]
                },
                "alerting": {
                    "status": "healthy",
                    "active_alerts": alerting_stats["active_alerts"],
                    "total_alerts_24h": alerting_stats["total_alerts"]
                },
                "quality": {
                    "status": "healthy",
                    "avg_quality_score": quality_metrics.avg_response_quality,
                    "avg_user_satisfaction": quality_metrics.avg_user_satisfaction,
                    "total_interactions": quality_metrics.total_interactions
                }
            },
            "monitoring_active": self.system_started
        }

    def get_comprehensive_dashboard_data(self) -> Dict[str, Any]:
        """Obtiene datos completos para dashboard de monitoreo"""

        return {
            "system_health": self.get_system_health_status(),
            "metrics_summary": self.metrics.get_all_metrics_summary(minutes=60),
            "agent_performance": self.metrics.get_agent_performance_report(minutes=60),
            "recent_traces": [
                self.tracing.export_conversation_trace(trace.conversation_id)
                for trace in self.tracing.get_recent_conversations(10)
            ],
            "active_alerts": [alert.to_dict() for alert in self.alerting.get_active_alerts()],
            "quality_report": self.quality.get_agent_quality_report(hours=24),
            "feedback_analysis": self.quality.get_feedback_analysis(hours=24),
            "compliance_report": self.audit.get_compliance_report(days=7),
            "dashboard_timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _background_monitoring_loop(self):
        """Loop de monitoreo en background"""
        while self.running:
            try:
                # Actualizar métricas del sistema cada 30 segundos
                self.metrics.update_system_metrics()
                time.sleep(30)
            except Exception as e:
                print(f"Error en background monitoring: {e}")
                time.sleep(30)

    def _calculate_agent_error_rate(self, agent_name: str) -> float:
        """Calcula tasa de errores para un agente"""
        try:
            total_requests = self.metrics.counters.get("agent_requests_total", 0)
            agent_errors = self.metrics.counters.get("agent_errors_total", 0)

            if total_requests == 0:
                return 0.0

            return agent_errors / total_requests
        except:
            return 0.0


# Instancia global del sistema de monitoreo integrado
_global_monitoring_system: Optional[IntegratedMonitoringSystem] = None


def get_monitoring_system() -> IntegratedMonitoringSystem:
    """Obtiene instancia global del sistema de monitoreo integrado"""
    global _global_monitoring_system

    if _global_monitoring_system is None:
        _global_monitoring_system = IntegratedMonitoringSystem()

    return _global_monitoring_system


# Decorador para monitoreo automático completo
def monitor_multiagent_function(component: str = "system"):
    """Decorador para monitoreo automático integral de funciones"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitoring = get_monitoring_system()

            # Extract context if available
            user_id = kwargs.get('user_id') or (args[0].get('user_id') if args and isinstance(args[0], dict) else None)
            conversation_id = kwargs.get('conversation_id') or (args[0].get('conversation_id') if args and isinstance(args[0], dict) else None)

            start_time = time.time()

            try:
                # Logging
                logger = get_structured_logger(component)
                logger.info(
                    f"Ejecutando {func.__name__}",
                    event_type="function_execution",
                    metadata={"user_id": user_id, "conversation_id": conversation_id}
                )

                # Métricas
                monitoring.metrics.increment_counter(f"{component}_function_calls_total")

                # Auditoría
                monitoring.audit.log_system_action(
                    action=f"execute_{func.__name__}",
                    component=component,
                    user_id=user_id,
                    details={
                        "function_name": func.__name__,
                        "conversation_id": conversation_id
                    }
                )

                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Métricas de éxito
                monitoring.metrics.observe_histogram(f"{component}_function_duration_seconds", execution_time)

                # Logging de éxito
                logger.info(
                    f"Función {func.__name__} ejecutada exitosamente",
                    event_type="function_success",
                    performance={"execution_time": execution_time}
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Métricas de error
                monitoring.metrics.increment_counter(f"{component}_function_errors_total")

                # Logging de error
                logger.log_error_with_traceback(
                    error=e,
                    context_message=f"Error ejecutando {func.__name__}",
                    metadata={"execution_time": execution_time}
                )

                # Alerta por errores frecuentes
                error_rate = monitoring.metrics.counters.get(f"{component}_function_errors_total", 0) / max(monitoring.metrics.counters.get(f"{component}_function_calls_total", 1), 1)
                if error_rate > 0.1:  # >10% error rate
                    monitoring.alerting.create_alert(
                        name="high_function_error_rate",
                        level=AlertLevel.WARNING,
                        message=f"Alta tasa de errores en {component}.{func.__name__}: {error_rate:.1%}",
                        source_component=component
                    )

                raise

        def sync_wrapper(*args, **kwargs):
            # Para funciones síncronas, usar versión simplificada
            monitoring = get_monitoring_system()
            start_time = time.time()

            try:
                monitoring.metrics.increment_counter(f"{component}_function_calls_total")
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                monitoring.metrics.observe_histogram(f"{component}_function_duration_seconds", execution_time)
                return result
            except Exception as e:
                monitoring.metrics.increment_counter(f"{component}_function_errors_total")
                raise

        # Determinar si la función es async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator