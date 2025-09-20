import re
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

from .models import WhatsAppMessage, WhatsAppConfig, WhatsAppConversation, MessageTemplate


class ResponseRule:
    """
    Regla de respuesta automática
    """

    def __init__(self, name: str, patterns: List[str], response: str,
                 priority: int = 1, conditions: Dict = None, variables: Dict = None):
        self.name = name
        self.patterns = [pattern.lower() for pattern in patterns]
        self.response = response
        self.priority = priority
        self.conditions = conditions or {}
        self.variables = variables or {}

    def matches(self, message: WhatsAppMessage, context: Dict) -> bool:
        """
        Verifica si esta regla aplica al mensaje
        """
        content = message.content.lower().strip()

        # Verificar patrones
        pattern_match = any(
            any(word in content for word in pattern.split())
            for pattern in self.patterns
        )

        if not pattern_match:
            return False

        # Verificar condiciones adicionales
        return self._check_conditions(message, context)

    def _check_conditions(self, message: WhatsAppMessage, context: Dict) -> bool:
        """
        Verifica condiciones adicionales
        """
        # Condición de horario
        if 'business_hours_only' in self.conditions:
            if self.conditions['business_hours_only']:
                config = message.conversation.whatsapp_config
                now = timezone.now().time()
                if not (config.business_hours_start <= now <= config.business_hours_end):
                    return False

        # Condición de tiempo desde último mensaje
        if 'min_time_since_last' in self.conditions:
            min_minutes = self.conditions['min_time_since_last']
            last_message = WhatsAppMessage.objects.filter(
                conversation=message.conversation,
                direction='outbound',
                is_auto_response=True,
                created_at__gte=timezone.now() - timedelta(minutes=min_minutes)
            ).first()
            if last_message:
                return False

        # Condición de número de mensajes en conversación
        if 'max_messages_in_conversation' in self.conditions:
            max_msgs = self.conditions['max_messages_in_conversation']
            if message.conversation.message_count > max_msgs:
                return False

        return True

    def generate_response(self, message: WhatsAppMessage, context: Dict) -> str:
        """
        Genera la respuesta aplicando variables
        """
        response = self.response

        # Variables del sistema
        system_vars = {
            'company_name': message.company.name,
            'contact_name': message.conversation.contact_name or 'Estimado/a',
            'phone_number': message.conversation.phone_number,
            'current_time': timezone.now().strftime('%H:%M'),
            'current_date': timezone.now().strftime('%d/%m/%Y'),
            'day_of_week': timezone.now().strftime('%A'),
        }

        # Variables personalizadas
        all_vars = {**system_vars, **self.variables, **context.get('variables', {})}

        # Reemplazar variables
        for var, value in all_vars.items():
            response = response.replace(f'{{{var}}}', str(value))

        return response


