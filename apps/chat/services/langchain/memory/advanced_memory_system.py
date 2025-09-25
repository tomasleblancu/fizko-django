"""
Sistema Avanzado de Memoria y Contexto para Multi-Agente

Características:
- Memoria separada por agente
- Memoria a corto y largo plazo
- Context injection seguro
- Resumen automático de contexto
- Memoria basada en eventos
- Sincronización entre agentes
"""
import json
import hashlib
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from django.core.cache import cache
from django.conf import settings
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationEvent:
    """Evento de conversación para memoria procedimental"""
    timestamp: datetime
    event_type: str  # 'user_query', 'agent_response', 'action_taken', 'error_occurred'
    agent: str
    content: str
    metadata: Dict[str, Any] = None
    importance: float = 0.5  # 0.0-1.0, para filtrado futuro

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationEvent':
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class UserProfile:
    """Perfil del usuario para personalización"""
    user_id: str
    company_ids: List[str]
    preferences: Dict[str, Any]
    expertise_level: str  # 'beginner', 'intermediate', 'expert'
    frequently_used_agents: List[str]
    last_activity: datetime
    security_context: Dict[str, Any] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['last_activity'] = self.last_activity.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'UserProfile':
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        return cls(**data)


class AgentMemoryManager:
    """Gestor de memoria específico para cada agente"""

    def __init__(self, agent_name: str, user_id: str, conversation_id: str):
        self.agent_name = agent_name
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.memory_key = f"agent_memory_{agent_name}_{user_id}_{conversation_id}"

        # Configuración de memoria
        self.short_term_limit = 20  # Últimos N mensajes
        self.long_term_days = 30    # Días de retención
        self.max_context_tokens = 3000  # Límite para LLM

        # Estado de memoria
        self.short_term_memory: List[BaseMessage] = []
        self.long_term_events: List[ConversationEvent] = []
        self.context_summary: Optional[str] = None
        self.agent_specific_data: Dict[str, Any] = {}

        self._load_memory()

    def _get_memory_cache_key(self, memory_type: str) -> str:
        """Genera clave de cache para diferentes tipos de memoria"""
        return f"{self.memory_key}_{memory_type}"

    def _load_memory(self):
        """Carga memoria desde cache/persistencia"""
        try:
            # Cargar memoria a corto plazo
            short_term_data = cache.get(self._get_memory_cache_key("short_term"))
            if short_term_data:
                self.short_term_memory = pickle.loads(short_term_data)

            # Cargar eventos a largo plazo
            long_term_data = cache.get(self._get_memory_cache_key("long_term"))
            if long_term_data:
                events_dict = json.loads(long_term_data)
                self.long_term_events = [ConversationEvent.from_dict(e) for e in events_dict]

            # Cargar resumen de contexto
            self.context_summary = cache.get(self._get_memory_cache_key("summary"))

            # Cargar datos específicos del agente
            agent_data = cache.get(self._get_memory_cache_key("agent_data"))
            if agent_data:
                self.agent_specific_data = json.loads(agent_data)

            logger.info(f"Memoria cargada para {self.agent_name}: {len(self.short_term_memory)} mensajes recientes")

        except Exception as e:
            logger.error(f"Error cargando memoria para {self.agent_name}: {e}")

    def _save_memory(self):
        """Guarda memoria en cache/persistencia"""
        try:
            # Guardar memoria a corto plazo (24 horas)
            cache.set(
                self._get_memory_cache_key("short_term"),
                pickle.dumps(self.short_term_memory),
                60 * 60 * 24
            )

            # Guardar eventos a largo plazo (30 días)
            events_dict = [event.to_dict() for event in self.long_term_events]
            cache.set(
                self._get_memory_cache_key("long_term"),
                json.dumps(events_dict, ensure_ascii=False),
                60 * 60 * 24 * 30
            )

            # Guardar resumen de contexto (7 días)
            if self.context_summary:
                cache.set(
                    self._get_memory_cache_key("summary"),
                    self.context_summary,
                    60 * 60 * 24 * 7
                )

            # Guardar datos específicos del agente (30 días)
            cache.set(
                self._get_memory_cache_key("agent_data"),
                json.dumps(self.agent_specific_data, ensure_ascii=False),
                60 * 60 * 24 * 30
            )

        except Exception as e:
            logger.error(f"Error guardando memoria para {self.agent_name}: {e}")

    def add_message(self, message: BaseMessage, importance: float = 0.5):
        """Añade mensaje a la memoria"""
        # Agregar a memoria a corto plazo
        self.short_term_memory.append(message)

        # Mantener límite de memoria a corto plazo
        if len(self.short_term_memory) > self.short_term_limit:
            # Mover mensajes antiguos a eventos de largo plazo
            old_message = self.short_term_memory.pop(0)
            event = ConversationEvent(
                timestamp=datetime.now(),
                event_type='message_archived',
                agent=self.agent_name,
                content=old_message.content if hasattr(old_message, 'content') else str(old_message),
                importance=importance
            )
            self.long_term_events.append(event)

        # Guardar cambios
        self._save_memory()

    def add_event(self, event_type: str, content: str, metadata: Dict[str, Any] = None, importance: float = 0.5):
        """Añade evento a la memoria procedimental"""
        event = ConversationEvent(
            timestamp=datetime.now(),
            event_type=event_type,
            agent=self.agent_name,
            content=content,
            metadata=metadata,
            importance=importance
        )

        self.long_term_events.append(event)

        # Limpiar eventos antiguos
        cutoff_date = datetime.now() - timedelta(days=self.long_term_days)
        self.long_term_events = [e for e in self.long_term_events if e.timestamp > cutoff_date]

        self._save_memory()

    def get_context_for_agent(self, include_summary: bool = True) -> List[BaseMessage]:
        """Obtiene contexto optimizado para el agente"""
        context_messages = []

        # Agregar resumen si existe y se solicita
        if include_summary and self.context_summary:
            context_messages.append(
                SystemMessage(content=f"Resumen de conversación previa: {self.context_summary}")
            )

        # Agregar mensajes recientes de memoria a corto plazo
        context_messages.extend(self.short_term_memory)

        # Agregar eventos importantes de largo plazo si hay espacio
        if len(context_messages) < self.short_term_limit:
            important_events = sorted(
                [e for e in self.long_term_events if e.importance > 0.7],
                key=lambda x: x.timestamp,
                reverse=True
            )[:5]  # Top 5 eventos importantes

            for event in important_events:
                context_messages.append(
                    SystemMessage(content=f"Evento previo ({event.event_type}): {event.content}")
                )

        return context_messages

    def update_agent_data(self, key: str, value: Any):
        """Actualiza datos específicos del agente"""
        self.agent_specific_data[key] = value
        self._save_memory()

    def get_agent_data(self, key: str, default: Any = None) -> Any:
        """Obtiene datos específicos del agente"""
        return self.agent_specific_data.get(key, default)

    async def generate_context_summary(self, llm: ChatOpenAI):
        """Genera resumen automático del contexto usando LLM"""
        if len(self.short_term_memory) < 10:  # No generar resumen si hay pocos mensajes
            return

        try:
            # Crear prompt para resumen
            messages_text = "\n".join([
                f"{msg.type}: {msg.content[:200]}"
                for msg in self.short_term_memory[-10:]  # Últimos 10 mensajes
                if hasattr(msg, 'content')
            ])

            summary_prompt = f"""Resume la siguiente conversación manteniendo información clave para futuras interacciones con el agente {self.agent_name}.

Conversación:
{messages_text}

Genera un resumen conciso (máximo 200 palabras) que incluya:
- Temas principales discutidos
- Decisiones o acciones tomadas
- Información relevante para futuras consultas
- Estado actual de cualquier proceso en curso"""

            response = await llm.ainvoke([HumanMessage(content=summary_prompt)])
            self.context_summary = response.content

            # Limpiar memoria a corto plazo después de resumir
            self.short_term_memory = self.short_term_memory[-5:]  # Mantener solo los últimos 5

            self._save_memory()

            logger.info(f"Resumen de contexto generado para {self.agent_name}")

        except Exception as e:
            logger.error(f"Error generando resumen para {self.agent_name}: {e}")

    def get_memory_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de memoria"""
        return {
            'agent_name': self.agent_name,
            'short_term_messages': len(self.short_term_memory),
            'long_term_events': len(self.long_term_events),
            'has_summary': bool(self.context_summary),
            'agent_data_keys': list(self.agent_specific_data.keys()),
            'memory_age_days': (datetime.now() - min(
                [e.timestamp for e in self.long_term_events] + [datetime.now()]
            )).days if self.long_term_events else 0
        }


class AdvancedMemorySystem:
    """Sistema central de gestión de memoria avanzada"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Gestores de memoria por agente/usuario/conversación
        self.memory_managers: Dict[str, AgentMemoryManager] = {}

        # Perfiles de usuario
        self.user_profiles: Dict[str, UserProfile] = {}

        # Configuración de seguridad
        self.security_context_keys = ['user_id', 'company_ids', 'permissions', 'role']

    def get_memory_manager(self, agent_name: str, user_id: str, conversation_id: str) -> AgentMemoryManager:
        """Obtiene o crea gestor de memoria para agente específico"""
        manager_key = f"{agent_name}_{user_id}_{conversation_id}"

        if manager_key not in self.memory_managers:
            self.memory_managers[manager_key] = AgentMemoryManager(
                agent_name, user_id, conversation_id
            )

        return self.memory_managers[manager_key]

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Obtiene perfil del usuario"""
        if user_id not in self.user_profiles:
            # Intentar cargar desde cache
            profile_data = cache.get(f"user_profile_{user_id}")
            if profile_data:
                self.user_profiles[user_id] = UserProfile.from_dict(json.loads(profile_data))

        return self.user_profiles.get(user_id)

    def update_user_profile(self, user_profile: UserProfile):
        """Actualiza perfil del usuario"""
        self.user_profiles[user_profile.user_id] = user_profile

        # Guardar en cache por 7 días
        cache.set(
            f"user_profile_{user_profile.user_id}",
            json.dumps(user_profile.to_dict(), ensure_ascii=False),
            60 * 60 * 24 * 7
        )

    def inject_secure_context(self, agent_name: str, user_id: str, conversation_id: str,
                             base_messages: List[BaseMessage]) -> List[BaseMessage]:
        """Inyecta contexto seguro y personalizado"""
        try:
            # Obtener gestor de memoria del agente
            memory_manager = self.get_memory_manager(agent_name, user_id, conversation_id)

            # Obtener perfil del usuario
            user_profile = self.get_user_profile(user_id)

            # Construir contexto seguro
            context_messages = []

            # 1. Contexto de usuario (anonimizado para seguridad)
            if user_profile:
                user_context = SystemMessage(content=f"""Contexto del usuario:
