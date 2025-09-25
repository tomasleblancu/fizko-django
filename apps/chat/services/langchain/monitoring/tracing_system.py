"""
Sistema de Trazabilidad Completa para Multi-Agent System
Proporciona visibilidad total del flujo de ejecución, tool calls y decisiones
"""

import time
import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import defaultdict
import json


@dataclass
class ToolCallTrace:
    """Traza de llamada a herramienta"""
    tool_name: str
    agent_name: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_info: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None

    def __post_init__(self):
        if self.end_time and not self.execution_time:
            self.execution_time = self.end_time - self.start_time


@dataclass
class AgentTrace:
    """Traza de ejecución de agente"""
    agent_name: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    input_messages: List[Dict[str, Any]] = field(default_factory=list)
    output_messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[ToolCallTrace] = field(default_factory=list)
    routing_info: Dict[str, Any] = field(default_factory=dict)
    memory_operations: List[Dict[str, Any]] = field(default_factory=list)
    error_info: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.end_time and not self.execution_time:
            self.execution_time = self.end_time - self.start_time


@dataclass
class ConversationTrace:
    """Traza completa de conversación"""
    conversation_id: str
    user_id: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    agents_executed: List[AgentTrace] = field(default_factory=list)
    routing_decisions: List[Dict[str, Any]] = field(default_factory=list)
    total_tool_calls: int = 0
    total_memory_operations: int = 0
    success: bool = True
    error_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_total_execution_time(self) -> float:
        """Calcula tiempo total de ejecución"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def get_agent_summary(self) -> Dict[str, Any]:
        """Resumen de agentes ejecutados"""
        summary = defaultdict(int)
        for agent_trace in self.agents_executed:
            summary[agent_trace.agent_name] += 1

        return dict(summary)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Resumen de performance"""
        total_time = self.get_total_execution_time()
        agent_times = [a.execution_time for a in self.agents_executed if a.execution_time]
        tool_times = []

        for agent in self.agents_executed:
            for tool_call in agent.tool_calls:
                if tool_call.execution_time:
                    tool_times.append(tool_call.execution_time)

        return {
            "total_execution_time": round(total_time, 3),
            "agents_executed": len(self.agents_executed),
            "total_tool_calls": self.total_tool_calls,
            "avg_agent_time": round(sum(agent_times) / len(agent_times), 3) if agent_times else 0,
            "avg_tool_time": round(sum(tool_times) / len(tool_times), 3) if tool_times else 0,
            "success_rate": sum(1 for a in self.agents_executed if a.success) / len(self.agents_executed) if self.agents_executed else 1.0
        }


class TracingContext:
    """Contexto de trazabilidad thread-local"""

    def __init__(self):
        self.local = threading.local()

    def get_current_conversation(self) -> Optional[ConversationTrace]:
        """Obtiene conversación actual del contexto"""
        return getattr(self.local, 'conversation_trace', None)

    def set_current_conversation(self, trace: ConversationTrace):
        """Establece conversación actual"""
        self.local.conversation_trace = trace

    def get_current_agent(self) -> Optional[AgentTrace]:
        """Obtiene agente actual del contexto"""
        return getattr(self.local, 'agent_trace', None)

    def set_current_agent(self, trace: AgentTrace):
        """Establece agente actual"""
        self.local.agent_trace = trace

    def clear_context(self):
        """Limpia contexto actual"""
        if hasattr(self.local, 'conversation_trace'):
            del self.local.conversation_trace
        if hasattr(self.local, 'agent_trace'):
            del self.local.agent_trace


