"""
Tipos de datos para el manejo de formularios F29
Migrado desde legacy fizko-backend
"""
from typing import List, Dict, Optional, TypedDict


class ValorFila(TypedDict):
    """Representa un valor individual en una fila del F29"""
    code: str
    value: str


class FilaDatos(TypedDict):
    """Representa una fila completa de datos en el F29"""
    line: str
    description: str
    values: List[ValorFila]


class ColumnasSubtabla(TypedDict):
    """Representa las columnas de una subtabla del F29"""
    title: str
    columns: List[str]


class SubtablaF29(TypedDict):
    """Representa una subtabla completa del formulario F29"""
    main_title: str
    subtitles: List[str]
    columns: ColumnasSubtabla
    rows: List[FilaDatos]


class CampoF29(TypedDict):
    """Representa un campo individual del F29 con su metadata"""
    name: str
    type: str
    task: str
    subject: str
    code: str
    xpath: str


class ResumenF29(TypedDict):
    """Resumen básico del formulario F29"""
    folio: str
    period: str
    contributor: str
    submission_date: str
    status: str
    amount: int


class EventoHistorialF29(TypedDict):
    """Evento en el historial del F29"""
    date: str
    description: str
    detail: str


class FormularioF29(TypedDict):
    """Representa un formulario F29 encontrado en búsquedas"""
    folio: str
    period: str
    contributor: str
    submission_date: str
    status: str
    amount: int


class DetalleF29(TypedDict):
    """Detalle completo del formulario F29"""
    resumen: ResumenF29
    subtablas: List[SubtablaF29]
    historial: List[EventoHistorialF29]
    campos_extraidos: List[ValorFila]