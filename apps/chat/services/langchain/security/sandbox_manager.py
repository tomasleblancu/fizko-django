"""
Sistema de Sandboxing y Aislamiento para Multi-Agent System
Proporciona aislamiento seguro para la ejecución de agentes y herramientas
"""

import logging
import os
import tempfile
import subprocess
import time
import signal
import resource
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import threading
import queue
import psutil
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class IsolationLevel(Enum):
    """Niveles de aislamiento disponibles"""
    NONE = "none"              # Sin aislamiento
    PROCESS = "process"        # Proceso separado
    CONTAINER = "container"    # Contenedor Docker (si está disponible)
    CHROOT = "chroot"         # Chroot jail
    NAMESPACE = "namespace"    # Linux namespaces


@dataclass
class ResourceLimits:
    """Límites de recursos para sandboxes"""
    max_cpu_percent: float = 50.0      # % máximo de CPU
    max_memory_mb: int = 512           # MB máximos de memoria
    max_execution_time: int = 30       # Segundos máximos de ejecución
    max_file_descriptors: int = 100    # Descriptores de archivo máximos
    max_processes: int = 10            # Procesos máximos
    allowed_network: bool = False      # Acceso a red
    read_only_filesystem: bool = True  # Sistema de archivos de solo lectura


@dataclass
class SandboxConfiguration:
    """Configuración de sandbox para un tipo de agente"""
    agent_type: str
    isolation_level: IsolationLevel
    resource_limits: ResourceLimits
    allowed_imports: List[str] = field(default_factory=list)
    blocked_imports: List[str] = field(default_factory=list)
    allowed_functions: List[str] = field(default_factory=list)
    blocked_functions: List[str] = field(default_factory=list)
    environment_variables: Dict[str, str] = field(default_factory=dict)
    working_directory: Optional[str] = None
    temp_directory: Optional[str] = None


