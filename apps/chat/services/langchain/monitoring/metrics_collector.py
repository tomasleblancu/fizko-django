"""
Sistema de Métricas para Multi-Agent System
Compatible con Prometheus/Grafana para visualización y alertas
"""

import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from statistics import mean, median
import json

import psutil


@dataclass
class MetricPoint:
    """Punto de métrica individual"""
    timestamp: float
    value: Union[float, int]
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Resumen estadístico de métrica"""
    count: int
    sum: float
    min: float
    max: float
    avg: float
    median: float
    p95: float
    p99: float


class TimeSeries:
    """Serie de tiempo para métricas con retención automática"""

    def __init__(self, name: str, retention_minutes: int = 60):
        self.name = name
        self.retention_seconds = retention_minutes * 60
        self.points: deque = deque()
        self.lock = threading.RLock()

    def add_point(self, value: Union[float, int], labels: Dict[str, str] = None, metadata: Dict[str, Any] = None):
        """Agrega punto a la serie temporal"""
        with self.lock:
            point = MetricPoint(
                timestamp=time.time(),
                value=float(value),
                labels=labels or {},
                metadata=metadata or {}
            )
            self.points.append(point)
            self._cleanup_old_points()

    def _cleanup_old_points(self):
        """Elimina puntos antiguos según retención"""
        cutoff_time = time.time() - self.retention_seconds
        while self.points and self.points[0].timestamp < cutoff_time:
            self.points.popleft()

    def get_points(self, minutes: int = None) -> List[MetricPoint]:
        """Obtiene puntos de los últimos N minutos"""
        with self.lock:
            if not minutes:
                return list(self.points)

            cutoff_time = time.time() - (minutes * 60)
            return [p for p in self.points if p.timestamp >= cutoff_time]

    def get_summary(self, minutes: int = None) -> Optional[MetricSummary]:
        """Obtiene resumen estadístico"""
        points = self.get_points(minutes)
        if not points:
            return None

        values = [p.value for p in points]
        values.sort()

        count = len(values)
        sum_val = sum(values)
        min_val = min(values)
        max_val = max(values)
        avg_val = mean(values)
        median_val = median(values)

        # Percentiles
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        p95_val = values[min(p95_idx, count - 1)]
        p99_val = values[min(p99_idx, count - 1)]

        return MetricSummary(
            count=count,
            sum=sum_val,
            min=min_val,
            max=max_val,
            avg=avg_val,
            median=median_val,
            p95=p95_val,
            p99=p99_val
        )


class MetricsCollector:
    """Recolector central de métricas del sistema multi-agente"""

    def __init__(self):
        self.metrics: Dict[str, TimeSeries] = {}
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)

        self.lock = threading.RLock()

        # Métricas del sistema
        self.process = psutil.Process()

        # Estado del sistema multi-agente
        self.agent_states = {
            "active_conversations": 0,
            "total_requests": 0,
            "error_count": 0,
            "last_activity": time.time()
        }

    def _get_or_create_metric(self, name: str) -> TimeSeries:
        """Obtiene o crea métrica por nombre"""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = TimeSeries(name)
            return self.metrics[name]

    # === MÉTRICAS BÁSICAS ===

    def increment_counter(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        """Incrementa contador"""
        with self.lock:
            self.counters[name] += value

        # También agregar a time series
        metric = self._get_or_create_metric(f"{name}_total")
        metric.add_point(self.counters[name], labels)

    def set_gauge(self, name: str, value: Union[float, int], labels: Dict[str, str] = None):
        """Establece valor de gauge"""
        with self.lock:
            self.gauges[name] = float(value)

        # Agregar a time series
        metric = self._get_or_create_metric(name)
        metric.add_point(value, labels)

    def observe_histogram(self, name: str, value: Union[float, int], labels: Dict[str, str] = None):
        """Observa valor en histograma"""
        with self.lock:
            self.histograms[name].append(float(value))
            # Mantener solo últimos 1000 valores
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-1000:]

        # Agregar a time series
        metric = self._get_or_create_metric(name)
        metric.add_point(value, labels)

    # === MÉTRICAS ESPECÍFICAS DEL SISTEMA MULTI-AGENTE ===

    def record_agent_response_time(self, agent_name: str, response_time: float, success: bool):
        """Registra tiempo de respuesta de agente"""
        labels = {"agent": agent_name, "success": str(success).lower()}

        self.observe_histogram("agent_response_time_seconds", response_time, labels)
        self.increment_counter("agent_requests_total", labels=labels)

        if not success:
            self.increment_counter("agent_errors_total", labels={"agent": agent_name})

    def record_tool_execution_time(self, tool_name: str, agent_name: str, execution_time: float, success: bool):
        """Registra tiempo de ejecución de herramienta"""
        labels = {
            "tool": tool_name,
            "agent": agent_name,
            "success": str(success).lower()
        }

        self.observe_histogram("tool_execution_time_seconds", execution_time, labels)
        self.increment_counter("tool_calls_total", labels=labels)

    def record_routing_decision(self, selected_agent: str, method: str, confidence: float, decision_time: float):
        """Registra decisión de routing"""
        labels = {
            "selected_agent": selected_agent,
            "method": method
        }

        self.observe_histogram("routing_decision_time_seconds", decision_time, labels)
        self.observe_histogram("routing_confidence", confidence, labels)
        self.increment_counter("routing_decisions_total", labels=labels)

    def record_memory_operation(self, operation: str, agent_name: str, execution_time: float):
        """Registra operación de memoria"""
        labels = {
            "operation": operation,
            "agent": agent_name
        }

        self.observe_histogram("memory_operation_time_seconds", execution_time, labels)
        self.increment_counter("memory_operations_total", labels=labels)

    def record_search_operation(self, search_type: str, results_count: int, execution_time: float):
        """Registra operación de búsqueda"""
        labels = {"search_type": search_type}

        self.observe_histogram("search_operation_time_seconds", execution_time, labels)
        self.observe_histogram("search_results_count", results_count, labels)
        self.increment_counter("search_operations_total", labels=labels)

    def update_system_metrics(self):
        """Actualiza métricas del sistema"""
        try:
            # CPU y memoria
            cpu_percent = self.process.cpu_percent()
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            memory_percent = self.process.memory_percent()

            self.set_gauge("system_cpu_percent", cpu_percent)
            self.set_gauge("system_memory_mb", memory_mb)
            self.set_gauge("system_memory_percent", memory_percent)
            self.set_gauge("system_thread_count", self.process.num_threads())

            # Estado del sistema multi-agente
            for name, value in self.agent_states.items():
                self.set_gauge(f"multiagent_{name}", value)

        except Exception as e:
            self.increment_counter("metrics_collection_errors_total")

    # === ANÁLISIS Y REPORTING ===

    def get_metric_summary(self, metric_name: str, minutes: int = 60) -> Optional[MetricSummary]:
        """Obtiene resumen de métrica"""
        if metric_name not in self.metrics:
            return None
        return self.metrics[metric_name].get_summary(minutes)

    def get_all_metrics_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Obtiene resumen de todas las métricas"""
        summaries = {}

        for name, metric in self.metrics.items():
            summary = metric.get_summary(minutes)
            if summary:
                summaries[name] = {
                    "count": summary.count,
                    "avg": round(summary.avg, 4),
                    "median": round(summary.median, 4),
                    "p95": round(summary.p95, 4),
                    "p99": round(summary.p99, 4),
                    "min": round(summary.min, 4),
                    "max": round(summary.max, 4)
                }

        return {
            "time_range_minutes": minutes,
            "timestamp": datetime.now().isoformat(),
            "metrics": summaries,
            "counters": dict(self.counters),
            "gauges": {k: round(v, 4) for k, v in self.gauges.items()}
        }

    def get_agent_performance_report(self, minutes: int = 60) -> Dict[str, Any]:
        """Obtiene reporte de performance por agente"""
        report = {
            "time_range_minutes": minutes,
            "timestamp": datetime.now().isoformat(),
            "agents": {}
        }

        # Analizar métricas de agentes
        agent_response_summary = self.get_metric_summary("agent_response_time_seconds", minutes)
        if agent_response_summary:
            report["overall_response_time"] = {
                "avg_seconds": round(agent_response_summary.avg, 3),
                "p95_seconds": round(agent_response_summary.p95, 3),
                "p99_seconds": round(agent_response_summary.p99, 3)
            }

        # Información específica por agente (requeriría labels granulares)
        # Por simplicidad, usamos métricas agregadas aquí

        return report

    def get_health_status(self) -> Dict[str, Any]:
        """Obtiene estado de salud del sistema"""
        now = time.time()
        last_activity_minutes = (now - self.agent_states["last_activity"]) / 60

        # Métricas de los últimos 5 minutos
        recent_errors = 0
        response_time_summary = self.get_metric_summary("agent_response_time_seconds", 5)

        # Determinar estado de salud
        status = "healthy"
        issues = []

        if last_activity_minutes > 10:
            status = "degraded"
            issues.append("No activity in last 10 minutes")

        if response_time_summary and response_time_summary.p95 > 10:
            status = "degraded"
            issues.append("High response times (p95 > 10s)")

        if recent_errors > 10:
            status = "unhealthy"
            issues.append("High error rate")

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "issues": issues,
            "last_activity_minutes": round(last_activity_minutes, 1),
            "system_metrics": {
                "cpu_percent": self.gauges.get("system_cpu_percent", 0),
                "memory_mb": self.gauges.get("system_memory_mb", 0),
                "memory_percent": self.gauges.get("system_memory_percent", 0)
            },
            "recent_performance": {
                "avg_response_time": response_time_summary.avg if response_time_summary else 0,
                "p95_response_time": response_time_summary.p95 if response_time_summary else 0,
                "total_requests": self.agent_states.get("total_requests", 0),
                "error_count": self.agent_states.get("error_count", 0)
            }
        }


