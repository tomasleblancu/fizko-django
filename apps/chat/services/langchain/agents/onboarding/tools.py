"""
Tools para el agente de onboarding - integración con APIs reales de Django
"""
from langchain.tools import tool
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Context global para el usuario
_user_context = {}

def set_onboarding_context(session_id: str, context: dict):
    """Establece el contexto para la sesión de onboarding"""
    global _user_context
    _user_context[session_id] = context

def get_onboarding_context(session_id: str) -> dict:
    """Obtiene el contexto de la sesión de onboarding"""
    global _user_context
    return _user_context.get(session_id, {})


@tool
def get_onboarding_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual del onboarding para el usuario autenticado actual

    Returns:
        Dict con el estado actual del onboarding
    """
    try:
        # Obtener usuario del contexto global
        context_keys = list(_user_context.keys())
        if not context_keys:
            return {
                "success": False,
                "error": "NO_CONTEXT",
                "message": "No hay contexto de usuario disponible"
            }

        # Usar el contexto más reciente
        latest_context = _user_context[context_keys[-1]]
        user_id = latest_context.get('user_id')

        if not user_id:
            return {
                "success": False,
                "error": "NO_USER_ID",
                "message": "No se encontró user_id en el contexto"
            }

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Importar la vista de onboarding
        from apps.onboarding.views import UserOnboardingViewSet
        from unittest.mock import Mock

        # Crear request mock
        request = Mock()
        request.user = user

        # Crear instancia del viewset
        viewset = UserOnboardingViewSet()

        # Obtener status
        response = viewset.status(request)

        if response.status_code == 200:
            return {
                "success": True,
                "status": response.data,
                "message": "Estado de onboarding obtenido exitosamente"
            }
        else:
            return {
                "success": False,
                "error": "Error obteniendo estado",
                "message": "No se pudo obtener el estado del onboarding"
            }

    except Exception as e:
        logger.error(f"Error obteniendo estado de onboarding: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error interno obteniendo estado del onboarding"
        }


@tool
def update_onboarding_step(step: int, data: Dict[str, Any], status: str = "completed") -> Dict[str, Any]:
    """
    Actualiza un paso específico del onboarding

    Args:
        step: Número del paso (1-4)
        data: Datos del paso a guardar
        status: Estado del paso (completed, in_progress)

    Returns:
        Dict con resultado de la actualización
    """
    try:
        # Obtener usuario del contexto global
        context_keys = list(_user_context.keys())
        if not context_keys:
            return {
                "success": False,
                "error": "NO_CONTEXT",
                "message": "No hay contexto de usuario disponible"
            }

        latest_context = _user_context[context_keys[-1]]
        user_id = latest_context.get('user_id')

        if not user_id:
            return {
                "success": False,
                "error": "NO_USER_ID",
                "message": "No se encontró user_id en el contexto"
            }

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Importar la vista de onboarding
        from apps.onboarding.views import UserOnboardingViewSet
        from unittest.mock import Mock

        # Crear request mock
        request = Mock()
        request.user = user
        request.data = {
            'step': step,
            'data': data,
            'status': status
        }

        # Crear instancia del viewset
        viewset = UserOnboardingViewSet()

        # Actualizar paso
        response = viewset.update_step(request)

        if response.status_code == 200:
            return {
                "success": True,
                "step": step,
                "status": status,
                "data": response.data,
                "message": f"Paso {step} actualizado exitosamente"
            }
        else:
            return {
                "success": False,
                "error": f"Error HTTP {response.status_code}",
                "message": f"Error actualizando paso {step}",
                "details": response.data if hasattr(response, 'data') else None
            }

    except Exception as e:
        logger.error(f"Error actualizando paso {step}: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Error interno actualizando paso {step}"
        }


@tool
def finalize_onboarding() -> Dict[str, Any]:
    """
    Finaliza el onboarding creando la empresa y iniciando sincronizaciones

    Returns:
        Dict con resultado de la finalización
    """
    try:
        # Obtener usuario del contexto global
        context_keys = list(_user_context.keys())
        if not context_keys:
            return {
                "success": False,
                "error": "NO_CONTEXT",
                "message": "No hay contexto de usuario disponible"
            }

        latest_context = _user_context[context_keys[-1]]
        user_id = latest_context.get('user_id')

        if not user_id:
            return {
                "success": False,
                "error": "NO_USER_ID",
                "message": "No se encontró user_id en el contexto"
            }

        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Importar la vista de onboarding
        from apps.onboarding.views import UserOnboardingViewSet
        from unittest.mock import Mock

        # Crear request mock
        request = Mock()
        request.user = user

        # Crear instancia del viewset
        viewset = UserOnboardingViewSet()

        # Finalizar onboarding
        response = viewset.finalize(request)

        if response.status_code == 200:
            return {
                "success": True,
                "data": response.data,
                "message": "Onboarding finalizado exitosamente. Tu empresa ha sido creada y se están sincronizando los datos.",
                "next_steps": "Puedes acceder al dashboard para comenzar a usar Fizko"
            }
        else:
            error_data = response.data if hasattr(response, 'data') else {}
            return {
                "success": False,
                "error": error_data.get('error', 'FINALIZATION_ERROR'),
                "message": error_data.get('message', 'Error finalizando onboarding'),
                "details": error_data
            }

    except Exception as e:
        logger.error(f"Error finalizando onboarding: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error interno finalizando onboarding"
        }