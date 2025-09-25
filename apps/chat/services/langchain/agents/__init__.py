"""
Agentes especializados para el sistema multi-agente

Estructura simplificada:
- dte/     - Documentos Tributarios Electrónicos EXCLUSIVAMENTE
- sii/     - Agente General (servicios SII, FAQ, información de empresa, contabilidad general)
"""

from .dte.agent import DTEAgent
from .sii.agent import SIIAgent as GeneralAgent

__all__ = [
    'DTEAgent',
    'GeneralAgent'
]