class SandboxedExecution:
    """Contexto para ejecución sandboxeada"""

    def __init__(self, config: SandboxConfiguration, session_id: str):
        self.config = config
        self.session_id = session_id
        self.process = None
        self.start_time = None
        self.temp_dir = None
        self.monitoring_thread = None
        self._should_monitor = False
        self.resource_usage = {}

    def __enter__(self):
        self.setup_sandbox()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_sandbox()

    def setup_sandbox(self):
        """Configura el entorno de sandbox"""

        self.start_time = time.time()

        # Crear directorio temporal si es necesario
        if self.config.isolation_level != IsolationLevel.NONE:
            self.temp_dir = tempfile.mkdtemp(prefix=f"sandbox_{self.session_id}_")
            logger.info(f"Sandbox creado: {self.temp_dir}")

        # Iniciar monitoreo de recursos
        self._should_monitor = True
        self.monitoring_thread = threading.Thread(target=self._monitor_resources)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

    def cleanup_sandbox(self):
        """Limpia el entorno de sandbox"""

        # Detener monitoreo
        self._should_monitor = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)

        # Terminar proceso si está ejecutándose
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

        # Limpiar directorio temporal
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Sandbox limpiado: {self.temp_dir}")
            except Exception as e:
                logger.error(f"Error limpiando sandbox: {e}")

    def execute_function(self, function: Callable, *args, **kwargs) -> Any:
        """Ejecuta una función en el sandbox"""

        if self.config.isolation_level == IsolationLevel.NONE:
            return self._execute_direct(function, *args, **kwargs)
        elif self.config.isolation_level == IsolationLevel.PROCESS:
            return self._execute_in_process(function, *args, **kwargs)
        else:
            logger.warning(f"Nivel de aislamiento {self.config.isolation_level} no implementado")
            return self._execute_direct(function, *args, **kwargs)

    def _execute_direct(self, function: Callable, *args, **kwargs) -> Any:
        """Ejecución directa con límites de recursos básicos"""

        # Aplicar límites de recursos básicos
        original_limits = self._apply_resource_limits()

        try:
            # Verificar tiempo máximo de ejecución
            start_time = time.time()
            result = function(*args, **kwargs)
            execution_time = time.time() - start_time

            if execution_time > self.config.resource_limits.max_execution_time:
                raise TimeoutError(f"Ejecución excedió tiempo límite: {execution_time:.2f}s")

            return result

        finally:
            # Restaurar límites originales
            self._restore_resource_limits(original_limits)

    def _execute_in_process(self, function: Callable, *args, **kwargs) -> Any:
        """Ejecución en proceso separado"""

        # Crear cola para resultados
        result_queue = queue.Queue()

        def worker():
            try:
                # Aplicar límites de recursos
                self._apply_resource_limits_to_process()

                # Ejecutar función
                result = function(*args, **kwargs)
                result_queue.put({"success": True, "result": result})
            except Exception as e:
                result_queue.put({"success": False, "error": str(e)})

        # Ejecutar en hilo separado (simulando proceso)
        worker_thread = threading.Thread(target=worker)
        worker_thread.daemon = True
        worker_thread.start()

        # Esperar resultado con timeout
        try:
            result_data = result_queue.get(timeout=self.config.resource_limits.max_execution_time)
            worker_thread.join(timeout=1)

            if result_data["success"]:
                return result_data["result"]
            else:
                raise RuntimeError(result_data["error"])

        except queue.Empty:
            raise TimeoutError(f"Ejecución excedió tiempo límite")

    def _apply_resource_limits(self) -> Dict[str, Any]:
        """Aplica límites de recursos al proceso actual"""

        original_limits = {}

        try:
            # Límite de memoria (si está disponible)
            if hasattr(resource, 'RLIMIT_AS'):
                original_limits['memory'] = resource.getrlimit(resource.RLIMIT_AS)
                max_memory_bytes = self.config.resource_limits.max_memory_mb * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (max_memory_bytes, max_memory_bytes))

            # Límite de tiempo de CPU
            original_limits['cpu_time'] = resource.getrlimit(resource.RLIMIT_CPU)
            max_cpu_time = self.config.resource_limits.max_execution_time
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu_time, max_cpu_time))

            # Límite de descriptores de archivo
            original_limits['files'] = resource.getrlimit(resource.RLIMIT_NOFILE)
            max_files = self.config.resource_limits.max_file_descriptors
            resource.setrlimit(resource.RLIMIT_NOFILE, (max_files, max_files))

        except Exception as e:
            logger.warning(f"No se pudieron aplicar todos los límites de recursos: {e}")

        return original_limits

    def _restore_resource_limits(self, original_limits: Dict[str, Any]):
        """Restaura límites de recursos originales"""

        try:
            if 'memory' in original_limits:
                resource.setrlimit(resource.RLIMIT_AS, original_limits['memory'])
            if 'cpu_time' in original_limits:
                resource.setrlimit(resource.RLIMIT_CPU, original_limits['cpu_time'])
            if 'files' in original_limits:
                resource.setrlimit(resource.RLIMIT_NOFILE, original_limits['files'])
        except Exception as e:
            logger.warning(f"Error restaurando límites de recursos: {e}")

    def _apply_resource_limits_to_process(self):
        """Aplica límites de recursos específicos para proceso separado"""

        try:
            # Obtener proceso actual
            process = psutil.Process()

            # Límites de CPU (afinidad si está disponible)
            if hasattr(process, 'cpu_affinity'):
                cpu_count = psutil.cpu_count()
                max_cpus = max(1, int(cpu_count * self.config.resource_limits.max_cpu_percent / 100))
                available_cpus = list(range(max_cpus))
                process.cpu_affinity(available_cpus)

            # Prioridad de proceso (nice)
            if hasattr(process, 'nice'):
                process.nice(10)  # Baja prioridad

        except Exception as e:
            logger.warning(f"No se pudieron aplicar límites de proceso: {e}")

    def _monitor_resources(self):
        """Monitorea el uso de recursos en tiempo real"""

        while self._should_monitor:
            try:
                if self.process:
                    process = psutil.Process(self.process.pid)
                else:
                    process = psutil.Process()

                # Recopilar métricas
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024

                self.resource_usage = {
                    "timestamp": datetime.now().isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds() if hasattr(process, 'num_fds') else 0
                }

                # Verificar límites y actuar si es necesario
                if memory_mb > self.config.resource_limits.max_memory_mb:
                    logger.warning(f"Límite de memoria excedido: {memory_mb:.1f}MB")
                    self._terminate_execution("memory_limit_exceeded")
                    break

                if cpu_percent > self.config.resource_limits.max_cpu_percent:
                    logger.warning(f"Límite de CPU excedido: {cpu_percent:.1f}%")

                # Verificar tiempo máximo
                if (self.start_time and
                    time.time() - self.start_time > self.config.resource_limits.max_execution_time):
                    logger.warning("Tiempo máximo de ejecución excedido")
                    self._terminate_execution("time_limit_exceeded")
                    break

                time.sleep(0.5)  # Monitoreo cada 500ms

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception as e:
                logger.error(f"Error en monitoreo de recursos: {e}")
                break

    def _terminate_execution(self, reason: str):
        """Termina la ejecución por violación de límites"""

        logger.error(f"Terminando ejecución: {reason}")

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

        # Log para auditoría
        try:
            from ..monitoring.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_security_event(
                event_name="sandbox_execution_terminated",
                severity="HIGH",
                details={
                    "session_id": self.session_id,
                    "reason": reason,
                    "resource_usage": self.resource_usage
                }
            )
        except ImportError:
            logger.warning(f"Sandbox execution terminated: {reason}")

    def get_resource_usage(self) -> Dict[str, Any]:
        """Obtiene uso actual de recursos"""
        return self.resource_usage.copy()


