"""
Sistema de ejecución de agentes con fallback, timeouts y recuperación
"""
import time
import asyncio
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Ejecutor robusto de agentes con sistema de fallback"""

    def __init__(self, agents: Dict[str, Any], default_timeout: float = 30.0):
        self.agents = agents
        self.default_timeout = default_timeout
        self.execution_stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'timeout_errors': 0,
            'fallback_used': 0,
            'agent_errors': {},
            'response_times': []
        }

    def execute_agent(self, agent_key: str, state: Dict[str, Any],
                     timeout: Optional[float] = None,
                     enable_fallback: bool = True) -> Dict[str, Any]:
        """
        Ejecuta un agente con timeout y sistema de fallback

        Args:
            agent_key: Clave del agente a ejecutar
            state: Estado del agente
            timeout: Timeout personalizado (usa default si None)
            enable_fallback: Si activar sistema de fallback

        Returns:
            Resultado de la ejecución del agente
        """
        self.execution_stats['total_executions'] += 1
        start_time = time.time()

        timeout = timeout or self.default_timeout
        agent = self.agents.get(agent_key)

        if not agent:
            logger.error(f"Agente no encontrado: {agent_key}")
            if enable_fallback:
                return self._execute_fallback(state, f"Agente {agent_key} no encontrado")
            else:
                return self._create_error_response("Agente no encontrado")

        execution_result = {
            'agent_used': agent_key,
            'execution_time': 0.0,
            'success': False,
            'fallback_used': False,
            'error': None,
            'messages': []
        }

        try:
            logger.info(f"Ejecutando {agent_key} con timeout de {timeout}s...")

            # Ejecutar agente con timeout usando ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._safe_agent_execution, agent, state)

                try:
                    result = future.result(timeout=timeout)

                    # Verificar que el resultado sea válido
                    if self._is_valid_agent_response(result):
                        execution_time = time.time() - start_time
                        execution_result.update({
                            'success': True,
                            'execution_time': execution_time,
                            'messages': result.get('messages', [])
                        })

                        self.execution_stats['successful_executions'] += 1
                        self.execution_stats['response_times'].append(execution_time)

                        logger.info(f"{agent_key} ejecutado exitosamente en {execution_time:.2f}s")
                        return {**result, **execution_result}

                    else:
                        # Respuesta inválida del agente
                        logger.warning(f"{agent_key} retornó respuesta inválida")
                        if enable_fallback:
                            return self._execute_fallback(state, f"Respuesta inválida de {agent_key}", execution_result)
                        else:
                            execution_result['error'] = "Respuesta inválida del agente"
                            return self._create_error_response("Respuesta inválida del agente")

                except FutureTimeoutError:
                    # Timeout del agente
                    logger.warning(f"{agent_key} excedió timeout de {timeout}s")
                    self.execution_stats['timeout_errors'] += 1

                    if enable_fallback:
                        return self._execute_fallback(state, f"Timeout en {agent_key} ({timeout}s)", execution_result)
                    else:
                        execution_result['error'] = f"Timeout después de {timeout}s"
                        return self._create_error_response(f"Timeout después de {timeout}s")

        except Exception as e:
            # Error inesperado
            logger.error(f"Error ejecutando {agent_key}: {e}")

            # Registrar error por agente
            if agent_key not in self.execution_stats['agent_errors']:
                self.execution_stats['agent_errors'][agent_key] = 0
            self.execution_stats['agent_errors'][agent_key] += 1

            execution_result['error'] = str(e)

            if enable_fallback:
                return self._execute_fallback(state, f"Error en {agent_key}: {str(e)}", execution_result)
            else:
                return self._create_error_response(f"Error ejecutando agente: {str(e)}")

    def _safe_agent_execution(self, agent, state: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el agente de forma segura con manejo de excepciones"""
        try:
            return agent.run(state)
        except Exception as e:
            logger.error(f"Error interno del agente: {e}")
            raise

    def _is_valid_agent_response(self, response: Dict[str, Any]) -> bool:
        """Verifica que la respuesta del agente sea válida"""
        if not isinstance(response, dict):
            return False

        # Debe tener mensajes
        if 'messages' not in response or not response['messages']:
            return False

        # Los mensajes deben ser válidos
        messages = response['messages']
        if not isinstance(messages, list):
            return False

        # Verificar que hay al menos un mensaje AI válido
        for message in messages:
            if hasattr(message, 'type') and message.type == 'ai':
                if hasattr(message, 'content') and message.content.strip():
                    return True

        return False

    def _execute_fallback(self, state: Dict[str, Any], reason: str,
                         original_result: Optional[Dict] = None) -> Dict[str, Any]:
        """Ejecuta agente de fallback (GeneralAgent)"""
        logger.info(f"Ejecutando fallback por: {reason}")

        self.execution_stats['fallback_used'] += 1

        try:
            # Usar GeneralAgent como fallback
            fallback_agent = self.agents.get('general')
            if not fallback_agent:
                logger.error("GeneralAgent no disponible para fallback")
                return self._create_error_response("Sistema temporalmente no disponible")

            # Modificar estado para incluir contexto del error
            fallback_state = state.copy()

            # Agregar contexto del problema al último mensaje
            if fallback_state.get('messages'):
                last_message = fallback_state['messages'][-1]
                if hasattr(last_message, 'content'):
                    # Agregar contexto discreto
                    original_content = last_message.content
                    fallback_state['messages'][-1].content = original_content

            # Ejecutar fallback sin timeout (más permisivo)
            result = self._safe_agent_execution(fallback_agent, fallback_state)

            if self._is_valid_agent_response(result):
                fallback_result = {
                    'agent_used': 'general',
                    'success': True,
                    'fallback_used': True,
                    'fallback_reason': reason,
                    'original_agent_error': original_result,
                    'execution_time': 0.0,  # No medimos tiempo del fallback
                    'messages': result.get('messages', [])
                }

                logger.info("Fallback ejecutado exitosamente")
                return {**result, **fallback_result}

        except Exception as e:
            logger.error(f"Error en fallback: {e}")

        # Si el fallback también falla, respuesta de emergencia
        return self._create_error_response(
            "Sistema temporalmente no disponible. Por favor, intenta nuevamente en unos momentos."
        )

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Crea respuesta de error estándar"""
        error_response = AIMessage(content=error_message)

        return {
            'messages': [error_response],
            'next_agent': 'supervisor',
            'agent_used': 'error_handler',
            'success': False,
            'fallback_used': False,
            'error': error_message,
            'execution_time': 0.0
        }

    def get_execution_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de ejecución"""
        stats = self.execution_stats.copy()

        # Calcular métricas adicionales
        total = stats['total_executions']
        if total > 0:
            stats['success_rate'] = stats['successful_executions'] / total
            stats['fallback_rate'] = stats['fallback_used'] / total
            stats['timeout_rate'] = stats['timeout_errors'] / total
        else:
            stats['success_rate'] = 0.0
            stats['fallback_rate'] = 0.0
            stats['timeout_rate'] = 0.0

        if stats['response_times']:
            import numpy as np
            stats['avg_response_time'] = float(np.mean(stats['response_times']))
            stats['max_response_time'] = float(np.max(stats['response_times']))
            stats['min_response_time'] = float(np.min(stats['response_times']))
        else:
            stats['avg_response_time'] = 0.0
            stats['max_response_time'] = 0.0
            stats['min_response_time'] = 0.0

        return stats

    def reset_stats(self):
        """Reinicia las estadísticas"""
        self.execution_stats = {
            'total_executions': 0,
            'successful_executions': 0,
            'timeout_errors': 0,
            'fallback_used': 0,
            'agent_errors': {},
            'response_times': []
        }
        logger.info("Estadísticas de ejecución reiniciadas")

    def set_agent_timeout(self, agent_key: str, timeout: float):
        """Establece timeout personalizado para un agente específico"""
        # Por ahora guardamos en memoria, en futuro podría ser en BD
        if not hasattr(self, 'agent_timeouts'):
            self.agent_timeouts = {}

        self.agent_timeouts[agent_key] = timeout
        logger.info(f"Timeout personalizado para {agent_key}: {timeout}s")

    def get_agent_timeout(self, agent_key: str) -> float:
        """Obtiene timeout personalizado o default para un agente"""
        if hasattr(self, 'agent_timeouts') and agent_key in self.agent_timeouts:
            return self.agent_timeouts[agent_key]
        return self.default_timeout