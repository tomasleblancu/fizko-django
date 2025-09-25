"""
Sistema de Logging Estructurado en JSON para Multi-Agent System
Proporciona trazabilidad completa y búsquedas eficientes
"""

import json
import logging
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from pathlib import Path

import psutil


@dataclass
class LogContext:
    """Contexto de logging para trazabilidad"""
    conversation_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class LogEntry:
    """Entrada de log estructurada"""
    timestamp: str
    level: str
    message: str
    logger_name: str
    event_type: str
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    performance: Dict[str, Any]
    system_info: Dict[str, Any]


class StructuredLogger:
    """Logger estructurado con formato JSON para sistemas distribuidos"""

    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger(f"multiagent.{name}")
        self.logger.setLevel(logging.INFO)

        # Thread local storage para contexto
        self.local = threading.local()

        # Configurar handler JSON
        self._setup_json_handler(log_file)

        # Proceso info para métricas de sistema
        self.process = psutil.Process()

    def _setup_json_handler(self, log_file: Optional[str]):
        """Configura handler para salida JSON"""
        if not self.logger.handlers:
            # Handler para archivo
            if log_file:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(logging.Formatter('%(message)s'))
                self.logger.addHandler(file_handler)

            # Handler para consola (desarrollo)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(console_handler)

    def set_context(self, context: LogContext):
        """Establece contexto para el thread actual"""
        self.local.context = context

    def get_context(self) -> Optional[LogContext]:
        """Obtiene contexto del thread actual"""
        return getattr(self.local, 'context', None)

    @contextmanager
    def with_context(self, **kwargs):
        """Context manager para logging con contexto temporal"""
        old_context = self.get_context()

        if old_context:
            # Merge con contexto existente
            new_context = LogContext(
                conversation_id=kwargs.get('conversation_id', old_context.conversation_id),
                user_id=kwargs.get('user_id', old_context.user_id),
                session_id=kwargs.get('session_id', old_context.session_id),
                agent_name=kwargs.get('agent_name', old_context.agent_name),
                tool_name=kwargs.get('tool_name', old_context.tool_name),
                request_id=kwargs.get('request_id', old_context.request_id),
                correlation_id=kwargs.get('correlation_id', old_context.correlation_id)
            )
        else:
            new_context = LogContext(
                conversation_id=kwargs.get('conversation_id', str(uuid.uuid4())),
                **kwargs
            )

        self.set_context(new_context)
        try:
            yield
        finally:
            self.set_context(old_context)

    def _get_system_info(self) -> Dict[str, Any]:
        """Obtiene información del sistema para logging"""
        try:
            return {
                "cpu_percent": self.process.cpu_percent(),
                "memory_mb": round(self.process.memory_info().rss / 1024 / 1024, 2),
                "memory_percent": round(self.process.memory_percent(), 2),
                "thread_count": self.process.num_threads(),
                "pid": self.process.pid
            }
        except Exception:
            return {"error": "Could not get system info"}

    def _create_log_entry(
        self,
        level: str,
        message: str,
        event_type: str,
        metadata: Dict[str, Any] = None,
        performance: Dict[str, Any] = None
    ) -> LogEntry:
        """Crea entrada de log estructurada"""
        context = self.get_context()

        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            message=message,
            logger_name=self.name,
            event_type=event_type,
            context=asdict(context) if context else {},
            metadata=metadata or {},
            performance=performance or {},
            system_info=self._get_system_info()
        )

    def _log(
        self,
        level: int,
        level_name: str,
        message: str,
        event_type: str,
        **kwargs
    ):
        """Método interno de logging"""
        entry = self._create_log_entry(
            level=level_name,
            message=message,
            event_type=event_type,
            metadata=kwargs.get('metadata', {}),
            performance=kwargs.get('performance', {})
        )

        json_message = json.dumps(asdict(entry), ensure_ascii=False, separators=(',', ':'))
        self.logger.log(level, json_message)

    # Métodos de logging por nivel
    def info(self, message: str, event_type: str = "info", **kwargs):
        """Log nivel INFO"""
        self._log(logging.INFO, "INFO", message, event_type, **kwargs)

    def warning(self, message: str, event_type: str = "warning", **kwargs):
        """Log nivel WARNING"""
        self._log(logging.WARNING, "WARNING", message, event_type, **kwargs)

    def error(self, message: str, event_type: str = "error", **kwargs):
        """Log nivel ERROR"""
        self._log(logging.ERROR, "ERROR", message, event_type, **kwargs)

    def debug(self, message: str, event_type: str = "debug", **kwargs):
        """Log nivel DEBUG"""
        self._log(logging.DEBUG, "DEBUG", message, event_type, **kwargs)

    def critical(self, message: str, event_type: str = "critical", **kwargs):
        """Log nivel CRITICAL"""
        self._log(logging.CRITICAL, "CRITICAL", message, event_type, **kwargs)

    # Métodos específicos para eventos del sistema multi-agente
    def log_agent_start(self, agent_name: str, metadata: Dict[str, Any] = None):
        """Log inicio de agente"""
        with self.with_context(agent_name=agent_name):
            self.info(
                f"Agente {agent_name} iniciado",
                event_type="agent_start",
                metadata=metadata or {}
            )

    def log_agent_response(
        self,
        agent_name: str,
        response_time: float,
        success: bool,
        metadata: Dict[str, Any] = None
    ):
        """Log respuesta de agente"""
        with self.with_context(agent_name=agent_name):
            self.info(
                f"Agente {agent_name} {'completado' if success else 'falló'}",
                event_type="agent_response",
                performance={"response_time": response_time, "success": success},
                metadata=metadata or {}
            )

    def log_tool_call(
        self,
        tool_name: str,
        agent_name: str,
        execution_time: float,
        success: bool,
        metadata: Dict[str, Any] = None
    ):
        """Log llamada a herramienta"""
        with self.with_context(agent_name=agent_name, tool_name=tool_name):
            self.info(
                f"Tool {tool_name} ejecutado por {agent_name}",
                event_type="tool_call",
                performance={
                    "execution_time": execution_time,
                    "success": success
                },
                metadata=metadata or {}
            )

    def log_routing_decision(
        self,
        selected_agent: str,
        routing_method: str,
        confidence: float,
        metadata: Dict[str, Any] = None
    ):
        """Log decisión de routing"""
        self.info(
            f"Routing a {selected_agent} via {routing_method}",
            event_type="routing_decision",
            performance={"confidence": confidence, "method": routing_method},
            metadata=metadata or {}
        )

    def log_memory_operation(
        self,
        operation: str,
        agent_name: str,
        execution_time: float,
        metadata: Dict[str, Any] = None
    ):
        """Log operación de memoria"""
        with self.with_context(agent_name=agent_name):
            self.info(
                f"Operación memoria: {operation}",
                event_type="memory_operation",
                performance={"execution_time": execution_time},
                metadata=metadata or {}
            )

    def log_search_operation(
        self,
        query: str,
        results_count: int,
        execution_time: float,
        search_type: str = "vectorial",
        metadata: Dict[str, Any] = None
    ):
        """Log operación de búsqueda"""
        self.info(
            f"Búsqueda {search_type}: {results_count} resultados",
            event_type="search_operation",
            performance={
                "execution_time": execution_time,
                "results_count": results_count,
                "search_type": search_type
            },
            metadata={"query": query[:100], **(metadata or {})}  # Truncar query para logs
        )

    def log_error_with_traceback(
        self,
        error: Exception,
        context_message: str,
        metadata: Dict[str, Any] = None
    ):
        """Log error con traceback completo"""
        import traceback

        self.error(
            context_message,
            event_type="error_with_traceback",
            metadata={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                **(metadata or {})
            }
        )


