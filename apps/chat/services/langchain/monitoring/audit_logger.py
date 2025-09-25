"""
Sistema de Auditoría y Cumplimiento para Multi-Agent System
Mantiene registros detallados de accesos, acciones y datos para auditoría y cumplimiento
"""

import time
import json
import hashlib
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


class AuditEventType(Enum):
    """Tipos de eventos de auditoría"""
    USER_ACCESS = "user_access"
    DATA_ACCESS = "data_access"
    SYSTEM_ACTION = "system_action"
    SECURITY_EVENT = "security_event"
    DATA_MODIFICATION = "data_modification"
    TOOL_EXECUTION = "tool_execution"
    AGENT_EXECUTION = "agent_execution"
    CONFIGURATION_CHANGE = "configuration_change"
    ERROR_EVENT = "error_event"
    COMPLIANCE_EVENT = "compliance_event"


class AuditLevel(Enum):
    """Niveles de auditoría"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Evento de auditoría"""
    id: str
    timestamp: float
    event_type: AuditEventType
    level: AuditLevel
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    action: str
    resource: str
    result: str  # success, failure, partial
    details: Dict[str, Any]
    sensitive_data_hash: Optional[str] = None  # Hash de datos sensibles para trazabilidad
    compliance_tags: List[str] = field(default_factory=list)
    retention_days: int = 2555  # 7 años por defecto para cumplimiento

    def to_audit_log(self) -> Dict[str, Any]:
        """Convierte evento a formato de log de auditoría"""
        return {
            "audit_id": self.id,
            "timestamp": datetime.fromtimestamp(self.timestamp, timezone.utc).isoformat(),
            "event_type": self.event_type.value,
            "level": self.level.value,
            "user_context": {
                "user_id": self.user_id,
                "session_id": self.session_id,
                "ip_address": self.ip_address,
                "user_agent": self.user_agent
            },
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "details": self.details,
            "sensitive_data_hash": self.sensitive_data_hash,
            "compliance_tags": self.compliance_tags,
            "retention_until": datetime.fromtimestamp(
                self.timestamp + (self.retention_days * 24 * 3600),
                timezone.utc
            ).isoformat()
        }


@dataclass
class ComplianceRule:
    """Regla de cumplimiento"""
    name: str
    description: str
    event_types: List[AuditEventType]
    required_fields: List[str]
    data_retention_days: int
    notification_required: bool = False
    severity_threshold: AuditLevel = AuditLevel.MEDIUM
    enabled: bool = True


class SensitiveDataDetector:
    """Detector de datos sensibles para cumplimiento"""

    def __init__(self):
        # Patrones para detectar datos sensibles
        self.patterns = {
            "rut_chileno": r'\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+56|56)?[1-9]\d{8}\b',
            "credit_card": r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            "bank_account": r'\b\d{10,20}\b',
            "address": r'\b\d+\s+[A-Za-z\s]+\s+\d+\b'
        }

    def detect_sensitive_data(self, text: str) -> Dict[str, List[str]]:
        """Detecta datos sensibles en texto"""
        import re
        detected = {}

        for data_type, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected[data_type] = matches

        return detected

    def hash_sensitive_data(self, data: Any) -> str:
        """Genera hash de datos sensibles para trazabilidad"""
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)

        return hashlib.sha256(data_str.encode()).hexdigest()

    def mask_sensitive_data(self, text: str) -> str:
        """Enmascara datos sensibles en texto"""
        import re
        masked_text = text

        # Enmascarar RUTs chilenos
        masked_text = re.sub(r'\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b', 'XX.XXX.XXX-X', masked_text)

        # Enmascarar emails
        masked_text = re.sub(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'xxx@xxx.com',
            masked_text,
            flags=re.IGNORECASE
        )

        # Enmascarar teléfonos
        masked_text = re.sub(r'\b(?:\+56|56)?[1-9]\d{8}\b', '+56 X XXXX XXXX', masked_text)

        return masked_text


