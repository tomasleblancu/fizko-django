"""
Monitor de Seguridad Avanzado para Multi-Agent System
Proporciona monitoreo en tiempo real de eventos de seguridad y detección de anomalías
"""

import logging
import time
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import json
import threading
import statistics

from .privilege_manager import get_privilege_manager
from .input_validator import get_input_validator, ValidationResult
from .sandbox_manager import get_sandbox_manager

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Tipos de eventos de seguridad"""
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_DENIED = "authorization_denied"
    SUSPICIOUS_INPUT = "suspicious_input"
    ATTACK_ATTEMPT = "attack_attempt"
    RESOURCE_ABUSE = "resource_abuse"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    SANDBOX_VIOLATION = "sandbox_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class ThreatLevel(Enum):
    """Niveles de amenaza"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Evento de seguridad detectado"""
    event_type: SecurityEventType
    threat_level: ThreatLevel
    timestamp: datetime
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0  # 0.0 - 1.0
    mitigated: bool = False
    mitigation_actions: List[str] = field(default_factory=list)


@dataclass
class UserBehaviorProfile:
    """Perfil de comportamiento de usuario"""
    user_id: str
    session_count: int = 0
    avg_session_duration: float = 0.0
    typical_agents_used: Set[str] = field(default_factory=set)
    typical_query_patterns: List[str] = field(default_factory=list)
    typical_hours: Set[int] = field(default_factory=set)  # Horas típicas de actividad
    failed_authentications: int = 0
    last_activity: Optional[datetime] = None
    risk_score: float = 0.0  # 0.0 = bajo riesgo, 1.0 = alto riesgo


@dataclass
class ThreatIndicator:
    """Indicador de amenaza"""
    name: str
    pattern: str
    threat_level: ThreatLevel
    description: str
    actions: List[str] = field(default_factory=list)