class PrometheusExporter:
    """Exportador de métricas en formato Prometheus"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def export_metrics(self) -> str:
        """Exporta métricas en formato Prometheus"""
        lines = []
        timestamp = int(time.time() * 1000)  # Prometheus usa milisegundos

        # Contadores
        for name, value in self.collector.counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value} {timestamp}")

        # Gauges
        for name, value in self.collector.gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value} {timestamp}")

        # Histogramas (simplificado)
        for name, values in self.collector.histograms.items():
            if values:
                lines.append(f"# TYPE {name} histogram")
                # Buckets simples
                for quantile in [0.5, 0.95, 0.99]:
                    idx = int(len(values) * quantile)
                    if idx < len(values):
                        sorted_values = sorted(values)
                        value = sorted_values[idx]
                        lines.append(f'{name}{{quantile="{quantile}"}} {value} {timestamp}')

        return '\n'.join(lines)

    def get_metrics_endpoint_response(self) -> Dict[str, Any]:
        """Respuesta para endpoint de métricas HTTP"""
        return {
            "content": self.export_metrics(),
            "content_type": "text/plain; version=0.0.4; charset=utf-8"
        }


# Instancia global del colector de métricas
_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Obtiene instancia global del colector de métricas"""
    global _global_metrics_collector

    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()

        # Inicializar métricas del sistema
        _global_metrics_collector.update_system_metrics()

    return _global_metrics_collector


def get_prometheus_exporter() -> PrometheusExporter:
    """Obtiene exportador Prometheus"""
    collector = get_metrics_collector()
    return PrometheusExporter(collector)


# Decorador para métricas automáticas
def track_execution_time(metric_name: str, labels: Dict[str, str] = None):
    """Decorador para trackear tiempo de ejecución automáticamente"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Registrar métrica exitosa
                final_labels = (labels or {}).copy()
                final_labels["success"] = "true"
                collector.observe_histogram(metric_name, execution_time, final_labels)

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Registrar métrica de error
                final_labels = (labels or {}).copy()
                final_labels["success"] = "false"
                final_labels["error_type"] = type(e).__name__
                collector.observe_histogram(metric_name, execution_time, final_labels)

                raise

        return wrapper
    return decorator