class TracingSystem:
    """Sistema central de trazabilidad para multi-agent system"""

    def __init__(self, retention_hours: int = 24):
        self.retention_seconds = retention_hours * 3600
        self.active_traces: Dict[str, ConversationTrace] = {}
        self.completed_traces: Dict[str, ConversationTrace] = {}
        self.context = TracingContext()
        self.lock = threading.RLock()

        # Estadísticas agregadas
        self.stats = {
            "total_conversations": 0,
            "total_agents_executed": 0,
            "total_tool_calls": 0,
            "total_errors": 0,
            "avg_conversation_time": 0.0
        }

    # === GESTIÓN DE CONVERSACIONES ===

    def start_conversation_trace(
        self,
        conversation_id: str,
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> ConversationTrace:
        """Inicia traza de conversación"""
        with self.lock:
            trace = ConversationTrace(
                conversation_id=conversation_id,
                user_id=user_id,
                start_time=time.time(),
                metadata=metadata or {}
            )

            self.active_traces[conversation_id] = trace
            self.context.set_current_conversation(trace)
            self.stats["total_conversations"] += 1

            return trace

    def end_conversation_trace(self, conversation_id: str, success: bool = True, error_info: Dict[str, Any] = None):
        """Finaliza traza de conversación"""
        with self.lock:
            if conversation_id in self.active_traces:
                trace = self.active_traces[conversation_id]
                trace.end_time = time.time()
                trace.success = success
                if error_info:
                    trace.error_info = error_info
                    self.stats["total_errors"] += 1

                # Mover a completadas
                self.completed_traces[conversation_id] = trace
                del self.active_traces[conversation_id]

                # Actualizar estadísticas
                self._update_conversation_stats(trace)

                # Limpiar contexto si es la conversación actual
                current = self.context.get_current_conversation()
                if current and current.conversation_id == conversation_id:
                    self.context.clear_context()

    # === GESTIÓN DE AGENTES ===

    @contextmanager
    def trace_agent_execution(
        self,
        agent_name: str,
        input_messages: List[Any] = None,
        metadata: Dict[str, Any] = None
    ):
        """Context manager para trazar ejecución de agente"""
        # Crear traza de agente
        agent_trace = AgentTrace(
            agent_name=agent_name,
            start_time=time.time(),
            input_messages=self._serialize_messages(input_messages or []),
            metadata=metadata or {}
        )

        # Agregar a conversación actual si existe
        conversation = self.context.get_current_conversation()
        if conversation:
            conversation.agents_executed.append(agent_trace)

        # Establecer como agente actual
        self.context.set_current_agent(agent_trace)

        try:
            yield agent_trace
            # Ejecución exitosa
            agent_trace.success = True
        except Exception as e:
            # Ejecución fallida
            agent_trace.success = False
            agent_trace.error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            raise
        finally:
            # Finalizar traza
            agent_trace.end_time = time.time()
            self.stats["total_agents_executed"] += 1

    def set_agent_output(self, output_messages: List[Any]):
        """Establece mensajes de salida del agente actual"""
        agent_trace = self.context.get_current_agent()
        if agent_trace:
            agent_trace.output_messages = self._serialize_messages(output_messages)

    def add_routing_info(self, routing_info: Dict[str, Any]):
        """Agrega información de routing al agente actual"""
        agent_trace = self.context.get_current_agent()
        if agent_trace:
            agent_trace.routing_info = routing_info

    # === GESTIÓN DE TOOL CALLS ===

    @contextmanager
    def trace_tool_call(
        self,
        tool_name: str,
        agent_name: str = None,
        input_data: Dict[str, Any] = None
    ):
        """Context manager para trazar llamada a herramienta"""
        # Usar agente actual si no se especifica
        if not agent_name:
            current_agent = self.context.get_current_agent()
            agent_name = current_agent.agent_name if current_agent else "unknown"

        # Crear traza de tool call
        tool_trace = ToolCallTrace(
            tool_name=tool_name,
            agent_name=agent_name,
            start_time=time.time(),
            input_data=input_data or {}
        )

        # Agregar a agente actual
        current_agent = self.context.get_current_agent()
        if current_agent:
            current_agent.tool_calls.append(tool_trace)

        # Actualizar contador en conversación
        conversation = self.context.get_current_conversation()
        if conversation:
            conversation.total_tool_calls += 1

        try:
            yield tool_trace
            tool_trace.success = True
        except Exception as e:
            tool_trace.success = False
            tool_trace.error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            raise
        finally:
            tool_trace.end_time = time.time()
            self.stats["total_tool_calls"] += 1

    def set_tool_output(self, output_data: Dict[str, Any]):
        """Establece datos de salida del último tool call"""
        current_agent = self.context.get_current_agent()
        if current_agent and current_agent.tool_calls:
            current_agent.tool_calls[-1].output_data = output_data

    # === OPERACIONES DE MEMORIA ===

    def record_memory_operation(self, operation: str, details: Dict[str, Any] = None):
        """Registra operación de memoria"""
        memory_op = {
            "operation": operation,
            "timestamp": time.time(),
            "details": details or {}
        }

        # Agregar a agente actual
        current_agent = self.context.get_current_agent()
        if current_agent:
            current_agent.memory_operations.append(memory_op)

        # Actualizar contador en conversación
        conversation = self.context.get_current_conversation()
        if conversation:
            conversation.total_memory_operations += 1

    # === DECISIONES DE ROUTING ===

    def record_routing_decision(
        self,
        selected_agent: str,
        method: str,
        confidence: float,
        alternatives: List[Dict[str, Any]] = None,
        decision_time: float = None
    ):
        """Registra decisión de routing"""
        routing_decision = {
            "selected_agent": selected_agent,
            "method": method,
            "confidence": confidence,
            "alternatives": alternatives or [],
            "decision_time": decision_time,
            "timestamp": time.time()
        }

        # Agregar a conversación actual
        conversation = self.context.get_current_conversation()
        if conversation:
            conversation.routing_decisions.append(routing_decision)

    # === CONSULTAS Y ANÁLISIS ===

    def get_conversation_trace(self, conversation_id: str) -> Optional[ConversationTrace]:
        """Obtiene traza de conversación por ID"""
        with self.lock:
            # Buscar en activas primero
            if conversation_id in self.active_traces:
                return self.active_traces[conversation_id]

            # Buscar en completadas
            return self.completed_traces.get(conversation_id)

    def get_recent_conversations(self, limit: int = 50) -> List[ConversationTrace]:
        """Obtiene conversaciones recientes"""
        with self.lock:
            all_traces = list(self.completed_traces.values()) + list(self.active_traces.values())
            # Ordenar por tiempo de inicio (más reciente primero)
            sorted_traces = sorted(all_traces, key=lambda x: x.start_time, reverse=True)
            return sorted_traces[:limit]

    def get_agent_performance_stats(self, agent_name: str = None, hours: int = 24) -> Dict[str, Any]:
        """Obtiene estadísticas de performance de agentes"""
        cutoff_time = time.time() - (hours * 3600)
        agent_executions = []

        # Recopilar ejecuciones de agentes
        for trace in self.completed_traces.values():
            if trace.start_time >= cutoff_time:
                for agent_trace in trace.agents_executed:
                    if not agent_name or agent_trace.agent_name == agent_name:
                        agent_executions.append(agent_trace)

        if not agent_executions:
            return {"message": "No data available for specified criteria"}

        # Calcular estadísticas
        total_executions = len(agent_executions)
        successful_executions = sum(1 for a in agent_executions if a.success)
        execution_times = [a.execution_time for a in agent_executions if a.execution_time]

        # Tool calls por agente
        total_tool_calls = sum(len(a.tool_calls) for a in agent_executions)
        successful_tool_calls = sum(
            sum(1 for tool in a.tool_calls if tool.success)
            for a in agent_executions
        )

        return {
            "agent_name": agent_name or "all",
            "time_range_hours": hours,
            "total_executions": total_executions,
            "success_rate": round(successful_executions / total_executions, 3),
            "avg_execution_time": round(sum(execution_times) / len(execution_times), 3) if execution_times else 0,
            "total_tool_calls": total_tool_calls,
            "tool_call_success_rate": round(successful_tool_calls / total_tool_calls, 3) if total_tool_calls > 0 else 1.0,
            "executions_by_agent": self._get_agent_distribution(agent_executions)
        }

    def get_system_trace_summary(self) -> Dict[str, Any]:
        """Obtiene resumen completo del sistema de trazas"""
        with self.lock:
            # Limpiar trazas antiguas
            self._cleanup_old_traces()

            recent_conversations = self.get_recent_conversations(100)
            recent_performance = [c.get_performance_summary() for c in recent_conversations[:10]]

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_conversations": len(self.active_traces),
                "completed_conversations": len(self.completed_traces),
                "total_stats": self.stats.copy(),
                "recent_performance": recent_performance,
                "system_health": self._calculate_system_health(recent_conversations)
            }

    def export_conversation_trace(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Exporta traza completa de conversación en formato JSON"""
        trace = self.get_conversation_trace(conversation_id)
        if not trace:
            return None

        return {
            "conversation_id": trace.conversation_id,
            "user_id": trace.user_id,
            "start_time": trace.start_time,
            "end_time": trace.end_time,
            "total_execution_time": trace.get_total_execution_time(),
            "success": trace.success,
            "agents_executed": [
                {
                    "agent_name": agent.agent_name,
                    "execution_time": agent.execution_time,
                    "success": agent.success,
                    "tool_calls": [
                        {
                            "tool_name": tool.tool_name,
                            "execution_time": tool.execution_time,
                            "success": tool.success
                        }
                        for tool in agent.tool_calls
                    ],
                    "memory_operations": len(agent.memory_operations)
                }
                for agent in trace.agents_executed
            ],
            "routing_decisions": trace.routing_decisions,
            "performance_summary": trace.get_performance_summary(),
            "agent_summary": trace.get_agent_summary()
        }

    # === MÉTODOS PRIVADOS ===

    def _serialize_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """Serializa mensajes para storage"""
        serialized = []
        for msg in messages:
            if hasattr(msg, 'dict'):
                # LangChain message
                serialized.append(msg.dict())
            elif hasattr(msg, 'content'):
                # Message con content
                serialized.append({
                    "type": getattr(msg, 'type', 'unknown'),
                    "content": str(msg.content)[:500]  # Truncar para evitar logs gigantes
                })
            else:
                # Fallback
                serialized.append({"content": str(msg)[:500]})

        return serialized

    def _update_conversation_stats(self, trace: ConversationTrace):
        """Actualiza estadísticas agregadas"""
        # Actualizar promedio de tiempo de conversación
        total_conversations = self.stats["total_conversations"]
        current_avg = self.stats["avg_conversation_time"]
        execution_time = trace.get_total_execution_time()
        new_avg = ((current_avg * (total_conversations - 1)) + execution_time) / total_conversations
        self.stats["avg_conversation_time"] = new_avg

    def _get_agent_distribution(self, agent_executions: List[AgentTrace]) -> Dict[str, int]:
        """Obtiene distribución de ejecuciones por agente"""
        distribution = defaultdict(int)
        for agent in agent_executions:
            distribution[agent.agent_name] += 1
        return dict(distribution)

    def _calculate_system_health(self, recent_conversations: List[ConversationTrace]) -> Dict[str, Any]:
        """Calcula métricas de salud del sistema"""
        if not recent_conversations:
            return {"status": "no_data"}

        # Últimas 10 conversaciones
        recent_10 = recent_conversations[:10]
        success_rate = sum(1 for c in recent_10 if c.success) / len(recent_10)
        avg_time = sum(c.get_total_execution_time() for c in recent_10) / len(recent_10)

        status = "healthy"
        if success_rate < 0.9:
            status = "degraded"
        if success_rate < 0.7:
            status = "unhealthy"

        return {
            "status": status,
            "success_rate": round(success_rate, 3),
            "avg_response_time": round(avg_time, 3),
            "conversations_analyzed": len(recent_10)
        }

    def _cleanup_old_traces(self):
        """Limpia trazas antiguas según retención"""
        cutoff_time = time.time() - self.retention_seconds
        to_remove = [
            trace_id for trace_id, trace in self.completed_traces.items()
            if trace.start_time < cutoff_time
        ]

        for trace_id in to_remove:
            del self.completed_traces[trace_id]


# Instancia global del sistema de trazas
_global_tracing_system: Optional[TracingSystem] = None


def get_tracing_system() -> TracingSystem:
    """Obtiene instancia global del sistema de trazas"""
    global _global_tracing_system

    if _global_tracing_system is None:
        _global_tracing_system = TracingSystem()

    return _global_tracing_system


# Decoradores para trazabilidad automática
def trace_agent_call(agent_name: str = None):
    """Decorador para trazar automáticamente llamadas de agentes"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracing = get_tracing_system()
            name = agent_name or func.__name__

            with tracing.trace_agent_execution(name):
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_tool_call(tool_name: str = None):
    """Decorador para trazar automáticamente llamadas de herramientas"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracing = get_tracing_system()
            name = tool_name or func.__name__

            with tracing.trace_tool_call(name):
                return func(*args, **kwargs)

        return wrapper
    return decorator