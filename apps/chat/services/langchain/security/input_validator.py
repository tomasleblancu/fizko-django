"""
Sistema de Validación y Sanitización de Entradas
Valida y sanitiza todas las entradas del usuario para prevenir ataques de inyección
"""

import logging
import re
import html
import json
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import unicodedata
import bleach
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    """Resultados de validación"""
    VALID = "valid"
    SANITIZED = "sanitized"
    BLOCKED = "blocked"
    SUSPICIOUS = "suspicious"


class InputType(Enum):
    """Tipos de entrada reconocidos"""
    TEXT = "text"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    RUT = "rut"
    NUMBER = "number"
    DATE = "date"
    JSON = "json"
    SQL_FRAGMENT = "sql_fragment"
    COMMAND = "command"
    CODE = "code"


@dataclass
class ValidationRule:
    """Regla de validación para un tipo de entrada"""
    input_type: InputType
    max_length: int = 1000
    min_length: int = 0
    allowed_patterns: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    allowed_characters: Optional[str] = None
    blocked_characters: str = ""
    required_format: Optional[str] = None
    sanitization_enabled: bool = True
    description: str = ""


@dataclass
class ValidationOutput:
    """Resultado de validación de entrada"""
    original_input: str
    sanitized_input: str
    result: ValidationResult
    input_type: InputType
    issues_found: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence_score: float = 1.0  # 0.0 = muy sospechoso, 1.0 = muy confiable


