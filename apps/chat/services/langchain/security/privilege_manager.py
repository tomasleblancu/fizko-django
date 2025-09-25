"""
Sistema de Gestión de Privilegios - Principio de Menor Privilegio
Controla y limita los permisos de acceso de cada agente y herramienta
"""

import logging
from typing import Dict, List, Set, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import hashlib
from functools import wraps

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Niveles de permisos disponibles"""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SYSTEM = "system"


class ResourceType(Enum):
    """Tipos de recursos del sistema"""
    DATABASE = "database"
    SII_API = "sii_api"
    DOCUMENT = "document"
    USER_DATA = "user_data"
    COMPANY_DATA = "company_data"
    TAX_DATA = "tax_data"
    FINANCIAL_DATA = "financial_data"
    SYSTEM_CONFIG = "system_config"
    EXTERNAL_API = "external_api"
    FILE_SYSTEM = "file_system"


@dataclass
class Permission:
    """Representa un permiso específico"""
    resource_type: ResourceType
    resource_id: Optional[str] = None  # ID específico del recurso
    level: PermissionLevel = PermissionLevel.NONE
    conditions: Dict[str, Any] = field(default_factory=dict)  # Condiciones adicionales
    expires_at: Optional[datetime] = None
    granted_by: Optional[str] = None
    granted_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentRole:
    """Define el rol de un agente y sus permisos base"""
    name: str
    description: str
    base_permissions: List[Permission] = field(default_factory=list)
    max_session_duration: Optional[timedelta] = None
    allowed_tools: Set[str] = field(default_factory=set)
    data_access_policy: Dict[str, Any] = field(default_factory=dict)


class PrivilegeManager:
    """Gestor central de privilegios y permisos"""

    def __init__(self):
        self.roles: Dict[str, AgentRole] = {}
        self.agent_permissions: Dict[str, List[Permission]] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.access_log: List[Dict[str, Any]] = []
        self._setup_default_roles()

    def _setup_default_roles(self):
        """Configura los roles por defecto del sistema"""

        # Rol de agente SII - Solo lectura de datos SII y documentos
        sii_role = AgentRole(
            name="sii_agent",
            description="Agente especializado en consultas SII",
            base_permissions=[
                Permission(ResourceType.SII_API, level=PermissionLevel.READ),
                Permission(ResourceType.DOCUMENT, level=PermissionLevel.READ,
                          conditions={"document_type": ["dte", "factura", "boleta"]}),
                Permission(ResourceType.TAX_DATA, level=PermissionLevel.READ),
                Permission(ResourceType.COMPANY_DATA, level=PermissionLevel.READ,
                          conditions={"fields": ["rut", "razon_social", "giro"]})
            ],
            max_session_duration=timedelta(hours=2),
            allowed_tools={"search_sii_documents", "get_tax_info", "validate_rut"},
            data_access_policy={
                "anonymize_personal_data": True,
                "max_records_per_query": 100,
                "allowed_date_range_days": 365
            }
        )

        # Rol de agente DTE - Acceso a documentos tributarios
        dte_role = AgentRole(
            name="dte_agent",
            description="Agente especializado en documentos tributarios electrónicos",
            base_permissions=[
                Permission(ResourceType.DOCUMENT, level=PermissionLevel.READ),
                Permission(ResourceType.FINANCIAL_DATA, level=PermissionLevel.READ,
                          conditions={"data_types": ["amounts", "taxes", "totals"]}),
                Permission(ResourceType.COMPANY_DATA, level=PermissionLevel.READ,
                          conditions={"fields": ["rut", "razon_social"]})
            ],
            max_session_duration=timedelta(hours=1),
            allowed_tools={"search_documents_by_criteria", "get_document_stats_summary"},
            data_access_policy={
                "anonymize_personal_data": True,
                "max_records_per_query": 50
            }
        )

        # Rol de supervisor - Permisos de coordinación
        supervisor_role = AgentRole(
            name="supervisor_agent",
            description="Agente supervisor para coordinación",
            base_permissions=[
                Permission(ResourceType.USER_DATA, level=PermissionLevel.READ,
                          conditions={"fields": ["user_id", "session_id"]}),
                Permission(ResourceType.SYSTEM_CONFIG, level=PermissionLevel.READ)
            ],
            max_session_duration=timedelta(hours=4),
            allowed_tools={"route_query", "get_agent_status"},
            data_access_policy={
                "anonymize_personal_data": True,
                "log_all_decisions": True
            }
        )

        # Registrar roles
        self.roles["sii_agent"] = sii_role
        self.roles["dte_agent"] = dte_role
        self.roles["supervisor_agent"] = supervisor_role

    def create_agent_session(self, agent_name: str, user_id: str,
                           context: Optional[Dict[str, Any]] = None) -> str:
        """Crea una sesión de agente con permisos específicos"""

        # Determinar el rol del agente
        agent_role = None
        for role_name, role in self.roles.items():
            if role_name in agent_name.lower():
                agent_role = role
                break

        if not agent_role:
            logger.warning(f"No se encontró rol para agente: {agent_name}")
            agent_role = self.roles.get("supervisor_agent")

        # Generar ID de sesión único
        session_data = f"{agent_name}:{user_id}:{datetime.now().isoformat()}"
        session_id = hashlib.sha256(session_data.encode()).hexdigest()[:16]

        # Configurar sesión
        expires_at = None
        if agent_role.max_session_duration:
            expires_at = datetime.now() + agent_role.max_session_duration

        session = {
            "session_id": session_id,
            "agent_name": agent_name,
            "user_id": user_id,
            "role": agent_role.name,
            "permissions": [p.__dict__ for p in agent_role.base_permissions],
            "allowed_tools": list(agent_role.allowed_tools),
            "data_access_policy": agent_role.data_access_policy.copy(),
            "created_at": datetime.now(),
            "expires_at": expires_at,
            "context": context or {},
            "access_count": 0,
            "last_access": datetime.now()
        }

        self.active_sessions[session_id] = session

        # Log de auditoría
        self._log_access("session_created", {
            "session_id": session_id,
            "agent_name": agent_name,
            "user_id": user_id,
            "role": agent_role.name
        })

        logger.info(f"Sesión creada para agente {agent_name}: {session_id}")
        return session_id

    def check_permission(self, session_id: str, resource_type: ResourceType,
                        resource_id: Optional[str] = None,
                        action: PermissionLevel = PermissionLevel.READ) -> bool:
        """Verifica si una sesión tiene permisos para acceder a un recurso"""

        session = self.active_sessions.get(session_id)
        if not session:
            logger.warning(f"Sesión no encontrada: {session_id}")
            return False

        # Verificar expiración de sesión
        if session.get("expires_at") and datetime.now() > session["expires_at"]:
            logger.warning(f"Sesión expirada: {session_id}")
            self._terminate_session(session_id)
            return False

        # Actualizar último acceso
        session["last_access"] = datetime.now()
        session["access_count"] += 1

        # Verificar permisos
        for perm_data in session["permissions"]:
            perm = Permission(**perm_data)

            # Verificar tipo de recurso
            if perm.resource_type.value != resource_type.value:
                continue

            # Verificar ID específico si se proporciona
            if resource_id and perm.resource_id and perm.resource_id != resource_id:
                continue

            # Verificar nivel de permiso
            if not self._check_permission_level(perm.level, action):
                continue

            # Verificar condiciones adicionales
            if perm.conditions and not self._check_conditions(perm.conditions, session):
                continue

            # Verificar expiración del permiso
            if perm.expires_at and datetime.now() > perm.expires_at:
                continue

            # Log de acceso exitoso
            self._log_access("permission_granted", {
                "session_id": session_id,
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "action": action.value,
                "permission_level": perm.level.value
            })

            return True

        # Log de acceso denegado
        self._log_access("permission_denied", {
            "session_id": session_id,
            "agent_name": session["agent_name"],
            "user_id": session["user_id"],
            "resource_type": resource_type.value,
            "resource_id": resource_id,
            "action": action.value
        })

        logger.warning(f"Permiso denegado: {session_id} -> {resource_type.value}:{resource_id}")
        return False

    def _check_permission_level(self, granted_level: PermissionLevel,
                              required_level: PermissionLevel) -> bool:
        """Verifica si el nivel de permiso concedido es suficiente"""
        levels = {
            PermissionLevel.NONE: 0,
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.SYSTEM: 4
        }

        return levels.get(granted_level, 0) >= levels.get(required_level, 0)

    def _check_conditions(self, conditions: Dict[str, Any],
                         session: Dict[str, Any]) -> bool:
        """Verifica condiciones adicionales de permisos"""

        # Verificar límite de registros por consulta
        if "max_records_per_query" in conditions:
            max_records = conditions["max_records_per_query"]
            # Esta verificación se haría en el nivel de la herramienta
            pass

        # Verificar campos permitidos
        if "fields" in conditions:
            allowed_fields = conditions["fields"]
            # Esta verificación se haría en el nivel de la consulta
            pass

        # Verificar tipos de documento
        if "document_type" in conditions:
            allowed_types = conditions["document_type"]
            # Esta verificación se haría en el nivel de la consulta
            pass

        return True

    def get_tool_permissions(self, session_id: str) -> Set[str]:
        """Obtiene las herramientas permitidas para una sesión"""

        session = self.active_sessions.get(session_id)
        if not session:
            return set()

        return set(session.get("allowed_tools", []))

    def get_data_access_policy(self, session_id: str) -> Dict[str, Any]:
        """Obtiene la política de acceso a datos para una sesión"""

        session = self.active_sessions.get(session_id)
        if not session:
            return {}

        return session.get("data_access_policy", {})

    def _terminate_session(self, session_id: str):
        """Termina una sesión"""

        session = self.active_sessions.get(session_id)
        if session:
            self._log_access("session_terminated", {
                "session_id": session_id,
                "agent_name": session["agent_name"],
                "user_id": session["user_id"],
                "duration_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60,
                "access_count": session["access_count"]
            })

            del self.active_sessions[session_id]
            logger.info(f"Sesión terminada: {session_id}")

    def cleanup_expired_sessions(self):
        """Limpia sesiones expiradas"""

        expired_sessions = []
        for session_id, session in self.active_sessions.items():
            if session.get("expires_at") and datetime.now() > session["expires_at"]:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self._terminate_session(session_id)

        logger.info(f"Sesiones expiradas limpiadas: {len(expired_sessions)}")

    def _log_access(self, event_type: str, data: Dict[str, Any]):
        """Registra eventos de acceso para auditoría"""

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }

        self.access_log.append(log_entry)

        # Mantener solo los últimos 10000 logs en memoria
        if len(self.access_log) > 10000:
            self.access_log = self.access_log[-5000:]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de una sesión activa"""

        session = self.active_sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session_id,
            "agent_name": session["agent_name"],
            "user_id": session["user_id"],
            "role": session["role"],
            "created_at": session["created_at"].isoformat(),
            "expires_at": session["expires_at"].isoformat() if session["expires_at"] else None,
            "access_count": session["access_count"],
            "last_access": session["last_access"].isoformat(),
            "allowed_tools_count": len(session["allowed_tools"]),
            "permissions_count": len(session["permissions"])
        }

    def get_access_audit_log(self, user_id: Optional[str] = None,
                           hours: int = 24) -> List[Dict[str, Any]]:
        """Obtiene el log de auditoría de accesos"""

        since = datetime.now() - timedelta(hours=hours)

        filtered_logs = []
        for entry in self.access_log:
            entry_time = datetime.fromisoformat(entry["timestamp"])
            if entry_time < since:
                continue

            if user_id and entry["data"].get("user_id") != user_id:
                continue

            filtered_logs.append(entry)

        return filtered_logs

    def get_system_security_report(self) -> Dict[str, Any]:
        """Genera un reporte de seguridad del sistema"""

        active_sessions_count = len(self.active_sessions)

        # Contar sesiones por agente
        agent_sessions = {}
        for session in self.active_sessions.values():
            agent_name = session["agent_name"]
            agent_sessions[agent_name] = agent_sessions.get(agent_name, 0) + 1

        # Contar eventos de acceso recientes
        recent_accesses = len(self.get_access_audit_log(hours=1))
        denied_accesses = len([
            entry for entry in self.get_access_audit_log(hours=24)
            if entry["event_type"] == "permission_denied"
        ])

        return {
            "timestamp": datetime.now().isoformat(),
            "active_sessions": active_sessions_count,
            "sessions_by_agent": agent_sessions,
            "recent_accesses_1h": recent_accesses,
            "denied_accesses_24h": denied_accesses,
            "total_roles": len(self.roles),
            "audit_log_entries": len(self.access_log)
        }


# Singleton global
_privilege_manager = None


def get_privilege_manager() -> PrivilegeManager:
    """Obtiene la instancia global del gestor de privilegios"""
    global _privilege_manager
    if _privilege_manager is None:
        _privilege_manager = PrivilegeManager()
    return _privilege_manager


def require_permission(resource_type: ResourceType, resource_id: Optional[str] = None,
                      action: PermissionLevel = PermissionLevel.READ):
    """Decorador para verificar permisos antes de ejecutar una función"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Buscar session_id en argumentos o kwargs
            session_id = kwargs.get("session_id")
            if not session_id and args:
                # Buscar en argumentos posicionales
                for arg in args:
                    if isinstance(arg, str) and len(arg) == 16:  # formato session_id
                        session_id = arg
                        break

            if not session_id:
                raise ValueError("session_id requerido para verificación de permisos")

            privilege_manager = get_privilege_manager()
            if not privilege_manager.check_permission(session_id, resource_type, resource_id, action):
                raise PermissionError(f"Acceso denegado a {resource_type.value}:{resource_id}")

            return func(*args, **kwargs)

        return wrapper
    return decorator