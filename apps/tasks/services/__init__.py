"""
Servicios de lógica de negocio para el módulo de tareas
"""
from .process_assignment import ProcessAssignmentService
from .template_factory import ProcessTemplateFactory

__all__ = ['ProcessAssignmentService', 'ProcessTemplateFactory']