class MultiAgentLogger:
    """Logger centralizado para todo el sistema multi-agente"""

    def __init__(self, base_log_dir: Optional[str] = None):
        self.base_log_dir = Path(base_log_dir) if base_log_dir else Path("logs")
        self.base_log_dir.mkdir(exist_ok=True)

        # Loggers especializados por componente
        self.loggers = {
            "supervisor": StructuredLogger(
                "supervisor",
                str(self.base_log_dir / "supervisor.jsonl")
            ),
            "routing": StructuredLogger(
                "routing",
                str(self.base_log_dir / "routing.jsonl")
            ),
            "agents": StructuredLogger(
                "agents",
                str(self.base_log_dir / "agents.jsonl")
            ),
            "tools": StructuredLogger(
                "tools",
                str(self.base_log_dir / "tools.jsonl")
            ),
            "memory": StructuredLogger(
                "memory",
                str(self.base_log_dir / "memory.jsonl")
            ),
            "search": StructuredLogger(
                "search",
                str(self.base_log_dir / "search.jsonl")
            ),
            "system": StructuredLogger(
                "system",
                str(self.base_log_dir / "system.jsonl")
            )
        }

    def get_logger(self, component: str) -> StructuredLogger:
        """Obtiene logger para componente específico"""
        return self.loggers.get(component, self.loggers["system"])

    def set_global_context(self, context: LogContext):
        """Establece contexto global para todos los loggers"""
        for logger in self.loggers.values():
            logger.set_context(context)

    @contextmanager
    def conversation_context(self, conversation_id: str, user_id: str = None):
        """Context manager para una conversación completa"""
        context = LogContext(
            conversation_id=conversation_id,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4())
        )

        # Establecer contexto en todos los loggers
        old_contexts = {}
        for name, logger in self.loggers.items():
            old_contexts[name] = logger.get_context()
            logger.set_context(context)

        try:
            yield self
        finally:
            # Restaurar contextos anteriores
            for name, logger in self.loggers.items():
                logger.set_context(old_contexts[name])