class AuditLogger:
    """Sistema central de auditoría y cumplimiento"""

    def __init__(self, audit_log_dir: str = None):
        self.audit_log_dir = Path(audit_log_dir) if audit_log_dir else Path("audit_logs")
        self.audit_log_dir.mkdir(exist_ok=True)

        self.sensitive_detector = SensitiveDataDetector()
        self.events: List[AuditEvent] = []
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.lock = threading.RLock()

        # Configurar reglas de cumplimiento por defecto
        self._setup_default_compliance_rules()

        # Archivos de log por tipo
        self.log_files = {
            "security": self.audit_log_dir / "security_audit.jsonl",
            "data_access": self.audit_log_dir / "data_access_audit.jsonl",
            "system": self.audit_log_dir / "system_audit.jsonl",
            "compliance": self.audit_log_dir / "compliance_audit.jsonl"
        }

    def log_event(
        self,
        event_type: AuditEventType,
        level: AuditLevel,
        action: str,
        resource: str,
        result: str = "success",
        user_id: str = None,
        session_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        details: Dict[str, Any] = None,
        compliance_tags: List[str] = None
    ) -> AuditEvent:
        """Registra evento de auditoría"""
        import uuid

        with self.lock:
            # Procesar detalles para datos sensibles
            processed_details = details.copy() if details else {}
            sensitive_data_hash = None

            if details:
                # Detectar datos sensibles
                details_str = json.dumps(details)
                sensitive_data = self.sensitive_detector.detect_sensitive_data(details_str)

                if sensitive_data:
                    # Generar hash para trazabilidad
                    sensitive_data_hash = self.sensitive_detector.hash_sensitive_data(sensitive_data)

                    # Enmascarar datos sensibles en detalles
                    masked_details_str = self.sensitive_detector.mask_sensitive_data(details_str)
                    try:
                        processed_details = json.loads(masked_details_str)
                    except:
                        processed_details["masked_data"] = masked_details_str

                    # Agregar información sobre datos sensibles detectados
                    processed_details["sensitive_data_types"] = list(sensitive_data.keys())
                    processed_details["sensitive_data_hash"] = sensitive_data_hash

            # Crear evento de auditoría
            event = AuditEvent(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                event_type=event_type,
                level=level,
                user_id=user_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                action=action,
                resource=resource,
                result=result,
                details=processed_details,
                sensitive_data_hash=sensitive_data_hash,
                compliance_tags=compliance_tags or []
            )

            # Almacenar evento
            self.events.append(event)

            # Escribir a archivo de log apropiado
            self._write_audit_log(event)

            # Verificar reglas de cumplimiento
            self._check_compliance_rules(event)

            return event

    def log_user_access(
        self,
        user_id: str,
        action: str,
        resource: str,
        session_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        result: str = "success",
        details: Dict[str, Any] = None
    ):
        """Registra acceso de usuario"""
        self.log_event(
            event_type=AuditEventType.USER_ACCESS,
            level=AuditLevel.MEDIUM,
            action=action,
            resource=resource,
            result=result,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            compliance_tags=["user_access", "authentication"]
        )

    def log_data_access(
        self,
        user_id: str,
        data_type: str,
        data_identifier: str,
        action: str,
        result: str = "success",
        session_id: str = None,
        sensitive_level: str = "normal",
        details: Dict[str, Any] = None
    ):
        """Registra acceso a datos"""
        level = AuditLevel.HIGH if sensitive_level == "high" else AuditLevel.MEDIUM

        audit_details = details.copy() if details else {}
        audit_details.update({
            "data_type": data_type,
            "data_identifier": data_identifier,
            "sensitive_level": sensitive_level
        })

        self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            level=level,
            action=action,
            resource=f"{data_type}:{data_identifier}",
            result=result,
            user_id=user_id,
            session_id=session_id,
            details=audit_details,
            compliance_tags=["data_access", "privacy", sensitive_level]
        )

    def log_system_action(
        self,
        action: str,
        component: str,
        result: str = "success",
        user_id: str = None,
        details: Dict[str, Any] = None
    ):
        """Registra acción del sistema"""
        self.log_event(
            event_type=AuditEventType.SYSTEM_ACTION,
            level=AuditLevel.LOW,
            action=action,
            resource=component,
            result=result,
            user_id=user_id,
            details=details,
            compliance_tags=["system_action"]
        )

    def log_security_event(
        self,
        event_name: str,
        severity: AuditLevel,
        user_id: str = None,
        ip_address: str = None,
        details: Dict[str, Any] = None
    ):
        """Registra evento de seguridad"""
        self.log_event(
            event_type=AuditEventType.SECURITY_EVENT,
            level=severity,
            action=event_name,
            resource="security_system",
            result="detected",
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            compliance_tags=["security", "threat_detection"]
        )

    def log_tool_execution(
        self,
        tool_name: str,
        agent_name: str,
        user_id: str,
        execution_time: float,
        success: bool,
        input_data: Dict[str, Any] = None,
        output_data: Dict[str, Any] = None,
        session_id: str = None
    ):
        """Registra ejecución de herramienta"""
        audit_details = {
            "agent_name": agent_name,
            "execution_time": execution_time,
            "tool_input": input_data,
            "tool_output": output_data
        }

        self.log_event(
            event_type=AuditEventType.TOOL_EXECUTION,
            level=AuditLevel.MEDIUM,
            action="tool_execute",
            resource=f"{agent_name}:{tool_name}",
            result="success" if success else "failure",
            user_id=user_id,
            session_id=session_id,
            details=audit_details,
            compliance_tags=["tool_execution", "agent_action"]
        )

    def log_agent_execution(
        self,
        agent_name: str,
        user_id: str,
        conversation_id: str,
        execution_time: float,
        success: bool,
        messages_processed: int,
        tools_used: List[str] = None,
        session_id: str = None
    ):
        """Registra ejecución de agente"""
        audit_details = {
            "conversation_id": conversation_id,
            "execution_time": execution_time,
            "messages_processed": messages_processed,
            "tools_used": tools_used or []
        }

        self.log_event(
            event_type=AuditEventType.AGENT_EXECUTION,
            level=AuditLevel.MEDIUM,
            action="agent_execute",
            resource=agent_name,
            result="success" if success else "failure",
            user_id=user_id,
            session_id=session_id,
            details=audit_details,
            compliance_tags=["agent_execution", "conversation"]
        )

    def log_data_modification(
        self,
        user_id: str,
        data_type: str,
        operation: str,
        data_identifier: str,
        old_value_hash: str = None,
        new_value_hash: str = None,
        session_id: str = None,
        details: Dict[str, Any] = None
    ):
        """Registra modificación de datos"""
        audit_details = details.copy() if details else {}
        audit_details.update({
            "data_type": data_type,
            "operation": operation,
            "data_identifier": data_identifier,
            "old_value_hash": old_value_hash,
            "new_value_hash": new_value_hash
        })

        self.log_event(
            event_type=AuditEventType.DATA_MODIFICATION,
            level=AuditLevel.HIGH,
            action=operation,
            resource=f"{data_type}:{data_identifier}",
            result="success",
            user_id=user_id,
            session_id=session_id,
            details=audit_details,
            compliance_tags=["data_modification", "data_integrity"]
        )

    def get_audit_trail(
        self,
        user_id: str = None,
        event_type: AuditEventType = None,
        start_time: float = None,
        end_time: float = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Obtiene rastro de auditoría filtrado"""
        with self.lock:
            filtered_events = self.events

            # Filtrar por usuario
            if user_id:
                filtered_events = [e for e in filtered_events if e.user_id == user_id]

            # Filtrar por tipo de evento
            if event_type:
                filtered_events = [e for e in filtered_events if e.event_type == event_type]

            # Filtrar por tiempo
            if start_time:
                filtered_events = [e for e in filtered_events if e.timestamp >= start_time]

            if end_time:
                filtered_events = [e for e in filtered_events if e.timestamp <= end_time]

            # Ordenar por timestamp (más reciente primero) y limitar
            filtered_events.sort(key=lambda x: x.timestamp, reverse=True)
            return filtered_events[:limit]

    def get_compliance_report(self, days: int = 30) -> Dict[str, Any]:
        """Genera reporte de cumplimiento"""
        cutoff_time = time.time() - (days * 24 * 3600)
        recent_events = [e for e in self.events if e.timestamp >= cutoff_time]

        # Estadísticas por tipo de evento
        event_stats = {}
        for event_type in AuditEventType:
            count = len([e for e in recent_events if e.event_type == event_type])
            event_stats[event_type.value] = count

        # Estadísticas por nivel
        level_stats = {}
        for level in AuditLevel:
            count = len([e for e in recent_events if e.level == level])
            level_stats[level.value] = count

        # Eventos de seguridad críticos
        critical_security_events = [
            e for e in recent_events
            if e.event_type == AuditEventType.SECURITY_EVENT and e.level == AuditLevel.CRITICAL
        ]

        # Accesos a datos sensibles
        sensitive_data_accesses = [
            e for e in recent_events
            if e.sensitive_data_hash is not None
        ]

        # Cumplimiento de reglas
        compliance_violations = []
        for rule_name, rule in self.compliance_rules.items():
            if not rule.enabled:
                continue

            rule_events = [
                e for e in recent_events
                if e.event_type in rule.event_types and e.level.value in [l.value for l in [rule.severity_threshold, AuditLevel.HIGH, AuditLevel.CRITICAL]]
            ]

            # Verificar campos requeridos
            for event in rule_events:
                missing_fields = []
                for field in rule.required_fields:
                    if not getattr(event, field, None):
                        missing_fields.append(field)

                if missing_fields:
                    compliance_violations.append({
                        "rule": rule_name,
                        "event_id": event.id,
                        "missing_fields": missing_fields,
                        "timestamp": event.timestamp
                    })

        return {
            "report_period_days": days,
            "total_events": len(recent_events),
            "event_statistics": event_stats,
            "level_statistics": level_stats,
            "critical_security_events": len(critical_security_events),
            "sensitive_data_accesses": len(sensitive_data_accesses),
            "compliance_violations": len(compliance_violations),
            "compliance_details": compliance_violations[:10],  # Primeras 10
            "data_retention_compliance": self._check_data_retention_compliance(),
            "report_timestamp": datetime.now(timezone.utc).isoformat()
        }

    def export_audit_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: List[AuditEventType] = None,
        format: str = "json"
    ) -> str:
        """Exporta logs de auditoría para cumplimiento"""
        start_time = start_date.timestamp()
        end_time = end_date.timestamp()

        filtered_events = []
        for event in self.events:
            if start_time <= event.timestamp <= end_time:
                if not event_types or event.event_type in event_types:
                    filtered_events.append(event)

        if format == "json":
            export_data = {
                "export_metadata": {
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                    "total_events": len(filtered_events),
                    "event_types_filter": [et.value for et in event_types] if event_types else "all"
                },
                "audit_events": [event.to_audit_log() for event in filtered_events]
            }
            return json.dumps(export_data, indent=2)

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                "audit_id", "timestamp", "event_type", "level", "user_id",
                "action", "resource", "result", "details", "compliance_tags"
            ])

            # Data
            for event in filtered_events:
                writer.writerow([
                    event.id,
                    datetime.fromtimestamp(event.timestamp, timezone.utc).isoformat(),
                    event.event_type.value,
                    event.level.value,
                    event.user_id or "",
                    event.action,
                    event.resource,
                    event.result,
                    json.dumps(event.details),
                    ",".join(event.compliance_tags)
                ])

            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _write_audit_log(self, event: AuditEvent):
        """Escribe evento a archivo de log apropiado"""
        # Determinar archivo de log
        if event.event_type == AuditEventType.SECURITY_EVENT:
            log_file = self.log_files["security"]
        elif event.event_type == AuditEventType.DATA_ACCESS:
            log_file = self.log_files["data_access"]
        elif event.compliance_tags:
            log_file = self.log_files["compliance"]
        else:
            log_file = self.log_files["system"]

        # Escribir evento
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event.to_audit_log()) + '\n')
        except Exception as e:
            print(f"Error escribiendo audit log: {e}")

    def _check_compliance_rules(self, event: AuditEvent):
        """Verifica reglas de cumplimiento para evento"""
        for rule_name, rule in self.compliance_rules.items():
            if not rule.enabled:
                continue

            if event.event_type in rule.event_types:
                # Verificar campos requeridos
                missing_fields = []
                for field in rule.required_fields:
                    if not getattr(event, field, None):
                        missing_fields.append(field)

                if missing_fields:
                    # Log violation
                    self.log_event(
                        event_type=AuditEventType.COMPLIANCE_EVENT,
                        level=AuditLevel.HIGH,
                        action="compliance_violation",
                        resource=rule_name,
                        result="violation_detected",
                        details={
                            "rule_violated": rule_name,
                            "original_event_id": event.id,
                            "missing_fields": missing_fields
                        },
                        compliance_tags=["compliance_violation"]
                    )

    def _check_data_retention_compliance(self) -> Dict[str, Any]:
        """Verifica cumplimiento de retención de datos"""
        current_time = time.time()
        expired_events = []
        total_events_checked = 0

        for event in self.events:
            total_events_checked += 1
            retention_until = event.timestamp + (event.retention_days * 24 * 3600)

            if current_time > retention_until:
                expired_events.append({
                    "event_id": event.id,
                    "timestamp": event.timestamp,
                    "retention_days": event.retention_days,
                    "days_overdue": (current_time - retention_until) / (24 * 3600)
                })

        return {
            "total_events_checked": total_events_checked,
            "events_past_retention": len(expired_events),
            "compliance_percentage": ((total_events_checked - len(expired_events)) / total_events_checked * 100) if total_events_checked > 0 else 100,
            "expired_events_sample": expired_events[:5]  # Primeros 5 como muestra
        }

    def _setup_default_compliance_rules(self):
        """Configura reglas de cumplimiento por defecto"""
        # Regla para accesos de usuarios
        self.compliance_rules["user_access_audit"] = ComplianceRule(
            name="user_access_audit",
            description="Auditoría de accesos de usuario requerida",
            event_types=[AuditEventType.USER_ACCESS],
            required_fields=["user_id", "session_id", "ip_address"],
            data_retention_days=2555,  # 7 años
            notification_required=False
        )

        # Regla para accesos a datos sensibles
        self.compliance_rules["sensitive_data_access"] = ComplianceRule(
            name="sensitive_data_access",
            description="Auditoría de accesos a datos sensibles",
            event_types=[AuditEventType.DATA_ACCESS],
            required_fields=["user_id", "sensitive_data_hash"],
            data_retention_days=2555,
            severity_threshold=AuditLevel.HIGH,
            notification_required=True
        )

        # Regla para eventos de seguridad
        self.compliance_rules["security_events"] = ComplianceRule(
            name="security_events",
            description="Registro completo de eventos de seguridad",
            event_types=[AuditEventType.SECURITY_EVENT],
            required_fields=["details", "ip_address"],
            data_retention_days=2555,
            severity_threshold=AuditLevel.HIGH,
            notification_required=True
        )


# Instancia global del logger de auditoría
_global_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Obtiene instancia global del logger de auditoría"""
    global _global_audit_logger

    if _global_audit_logger is None:
        # Configurar directorio de auditoría
        audit_dir = Path(__file__).parent.parent / "audit_logs"
        _global_audit_logger = AuditLogger(str(audit_dir))

    return _global_audit_logger