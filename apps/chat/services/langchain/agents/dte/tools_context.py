"""
Herramientas DTE que reciben contexto del usuario para restricción de acceso
"""
from typing import Dict, Any, Optional
from langchain_core.tools import tool

# Importar las herramientas base con restricción de usuario
from .tools import (
    get_document_types_info as _get_document_types_info,
    validate_dte_code as _validate_dte_code,
    search_documents_by_criteria as _search_documents_by_criteria,
    get_document_stats_summary as _get_document_stats_summary,
    calculate_dte_tax_impact as _calculate_dte_tax_impact,
    get_recent_documents_summary as _get_recent_documents_summary,
    get_taxpayer_information as _get_taxpayer_information,
)


# Variables globales para almacenar el contexto completo del usuario
_current_user_id: Optional[int] = None
_current_user_context: Dict[str, Any] = {}


def set_user_context(user_id: Optional[int], full_context: Optional[Dict[str, Any]] = None):
    """Establece el contexto del usuario para las herramientas"""
    global _current_user_id, _current_user_context
    _current_user_id = user_id
    if full_context:
        _current_user_context = full_context
    else:
        _current_user_context = {"user_id": user_id}


def get_user_context() -> Optional[int]:
    """Obtiene el user_id del usuario actual"""
    return _current_user_id


def get_full_user_context() -> Dict[str, Any]:
    """Obtiene el contexto completo del usuario actual"""
    return _current_user_context


@tool
def get_document_types_info_secured(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene información sobre los tipos de documentos DTE disponibles.
    Versión con contexto de usuario.

    Args:
        category: Categoría opcional (invoice, receipt, credit_note, debit_note, dispatch, export, other)

    Returns:
        Dict con información de tipos de documentos
    """
    return _get_document_types_info.invoke({"category": category})


@tool
def validate_dte_code_secured(dte_code: int) -> Dict[str, Any]:
    """
    Valida un código de DTE y retorna información sobre el tipo de documento.
    Versión con contexto de usuario.

    Args:
        dte_code: Código numérico del DTE (ej: 33, 34, 39, 61, etc.)

    Returns:
        Dict con validación y información del DTE
    """
    return _validate_dte_code.invoke({"dte_code": dte_code})


@tool
def search_documents_by_criteria_secured(
    company_rut: Optional[str] = None,
    document_type_code: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Busca documentos según criterios específicos, restringido a las empresas del usuario autenticado.

    Args:
        company_rut: RUT de la empresa (sin puntos ni guión)
        document_type_code: Código del tipo de documento
        status: Estado del documento (draft, pending, signed, sent, accepted, rejected, cancelled, processed)
        date_from: Fecha desde (formato YYYY-MM-DD)
        date_to: Fecha hasta (formato YYYY-MM-DD)
        limit: Límite de resultados (default: 10)

    Returns:
        Dict con documentos encontrados (solo del usuario actual)
    """
    return _search_documents_by_criteria.invoke({
        "company_rut": company_rut,
        "document_type_code": document_type_code,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "user_id": get_user_context()
    })


@tool
def get_document_stats_summary_secured(company_rut: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene un resumen estadístico de documentos, restringido a las empresas del usuario autenticado.

    Args:
        company_rut: RUT de la empresa (opcional, sin puntos ni guión)

    Returns:
        Dict con estadísticas de documentos (solo del usuario actual)
    """
    return _get_document_stats_summary.invoke({
        "company_rut": company_rut,
        "user_id": get_user_context()
    })


@tool
def calculate_dte_tax_impact_secured(
    net_amount: float,
    document_type_code: int,
    is_credit_note: bool = False
) -> Dict[str, Any]:
    """
    Calcula el impacto tributario de un DTE.
    Versión con contexto de usuario.

    Args:
        net_amount: Monto neto del documento
        document_type_code: Código del tipo de documento
        is_credit_note: True si es nota de crédito (afecta negativamente)

    Returns:
        Dict con cálculos tributarios
    """
    return _calculate_dte_tax_impact.invoke({
        "net_amount": net_amount,
        "document_type_code": document_type_code,
        "is_credit_note": is_credit_note
    })


@tool
def get_recent_documents_summary_secured(
    days_back: int = 30,
    company_rut: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Obtiene un resumen de documentos recientes con detalles específicos, restringido a las empresas del usuario autenticado.

    Args:
        days_back: Días hacia atrás para buscar (default: 30)
        company_rut: RUT de la empresa (opcional, sin puntos ni guión)
        document_type: Tipo de documento: 'received' (recibidos), 'issued' (emitidos), 'all' (todos)
        limit: Límite de documentos a mostrar (default: 20)

    Returns:
        Dict con resumen detallado de documentos recientes (solo del usuario actual)
    """
    return _get_recent_documents_summary.invoke({
        "days_back": days_back,
        "company_rut": company_rut,
        "document_type": document_type,
        "limit": limit,
        "user_id": get_user_context()
    })


@tool
def get_taxpayer_information_secured(
    include_raw_data: bool = True,
    include_socios: bool = True,
    include_actividades: bool = True,
    include_representantes: bool = True,
    include_direcciones: bool = True,
    include_timbrajes: bool = True
) -> Dict[str, Any]:
    """
    Obtiene información completa del contribuyente (Taxpayer) incluyendo raw data del SII.
    Versión con contexto de usuario.

    Args:
        include_raw_data: Incluir datos raw completos del SII
        include_socios: Incluir información de socios
        include_actividades: Incluir actividades económicas
        include_representantes: Incluir representantes legales
        include_direcciones: Incluir direcciones registradas
        include_timbrajes: Incluir información de documentos timbrados

    Returns:
        Dict con información completa del taxpayer (solo del usuario actual)
    """
    return _get_taxpayer_information.invoke({
        "user_id": get_user_context(),
        "include_raw_data": include_raw_data,
        "include_socios": include_socios,
        "include_actividades": include_actividades,
        "include_representantes": include_representantes,
        "include_direcciones": include_direcciones,
        "include_timbrajes": include_timbrajes
    })