class SandboxManager:
    """Gestor de sandboxes para el sistema multi-agente"""

    def __init__(self):
        self.configurations = {}
        self.active_sandboxes = {}
        self._setup_default_configurations()

    def _setup_default_configurations(self):
        """Configura sandboxes por defecto para diferentes tipos de agentes"""

        # Configuración para agente SII (acceso limitado)
        sii_limits = ResourceLimits(
            max_cpu_percent=30.0,
            max_memory_mb=256,
            max_execution_time=20,
            max_file_descriptors=50,
            max_processes=5,
            allowed_network=True,  # Necesita acceso a SII
            read_only_filesystem=True
        )

        self.configurations["sii_agent"] = SandboxConfiguration(
            agent_type="sii_agent",
            isolation_level=IsolationLevel.PROCESS,
            resource_limits=sii_limits,
            allowed_imports=[
                "requests", "selenium", "beautifulsoup4", "pandas", "datetime",
                "json", "logging", "apps.sii", "apps.documents"
            ],
            blocked_imports=[
                "os", "subprocess", "shutil", "socket", "ftplib", "urllib",
                "__import__", "exec", "eval"
            ],
            blocked_functions=[
                "exec", "eval", "compile", "open", "__import__"
            ]
        )

        # Configuración para agente DTE (más restrictivo)
        dte_limits = ResourceLimits(
            max_cpu_percent=25.0,
            max_memory_mb=128,
            max_execution_time=15,
            max_file_descriptors=30,
            max_processes=3,
            allowed_network=False,  # Solo acceso a BD
            read_only_filesystem=True
        )

        self.configurations["dte_agent"] = SandboxConfiguration(
            agent_type="dte_agent",
            isolation_level=IsolationLevel.PROCESS,
            resource_limits=dte_limits,
            allowed_imports=[
                "pandas", "datetime", "json", "logging",
                "apps.documents", "apps.companies"
            ],
            blocked_imports=[
                "os", "subprocess", "shutil", "socket", "requests",
                "urllib", "__import__", "exec", "eval"
            ],
            blocked_functions=[
                "exec", "eval", "compile", "open", "__import__"
            ]
        )

        # Configuración para supervisor (mínimo)
        supervisor_limits = ResourceLimits(
            max_cpu_percent=15.0,
            max_memory_mb=64,
            max_execution_time=10,
            max_file_descriptors=20,
            max_processes=2,
            allowed_network=False,
            read_only_filesystem=True
        )

        self.configurations["supervisor_agent"] = SandboxConfiguration(
            agent_type="supervisor_agent",
            isolation_level=IsolationLevel.PROCESS,
            resource_limits=supervisor_limits,
            allowed_imports=["json", "logging", "datetime"],
            blocked_imports=[
                "os", "subprocess", "shutil", "socket", "requests",
                "urllib", "__import__", "exec", "eval", "pandas"
            ],
            blocked_functions=[
                "exec", "eval", "compile", "open", "__import__"
            ]
        )

    @contextmanager
    def create_sandbox(self, agent_type: str, session_id: str) -> SandboxedExecution:
        """Crea un sandbox para un agente específico"""

        config = self.configurations.get(agent_type)
        if not config:
            logger.warning(f"No hay configuración de sandbox para: {agent_type}")
            # Usar configuración más restrictiva por defecto
            config = self.configurations["supervisor_agent"]

        sandbox = SandboxedExecution(config, session_id)

        # Registrar sandbox activo
        sandbox_id = f"{agent_type}_{session_id}_{int(time.time())}"
        self.active_sandboxes[sandbox_id] = {
            "sandbox": sandbox,
            "agent_type": agent_type,
            "session_id": session_id,
            "created_at": datetime.now()
        }

        try:
            with sandbox:
                yield sandbox
        finally:
            # Limpiar registro
            self.active_sandboxes.pop(sandbox_id, None)

    def execute_safely(self, agent_type: str, session_id: str,
                      function: Callable, *args, **kwargs) -> Any:
        """Ejecuta una función de manera segura en un sandbox"""

        with self.create_sandbox(agent_type, session_id) as sandbox:
            return sandbox.execute_function(function, *args, **kwargs)

    def get_active_sandboxes(self) -> Dict[str, Any]:
        """Obtiene información de sandboxes activos"""

        active_info = {}
        for sandbox_id, info in self.active_sandboxes.items():
            sandbox = info["sandbox"]
            active_info[sandbox_id] = {
                "agent_type": info["agent_type"],
                "session_id": info["session_id"],
                "created_at": info["created_at"].isoformat(),
                "resource_usage": sandbox.get_resource_usage(),
                "isolation_level": sandbox.config.isolation_level.value,
                "resource_limits": {
                    "max_cpu_percent": sandbox.config.resource_limits.max_cpu_percent,
                    "max_memory_mb": sandbox.config.resource_limits.max_memory_mb,
                    "max_execution_time": sandbox.config.resource_limits.max_execution_time
                }
            }

        return active_info

    def cleanup_expired_sandboxes(self):
        """Limpia sandboxes expirados o inactivos"""

        current_time = datetime.now()
        expired_sandboxes = []

        for sandbox_id, info in self.active_sandboxes.items():
            # Sandboxes activos por más de 1 hora se consideran expirados
            if (current_time - info["created_at"]).total_seconds() > 3600:
                expired_sandboxes.append(sandbox_id)

        for sandbox_id in expired_sandboxes:
            info = self.active_sandboxes.pop(sandbox_id, None)
            if info:
                try:
                    info["sandbox"].cleanup_sandbox()
                    logger.info(f"Sandbox expirado limpiado: {sandbox_id}")
                except Exception as e:
                    logger.error(f"Error limpiando sandbox {sandbox_id}: {e}")

    def get_security_report(self) -> Dict[str, Any]:
        """Genera reporte de seguridad de sandboxes"""

        return {
            "timestamp": datetime.now().isoformat(),
            "active_sandboxes": len(self.active_sandboxes),
            "configurations_available": len(self.configurations),
            "sandbox_details": self.get_active_sandboxes()
        }

    def validate_function_safety(self, function: Callable, agent_type: str) -> Dict[str, Any]:
        """Valida si una función es segura para ejecutar en sandbox"""

        config = self.configurations.get(agent_type, self.configurations["supervisor_agent"])

        validation_result = {
            "is_safe": True,
            "issues": [],
            "recommendations": []
        }

        # Verificar nombre de función
        function_name = getattr(function, '__name__', str(function))
        if function_name in config.blocked_functions:
            validation_result["is_safe"] = False
            validation_result["issues"].append(f"Función bloqueada: {function_name}")

        # Verificar módulo de origen (si está disponible)
        if hasattr(function, '__module__'):
            module_name = function.__module__
            if module_name in config.blocked_imports:
                validation_result["is_safe"] = False
                validation_result["issues"].append(f"Módulo bloqueado: {module_name}")

        return validation_result


# Singleton global
_sandbox_manager = None


def get_sandbox_manager() -> SandboxManager:
    """Obtiene la instancia global del gestor de sandboxes"""
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager


def sandbox_execution(agent_type: str):
    """Decorador para ejecución automática en sandbox"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Buscar session_id en argumentos
            session_id = kwargs.get('session_id', 'default_session')

            sandbox_manager = get_sandbox_manager()
            return sandbox_manager.execute_safely(agent_type, session_id, func, *args, **kwargs)

        return wrapper
    return decorator