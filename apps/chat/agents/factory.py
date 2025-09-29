"""
Factory Pattern para crear agentes desde configuración de base de datos
Mantiene compatibilidad con sistema anterior mientras permite migración gradual
"""
from typing import Union, Dict, Any
from .dynamic_langchain_agent import DynamicLangChainAgent
import logging


class AgentFactory:
    """
    Factory para crear agentes dinámicos o del sistema anterior
    """

    @staticmethod
    def create_agent(agent_config_id: int = None, agent_type: str = None, **kwargs):
        """
        Crea un agente según el tipo especificado

        Args:
            agent_config_id: ID del AgentConfig en base de datos
            agent_type: Tipo de agente para crear (fallback al sistema anterior)
            **kwargs: Parámetros adicionales

        Returns:
            Instancia del agente correspondiente
        """
        logger = logging.getLogger(__name__)

        # Prioridad 1: Si se especifica agent_config_id, usar sistema dinámico
        if agent_config_id:
            try:
                return DynamicLangChainAgent(agent_config_id)
            except Exception as e:
                logger.error(f"Error creando agente dinámico {agent_config_id}: {e}")
                raise

        # Prioridad 2: Si se especifica agent_type, buscar en BD o usar sistema anterior
        if agent_type:
            return AgentFactory._create_by_type(agent_type, **kwargs)

        raise ValueError("Debe especificar agent_config_id o agent_type")

    @staticmethod
    def _create_by_type(agent_type: str, **kwargs):
        """
        Crea agente dinámico por tipo desde base de datos
        """
        from apps.chat.models import AgentConfig
        logger = logging.getLogger(__name__)

        # Buscar agente dinámico en base de datos
        agent_config = AgentConfig.objects.filter(
            agent_type=agent_type,
            status='active'
        ).first()

        if not agent_config:
            raise ValueError(f"No se encontró agente dinámico activo para tipo {agent_type}")

        logger.info(f"Usando agente dinámico: {agent_config.name} (ID: {agent_config.id})")
        return DynamicLangChainAgent(agent_config.id)

    @staticmethod
    def get_available_agents() -> Dict[str, Dict[str, Any]]:
        """
        Retorna información de todos los agentes disponibles
        """
        from apps.chat.models import AgentConfig

        agents_info = {
            "dynamic_agents": [],
            "legacy_agents": []
        }

        # Agentes dinámicos desde BD
        for config in AgentConfig.objects.filter(status='active'):
            agents_info["dynamic_agents"].append({
                "id": config.id,
                "name": config.name,
                "agent_type": config.agent_type,
                "description": config.description,
                "model_name": config.model_name,
                "created_at": config.created_at.isoformat() if config.created_at else None
            })

        # Agentes del sistema anterior
        legacy_agents = [
            {
                "agent_type": "dte",
                "name": "DTE Agent (Legacy)",
                "description": "Agente especializado en documentos tributarios electrónicos"
            },
            {
                "agent_type": "sii",
                "name": "SII Agent (Legacy)",
                "description": "Agente general para servicios del SII"
            }
        ]

        agents_info["legacy_agents"] = legacy_agents

        return agents_info

    @staticmethod
    def create_agent_for_chat(agent_identifier: Union[int, str], **kwargs):
        """
        Método específico para usar en el sistema de chat

        Args:
            agent_identifier: ID del AgentConfig o tipo de agente
            **kwargs: Contexto adicional

        Returns:
            Agente listo para usar en chat
        """
        if isinstance(agent_identifier, int):
            # Es un ID de AgentConfig
            return AgentFactory.create_agent(agent_config_id=agent_identifier, **kwargs)
        elif isinstance(agent_identifier, str):
            # Es un tipo de agente
            return AgentFactory.create_agent(agent_type=agent_identifier, **kwargs)
        else:
            raise ValueError("agent_identifier debe ser int (ID) o str (tipo)")


# Funciones de conveniencia para compatibilidad
def create_dte_agent():
    """Crea agente DTE (dinámico si existe, legacy si no)"""
    return AgentFactory.create_agent(agent_type='dte')


def create_sii_agent():
    """Crea agente SII (dinámico si existe, legacy si no)"""
    return AgentFactory.create_agent(agent_type='sii')


def create_dynamic_agent(agent_config_id: int):
    """Crea agente dinámico específico"""
    return AgentFactory.create_agent(agent_config_id=agent_config_id)


# Alias para compatibilidad con código existente
def get_agent_by_type(agent_type: str):
    """Alias para compatibilidad con código existente"""
    return AgentFactory.create_agent(agent_type=agent_type)