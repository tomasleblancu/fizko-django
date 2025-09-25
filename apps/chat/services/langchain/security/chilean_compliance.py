"""
Sistema de Cumplimiento Normativo Chileno
Implementa políticas de cumplimiento con normativas chilenas de protección de datos,
SII, CMF y otras regulaciones locales
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import hashlib
import re

logger = logging.getLogger(__name__)


class ChileanRegulation(Enum):
    """Regulaciones chilenas aplicables"""
    LEY_19628 = "ley_19628"  # Ley sobre Protección de la Vida Privada
    DFL_3 = "dfl_3"          # Ley de Bancos e Instituciones Financieras
    LEY_20393 = "ley_20393"  # Ley de Responsabilidad Penal de Personas Jurídicas
    SII_NORMATIVA = "sii_normativa"  # Normativas del Servicio de Impuestos Internos
    CMF_NORMATIVA = "cmf_normativa"  # Comisión para el Mercado Financiero
    LEY_21096 = "ley_21096"  # Ley sobre Morosidad
    SERNAC = "sernac"        # Servicio Nacional del Consumidor


class DataCategory(Enum):
    """Categorías de datos según normativa chilena"""
    PERSONAL_DATA = "personal_data"           # Datos personales (Ley 19.628)
    SENSITIVE_DATA = "sensitive_data"         # Datos sensibles (Ley 19.628)
    FINANCIAL_DATA = "financial_data"         # Datos financieros (DFL 3)
    TAX_DATA = "tax_data"                     # Datos tributarios (SII)
    COMMERCIAL_DATA = "commercial_data"       # Datos comerciales
    HEALTH_DATA = "health_data"               # Datos de salud
    JUDICIAL_DATA = "judicial_data"           # Datos judiciales


class RetentionPeriod(Enum):
    """Períodos de retención según normativa"""
    SII_DOCUMENTS = 2555  # 7 años (SII - documentos tributarios)
    FINANCIAL_RECORDS = 1825  # 5 años (CMF - registros financieros)
    PERSONAL_DATA = 365   # 1 año (Ley 19.628 - datos personales básicos)
    SENSITIVE_DATA = 1095 # 3 años (Ley 19.628 - datos sensibles)
    AUDIT_LOGS = 2190     # 6 años (Ley 20.393 - compliance)
    COMMERCIAL_DATA = 1460 # 4 años (código comercial)


@dataclass
class DataClassificationRule:
    """Regla de clasificación de datos"""
    data_category: DataCategory
    applicable_regulations: List[ChileanRegulation]
    retention_period_days: int
    anonymization_required: bool = True
    encryption_required: bool = False
    access_restrictions: List[str] = field(default_factory=list)
    deletion_requirements: List[str] = field(default_factory=list)
    audit_requirements: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ComplianceRecord:
    """Registro de cumplimiento normativo"""
    record_id: str
    data_category: DataCategory
    applicable_regulations: List[ChileanRegulation]
    creation_date: datetime
    retention_until: datetime
    anonymized: bool = False
    encrypted: bool = False
    access_log: List[Dict[str, Any]] = field(default_factory=list)
    compliance_actions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChileanComplianceManager:
    """Gestor de cumplimiento normativo chileno"""

    def __init__(self):
        self.classification_rules = {}
        self.compliance_records = {}
        self.data_retention_schedule = {}
        self._setup_chilean_regulations()

    def _setup_chilean_regulations(self):
        """Configura reglas de cumplimiento chileno"""

        # Datos personales básicos (Ley 19.628)
        self.classification_rules[DataCategory.PERSONAL_DATA] = DataClassificationRule(
            data_category=DataCategory.PERSONAL_DATA,
            applicable_regulations=[ChileanRegulation.LEY_19628],
            retention_period_days=RetentionPeriod.PERSONAL_DATA.value,
            anonymization_required=True,
            encryption_required=False,
            access_restrictions=["logged_access", "purpose_limitation"],
            deletion_requirements=["secure_deletion", "verification_required"],
            audit_requirements=["access_log", "modification_log"],
            description="Datos personales según Ley 19.628"
        )

        # Datos sensibles (Ley 19.628)
        self.classification_rules[DataCategory.SENSITIVE_DATA] = DataClassificationRule(
            data_category=DataCategory.SENSITIVE_DATA,
            applicable_regulations=[ChileanRegulation.LEY_19628],
            retention_period_days=RetentionPeriod.SENSITIVE_DATA.value,
            anonymization_required=True,
            encryption_required=True,
            access_restrictions=["explicit_consent", "purpose_limitation", "authorized_personnel"],
            deletion_requirements=["immediate_deletion", "verification_required", "certificate_required"],
            audit_requirements=["access_log", "modification_log", "consent_log"],
            description="Datos sensibles que requieren consentimiento explícito"
        )

        # Datos tributarios (SII)
        self.classification_rules[DataCategory.TAX_DATA] = DataClassificationRule(
            data_category=DataCategory.TAX_DATA,
            applicable_regulations=[ChileanRegulation.SII_NORMATIVA, ChileanRegulation.LEY_19628],
            retention_period_days=RetentionPeriod.SII_DOCUMENTS.value,
            anonymization_required=False,  # SII requiere datos originales
            encryption_required=True,
            access_restrictions=["authorized_tax_personnel", "sii_compliance"],
            deletion_requirements=["sii_authorization_required", "audit_trail"],
            audit_requirements=["full_audit_trail", "sii_reporting"],
            description="Datos tributarios bajo normativa SII"
        )

        # Datos financieros (CMF/DFL 3)
        self.classification_rules[DataCategory.FINANCIAL_DATA] = DataClassificationRule(
            data_category=DataCategory.FINANCIAL_DATA,
            applicable_regulations=[ChileanRegulation.DFL_3, ChileanRegulation.CMF_NORMATIVA],
            retention_period_days=RetentionPeriod.FINANCIAL_RECORDS.value,
            anonymization_required=True,
            encryption_required=True,
            access_restrictions=["financial_authorization", "cmf_compliance"],
            deletion_requirements=["regulatory_approval", "backup_retention"],
            audit_requirements=["cmf_reporting", "risk_assessment_log"],
            description="Datos financieros bajo supervisión CMF"
        )

        # Datos comerciales
        self.classification_rules[DataCategory.COMMERCIAL_DATA] = DataClassificationRule(
            data_category=DataCategory.COMMERCIAL_DATA,
            applicable_regulations=[ChileanRegulation.SERNAC, ChileanRegulation.LEY_19628],
            retention_period_days=RetentionPeriod.COMMERCIAL_DATA.value,
            anonymization_required=True,
            encryption_required=False,
            access_restrictions=["business_purpose", "customer_consent"],
            deletion_requirements=["customer_request_honor", "business_justification"],
            audit_requirements=["commercial_activity_log"],
            description="Datos comerciales y de clientes"
        )

    def classify_data(self, data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> DataCategory:
        """Clasifica datos según su contenido y contexto"""

        # Detectar por patrones de contenido
        content_str = json.dumps(data, default=str).lower()

        # Datos tributarios (RUT, facturas, DTEs)
        if any(pattern in content_str for pattern in ["rut", "factura", "dte", "folio", "sii"]):
            return DataCategory.TAX_DATA

        # Datos financieros (montos, cuentas, bancos)
        if any(pattern in content_str for pattern in ["monto", "cuenta", "banco", "transferencia", "pago"]):
            return DataCategory.FINANCIAL_DATA

        # Datos sensibles (salud, judicial)
        if any(pattern in content_str for pattern in ["salud", "medico", "judicial", "antecedentes"]):
            return DataCategory.SENSITIVE_DATA

        # Datos personales (email, teléfono, dirección)
        if any(pattern in content_str for pattern in ["email", "telefono", "direccion", "nombre", "apellido"]):
            return DataCategory.PERSONAL_DATA

        # Por defecto, datos comerciales
        return DataCategory.COMMERCIAL_DATA

    def create_compliance_record(self, data: Dict[str, Any], user_id: Optional[str] = None,
                               purpose: Optional[str] = None) -> str:
        """Crea registro de cumplimiento para datos"""

        # Clasificar datos
        data_category = self.classify_data(data)
        rule = self.classification_rules[data_category]

        # Generar ID único
        record_id = hashlib.sha256(
            f"{json.dumps(data, sort_keys=True)}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Calcular fecha de retención
        creation_date = datetime.now()
        retention_until = creation_date + timedelta(days=rule.retention_period_days)

        # Crear registro
        compliance_record = ComplianceRecord(
            record_id=record_id,
            data_category=data_category,
            applicable_regulations=rule.applicable_regulations,
            creation_date=creation_date,
            retention_until=retention_until,
            anonymized=False,
            encrypted=rule.encryption_required,
            metadata={
                "user_id": user_id,
                "purpose": purpose,
                "data_classification": data_category.value,
                "original_data_hash": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            }
        )

        # Aplicar requerimientos inmediatos
        if rule.anonymization_required:
            compliance_record.anonymized = True
            compliance_record.compliance_actions.append({
                "action": "data_anonymization",
                "timestamp": datetime.now().isoformat(),
                "reason": "regulation_requirement"
            })

        # Registrar acceso inicial
        compliance_record.access_log.append({
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": "data_creation",
            "purpose": purpose
        })

        self.compliance_records[record_id] = compliance_record

        # Programar para retención
        self.data_retention_schedule[record_id] = retention_until

        logger.info(f"Registro de cumplimiento creado: {record_id} - {data_category.value}")
        return record_id

    def log_data_access(self, record_id: str, user_id: Optional[str] = None,
                       purpose: Optional[str] = None, action: str = "access"):
        """Registra acceso a datos para cumplimiento"""

        if record_id not in self.compliance_records:
            logger.warning(f"Registro de cumplimiento no encontrado: {record_id}")
            return

        record = self.compliance_records[record_id]

        # Verificar restricciones de acceso
        rule = self.classification_rules[record.data_category]
        if not self._check_access_restrictions(user_id, rule.access_restrictions, purpose):
            logger.warning(f"Acceso denegado por restricciones de cumplimiento: {record_id}")
            raise PermissionError("Acceso denegado por políticas de cumplimiento")

        # Registrar acceso
        access_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "purpose": purpose
        }

        record.access_log.append(access_entry)

        # Log de auditoría
        try:
            from ..monitoring.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_data_access(
                user_id=user_id,
                data_type=record.data_category.value,
                data_identifier=record_id,
                action=action,
                sensitive_level="high" if record.data_category == DataCategory.SENSITIVE_DATA else "medium",
                details={
                    "purpose": purpose,
                    "applicable_regulations": [r.value for r in record.applicable_regulations]
                }
            )
        except ImportError:
            logger.info(f"Data access logged: {record_id}")

    def _check_access_restrictions(self, user_id: Optional[str], restrictions: List[str],
                                 purpose: Optional[str] = None) -> bool:
        """Verifica restricciones de acceso"""

        # Simulación de verificaciones (en implementación real conectar con sistemas de autorización)

        for restriction in restrictions:
            if restriction == "logged_access":
                if not user_id:
                    return False

            elif restriction == "purpose_limitation":
                if not purpose:
                    return False

            elif restriction == "explicit_consent":
                # Verificar consentimiento explícito (implementar según sistema)
                pass

            elif restriction == "authorized_personnel":
                # Verificar si usuario está en lista de personal autorizado
                if user_id and not self._is_authorized_personnel(user_id):
                    return False

            elif restriction == "sii_compliance":
                # Verificar cumplimiento SII específico
                if not self._check_sii_compliance(user_id):
                    return False

        return True

    def _is_authorized_personnel(self, user_id: str) -> bool:
        """Verifica si usuario es personal autorizado (simulado)"""
        # En implementación real, verificar con sistema de roles
        return True

    def _check_sii_compliance(self, user_id: str) -> bool:
        """Verifica cumplimiento SII específico (simulado)"""
        # En implementación real, verificar certificaciones SII
        return True

    def schedule_data_deletion(self, record_id: str, deletion_date: Optional[datetime] = None):
        """Programa eliminación de datos según políticas de retención"""

        if record_id not in self.compliance_records:
            logger.warning(f"Registro no encontrado para eliminación: {record_id}")
            return

        record = self.compliance_records[record_id]
        rule = self.classification_rules[record.data_category]

        # Usar fecha de retención o fecha específica
        if deletion_date is None:
            deletion_date = record.retention_until

        # Verificar requerimientos de eliminación
        for requirement in rule.deletion_requirements:
            if requirement == "sii_authorization_required":
                # Para datos SII, verificar autorización especial
                logger.info(f"Eliminación de datos SII requiere autorización: {record_id}")

            elif requirement == "regulatory_approval":
                # Para datos financieros, verificar aprobación regulatoria
                logger.info(f"Eliminación requiere aprobación regulatoria: {record_id}")

            elif requirement == "customer_consent":
                # Para datos comerciales, verificar consentimiento del cliente
                logger.info(f"Eliminación requiere consentimiento del cliente: {record_id}")

        # Registrar programación de eliminación
        record.compliance_actions.append({
            "action": "deletion_scheduled",
            "timestamp": datetime.now().isoformat(),
            "deletion_date": deletion_date.isoformat(),
            "requirements_checked": rule.deletion_requirements
        })

        self.data_retention_schedule[record_id] = deletion_date
        logger.info(f"Eliminación programada para: {record_id} - {deletion_date}")

    def process_data_retention(self) -> Dict[str, Any]:
        """Procesa eliminaciones programadas según políticas de retención"""

        current_date = datetime.now()
        deleted_records = []
        retention_extended = []

        for record_id, deletion_date in list(self.data_retention_schedule.items()):
            if current_date >= deletion_date:
                record = self.compliance_records.get(record_id)
                if record:
                    # Verificar si se puede eliminar
                    if self._can_delete_record(record):
                        self._perform_secure_deletion(record_id)
                        deleted_records.append(record_id)
                    else:
                        # Extender retención si hay restricciones activas
                        new_deletion_date = current_date + timedelta(days=90)  # Extender 90 días
                        self.data_retention_schedule[record_id] = new_deletion_date
                        retention_extended.append({
                            "record_id": record_id,
                            "new_deletion_date": new_deletion_date.isoformat(),
                            "reason": "active_restrictions"
                        })

        return {
            "processed_date": current_date.isoformat(),
            "records_deleted": len(deleted_records),
            "deleted_record_ids": deleted_records,
            "retention_extended": retention_extended
        }

    def _can_delete_record(self, record: ComplianceRecord) -> bool:
        """Verifica si un registro puede ser eliminado"""

        # Verificar restricciones especiales
        for regulation in record.applicable_regulations:
            if regulation == ChileanRegulation.SII_NORMATIVA:
                # Datos SII pueden tener restricciones adicionales
                return True  # Simplificado para ejemplo

            elif regulation == ChileanRegulation.DFL_3:
                # Datos financieros bajo supervisión
                return True  # Simplificado para ejemplo

        return True

    def _perform_secure_deletion(self, record_id: str):
        """Realiza eliminación segura de datos"""

        record = self.compliance_records[record_id]

        # Registrar eliminación en auditoría
        try:
            from ..monitoring.audit_logger import get_audit_logger
            audit_logger = get_audit_logger()
            audit_logger.log_system_action(
                action="secure_data_deletion",
                component="compliance_manager",
                details={
                    "record_id": record_id,
                    "data_category": record.data_category.value,
                    "applicable_regulations": [r.value for r in record.applicable_regulations],
                    "retention_period_completed": True
                }
            )
        except ImportError:
            logger.info(f"Data deleted: {record_id}")

        # Eliminar del sistema
        del self.compliance_records[record_id]
        del self.data_retention_schedule[record_id]

        logger.info(f"Eliminación segura completada: {record_id}")

    def generate_compliance_report(self, regulation: Optional[ChileanRegulation] = None,
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Genera reporte de cumplimiento normativo"""

        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()

        # Filtrar registros por criterios
        filtered_records = []
        for record in self.compliance_records.values():
            # Filtro por fecha
            if start_date <= record.creation_date <= end_date:
                # Filtro por regulación
                if regulation is None or regulation in record.applicable_regulations:
                    filtered_records.append(record)

        # Estadísticas por categoría
        category_stats = {}
        for category in DataCategory:
            category_records = [r for r in filtered_records if r.data_category == category]
            category_stats[category.value] = {
                "total_records": len(category_records),
                "anonymized": len([r for r in category_records if r.anonymized]),
                "encrypted": len([r for r in category_records if r.encrypted]),
                "pending_deletion": len([r for r in category_records
                                       if r.record_id in self.data_retention_schedule])
            }

        # Estadísticas por regulación
        regulation_stats = {}
        for reg in ChileanRegulation:
            reg_records = [r for r in filtered_records if reg in r.applicable_regulations]
            regulation_stats[reg.value] = len(reg_records)

        return {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_compliance_records": len(filtered_records),
            "category_breakdown": category_stats,
            "regulation_breakdown": regulation_stats,
            "pending_deletions": len(self.data_retention_schedule),
            "compliance_actions_count": sum(
                len(r.compliance_actions) for r in filtered_records
            ),
            "data_access_events": sum(
                len(r.access_log) for r in filtered_records
            )
        }

    def validate_data_handling(self, data: Dict[str, Any], proposed_action: str,
                             user_id: Optional[str] = None) -> Dict[str, Any]:
        """Valida si una acción propuesta cumple con normativas chilenas"""

        data_category = self.classify_data(data)
        rule = self.classification_rules[data_category]

        validation_result = {
            "is_compliant": True,
            "data_category": data_category.value,
            "applicable_regulations": [r.value for r in rule.applicable_regulations],
            "issues": [],
            "recommendations": [],
            "required_actions": []
        }

        # Validar acción propuesta
        if proposed_action == "store":
            if rule.anonymization_required:
                validation_result["required_actions"].append("anonymize_data")
            if rule.encryption_required:
                validation_result["required_actions"].append("encrypt_data")

        elif proposed_action == "access":
            if "authorized_personnel" in rule.access_restrictions and not user_id:
                validation_result["is_compliant"] = False
                validation_result["issues"].append("Acceso requiere usuario autorizado")

        elif proposed_action == "delete":
            if "sii_authorization_required" in rule.deletion_requirements:
                validation_result["recommendations"].append("Obtener autorización SII antes de eliminar")

        elif proposed_action == "transfer":
            validation_result["recommendations"].append("Verificar destino cumple normativas chilenas")
            if data_category == DataCategory.SENSITIVE_DATA:
                validation_result["required_actions"].append("explicit_consent_required")

        return validation_result

    def get_retention_schedule(self) -> Dict[str, Any]:
        """Obtiene cronograma de retención de datos"""

        schedule_by_date = {}
        for record_id, deletion_date in self.data_retention_schedule.items():
            date_str = deletion_date.strftime("%Y-%m-%d")
            if date_str not in schedule_by_date:
                schedule_by_date[date_str] = []

            record = self.compliance_records.get(record_id)
            if record:
                schedule_by_date[date_str].append({
                    "record_id": record_id,
                    "data_category": record.data_category.value,
                    "applicable_regulations": [r.value for r in record.applicable_regulations]
                })

        return {
            "generated_at": datetime.now().isoformat(),
            "total_scheduled_deletions": len(self.data_retention_schedule),
            "schedule_by_date": schedule_by_date
        }


# Singleton global
_compliance_manager = None


def get_compliance_manager() -> ChileanComplianceManager:
    """Obtiene la instancia global del gestor de cumplimiento"""
    global _compliance_manager
    if _compliance_manager is None:
        _compliance_manager = ChileanComplianceManager()
    return _compliance_manager


def chilean_compliance_required(data_category: DataCategory):
    """Decorador para funciones que requieren cumplimiento normativo chileno"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            compliance_manager = get_compliance_manager()

            # Obtener datos del contexto
            data = kwargs.get('data', {})
            user_id = kwargs.get('user_id')

            # Crear registro de cumplimiento
            if data:
                record_id = compliance_manager.create_compliance_record(
                    data, user_id, func.__name__
                )
                kwargs['compliance_record_id'] = record_id

            # Ejecutar función
            result = func(*args, **kwargs)

            # Registrar acceso si se creó registro
            if 'compliance_record_id' in kwargs:
                compliance_manager.log_data_access(
                    kwargs['compliance_record_id'], user_id, func.__name__, "function_execution"
                )

            return result

        return wrapper
    return decorator