class WhatsAppResponseEngine:
    """
    Motor de respuestas automáticas avanzado para WhatsApp
    """

    def __init__(self):
        self.rules = []
        self._load_default_rules()

    def _load_default_rules(self):
        """
        Carga reglas por defecto del sistema
        """
        # Regla de saludo
        self.add_rule(ResponseRule(
            name="saludo",
            patterns=["hola", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello"],
            response="¡Hola {contact_name}! 👋 Soy el asistente digital de {company_name}. ¿En qué puedo ayudarte hoy?",
            priority=10,
            conditions={'min_time_since_last': 30}
        ))

        # Regla de facturas/documentos
        self.add_rule(ResponseRule(
            name="facturas_documentos",
            patterns=["factura", "boleta", "documento", "dte", "documento tributario"],
            response="📄 Perfecto, te puedo ayudar con temas de facturación y documentos tributarios.\n\n{company_name} maneja:\n• Facturas electrónicas\n• Boletas\n• Notas de crédito/débito\n• Guías de despacho\n\n¿Qué necesitas específicamente?",
            priority=8
        ))

        # Regla de impuestos/SII
        self.add_rule(ResponseRule(
            name="impuestos_sii",
            patterns=["impuesto", "sii", "tributario", "f29", "f3323", "iva", "servicio de impuestos"],
            response="🏛️ Excelente, somos especialistas en temas tributarios.\n\n{company_name} te puede asesorar con:\n• Formularios F29 y F3323\n• Declaraciones de IVA\n• Cumplimiento SII\n• Vencimientos tributarios\n\n¿Cuál es tu consulta específica?",
            priority=8
        ))

        # Regla de precios
        self.add_rule(ResponseRule(
            name="precios_costos",
            patterns=["precio", "costo", "valor", "tarifa", "cuanto cuesta", "plan"],
            response="💰 Te contactamos pronto con información detallada de nuestros servicios y tarifas.\n\n{company_name} tiene planes flexibles para empresas de todos los tamaños.\n\n¿Te gustaría que un asesor te llame hoy?",
            priority=7,
            conditions={'business_hours_only': True}
        ))

        # Regla de soporte/problemas
        self.add_rule(ResponseRule(
            name="soporte_problemas",
            patterns=["ayuda", "problema", "error", "no funciona", "falla", "soporte"],
            response="🆘 ¡No te preocupes! El equipo de soporte de {company_name} está aquí para ayudarte.\n\nPara resolver tu consulta más rápido, por favor describe:\n• ¿Qué problema específico tienes?\n• ¿En qué momento ocurre?\n• ¿Has probado alguna solución?\n\nTe responderemos lo antes posible.",
            priority=9
        ))

        # Regla de agradecimiento
        self.add_rule(ResponseRule(
            name="agradecimiento",
            patterns=["gracias", "perfecto", "excelente", "ok", "muchas gracias", "thanks"],
            response="😊 ¡De nada! Es un placer ayudarte.\n\n{company_name} siempre está disponible para lo que necesites. ¡Que tengas un excelente día!",
            priority=5
        ))

        # Regla de horario no comercial
        self.add_rule(ResponseRule(
            name="fuera_horario",
            patterns=[".*"],  # Cualquier mensaje
            response="🌙 Hola {contact_name}, gracias por contactar a {company_name}.\n\nActualmente estamos fuera del horario de atención. Nuestro horario es de 9:00 a 18:00 hrs.\n\nTu mensaje es importante para nosotros y te responderemos apenas iniciemos nuestro horario de atención.\n\n¡Gracias por tu paciencia!",
            priority=1,
            conditions={'business_hours_only': False}
        ))

        # Regla genérica (fallback)
        self.add_rule(ResponseRule(
            name="mensaje_general",
            patterns=[".*"],  # Cualquier mensaje
            response="🤖 Hola {contact_name}, gracias por contactar a {company_name}.\n\nHemos recibido tu mensaje y un miembro de nuestro equipo te responderá pronto.\n\n💡 Mientras tanto, ¿sabías que manejamos:\n• Facturas electrónicas\n• Documentos SII\n• Asesoría tributaria\n• Automatización contable\n\n¿Hay algo específico en lo que te pueda ayudar ahora?",
            priority=1
        ))

    def add_rule(self, rule: ResponseRule):
        """
        Añade una regla al motor
        """
        self.rules.append(rule)
        # Ordenar por prioridad (mayor prioridad primero)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rule(self, rule_name: str):
        """
        Elimina una regla por nombre
        """
        self.rules = [r for r in self.rules if r.name != rule_name]

    def get_response(self, message: WhatsAppMessage, context: Dict = None) -> Optional[str]:
        """
        Obtiene la respuesta apropiada para un mensaje
        """
        context = context or {}

        # Solo responder a mensajes de texto entrantes
        if message.direction != 'inbound' or message.message_type != 'text':
            return None

        # Verificar si está en horario comercial
        config = message.conversation.whatsapp_config
        now = timezone.now().time()
        is_business_hours = config.business_hours_start <= now <= config.business_hours_end
        context['is_business_hours'] = is_business_hours

        # Buscar regla que aplique
        for rule in self.rules:
            if rule.matches(message, context):
                return rule.generate_response(message, context)

        return None

    def load_custom_rules_from_templates(self, company):
        """
        Carga reglas personalizadas desde las plantillas de la empresa
        """
        templates = MessageTemplate.objects.filter(
            company=company,
            is_active=True,
            template_type='custom'
        )

        for template in templates:
            # Las plantillas pueden tener metadata con patrones de activación
            metadata = template.metadata if hasattr(template, 'metadata') else {}
            patterns = metadata.get('activation_patterns', [template.name.lower()])
            conditions = metadata.get('conditions', {})

            rule = ResponseRule(
                name=f"custom_{template.id}",
                patterns=patterns,
                response=template.body_text,
                priority=metadata.get('priority', 5),
                conditions=conditions,
                variables=dict(zip(template.available_variables, template.available_variables))
            )

            self.add_rule(rule)

    def test_response(self, message_content: str, company, context: Dict = None) -> Dict:
        """
        Prueba qué respuesta se generaría para un mensaje dado
        """
        context = context or {}

        # Simular verificación de horario comercial
        now = timezone.now().time()
        business_start = timezone.now().replace(hour=9, minute=0).time()
        business_end = timezone.now().replace(hour=18, minute=0).time()
        is_business_hours = business_start <= now <= business_end
        context['is_business_hours'] = is_business_hours

        # Buscar regla que aplique
        content = message_content.lower().strip()
        applied_rule = None
        response = None

        for rule in self.rules:
            # Verificar patrones
            pattern_match = any(
                any(word in content for word in pattern.split())
                for pattern in rule.patterns
            )

            if not pattern_match:
                continue

            # Verificar condiciones simples para testing
            if 'business_hours_only' in rule.conditions:
                if rule.conditions['business_hours_only'] and not is_business_hours:
                    continue
                elif not rule.conditions['business_hours_only'] and is_business_hours:
                    continue

            # Aplicar esta regla
            applied_rule = rule.name

            # Generar respuesta con variables
            response = rule.response
            system_vars = {
                'company_name': company.name,
                'contact_name': 'Usuario de Prueba',
                'phone_number': '+56912345678',
                'current_time': timezone.now().strftime('%H:%M'),
                'current_date': timezone.now().strftime('%d/%m/%Y'),
                'day_of_week': timezone.now().strftime('%A'),
            }

            all_vars = {**system_vars, **rule.variables, **context.get('variables', {})}

            for var, value in all_vars.items():
                response = response.replace(f'{{{var}}}', str(value))

            break

        return {
            'message': message_content,
            'response': response,
            'applied_rule': applied_rule,
            'is_business_hours': is_business_hours
        }


# Instancia global del motor de respuestas
response_engine = WhatsAppResponseEngine()