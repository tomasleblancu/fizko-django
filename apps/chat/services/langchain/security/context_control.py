"""
Sistema de Control de Contexto e Inyección Segura
Maneja la inyección controlada de información con anonimización de datos sensibles
"""

import logging
import re
import hashlib
import json
from typing import Dict, List, Any, Optional, Set, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import copy

from .privilege_manager import get_privilege_manager, ResourceType

logger = logging.getLogger(__name__)


class SensitivityLevel(Enum):
    """Niveles de sensibilidad de datos"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class AnonymizationMethod(Enum):
    """Métodos de anonimización disponibles"""
    REDACTION = "redaction"  # Reemplazo con ***
    HASHING = "hashing"     # Hash SHA-256
    MASKING = "masking"     # Enmascaramiento parcial
    TOKENIZATION = "tokenization"  # Reemplazo con token
    REMOVAL = "removal"     # Eliminación completa


@dataclass
class DataClassification:
    """Clasificación de un tipo de dato"""
    name: str
    sensitivity_level: SensitivityLevel
    anonymization_method: AnonymizationMethod
    patterns: List[str] = field(default_factory=list)  # Patrones regex
    fields: List[str] = field(default_factory=list)    # Campos específicos
    description: str = ""


@dataclass
class ContextInjectionRule:
    """Regla para inyección de contexto"""
    agent_type: str
    resource_types: List[ResourceType]
    max_data_points: int = 100
    required_fields: List[str] = field(default_factory=list)
    excluded_fields: List[str] = field(default_factory=list)
    anonymization_rules: Dict[str, AnonymizationMethod] = field(default_factory=dict)
    time_window_hours: Optional[int] = None


class ContextController:
    """Controlador de contexto e inyección segura"""

    def __init__(self):
        self.data_classifications = {}
        self.injection_rules = {}
        self.anonymization_cache = {}  # Cache para tokens de anonimización
        self._setup_default_classifications()
        self._setup_default_injection_rules()

    def _setup_default_classifications(self):
        """Configura clasificaciones de datos por defecto"""

        # RUT chileno
        self.data_classifications["rut"] = DataClassification(
            name="rut",
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            anonymization_method=AnonymizationMethod.MASKING,
            patterns=[r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", r"\d{7,8}-[\dkK]"],
            fields=["rut", "tax_id", "cliente_rut", "emisor_rut"],
            description="RUT o identificación tributaria chilena"
        )

        # Email
        self.data_classifications["email"] = DataClassification(
            name="email",
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            anonymization_method=AnonymizationMethod.MASKING,
            patterns=[r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
            fields=["email", "correo", "email_cliente", "contacto_email"],
            description="Direcciones de correo electrónico"
        )

        # Teléfono
        self.data_classifications["phone"] = DataClassification(
            name="phone",
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            anonymization_method=AnonymizationMethod.MASKING,
            patterns=[r"\+56\s?[0-9]\s?\d{4}\s?\d{4}", r"\(56\)\s?\d{8,9}", r"\d{8,9}"],
            fields=["telefono", "phone", "celular", "fono"],
            description="Números telefónicos chilenos"
        )

        # Direcciones
        self.data_classifications["address"] = DataClassification(
            name="address",
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            anonymization_method=AnonymizationMethod.REDACTION,
            patterns=[],
            fields=["direccion", "address", "domicilio", "ubicacion"],
            description="Direcciones físicas"
        )

        # Montos financieros
        self.data_classifications["financial_amount"] = DataClassification(
            name="financial_amount",
            sensitivity_level=SensitivityLevel.INTERNAL,
            anonymization_method=AnonymizationMethod.MASKING,
            patterns=[r"\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?", r"\d{1,3}(?:\.\d{3})*\s?CLP"],
            fields=["monto", "total", "amount", "valor", "precio", "subtotal"],
            description="Montos y valores financieros"
        )

        # Nombres de personas
        self.data_classifications["person_name"] = DataClassification(
            name="person_name",
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
            anonymization_method=AnonymizationMethod.TOKENIZATION,
            patterns=[],
            fields=["nombre", "apellido", "razon_social", "cliente_nombre"],
            description="Nombres de personas naturales"
        )

        # Números de cuenta bancaria
        self.data_classifications["bank_account"] = DataClassification(
            name="bank_account",
            sensitivity_level=SensitivityLevel.RESTRICTED,
            anonymization_method=AnonymizationMethod.HASHING,
            patterns=[r"\d{10,20}"],
            fields=["cuenta_bancaria", "numero_cuenta", "account_number"],
            description="Números de cuenta bancaria"
        )

    def _setup_default_injection_rules(self):
        """Configura reglas de inyección por defecto"""

        # Reglas para agente SII
        self.injection_rules["sii_agent"] = ContextInjectionRule(
            agent_type="sii_agent",
            resource_types=[ResourceType.SII_API, ResourceType.TAX_DATA, ResourceType.DOCUMENT],
            max_data_points=50,
            required_fields=["tipo_documento", "folio", "fecha", "estado"],
            excluded_fields=["rut", "email", "telefono", "direccion"],
            anonymization_rules={
                "cliente_rut": AnonymizationMethod.MASKING,
                "emisor_rut": AnonymizationMethod.MASKING,
                "monto": AnonymizationMethod.MASKING
            },
            time_window_hours=720  # 30 días
        )

        # Reglas para agente DTE
        self.injection_rules["dte_agent"] = ContextInjectionRule(
            agent_type="dte_agent",
            resource_types=[ResourceType.DOCUMENT, ResourceType.FINANCIAL_DATA],
            max_data_points=100,
            required_fields=["tipo_dte", "folio", "fecha_emision", "total"],
            excluded_fields=["direccion", "telefono", "email"],
            anonymization_rules={
                "cliente_rut": AnonymizationMethod.MASKING,
                "razon_social": AnonymizationMethod.TOKENIZATION,
                "total": AnonymizationMethod.MASKING
            },
            time_window_hours=168  # 7 días
        )

        # Reglas para supervisor (mínimo contexto)
        self.injection_rules["supervisor_agent"] = ContextInjectionRule(
            agent_type="supervisor_agent",
            resource_types=[ResourceType.SYSTEM_CONFIG],
            max_data_points=20,
            required_fields=["timestamp", "agent_name", "query_type"],
            excluded_fields=["rut", "email", "telefono", "direccion", "nombre", "monto"],
            anonymization_rules={},
            time_window_hours=1
        )

    def prepare_secure_context(self, session_id: str, agent_name: str,
                             raw_data: Union[Dict, List[Dict], Any],
                             context_type: str = "general") -> Dict[str, Any]:
        """Prepara contexto seguro con anonimización para un agente"""

        privilege_manager = get_privilege_manager()
        session_info = privilege_manager.get_session_info(session_id)

        if not session_info:
            logger.error(f"Sesión no válida para preparar contexto: {session_id}")
            return {}

        # Determinar reglas de inyección
        agent_type = self._determine_agent_type(agent_name)
        injection_rule = self.injection_rules.get(agent_type)

        if not injection_rule:
            logger.warning(f"No hay reglas de inyección para: {agent_type}")
            return {"error": "No context rules available"}

        # Procesar datos
        if isinstance(raw_data, dict):
            processed_data = [raw_data]
        elif isinstance(raw_data, list):
            processed_data = raw_data
        else:
            processed_data = [{"data": str(raw_data)}]

        # Limitar cantidad de datos
        if len(processed_data) > injection_rule.max_data_points:
            processed_data = processed_data[:injection_rule.max_data_points]
            logger.info(f"Datos limitados a {injection_rule.max_data_points} elementos")

        # Filtrar por ventana temporal si aplica
        if injection_rule.time_window_hours:
            cutoff_time = datetime.now() - timedelta(hours=injection_rule.time_window_hours)
            processed_data = self._filter_by_time_window(processed_data, cutoff_time)

        # Aplicar filtros de campos
        processed_data = self._apply_field_filters(processed_data, injection_rule)

        # Aplicar anonimización
        anonymized_data = self._apply_anonymization(processed_data, injection_rule, session_id)

        # Preparar contexto final
        secure_context = {
            "context_type": context_type,
            "agent_type": agent_type,
            "data_count": len(anonymized_data),
            "data": anonymized_data,
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "anonymization_applied": True,
            "data_retention_hours": injection_rule.time_window_hours
        }

        # Log de auditoría
        self._log_context_injection(session_id, agent_name, secure_context)

        return secure_context

    def _determine_agent_type(self, agent_name: str) -> str:
        """Determina el tipo de agente basado en su nombre"""

        agent_name_lower = agent_name.lower()

        if "sii" in agent_name_lower:
            return "sii_agent"
        elif "dte" in agent_name_lower:
            return "dte_agent"
        elif "supervisor" in agent_name_lower:
            return "supervisor_agent"
        else:
            return "supervisor_agent"  # Por defecto, menor privilegio

    def _filter_by_time_window(self, data: List[Dict], cutoff_time: datetime) -> List[Dict]:
        """Filtra datos por ventana temporal"""

        filtered_data = []
        for item in data:
            # Buscar campos de fecha
            item_date = None
            for date_field in ["fecha", "timestamp", "created_at", "fecha_emision"]:
                if date_field in item and item[date_field]:
                    try:
                        if isinstance(item[date_field], str):
                            item_date = datetime.fromisoformat(item[date_field].replace('Z', '+00:00'))
                        elif isinstance(item[date_field], datetime):
                            item_date = item[date_field]
                        break
                    except:
                        continue

            if item_date and item_date >= cutoff_time:
                filtered_data.append(item)
            elif not item_date:  # Si no hay fecha, incluir por defecto
                filtered_data.append(item)

        return filtered_data

    def _apply_field_filters(self, data: List[Dict], rule: ContextInjectionRule) -> List[Dict]:
        """Aplica filtros de campos requeridos y excluidos"""

        filtered_data = []

        for item in data:
            filtered_item = {}

            # Incluir campos requeridos
            for field in rule.required_fields:
                if field in item:
                    filtered_item[field] = item[field]

            # Incluir otros campos si no están excluidos
            for field, value in item.items():
                if field not in rule.excluded_fields and field not in filtered_item:
                    filtered_item[field] = value

            # Excluir campos específicamente prohibidos
            for excluded_field in rule.excluded_fields:
                filtered_item.pop(excluded_field, None)

            filtered_data.append(filtered_item)

        return filtered_data

    def _apply_anonymization(self, data: List[Dict], rule: ContextInjectionRule,
                           session_id: str) -> List[Dict]:
        """Aplica anonimización según las reglas"""

        anonymized_data = []

        for item in data:
            anonymized_item = copy.deepcopy(item)

            # Aplicar anonimización por reglas específicas
            for field, method in rule.anonymization_rules.items():
                if field in anonymized_item:
                    anonymized_item[field] = self._anonymize_value(
                        anonymized_item[field], method, session_id, field
                    )

            # Aplicar anonimización por clasificaciones de datos
            for field, value in list(anonymized_item.items()):
                if isinstance(value, str):
                    anonymized_item[field] = self._anonymize_by_patterns(value, session_id)

            anonymized_data.append(anonymized_item)

        return anonymized_data

    def _anonymize_value(self, value: Any, method: AnonymizationMethod,
                        session_id: str, field_name: str) -> str:
        """Aplica anonimización a un valor específico"""

        if not value:
            return value

        str_value = str(value)

        if method == AnonymizationMethod.REDACTION:
            return "***REDACTED***"

        elif method == AnonymizationMethod.HASHING:
            hash_key = f"{session_id}:{field_name}:{str_value}"
            return hashlib.sha256(hash_key.encode()).hexdigest()[:12]

        elif method == AnonymizationMethod.MASKING:
            if len(str_value) <= 4:
                return "*" * len(str_value)
            else:
                return str_value[:2] + "*" * (len(str_value) - 4) + str_value[-2:]

        elif method == AnonymizationMethod.TOKENIZATION:
            # Generar token consistente para el mismo valor en la misma sesión
            token_key = f"{session_id}:{str_value}"
            if token_key not in self.anonymization_cache:
                token = f"TOKEN_{hashlib.md5(token_key.encode()).hexdigest()[:8].upper()}"
                self.anonymization_cache[token_key] = token
            return self.anonymization_cache[token_key]

        elif method == AnonymizationMethod.REMOVAL:
            return None

        else:
            return str_value

    def _anonymize_by_patterns(self, text: str, session_id: str) -> str:
        """Aplica anonimización basada en patrones regex"""

        anonymized_text = text

        for classification_name, classification in self.data_classifications.items():
            for pattern in classification.patterns:
                matches = re.finditer(pattern, anonymized_text)
                for match in matches:
                    original = match.group()
                    anonymized = self._anonymize_value(
                        original, classification.anonymization_method, session_id, classification_name
                    )
                    anonymized_text = anonymized_text.replace(original, str(anonymized))

        return anonymized_text

    def _log_context_injection(self, session_id: str, agent_name: str,
                             context: Dict[str, Any]):
        """Registra inyección de contexto para auditoría"""

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "context_injection",
            "session_id": session_id,
            "agent_name": agent_name,
            "context_type": context.get("context_type"),
            "data_count": context.get("data_count", 0),
            "anonymization_applied": context.get("anonymization_applied", False)
        }

        # Usar el sistema de auditoría existente
        try:
            from ..monitoring.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_system_action(
                action="context_injection",
                component="context_controller",
                details=log_entry
            )
        except ImportError:
            logger.info(f"Context injection logged: {json.dumps(log_entry)}")

    def get_anonymization_report(self, session_id: str) -> Dict[str, Any]:
        """Genera reporte de anonimización para una sesión"""

        # Contar tokens generados para esta sesión
        session_tokens = sum(
            1 for key in self.anonymization_cache.keys()
            if key.startswith(session_id + ":")
        )

        return {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "tokens_generated": session_tokens,
            "classifications_applied": len(self.data_classifications),
            "injection_rules_available": len(self.injection_rules)
        }

    def cleanup_session_cache(self, session_id: str):
        """Limpia cache de anonimización para una sesión terminada"""

        keys_to_remove = [
            key for key in self.anonymization_cache.keys()
            if key.startswith(session_id + ":")
        ]

        for key in keys_to_remove:
            del self.anonymization_cache[key]

        logger.info(f"Cache de anonimización limpiado para sesión: {session_id}")

    def validate_context_security(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que un contexto cumple con los requisitos de seguridad"""

        validation_results = {
            "is_secure": True,
            "issues": [],
            "recommendations": []
        }

        # Verificar que existe anonimización
        if not context.get("anonymization_applied"):
            validation_results["is_secure"] = False
            validation_results["issues"].append("No se aplicó anonimización")

        # Buscar posibles datos sensibles no anonimizados
        data_items = context.get("data", [])
        for i, item in enumerate(data_items):
            for field, value in item.items():
                if isinstance(value, str):
                    # Buscar patrones de datos sensibles
                    for classification in self.data_classifications.values():
                        for pattern in classification.patterns:
                            if re.search(pattern, value):
                                validation_results["is_secure"] = False
                                validation_results["issues"].append(
                                    f"Posible dato sensible no anonimizado en item {i}: {field}"
                                )

        # Verificar límites de datos
        data_count = len(data_items)
        if data_count > 200:
            validation_results["recommendations"].append(
                f"Consideraciones de privacidad: {data_count} elementos en contexto"
            )

        return validation_results


# Singleton global
_context_controller = None


def get_context_controller() -> ContextController:
    """Obtiene la instancia global del controlador de contexto"""
    global _context_controller
    if _context_controller is None:
        _context_controller = ContextController()
    return _context_controller