class InputValidator:
    """Validador y sanitizador de entradas"""

    def __init__(self):
        self.validation_rules = {}
        self.attack_patterns = {}
        self.suspicious_keywords = set()
        self._setup_default_rules()
        self._setup_attack_patterns()
        self._setup_suspicious_keywords()

    def _setup_default_rules(self):
        """Configura reglas de validación por defecto"""

        # Texto general
        self.validation_rules[InputType.TEXT] = ValidationRule(
            input_type=InputType.TEXT,
            max_length=2000,
            min_length=1,
            blocked_patterns=[
                r"<script[^>]*>.*?</script>",  # Scripts
                r"javascript:",               # URLs javascript
                r"vbscript:",                # VBScript
                r"onload\s*=",               # Event handlers
                r"onerror\s*=",
                r"onclick\s*=",
                r"eval\s*\(",                # Funciones peligrosas
                r"exec\s*\(",
                r"system\s*\(",
            ],
            blocked_characters="<>\"'&{}[]();",
            sanitization_enabled=True,
            description="Texto general con sanitización básica"
        )

        # Email
        self.validation_rules[InputType.EMAIL] = ValidationRule(
            input_type=InputType.EMAIL,
            max_length=254,
            min_length=5,
            allowed_patterns=[
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            ],
            blocked_characters="<>\"'&{}[]();",
            sanitization_enabled=True,
            description="Direcciones de email válidas"
        )

        # RUT chileno
        self.validation_rules[InputType.RUT] = ValidationRule(
            input_type=InputType.RUT,
            max_length=12,
            min_length=8,
            allowed_patterns=[
                r"^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$",  # Formato con puntos
                r"^\d{7,8}-[\dkK]$"                 # Formato sin puntos
            ],
            allowed_characters="0123456789.-kK",
            sanitization_enabled=False,  # RUT debe ser exacto
            description="RUT chileno válido"
        )

        # URL
        self.validation_rules[InputType.URL] = ValidationRule(
            input_type=InputType.URL,
            max_length=2048,
            min_length=7,
            allowed_patterns=[
                r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}.*$"
            ],
            blocked_patterns=[
                r"javascript:",
                r"vbscript:",
                r"data:",
                r"file:",
                r"ftp:",
            ],
            sanitization_enabled=True,
            description="URLs HTTP/HTTPS válidas"
        )

        # Número
        self.validation_rules[InputType.NUMBER] = ValidationRule(
            input_type=InputType.NUMBER,
            max_length=20,
            min_length=1,
            allowed_patterns=[
                r"^-?\d+(\.\d+)?$"  # Enteros y decimales
            ],
            allowed_characters="0123456789.-",
            sanitization_enabled=False,
            description="Números válidos"
        )

        # JSON
        self.validation_rules[InputType.JSON] = ValidationRule(
            input_type=InputType.JSON,
            max_length=10000,
            min_length=2,
            blocked_patterns=[
                r"__.*__",          # Atributos especiales Python
                r"\$.*\$",          # Variables especiales
                r"eval\s*\(",
                r"exec\s*\(",
            ],
            sanitization_enabled=True,
            description="JSON válido sin código peligroso"
        )

        # Comando de sistema (muy restrictivo)
        self.validation_rules[InputType.COMMAND] = ValidationRule(
            input_type=InputType.COMMAND,
            max_length=100,
            min_length=1,
            blocked_patterns=[
                r";",                        # Separadores de comando
                r"\|",                       # Pipes
                r"&&",                       # AND lógico
                r"\|\|",                     # OR lógico
                r"`",                        # Backticks
                r"\$\(",                     # Command substitution
                r"rm\s",                     # Comandos peligrosos
                r"del\s",
                r"format\s",
                r"shutdown\s",
            ],
            allowed_characters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_ ",
            sanitization_enabled=False,  # Comandos no se sanitizan, se rechazan
            description="Comandos de sistema seguros"
        )

    def _setup_attack_patterns(self):
        """Configura patrones de ataque conocidos"""

        # SQL Injection
        self.attack_patterns["sql_injection"] = [
            r"(?i)(union\s+select)",
            r"(?i)(drop\s+table)",
            r"(?i)(delete\s+from)",
            r"(?i)(insert\s+into)",
            r"(?i)(update\s+.*\s+set)",
            r"(?i)(alter\s+table)",
            r"(?i)(create\s+table)",
            r"'.*'.*=.*'.*'",  # Comparaciones SQL típicas
            r"--",             # Comentarios SQL
            r"/\*.*\*/",       # Comentarios SQL multilinea
        ]

        # XSS (Cross-Site Scripting)
        self.attack_patterns["xss"] = [
            r"<script[^>]*>",
            r"</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]

        # Command Injection
        self.attack_patterns["command_injection"] = [
            r";\s*(rm|del|format|shutdown)",
            r"\|\s*(rm|del|format|shutdown)",
            r"&&\s*(rm|del|format|shutdown)",
            r"`.*`",
            r"\$\(.*\)",
            r">\s*/",  # Redirección a archivos de sistema
        ]

        # NoSQL Injection
        self.attack_patterns["nosql_injection"] = [
            r"\$where",
            r"\$regex",
            r"\$ne",
            r"\$in",
            r"\$nin",
            r"ObjectId\(",
        ]

        # LDAP Injection
        self.attack_patterns["ldap_injection"] = [
            r"\*\)",
            r"\(\|",
            r"\(&",
            r"\(!\(",
        ]

        # Path Traversal
        self.attack_patterns["path_traversal"] = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%252e%252e%252f",
        ]

    def _setup_suspicious_keywords(self):
        """Configura palabras clave sospechosas"""

        self.suspicious_keywords = {
            # Comandos de sistema
            "exec", "eval", "system", "shell", "cmd", "powershell", "bash",
            "rm", "del", "delete", "format", "shutdown", "reboot",

            # Funciones peligrosas
            "__import__", "compile", "execfile", "reload",

            # Archivos sensibles
            "passwd", "shadow", "hosts", "config", "private", "secret",

            # Protocolos sospechosos
            "javascript", "vbscript", "data", "file", "ftp",

            # Bases de datos
            "drop", "truncate", "alter", "create", "grant", "revoke",

            # Expresiones regulares peligrosas
            ".*", ".+", "^", "$", "\\",
        }

    def validate_input(self, user_input: str, input_type: InputType = InputType.TEXT,
                      context: Optional[Dict[str, Any]] = None) -> ValidationOutput:
        """Valida y sanitiza una entrada del usuario"""

        if not isinstance(user_input, str):
            user_input = str(user_input)

        original_input = user_input
        sanitized_input = user_input
        issues_found = []
        warnings = []
        confidence_score = 1.0

        # Obtener reglas de validación
        rule = self.validation_rules.get(input_type, self.validation_rules[InputType.TEXT])

        # 1. Verificar longitud
        if len(user_input) > rule.max_length:
            issues_found.append(f"Entrada excede longitud máxima ({rule.max_length})")
            sanitized_input = sanitized_input[:rule.max_length]
            confidence_score -= 0.2

        if len(user_input) < rule.min_length:
            issues_found.append(f"Entrada menor a longitud mínima ({rule.min_length})")

        # 2. Detectar patrones de ataque
        attack_score = self._detect_attacks(user_input)
        confidence_score -= attack_score

        if attack_score > 0.5:
            issues_found.append("Patrones de ataque detectados")

        # 3. Verificar patrones bloqueados
        for pattern in rule.blocked_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                issues_found.append(f"Patrón bloqueado detectado: {pattern}")
                confidence_score -= 0.3

        # 4. Verificar patrones permitidos
        if rule.allowed_patterns:
            pattern_matched = False
            for pattern in rule.allowed_patterns:
                if re.match(pattern, user_input):
                    pattern_matched = True
                    break

            if not pattern_matched:
                issues_found.append("Entrada no coincide con patrones permitidos")
                confidence_score -= 0.4

        # 5. Verificar caracteres
        if rule.allowed_characters:
            invalid_chars = set(user_input) - set(rule.allowed_characters)
            if invalid_chars:
                issues_found.append(f"Caracteres no permitidos: {invalid_chars}")
                confidence_score -= 0.3

        if rule.blocked_characters:
            blocked_chars = set(user_input) & set(rule.blocked_characters)
            if blocked_chars:
                issues_found.append(f"Caracteres bloqueados encontrados: {blocked_chars}")
                confidence_score -= 0.2

        # 6. Buscar palabras clave sospechosas
        suspicious_found = self._find_suspicious_keywords(user_input.lower())
        if suspicious_found:
            warnings.append(f"Palabras clave sospechosas: {suspicious_found}")
            confidence_score -= len(suspicious_found) * 0.1

        # 7. Aplicar sanitización si está habilitada
        if rule.sanitization_enabled:
            sanitized_input = self._sanitize_input(sanitized_input, input_type)

        # 8. Determinar resultado
        result = self._determine_result(confidence_score, issues_found)

        return ValidationOutput(
            original_input=original_input,
            sanitized_input=sanitized_input,
            result=result,
            input_type=input_type,
            issues_found=issues_found,
            warnings=warnings,
            confidence_score=max(0.0, confidence_score)
        )

    def _detect_attacks(self, user_input: str) -> float:
        """Detecta patrones de ataque y retorna score de peligrosidad (0-1)"""

        attack_score = 0.0
        total_patterns = sum(len(patterns) for patterns in self.attack_patterns.values())

        for attack_type, patterns in self.attack_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input, re.IGNORECASE):
                    attack_score += 1.0 / total_patterns
                    logger.warning(f"Patrón de ataque {attack_type} detectado: {pattern}")

        return min(1.0, attack_score * 10)  # Amplificar score

    def _find_suspicious_keywords(self, user_input: str) -> List[str]:
        """Encuentra palabras clave sospechosas en la entrada"""

        found_keywords = []
        words = re.findall(r'\b\w+\b', user_input)

        for word in words:
            if word in self.suspicious_keywords:
                found_keywords.append(word)

        return found_keywords

    def _sanitize_input(self, user_input: str, input_type: InputType) -> str:
        """Sanitiza la entrada según el tipo"""

        sanitized = user_input

        if input_type == InputType.TEXT:
            # Sanitización básica de texto
            sanitized = html.escape(sanitized)  # Escapar HTML
            sanitized = sanitized.replace("'", "&#x27;")  # Escapar comillas simples
            sanitized = sanitized.replace('"', "&quot;")  # Escapar comillas dobles

        elif input_type == InputType.EMAIL:
            # Limpiar caracteres no válidos en email
            sanitized = re.sub(r'[^a-zA-Z0-9._%+-@]', '', sanitized)

        elif input_type == InputType.URL:
            # Sanitizar URL
            try:
                parsed = urlparse(sanitized)
                if parsed.scheme in ['http', 'https']:
                    # Reconstruir URL limpia
                    sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        sanitized += f"?{parsed.query}"
            except Exception:
                sanitized = ""

        elif input_type == InputType.JSON:
            # Validar y limpiar JSON
            try:
                # Intentar parsear JSON
                parsed_json = json.loads(sanitized)
                # Re-serializar para limpiar
                sanitized = json.dumps(parsed_json, ensure_ascii=True)
            except json.JSONDecodeError:
                sanitized = "{}"  # JSON vacío si no es válido

        elif input_type == InputType.NUMBER:
            # Limpiar solo números, puntos y guión
            sanitized = re.sub(r'[^0-9.-]', '', sanitized)

        elif input_type == InputType.RUT:
            # Limpiar RUT
            sanitized = re.sub(r'[^0-9.kK-]', '', sanitized).upper()

        # Normalización Unicode
        sanitized = unicodedata.normalize('NFKC', sanitized)

        return sanitized

    def _determine_result(self, confidence_score: float,
                         issues_found: List[str]) -> ValidationResult:
        """Determina el resultado de validación basado en el score y issues"""

        if confidence_score >= 0.8 and not issues_found:
            return ValidationResult.VALID

        elif confidence_score >= 0.5 and issues_found:
            return ValidationResult.SANITIZED

        elif confidence_score >= 0.2:
            return ValidationResult.SUSPICIOUS

        else:
            return ValidationResult.BLOCKED

    def validate_multiple_inputs(self, inputs: Dict[str, Any],
                                input_types: Optional[Dict[str, InputType]] = None) -> Dict[str, ValidationOutput]:
        """Valida múltiples entradas"""

        results = {}

        for field_name, value in inputs.items():
            # Determinar tipo de entrada
            input_type = InputType.TEXT
            if input_types and field_name in input_types:
                input_type = input_types[field_name]
            elif field_name.lower() in ['email', 'correo']:
                input_type = InputType.EMAIL
            elif field_name.lower() in ['rut', 'tax_id']:
                input_type = InputType.RUT
            elif field_name.lower() in ['url', 'website', 'sitio_web']:
                input_type = InputType.URL
            elif field_name.lower() in ['telefono', 'phone', 'fono']:
                input_type = InputType.PHONE

            results[field_name] = self.validate_input(str(value), input_type)

        return results

    def create_safe_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un contexto seguro validando todas las entradas"""

        safe_context = {}

        for key, value in raw_context.items():
            if isinstance(value, (str, int, float)):
                validation_result = self.validate_input(str(value))

                if validation_result.result in [ValidationResult.VALID, ValidationResult.SANITIZED]:
                    safe_context[key] = validation_result.sanitized_input
                else:
                    logger.warning(f"Entrada bloqueada en contexto: {key}")
                    safe_context[key] = "[ENTRADA_BLOQUEADA]"

            elif isinstance(value, dict):
                # Recursivo para diccionarios anidados
                safe_context[key] = self.create_safe_context(value)

            elif isinstance(value, list):
                # Validar elementos de lista
                safe_list = []
                for item in value:
                    if isinstance(item, (str, int, float)):
                        validation_result = self.validate_input(str(item))
                        if validation_result.result in [ValidationResult.VALID, ValidationResult.SANITIZED]:
                            safe_list.append(validation_result.sanitized_input)
                    else:
                        safe_list.append(item)  # Mantener otros tipos
                safe_context[key] = safe_list

            else:
                safe_context[key] = value  # Mantener otros tipos como están

        return safe_context

    def get_validation_report(self) -> Dict[str, Any]:
        """Genera reporte de validación del sistema"""

        return {
            "timestamp": "datetime.now().isoformat()",
            "validation_rules": len(self.validation_rules),
            "attack_patterns": sum(len(patterns) for patterns in self.attack_patterns.values()),
            "suspicious_keywords": len(self.suspicious_keywords),
            "input_types_supported": [t.value for t in InputType],
            "attack_types_detected": list(self.attack_patterns.keys())
        }


# Singleton global
_input_validator = None


def get_input_validator() -> InputValidator:
    """Obtiene la instancia global del validador de entradas"""
    global _input_validator
    if _input_validator is None:
        _input_validator = InputValidator()
    return _input_validator


def validate_user_input(input_type: InputType = InputType.TEXT):
    """Decorador para validar automáticamente entradas de usuario"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            validator = get_input_validator()

            # Buscar argumentos de entrada del usuario
            for i, arg in enumerate(args):
                if isinstance(arg, str) and i > 0:  # Omitir 'self'
                    validation_result = validator.validate_input(arg, input_type)

                    if validation_result.result == ValidationResult.BLOCKED:
                        raise ValueError(f"Entrada bloqueada por seguridad: {validation_result.issues_found}")

                    # Reemplazar con versión sanitizada
                    args = list(args)
                    args[i] = validation_result.sanitized_input
                    args = tuple(args)

            # Validar kwargs
            for key, value in kwargs.items():
                if isinstance(value, str):
                    validation_result = validator.validate_input(value, input_type)

                    if validation_result.result == ValidationResult.BLOCKED:
                        raise ValueError(f"Entrada bloqueada por seguridad en {key}: {validation_result.issues_found}")

                    kwargs[key] = validation_result.sanitized_input

            return func(*args, **kwargs)

        return wrapper
    return decorator