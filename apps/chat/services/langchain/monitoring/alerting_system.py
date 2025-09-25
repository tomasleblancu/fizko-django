"""
Sistema de Alertas y Notificaciones Automáticas para Multi-Agent System
Detecta problemas y envía notificaciones en tiempo real
"""

import time
import json
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum

# Imports opcionales para funcionalidades de email
try:
    import smtplib
    from email.mime.text import MimeText
    from email.mime.multipart import MimeMultipart
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .metrics_collector import get_metrics_collector
from .tracing_system import get_tracing_system


class AlertLevel(Enum):
    """Niveles de severidad de alerta"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Estados de alerta"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """Alerta del sistema"""
    id: str
    name: str
    level: AlertLevel
    message: str
    timestamp: float
    status: AlertStatus = AlertStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_component: str = "system"
    affected_agents: List[str] = field(default_factory=list)
    resolution_time: Optional[float] = None
    acknowledged_by: Optional[str] = None
    acknowledgement_time: Optional[float] = None

    def get_age_seconds(self) -> float:
        """Obtiene edad de la alerta en segundos"""
        return time.time() - self.timestamp

    def get_duration_seconds(self) -> Optional[float]:
        """Obtiene duración de la alerta (si está resuelta)"""
        if self.resolution_time:
            return self.resolution_time - self.timestamp
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte alerta a diccionario"""
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "metadata": self.metadata,
            "source_component": self.source_component,
            "affected_agents": self.affected_agents,
            "age_seconds": self.get_age_seconds(),
            "duration_seconds": self.get_duration_seconds(),
            "acknowledged_by": self.acknowledged_by
        }


@dataclass
class AlertRule:
    """Regla de alerta"""
    name: str
    condition: Callable[[], bool]
    level: AlertLevel
    message_template: str
    cooldown_seconds: int = 300  # 5 minutos por defecto
    max_alerts_per_hour: int = 10
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_triggered: Optional[float] = None
    trigger_count: int = 0
    hourly_trigger_count: int = 0
    last_hour_reset: float = field(default_factory=time.time)


class NotificationChannel:
    """Canal base para notificaciones"""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    def send(self, alert: Alert) -> bool:
        """Envía notificación (debe ser implementado por subclases)"""
        raise NotImplementedError

    def test_connection(self) -> bool:
        """Prueba la conexión del canal"""
        return True


