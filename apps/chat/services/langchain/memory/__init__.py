"""
Módulo de Memoria Avanzada para Sistema Multi-Agente

Proporciona:
- Memoria separada por agente
- Memoria a corto y largo plazo
- Context injection seguro
- Resumen automático de contexto
- Memoria basada en eventos
- Sincronización entre agentes
"""

from .advanced_memory_system import (
    AdvancedMemorySystem,
    AgentMemoryManager,
    ConversationEvent,
    UserProfile,
    advanced_memory_system
)

__all__ = [
    'AdvancedMemorySystem',
    'AgentMemoryManager',
    'ConversationEvent',
    'UserProfile',
    'advanced_memory_system'
]