# Instancia global del sistema de logging
_global_multiagent_logger: Optional[MultiAgentLogger] = None

def get_structured_logger(component: str = "system") -> StructuredLogger:
    """Obtiene logger estructurado para componente específico"""
    global _global_multiagent_logger

    if _global_multiagent_logger is None:
        # Configurar directorio de logs
        log_dir = Path(__file__).parent.parent / "logs"
        _global_multiagent_logger = MultiAgentLogger(str(log_dir))

    return _global_multiagent_logger.get_logger(component)


def get_multiagent_logger() -> MultiAgentLogger:
    """Obtiene instancia global del sistema de logging"""
    global _global_multiagent_logger

    if _global_multiagent_logger is None:
        log_dir = Path(__file__).parent.parent / "logs"
        _global_multiagent_logger = MultiAgentLogger(str(log_dir))

    return _global_multiagent_logger


# Decorador para logging automático de funciones
def log_function_call(component: str = "system", log_args: bool = False, log_result: bool = False):
    """Decorador para logging automático de llamadas a funciones"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_structured_logger(component)
            start_time = time.time()

            # Preparar metadata
            metadata = {
                "function_name": func.__name__,
                "module": func.__module__
            }

            if log_args:
                metadata["args"] = str(args)[:200]  # Truncar para evitar logs gigantes
                metadata["kwargs"] = str(kwargs)[:200]

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log resultado exitoso
                result_metadata = metadata.copy()
                if log_result:
                    result_metadata["result"] = str(result)[:200]

                logger.info(
                    f"Función {func.__name__} ejecutada exitosamente",
                    event_type="function_call",
                    performance={"execution_time": execution_time},
                    metadata=result_metadata
                )

                return result

            except Exception as e:
                execution_time = time.time() - start_time

                # Log error
                logger.log_error_with_traceback(
                    e,
                    f"Error ejecutando función {func.__name__}",
                    metadata={
                        **metadata,
                        "execution_time": execution_time
                    }
                )
                raise

        return wrapper
    return decorator