class EmailNotificationChannel(NotificationChannel):
    """Canal de notificación por email"""

    def __init__(
        self,
        name: str,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        recipients: List[str],
        use_tls: bool = True
    ):
        super().__init__(name)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients
        self.use_tls = use_tls

    def send(self, alert: Alert) -> bool:
        """Envía alerta por email"""
        if not EMAIL_AVAILABLE:
            print("Email functionality not available - skipping email notification")
            return False

        try:
            # Crear mensaje
            msg = MimeMultipart()
            msg['From'] = self.username
            msg['To'] = ', '.join(self.recipients)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.name}"

            # Cuerpo del mensaje
            body = self._format_alert_email(alert)
            msg.attach(MimeText(body, 'html'))

            # Enviar
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()

            return True

        except Exception as e:
            print(f"Error enviando email: {e}")
            return False

    def _format_alert_email(self, alert: Alert) -> str:
        """Formatea alerta para email HTML"""
        color = {
            AlertLevel.INFO: "#17a2b8",
            AlertLevel.WARNING: "#ffc107",
            AlertLevel.ERROR: "#dc3545",
            AlertLevel.CRITICAL: "#dc3545"
        }.get(alert.level, "#6c757d")

        return f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <h2 style="color: {color};">🚨 Alerta del Sistema Multi-Agente</h2>

                <table style="border-collapse: collapse; width: 100%;">
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;"><strong>Nivel</strong></td>
                        <td style="border: 1px solid #ddd; padding: 8px; color: {color};"><strong>{alert.level.value.upper()}</strong></td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;"><strong>Mensaje</strong></td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert.message}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;"><strong>Componente</strong></td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{alert.source_component}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;"><strong>Tiempo</strong></td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{datetime.fromtimestamp(alert.timestamp)}</td>
                    </tr>
                    {f'''<tr>
                        <td style="border: 1px solid #ddd; padding: 8px; background-color: #f2f2f2;"><strong>Agentes Afectados</strong></td>
                        <td style="border: 1px solid #ddd; padding: 8px;">{", ".join(alert.affected_agents)}</td>
                    </tr>''' if alert.affected_agents else ''}
                </table>

                {f'''<h3>Metadatos</h3>
                <pre style="background-color: #f8f9fa; padding: 10px; border-radius: 4px;">{json.dumps(alert.metadata, indent=2)}</pre>''' if alert.metadata else ''}

                <p style="color: #6c757d; font-size: 0.9em;">
                    Este es un mensaje automático del sistema de monitoreo Multi-Agente Fizko.
                </p>
            </div>
        </body>
        </html>
        """


class SlackNotificationChannel(NotificationChannel):
    """Canal de notificación por Slack"""

    def __init__(self, name: str, webhook_url: str):
        super().__init__(name)
        self.webhook_url = webhook_url

    def send(self, alert: Alert) -> bool:
        """Envía alerta a Slack"""
        if not REQUESTS_AVAILABLE:
            print("Requests library not available - skipping Slack notification")
            return False

        try:
            # Mapear colores por nivel
            colors = {
                AlertLevel.INFO: "#36a64f",
                AlertLevel.WARNING: "#ff9900",
                AlertLevel.ERROR: "#ff0000",
                AlertLevel.CRITICAL: "#ff0000"
            }

            # Formato de mensaje Slack
            payload = {
                "attachments": [
                    {
                        "color": colors.get(alert.level, "#36a64f"),
                        "title": f"🚨 {alert.name}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Nivel",
                                "value": alert.level.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Componente",
                                "value": alert.source_component,
                                "short": True
                            },
                            {
                                "title": "Tiempo",
                                "value": datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True
                            }
                        ],
                        "ts": int(alert.timestamp)
                    }
                ]
            }

            if alert.affected_agents:
                payload["attachments"][0]["fields"].append({
                    "title": "Agentes Afectados",
                    "value": ", ".join(alert.affected_agents),
                    "short": False
                })

            # Enviar a Slack
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200

        except Exception as e:
            print(f"Error enviando a Slack: {e}")
            return False


class WebhookNotificationChannel(NotificationChannel):
    """Canal de notificación por webhook genérico"""

    def __init__(self, name: str, webhook_url: str, headers: Dict[str, str] = None):
        super().__init__(name)
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, alert: Alert) -> bool:
        """Envía alerta via webhook"""
        if not REQUESTS_AVAILABLE:
            print("Requests library not available - skipping webhook notification")
            return False

        try:
            payload = alert.to_dict()
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200

        except Exception as e:
            print(f"Error enviando webhook: {e}")
            return False


class AlertingSystem:
    """Sistema central de alertas y notificaciones"""

    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}

        self.lock = threading.RLock()
        self.monitoring_thread = None
        self.running = False

        # Configurar reglas por defecto
        self._setup_default_rules()

    def start_monitoring(self, check_interval_seconds: int = 30):
        """Inicia monitoreo automático de alertas"""
        if self.running:
            return

        self.running = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(check_interval_seconds,),
            daemon=True
        )
        self.monitoring_thread.start()

    def stop_monitoring(self):
        """Detiene monitoreo automático"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

    def add_notification_channel(self, channel: NotificationChannel):
        """Agrega canal de notificación"""
        with self.lock:
            self.notification_channels[channel.name] = channel

    def add_alert_rule(self, rule: AlertRule):
        """Agrega regla de alerta"""
        with self.lock:
            self.alert_rules[rule.name] = rule

    def create_alert(
        self,
        name: str,
        level: AlertLevel,
        message: str,
        source_component: str = "system",
        affected_agents: List[str] = None,
        metadata: Dict[str, Any] = None,
        notify: bool = True
    ) -> Alert:
        """Crea nueva alerta"""
        import uuid

        with self.lock:
            alert = Alert(
                id=str(uuid.uuid4()),
                name=name,
                level=level,
                message=message,
                timestamp=time.time(),
                source_component=source_component,
                affected_agents=affected_agents or [],
                metadata=metadata or {}
            )

            # Agregar a alertas activas
            self.active_alerts[alert.id] = alert
            self.alert_history.append(alert)

            # Enviar notificaciones
            if notify:
                self._send_notifications(alert)

            return alert

    def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resuelve alerta"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.RESOLVED
                alert.resolution_time = time.time()

                # Remover de activas
                del self.active_alerts[alert_id]

                return True

        return False

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Reconoce alerta"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_by = acknowledged_by
                alert.acknowledgement_time = time.time()
                return True

        return False

    def get_active_alerts(self, level: AlertLevel = None) -> List[Alert]:
        """Obtiene alertas activas"""
        with self.lock:
            alerts = list(self.active_alerts.values())
            if level:
                alerts = [a for a in alerts if a.level == level]
            return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_history(self, hours: int = 24, level: AlertLevel = None) -> List[Alert]:
        """Obtiene historial de alertas"""
        cutoff_time = time.time() - (hours * 3600)

        with self.lock:
            alerts = [a for a in self.alert_history if a.timestamp >= cutoff_time]
            if level:
                alerts = [a for a in alerts if a.level == level]
            return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Obtiene estadísticas de alertas"""
        cutoff_time = time.time() - (hours * 3600)
        recent_alerts = [a for a in self.alert_history if a.timestamp >= cutoff_time]

        stats = {
            "total_alerts": len(recent_alerts),
            "active_alerts": len(self.active_alerts),
            "alerts_by_level": {},
            "alerts_by_component": {},
            "avg_resolution_time": 0.0,
            "top_alert_names": {}
        }

        # Contar por nivel
        for level in AlertLevel:
            stats["alerts_by_level"][level.value] = len([a for a in recent_alerts if a.level == level])

        # Contar por componente
        for alert in recent_alerts:
            component = alert.source_component
            stats["alerts_by_component"][component] = stats["alerts_by_component"].get(component, 0) + 1

        # Tiempo promedio de resolución
        resolved_alerts = [a for a in recent_alerts if a.resolution_time]
        if resolved_alerts:
            total_resolution_time = sum(a.get_duration_seconds() for a in resolved_alerts)
            stats["avg_resolution_time"] = total_resolution_time / len(resolved_alerts)

        # Top alertas por nombre
        for alert in recent_alerts:
            name = alert.name
            stats["top_alert_names"][name] = stats["top_alert_names"].get(name, 0) + 1

        return stats

    def _monitoring_loop(self, check_interval: int):
        """Loop principal de monitoreo"""
        while self.running:
            try:
                self._check_alert_rules()
                self._cleanup_old_alerts()
                time.sleep(check_interval)
            except Exception as e:
                print(f"Error en loop de monitoreo: {e}")
                time.sleep(check_interval)

    def _check_alert_rules(self):
        """Verifica reglas de alerta"""
        current_time = time.time()

        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            try:
                # Resetear contador horario si es necesario
                if current_time - rule.last_hour_reset > 3600:
                    rule.hourly_trigger_count = 0
                    rule.last_hour_reset = current_time

                # Verificar cooldown
                if rule.last_triggered and (current_time - rule.last_triggered) < rule.cooldown_seconds:
                    continue

                # Verificar límite por hora
                if rule.hourly_trigger_count >= rule.max_alerts_per_hour:
                    continue

                # Evaluar condición
                if rule.condition():
                    self._trigger_alert_rule(rule)

            except Exception as e:
                print(f"Error evaluando regla {rule_name}: {e}")

    def _trigger_alert_rule(self, rule: AlertRule):
        """Dispara alerta basada en regla"""
        current_time = time.time()

        # Actualizar estadísticas de la regla
        rule.last_triggered = current_time
        rule.trigger_count += 1
        rule.hourly_trigger_count += 1

        # Crear alerta
        message = rule.message_template
        if rule.metadata:
            # Reemplazar variables en el mensaje si existen en metadata
            for key, value in rule.metadata.items():
                message = message.replace(f"{{{key}}}", str(value))

        self.create_alert(
            name=rule.name,
            level=rule.level,
            message=message,
            metadata=rule.metadata.copy()
        )

    def _send_notifications(self, alert: Alert):
        """Envía notificaciones para alerta"""
        for channel_name, channel in self.notification_channels.items():
            if not channel.enabled:
                continue

            try:
                success = channel.send(alert)
                if not success:
                    print(f"Failed to send alert via {channel_name}")
            except Exception as e:
                print(f"Error sending alert via {channel_name}: {e}")

    def _cleanup_old_alerts(self):
        """Limpia alertas antiguas del historial"""
        # Mantener solo últimas 1000 alertas en historial
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

    def _setup_default_rules(self):
        """Configura reglas de alerta por defecto"""

        # Regla: Alto tiempo de respuesta
        def high_response_time():
            metrics = get_metrics_collector()
            summary = metrics.get_metric_summary("agent_response_time_seconds", 5)
            return summary and summary.p95 > 10.0

        self.add_alert_rule(AlertRule(
            name="high_response_time",
            condition=high_response_time,
            level=AlertLevel.WARNING,
            message_template="Tiempo de respuesta alto detectado: P95 > 10 segundos",
            cooldown_seconds=300
        ))

        # Regla: Alta tasa de errores
        def high_error_rate():
            metrics = get_metrics_collector()
            error_count = metrics.counters.get("agent_errors_total", 0)
            total_count = metrics.counters.get("agent_requests_total", 1)
            error_rate = error_count / total_count if total_count > 0 else 0
            return error_rate > 0.1 and total_count > 10  # >10% error rate con al menos 10 requests

        self.add_alert_rule(AlertRule(
            name="high_error_rate",
            condition=high_error_rate,
            level=AlertLevel.ERROR,
            message_template="Alta tasa de errores detectada: >10% de requests fallan",
            cooldown_seconds=600
        ))

        # Regla: Sin actividad
        def no_activity():
            metrics = get_metrics_collector()
            last_activity = metrics.agent_states.get("last_activity", time.time())
            return (time.time() - last_activity) > 1800  # 30 minutos sin actividad

        self.add_alert_rule(AlertRule(
            name="no_activity",
            condition=no_activity,
            level=AlertLevel.WARNING,
            message_template="Sin actividad del sistema en los últimos 30 minutos",
            cooldown_seconds=1800
        ))

        # Regla: Alto uso de memoria
        def high_memory_usage():
            metrics = get_metrics_collector()
            memory_percent = metrics.gauges.get("system_memory_percent", 0)
            return memory_percent > 85.0

        self.add_alert_rule(AlertRule(
            name="high_memory_usage",
            condition=high_memory_usage,
            level=AlertLevel.WARNING,
            message_template="Alto uso de memoria detectado: >85%",
            cooldown_seconds=900
        ))

        # Regla: Múltiples conversaciones fallidas
        def multiple_failed_conversations():
            tracing = get_tracing_system()
            recent_conversations = tracing.get_recent_conversations(20)
            if len(recent_conversations) < 5:
                return False

            failed_count = sum(1 for c in recent_conversations[:10] if not c.success)
            return failed_count >= 3  # 3 o más conversaciones fallidas en las últimas 10

        self.add_alert_rule(AlertRule(
            name="multiple_failed_conversations",
            condition=multiple_failed_conversations,
            level=AlertLevel.ERROR,
            message_template="Múltiples conversaciones fallidas detectadas",
            cooldown_seconds=600
        ))


# Instancia global del sistema de alertas
_global_alerting_system: Optional[AlertingSystem] = None


def get_alerting_system() -> AlertingSystem:
    """Obtiene instancia global del sistema de alertas"""
    global _global_alerting_system

    if _global_alerting_system is None:
        _global_alerting_system = AlertingSystem()

    return _global_alerting_system