class SecurityMonitor:
    """Monitor principal de seguridad"""

    def __init__(self):
        self.security_events = deque(maxlen=10000)  # Últimos 10K eventos
        self.user_profiles = {}
        self.threat_indicators = {}
        self.rate_limits = defaultdict(lambda: defaultdict(int))
        self.blocked_ips = set()
        self.blocked_users = set()
        self.monitoring_active = False
        self.monitoring_thread = None
        self._event_callbacks = {}

        self._setup_threat_indicators()
        self._setup_rate_limits()

    def _setup_threat_indicators(self):
        """Configura indicadores de amenaza por defecto"""

        # Inyección SQL
        self.threat_indicators["sql_injection"] = ThreatIndicator(
            name="sql_injection",
            pattern=r"(?i)(union\s+select|drop\s+table|delete\s+from)",
            threat_level=ThreatLevel.HIGH,
            description="Intento de inyección SQL",
            actions=["block_input", "log_event", "alert_admin"]
        )

        # XSS
        self.threat_indicators["xss_attempt"] = ThreatIndicator(
            name="xss_attempt",
            pattern=r"<script[^>]*>|javascript:",
            threat_level=ThreatLevel.HIGH,
            description="Intento de Cross-Site Scripting",
            actions=["sanitize_input", "log_event", "monitor_user"]
        )

        # Command Injection
        self.threat_indicators["command_injection"] = ThreatIndicator(
            name="command_injection",
            pattern=r";\s*(rm|del|format|shutdown)",
            threat_level=ThreatLevel.CRITICAL,
            description="Intento de inyección de comandos",
            actions=["block_input", "block_user", "alert_admin"]
        )

        # Acceso a datos sensibles
        self.threat_indicators["sensitive_data_access"] = ThreatIndicator(
            name="sensitive_data_access",
            pattern=r"(rut|email|telefono|direccion)",
            threat_level=ThreatLevel.MEDIUM,
            description="Acceso a datos sensibles",
            actions=["log_event", "anonymize_data"]
        )

        # Comportamiento anómalo
        self.threat_indicators["anomalous_requests"] = ThreatIndicator(
            name="anomalous_requests",
            pattern=r"",  # Se detecta por frecuencia, no por patrón
            threat_level=ThreatLevel.MEDIUM,
            description="Comportamiento de consultas anómalo",
            actions=["rate_limit", "monitor_user"]
        )

    def _setup_rate_limits(self):
        """Configura límites de tasa por defecto"""
        self.rate_limit_config = {
            "requests_per_minute": 60,
            "failed_auth_per_hour": 10,
            "suspicious_queries_per_hour": 5,
            "agent_calls_per_minute": 30,
            "data_queries_per_minute": 20
        }

    def start_monitoring(self):
        """Inicia el monitoreo de seguridad"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            logger.info("Monitor de seguridad iniciado")

    def stop_monitoring(self):
        """Detiene el monitoreo de seguridad"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Monitor de seguridad detenido")

    def _monitoring_loop(self):
        """Bucle principal de monitoreo"""
        while self.monitoring_active:
            try:
                self._check_rate_limits()
                self._update_user_profiles()
                self._detect_anomalies()
                self._cleanup_old_events()
                time.sleep(10)  # Check cada 10 segundos
            except Exception as e:
                logger.error(f"Error en bucle de monitoreo: {e}")

    def record_security_event(self, event: SecurityEvent):
        """Registra un evento de seguridad"""

        # Agregar timestamp si no existe
        if not event.timestamp:
            event.timestamp = datetime.now()

        # Calcular nivel de amenaza automático si no está definido
        if event.threat_level == ThreatLevel.LOW:
            event.threat_level = self._calculate_threat_level(event)

        self.security_events.append(event)

        # Actualizar perfil de usuario
        if event.user_id:
            self._update_user_risk_score(event.user_id, event)

        # Aplicar acciones de mitigación
        self._apply_mitigation_actions(event)

        # Ejecutar callbacks
        self._execute_callbacks(event)

        # Log para auditoría
        self._log_security_event(event)

        logger.warning(f"Evento de seguridad: {event.event_type.value} - {event.threat_level.value}")

    def validate_user_input(self, user_input: str, user_id: Optional[str] = None,
                          session_id: Optional[str] = None) -> Dict[str, Any]:
        """Valida entrada del usuario y detecta amenazas"""

        validator = get_input_validator()
        validation_result = validator.validate_input(user_input)

        # Crear evento si hay problemas de seguridad
        if validation_result.result in [ValidationResult.BLOCKED, ValidationResult.SUSPICIOUS]:
            event = SecurityEvent(
                event_type=SecurityEventType.SUSPICIOUS_INPUT,
                threat_level=ThreatLevel.HIGH if validation_result.result == ValidationResult.BLOCKED else ThreatLevel.MEDIUM,
                timestamp=datetime.now(),
                user_id=user_id,
                session_id=session_id,
                details={
                    "original_input": user_input[:100],  # Primeros 100 chars
                    "issues_found": validation_result.issues_found,
                    "confidence_score": validation_result.confidence_score
                },
                confidence=1.0 - validation_result.confidence_score
            )
            self.record_security_event(event)

        return {
            "is_safe": validation_result.result not in [ValidationResult.BLOCKED],
            "sanitized_input": validation_result.sanitized_input,
            "threat_level": "HIGH" if validation_result.result == ValidationResult.BLOCKED else "MEDIUM",
            "issues": validation_result.issues_found
        }

    def check_permission_access(self, user_id: str, resource: str, action: str,
                              session_id: Optional[str] = None) -> bool:
        """Verifica acceso y registra eventos de seguridad"""

        # Verificar si usuario está bloqueado
        if user_id in self.blocked_users:
            event = SecurityEvent(
                event_type=SecurityEventType.AUTHORIZATION_DENIED,
                threat_level=ThreatLevel.HIGH,
                timestamp=datetime.now(),
                user_id=user_id,
                session_id=session_id,
                details={"resource": resource, "action": action, "reason": "user_blocked"}
            )
            self.record_security_event(event)
            return False

        # Usar privilege manager para verificación real
        privilege_manager = get_privilege_manager()
        if session_id:
            # Simular verificación de permisos (adaptar según implementación real)
            session_info = privilege_manager.get_session_info(session_id)
            if not session_info:
                event = SecurityEvent(
                    event_type=SecurityEventType.AUTHORIZATION_DENIED,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=datetime.now(),
                    user_id=user_id,
                    session_id=session_id,
                    details={"resource": resource, "action": action, "reason": "invalid_session"}
                )
                self.record_security_event(event)
                return False

        return True

    def _calculate_threat_level(self, event: SecurityEvent) -> ThreatLevel:
        """Calcula nivel de amenaza basado en el evento"""

        threat_score = 0.0

        # Factores que aumentan el nivel de amenaza
        if event.event_type in [SecurityEventType.ATTACK_ATTEMPT, SecurityEventType.PRIVILEGE_ESCALATION]:
            threat_score += 0.8

        if event.event_type in [SecurityEventType.SUSPICIOUS_INPUT, SecurityEventType.DATA_EXFILTRATION]:
            threat_score += 0.6

        if event.user_id in self.blocked_users:
            threat_score += 0.3

        # Historial del usuario
        if event.user_id:
            profile = self.user_profiles.get(event.user_id)
            if profile and profile.risk_score > 0.7:
                threat_score += 0.4

        # Determinar nivel
        if threat_score >= 0.8:
            return ThreatLevel.CRITICAL
        elif threat_score >= 0.6:
            return ThreatLevel.HIGH
        elif threat_score >= 0.3:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW

    def _update_user_risk_score(self, user_id: str, event: SecurityEvent):
        """Actualiza el score de riesgo del usuario"""

        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserBehaviorProfile(user_id=user_id)

        profile = self.user_profiles[user_id]

        # Incrementar score basado en tipo de evento
        risk_increment = {
            SecurityEventType.ATTACK_ATTEMPT: 0.3,
            SecurityEventType.SUSPICIOUS_INPUT: 0.2,
            SecurityEventType.AUTHORIZATION_DENIED: 0.1,
            SecurityEventType.RESOURCE_ABUSE: 0.2,
            SecurityEventType.ANOMALOUS_BEHAVIOR: 0.15
        }.get(event.event_type, 0.05)

        profile.risk_score = min(1.0, profile.risk_score + risk_increment)

        # Decay natural del riesgo (disminuye con el tiempo)
        if profile.last_activity:
            hours_since_last = (datetime.now() - profile.last_activity).total_seconds() / 3600
            decay_factor = max(0.0, 0.01 * hours_since_last)
            profile.risk_score = max(0.0, profile.risk_score - decay_factor)

        profile.last_activity = datetime.now()

    def _apply_mitigation_actions(self, event: SecurityEvent):
        """Aplica acciones de mitigación automáticas"""

        actions_taken = []

        # Acciones basadas en nivel de amenaza
        if event.threat_level == ThreatLevel.CRITICAL:
            # Bloquear usuario temporalmente
            if event.user_id:
                self.blocked_users.add(event.user_id)
                actions_taken.append("user_blocked")

            # Alertar administradores
            self._alert_administrators(event)
            actions_taken.append("admin_alerted")

        elif event.threat_level == ThreatLevel.HIGH:
            # Incrementar monitoreo del usuario
            if event.user_id:
                profile = self.user_profiles.get(event.user_id)
                if profile:
                    profile.risk_score = min(1.0, profile.risk_score + 0.2)
                actions_taken.append("increased_monitoring")

        elif event.threat_level == ThreatLevel.MEDIUM:
            # Aplicar rate limiting más estricto
            if event.user_id:
                self.rate_limits[event.user_id]["current_penalty"] = self.rate_limits[event.user_id].get("current_penalty", 0) + 1
                actions_taken.append("rate_limited")

        event.mitigation_actions = actions_taken
        event.mitigated = len(actions_taken) > 0

    def _alert_administrators(self, event: SecurityEvent):
        """Envía alerta a administradores"""

        alert_data = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "threat_level": event.threat_level.value,
            "user_id": event.user_id,
            "details": event.details,
            "confidence": event.confidence
        }

        # Usar sistema de alertas existente
        try:
            from ..monitoring.alerting_system import get_alerting_system
            alerting = get_alerting_system()
            alerting.create_alert(
                name=f"security_{event.event_type.value}",
                level="CRITICAL",
                message=f"Evento de seguridad crítico: {event.event_type.value}",
                source_component="security_monitor",
                metadata=alert_data
            )
        except ImportError:
            logger.critical(f"Alerta de seguridad: {json.dumps(alert_data)}")

    def _check_rate_limits(self):
        """Verifica límites de tasa para todos los usuarios"""

        current_time = datetime.now()
        current_minute = int(current_time.timestamp() // 60)

        # Limpiar contadores antiguos (más de 1 hora)
        for user_id in list(self.rate_limits.keys()):
            user_limits = self.rate_limits[user_id]
            old_keys = [k for k in user_limits.keys() if isinstance(k, int) and k < current_minute - 60]
            for key in old_keys:
                del user_limits[key]

    def _update_user_profiles(self):
        """Actualiza perfiles de comportamiento de usuarios"""

        # Decay natural de risk scores
        for profile in self.user_profiles.values():
            if profile.last_activity:
                hours_since = (datetime.now() - profile.last_activity).total_seconds() / 3600
                if hours_since > 24:  # Un día sin actividad
                    profile.risk_score = max(0.0, profile.risk_score - 0.1)

    def _detect_anomalies(self):
        """Detecta comportamientos anómalos"""

        # Analizar eventos recientes
        recent_events = [e for e in self.security_events
                        if (datetime.now() - e.timestamp).total_seconds() < 3600]

        # Detectar patrones anómalos
        user_event_counts = defaultdict(int)
        for event in recent_events:
            if event.user_id:
                user_event_counts[event.user_id] += 1

        # Usuarios con actividad anómala
        for user_id, event_count in user_event_counts.items():
            if event_count > 20:  # Más de 20 eventos por hora
                anomaly_event = SecurityEvent(
                    event_type=SecurityEventType.ANOMALOUS_BEHAVIOR,
                    threat_level=ThreatLevel.MEDIUM,
                    timestamp=datetime.now(),
                    user_id=user_id,
                    details={"event_count_1h": event_count, "threshold": 20},
                    confidence=0.8
                )
                self.record_security_event(anomaly_event)

    def _cleanup_old_events(self):
        """Limpia eventos antiguos"""

        # Los eventos se manejan automáticamente con deque(maxlen=10000)
        # pero podemos hacer limpieza adicional si es necesario
        cutoff_time = datetime.now() - timedelta(days=7)

        # Limpiar perfiles de usuario inactivos
        inactive_users = [
            user_id for user_id, profile in self.user_profiles.items()
            if profile.last_activity and profile.last_activity < cutoff_time
        ]

        for user_id in inactive_users:
            del self.user_profiles[user_id]

    def _execute_callbacks(self, event: SecurityEvent):
        """Ejecuta callbacks registrados para eventos"""

        event_type = event.event_type
        if event_type in self._event_callbacks:
            for callback in self._event_callbacks[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error ejecutando callback de seguridad: {e}")

    def _log_security_event(self, event: SecurityEvent):
        """Registra evento en el sistema de auditoría"""

        try:
            from ..monitoring.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_security_event(
                event_name=event.event_type.value,
                severity=event.threat_level.value.upper(),
                user_id=event.user_id,
                ip_address=event.ip_address,
                details=event.details
            )
        except ImportError:
            logger.info(f"Security event logged: {event.event_type.value}")

    def register_event_callback(self, event_type: SecurityEventType, callback: Callable):
        """Registra callback para tipo de evento específico"""

        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        self._event_callbacks[event_type].append(callback)

    def get_user_risk_assessment(self, user_id: str) -> Dict[str, Any]:
        """Obtiene evaluación de riesgo de un usuario"""

        profile = self.user_profiles.get(user_id)
        if not profile:
            return {"user_id": user_id, "risk_level": "UNKNOWN", "risk_score": 0.0}

        # Determinar nivel de riesgo
        if profile.risk_score >= 0.8:
            risk_level = "CRITICAL"
        elif profile.risk_score >= 0.6:
            risk_level = "HIGH"
        elif profile.risk_score >= 0.3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "user_id": user_id,
            "risk_level": risk_level,
            "risk_score": profile.risk_score,
            "session_count": profile.session_count,
            "failed_authentications": profile.failed_authentications,
            "last_activity": profile.last_activity.isoformat() if profile.last_activity else None,
            "is_blocked": user_id in self.blocked_users
        }

    def get_security_dashboard_data(self) -> Dict[str, Any]:
        """Genera datos para dashboard de seguridad"""

        # Eventos por tipo en las últimas 24 horas
        recent_events = [e for e in self.security_events
                        if (datetime.now() - e.timestamp).total_seconds() < 86400]

        event_counts = defaultdict(int)
        threat_level_counts = defaultdict(int)

        for event in recent_events:
            event_counts[event.event_type.value] += 1
            threat_level_counts[event.threat_level.value] += 1

        # Top usuarios de riesgo
        high_risk_users = [
            (user_id, profile.risk_score)
            for user_id, profile in self.user_profiles.items()
            if profile.risk_score > 0.5
        ]
        high_risk_users.sort(key=lambda x: x[1], reverse=True)

        return {
            "timestamp": datetime.now().isoformat(),
            "events_last_24h": len(recent_events),
            "events_by_type": dict(event_counts),
            "events_by_threat_level": dict(threat_level_counts),
            "blocked_users": len(self.blocked_users),
            "blocked_ips": len(self.blocked_ips),
            "high_risk_users": high_risk_users[:10],  # Top 10
            "monitoring_active": self.monitoring_active,
            "total_user_profiles": len(self.user_profiles)
        }


# Singleton global
_security_monitor = None


def get_security_monitor() -> SecurityMonitor:
    """Obtiene la instancia global del monitor de seguridad"""
    global _security_monitor
    if _security_monitor is None:
        _security_monitor = SecurityMonitor()
    return _security_monitor


def security_check(check_input: bool = True, check_permissions: bool = True):
    """Decorador para verificaciones automáticas de seguridad"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = get_security_monitor()

            # Extraer información del contexto
            user_id = kwargs.get('user_id')
            session_id = kwargs.get('session_id')

            # Validar entradas si está habilitado
            if check_input:
                for arg in args:
                    if isinstance(arg, str):
                        validation = monitor.validate_user_input(arg, user_id, session_id)
                        if not validation["is_safe"]:
                            raise ValueError(f"Entrada bloqueada por seguridad: {validation['issues']}")

            # Verificar permisos si está habilitado
            if check_permissions and user_id:
                resource = func.__name__
                if not monitor.check_permission_access(user_id, resource, "execute", session_id):
                    raise PermissionError("Acceso denegado por políticas de seguridad")

            return func(*args, **kwargs)

        return wrapper
    return decorator