- Nivel de experiencia: {user_profile.expertise_level}
- Agentes frecuentes: {user_profile.frequently_used_agents}
- Preferencias: {json.dumps(user_profile.preferences, ensure_ascii=False)}
- Empresas autorizadas: {len(user_profile.company_ids)} empresa(s)""")
                context_messages.append(user_context)

            # 2. Contexto específico del agente desde memoria
            agent_context = memory_manager.get_context_for_agent()
            context_messages.extend(agent_context)

            # 3. Mensajes base de la conversación actual
            context_messages.extend(base_messages)

            # 4. Contexto de seguridad (sin exponer datos sensibles)
            if user_profile and user_profile.security_context:
                security_info = {
                    k: "***" for k in self.security_context_keys
                    if k in user_profile.security_context
                }
                security_context = SystemMessage(
                    content=f"Contexto de seguridad: Usuario autenticado con permisos validados."
                )
                context_messages.insert(-len(base_messages), security_context)

            logger.info(f"Contexto inyectado para {agent_name}: {len(context_messages)} mensajes")

            return context_messages

        except Exception as e:
            logger.error(f"Error inyectando contexto para {agent_name}: {e}")
            return base_messages  # Fallback a mensajes base

    def synchronize_agents_memory(self, user_id: str, conversation_id: str,
                                 source_agent: str, target_agents: List[str],
                                 shared_info: Dict[str, Any]):
        """Sincroniza información entre agentes"""
        try:
            source_manager = self.get_memory_manager(source_agent, user_id, conversation_id)

            for target_agent in target_agents:
                target_manager = self.get_memory_manager(target_agent, user_id, conversation_id)

                # Crear evento de sincronización
                sync_event = ConversationEvent(
                    timestamp=datetime.now(),
                    event_type='agent_sync',
                    agent=target_agent,
                    content=f"Información compartida desde {source_agent}",
                    metadata=shared_info,
                    importance=0.8
                )

                target_manager.long_term_events.append(sync_event)
                target_manager._save_memory()

            logger.info(f"Memoria sincronizada de {source_agent} a {len(target_agents)} agentes")

        except Exception as e:
            logger.error(f"Error sincronizando memoria: {e}")

    async def compress_agent_memory(self, agent_name: str, user_id: str, conversation_id: str):
        """Comprime memoria del agente generando resúmenes"""
        memory_manager = self.get_memory_manager(agent_name, user_id, conversation_id)
        await memory_manager.generate_context_summary(self.llm)

    def get_system_memory_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema completo de memoria"""
        stats = {
            'total_memory_managers': len(self.memory_managers),
            'total_user_profiles': len(self.user_profiles),
            'memory_managers_by_agent': {},
            'avg_messages_per_manager': 0,
            'total_events': 0
        }

        if self.memory_managers:
            for manager_key, manager in self.memory_managers.items():
                agent_name = manager.agent_name
                if agent_name not in stats['memory_managers_by_agent']:
                    stats['memory_managers_by_agent'][agent_name] = 0
                stats['memory_managers_by_agent'][agent_name] += 1

            # Calcular promedios
            total_messages = sum(len(m.short_term_memory) for m in self.memory_managers.values())
            stats['avg_messages_per_manager'] = total_messages / len(self.memory_managers)

            total_events = sum(len(m.long_term_events) for m in self.memory_managers.values())
            stats['total_events'] = total_events

        return stats

    def cleanup_old_memory(self, days_threshold: int = 30):
        """Limpia memoria antigua del sistema"""
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        cleaned_managers = 0

        for manager_key in list(self.memory_managers.keys()):
            manager = self.memory_managers[manager_key]

            # Limpiar eventos antiguos
            original_events = len(manager.long_term_events)
            manager.long_term_events = [
                e for e in manager.long_term_events
                if e.timestamp > cutoff_date
            ]

            # Si no quedan eventos y no hay mensajes recientes, remover manager
            if not manager.long_term_events and not manager.short_term_memory:
                del self.memory_managers[manager_key]
                cleaned_managers += 1
            else:
                manager._save_memory()

        logger.info(f"Limpieza de memoria completada: {cleaned_managers} managers removidos")

        return cleaned_managers


# Instancia global del sistema de memoria
advanced_memory_system = AdvancedMemorySystem()