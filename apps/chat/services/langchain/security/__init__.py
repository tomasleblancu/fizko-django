"""
Sistema de Seguridad y Privacidad para Multi-Agent System

Proporciona:
- Principio de menor privilegio
- Inyección controlada de contexto con anonimización
- Sandboxing y aislamiento de agentes
- Validación y sanitización de entradas
- Monitoreo de seguridad avanzado
- Cumplimiento normativo chileno
- Framework de pruebas de vulnerabilidades

Cumplimiento Regulatorio:
- Ley 19.628 (Protección de la Vida Privada)
- DFL 3 (Ley de Bancos)
- Normativas SII
- Regulaciones CMF
- Ley 20.393 (Responsabilidad Penal Empresarial)
"""

from .privilege_manager import (
    PrivilegeManager,
    Permission,
    PermissionLevel,
    ResourceType,
    AgentRole,
    get_privilege_manager,
    require_permission
)

from .context_control import (
    ContextController,
    SensitivityLevel,
    AnonymizationMethod,
    DataClassification,
    ContextInjectionRule,
    get_context_controller
)

from .sandbox_manager import (
    SandboxManager,
    IsolationLevel,
    ResourceLimits,
    SandboxConfiguration,
    get_sandbox_manager,
    sandbox_execution
)

from .input_validator import (
    InputValidator,
    ValidationResult,
    InputType,
    ValidationRule,
    ValidationOutput,
    get_input_validator,
    validate_user_input
)

from .security_monitor import (
    SecurityMonitor,
    SecurityEventType,
    ThreatLevel,
    SecurityEvent,
    UserBehaviorProfile,
    get_security_monitor,
    security_check
)

from .chilean_compliance import (
    ChileanComplianceManager,
    ChileanRegulation,
    DataCategory,
    RetentionPeriod,
    ComplianceRecord,
    get_compliance_manager,
    chilean_compliance_required
)

from .security_testing import (
    SecurityTester,
    VulnerabilityType,
    SeverityLevel,
    Vulnerability,
    SecurityAuditResult,
    get_security_tester,
    run_quick_security_scan
)

__all__ = [
    # Privilege Management
    'PrivilegeManager',
    'Permission',
    'PermissionLevel',
    'ResourceType',
    'AgentRole',
    'get_privilege_manager',
    'require_permission',

    # Context Control
    'ContextController',
    'SensitivityLevel',
    'AnonymizationMethod',
    'DataClassification',
    'ContextInjectionRule',
    'get_context_controller',

    # Sandbox Management
    'SandboxManager',
    'IsolationLevel',
    'ResourceLimits',
    'SandboxConfiguration',
    'get_sandbox_manager',
    'sandbox_execution',

    # Input Validation
    'InputValidator',
    'ValidationResult',
    'InputType',
    'ValidationRule',
    'ValidationOutput',
    'get_input_validator',
    'validate_user_input',

    # Security Monitoring
    'SecurityMonitor',
    'SecurityEventType',
    'ThreatLevel',
    'SecurityEvent',
    'UserBehaviorProfile',
    'get_security_monitor',
    'security_check',

    # Chilean Compliance
    'ChileanComplianceManager',
    'ChileanRegulation',
    'DataCategory',
    'RetentionPeriod',
    'ComplianceRecord',
    'get_compliance_manager',
    'chilean_compliance_required',

    # Security Testing
    'SecurityTester',
    'VulnerabilityType',
    'SeverityLevel',
    'Vulnerability',
    'SecurityAuditResult',
    'get_security_tester',
    'run_quick_security_scan'
]


def get_security_system_status() -> dict:
    """Obtiene estado general del sistema de seguridad"""

    try:
        # Verificar componentes principales
        privilege_manager = get_privilege_manager()
        context_controller = get_context_controller()
        sandbox_manager = get_sandbox_manager()
        input_validator = get_input_validator()
        security_monitor = get_security_monitor()
        compliance_manager = get_compliance_manager()
        security_tester = get_security_tester()

        return {
            "status": "operational",
            "components": {
                "privilege_manager": "active",
                "context_controller": "active",
                "sandbox_manager": "active",
                "input_validator": "active",
                "security_monitor": "active" if security_monitor.monitoring_active else "inactive",
                "compliance_manager": "active",
                "security_tester": "active"
            },
            "active_sessions": len(privilege_manager.active_sessions),
            "sandboxes_active": len(sandbox_manager.active_sandboxes),
            "compliance_records": len(compliance_manager.compliance_records),
            "security_events_24h": len([
                e for e in security_monitor.security_events
                if (security_monitor.datetime.now() - e.timestamp).total_seconds() < 86400
            ]) if hasattr(security_monitor, 'security_events') else 0,
            "blocked_users": len(security_monitor.blocked_users) if hasattr(security_monitor, 'blocked_users') else 0,
            "last_audit": security_tester.audit_history[-1].start_time.isoformat() if security_tester.audit_history else None
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "components": {}
        }


def initialize_security_system() -> dict:
    """Inicializa sistema completo de seguridad"""

    try:
        # Inicializar componentes
        privilege_manager = get_privilege_manager()
        context_controller = get_context_controller()
        sandbox_manager = get_sandbox_manager()
        input_validator = get_input_validator()
        security_monitor = get_security_monitor()
        compliance_manager = get_compliance_manager()
        security_tester = get_security_tester()

        # Iniciar monitoreo
        security_monitor.start_monitoring()

        return {
            "status": "initialized",
            "message": "Sistema de seguridad inicializado correctamente",
            "components_initialized": 7,
            "monitoring_active": True
        }

    except Exception as e:
        return {
            "status": "initialization_failed",
            "error": str(e)
        }


def shutdown_security_system() -> dict:
    """Cierra sistema de seguridad de forma segura"""

    try:
        # Detener monitoreo
        security_monitor = get_security_monitor()
        security_monitor.stop_monitoring()

        # Limpiar sandboxes activos
        sandbox_manager = get_sandbox_manager()
        sandbox_manager.cleanup_expired_sandboxes()

        # Limpiar sesiones
        privilege_manager = get_privilege_manager()
        privilege_manager.cleanup_expired_sessions()

        return {
            "status": "shutdown_complete",
            "message": "Sistema de seguridad cerrado correctamente"
        }

    except Exception as e:
        return {
            "status": "shutdown_error",
            "error": str(e)
        }