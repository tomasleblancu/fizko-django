from typing import List
from .base_agent import RuleBasedAgent, BaseAgent


def create_fiscko_agents() -> List[BaseAgent]:
    """
    Crea los agentes especializados de Fizko para contabilidad chilena
    """
    agents = []

    # Agente de saludo
    agents.append(RuleBasedAgent(
        name="saludo_fiscko",
        patterns=["hola", "buenos dias", "buenas tardes", "buenas noches", "hi", "hello"],
        response_template="¡Hola {sender_name}! 👋 Soy el asistente digital de {company_name}. "
                         "Estoy aquí para ayudarte con todas tus consultas de contabilidad y tributación chilena. "
                         "¿En qué puedo ayudarte hoy?",
        priority=10,
        conditions={'min_time_since_last': 30}
    ))

    # Agente especializado en documentos DTE
    agents.append(RuleBasedAgent(
        name="documentos_dte",
        patterns=[
            "factura electronica", "boleta electronica", "dte", "documento tributario",
            "factura", "boleta", "nota credito", "nota debito", "guia despacho",
            "documento electronico", "emision", "emitir documento"
        ],
        response_template="📄 Perfecto, soy experto en Documentos Tributarios Electrónicos (DTE).\n\n"
                         "{company_name} puede ayudarte con:\n"
                         "• ✅ Facturas electrónicas\n"
                         "• ✅ Boletas electrónicas\n"
                         "• ✅ Notas de crédito y débito\n"
                         "• ✅ Guías de despacho\n"
                         "• ✅ Validación y timbraje SII\n\n"
                         "¿Qué tipo de documento necesitas o tienes dudas específicas sobre algún DTE?",
        priority=9,
        variables={'expertise': 'documentos_electronicos'}
    ))

    # Agente especializado en SII y tributación
    agents.append(RuleBasedAgent(
        name="tributario_sii",
        patterns=[
            "sii", "servicio impuestos internos", "tributario", "impuesto", "declaracion",
            "f29", "f3323", "iva", "formulario", "vencimiento", "plazo", "multa",
            "renta", "ppm", "primera categoria", "honorarios", "suplementario"
        ],
        response_template="🏛️ Excelente, soy especialista en tributación chilena y el SII.\n\n"
                         "{company_name} te asesora en:\n"
                         "• 📋 Formularios F29 (IVA mensual)\n"
                         "• 📋 Formulario F3323 (Régimen simplificado)\n"
                         "• 💰 Declaraciones de renta\n"
                         "• ⏰ Control de vencimientos\n"
                         "• 🔍 Cumplimiento normativo SII\n"
                         "• ⚖️ Evitar multas y recargos\n\n"
                         "¿Cuál es tu consulta tributaria específica?",
        priority=9,
        variables={'expertise': 'tributacion_chilena'}
    ))

    # Agente para consultas de IVA específico
    agents.append(RuleBasedAgent(
        name="iva_especialista",
        patterns=[
            "iva", "impuesto valor agregado", "debito fiscal", "credito fiscal",
            "iva retenido", "iva recargo", "exento iva", "afecto iva",
            "tasa iva", "19%", "diferencia iva"
        ],
        response_template="💎 Soy tu especialista en IVA chileno.\n\n"
                         "En Chile manejamos:\n"
                         "• 📊 IVA 19% (tasa general)\n"
                         "• ➖ IVA Débito (ventas)\n"
                         "• ➕ IVA Crédito (compras)\n"
                         "• 🚫 Operaciones exentas\n"
                         "• 🔒 IVA retenido (honorarios)\n"
                         "• 📝 Declaración F29 mensual\n\n"
                         "¿Tienes dudas sobre algún aspecto específico del IVA o necesitas calcular algo?",
        priority=8,
        variables={'iva_rate': '19%'}
    ))

    # Agente para régimen simplificado (Pymes)
    agents.append(RuleBasedAgent(
        name="regimen_simplificado",
        patterns=[
            "regimen simplificado", "pro pyme", "pyme", "pequeña empresa",
            "14 ter", "articulo 14", "renta presunta", "simplificado"
        ],
        response_template="🏢 ¡Perfecto! Conozco muy bien el régimen simplificado chileno.\n\n"
                         "Para PyMEs tenemos:\n"
                         "• 📄 Formulario F3323\n"
                         "• 💡 Artículo 14 TER (renta presunta)\n"
                         "• 📊 Contabilidad simplificada\n"
                         "• 🎯 Beneficios Pro-PyME\n"
                         "• ⚡ Menos obligaciones formales\n\n"
                         "¿Tu empresa está en régimen simplificado o quieres saber si te conviene?",
        priority=8,
        variables={'target': 'pymes'}
    ))

    # Agente para honorarios y segunda categoría
    agents.append(RuleBasedAgent(
        name="honorarios_profesionales",
        patterns=[
            "honorarios", "segunda categoria", "profesional independiente",
            "trabajador independiente", "retencion", "10%", "boleta honorarios",
            "factura honorarios", "profesional", "independiente"
        ],
        response_template="👨‍💼 Especialista en honorarios y trabajadores independientes.\n\n"
                         "Te ayudo con:\n"
                         "• 📑 Emisión de boletas de honorarios\n"
                         "• 🔒 Retenciones del 10%\n"
                         "• 📊 Declaración segunda categoría\n"
                         "• 💰 Reliquidación de honorarios\n"
                         "• 📝 Registro de ingresos\n"
                         "• ⏰ Plazos de declaración\n\n"
                         "¿Necesitas ayuda con tus honorarios profesionales?",
        priority=7,
        variables={'retencion_rate': '10%'}
    ))

    # Agente para fechas y vencimientos
    agents.append(RuleBasedAgent(
        name="vencimientos_fiscales",
        patterns=[
            "vencimiento", "plazo", "fecha", "cuando vence", "hasta cuando",
            "calendario tributario", "cronograma", "abril", "mayo", "junio",
            "f29 vence", "renta vence", "cuando pagar"
        ],
        response_template="📅 Te ayudo con el calendario tributario chileno.\n\n"
                         "Vencimientos principales:\n"
                         "• 📋 F29: día 12 de cada mes\n"
                         "• 🏛️ Renta: 30 de abril (personas), 31 de mayo (empresas)\n"
                         "• 📊 F3323: junto con la renta\n"
                         "• 📑 Honorarios: abril del año siguiente\n\n"
                         "⚠️ ¡Importante! Los plazos pueden extenderse si el día cae en fin de semana.\n\n"
                         "¿Qué vencimiento específico necesitas verificar?",
        priority=7,
        variables={'current_date': '{current_date}'}
    ))

    # Agente para precios y servicios
    agents.append(RuleBasedAgent(
        name="comercial_fiscko",
        patterns=[
            "precio", "costo", "valor", "tarifa", "cuanto cuesta", "plan",
            "servicio", "contratar", "cotizar", "presupuesto", "demo"
        ],
        response_template="💰 Te contactamos pronto con información de nuestros servicios.\n\n"
                         "{company_name} ofrece:\n"
                         "• 🤖 Automatización tributaria completa\n"
                         "• 📊 Conexión directa con SII\n"
                         "• 📑 Emisión de DTEs\n"
                         "• 📈 Reportes en tiempo real\n"
                         "• 👨‍💼 Asesoría contable especializada\n\n"
                         "¿Te gustaría que un asesor te llame hoy para una cotización personalizada?",
        priority=6,
        conditions={'business_hours_only': True}
    ))

    # Agente de soporte técnico
    agents.append(RuleBasedAgent(
        name="soporte_tecnico",
        patterns=[
            "ayuda", "problema", "error", "no funciona", "falla", "soporte",
            "bug", "no puedo", "no me deja", "se cayo", "lento"
        ],
        response_template="🆘 Soporte técnico de {company_name} a tu servicio.\n\n"
                         "Para resolver tu consulta más rápido, describe:\n"
                         "• 🔍 ¿Qué problema específico tienes?\n"
                         "• ⏰ ¿En qué momento ocurre?\n"
                         "• 🔧 ¿Has probado alguna solución?\n"
                         "• 💻 ¿Qué navegador usas?\n\n"
                         "📞 También puedes llamarnos o enviar un email.\n"
                         "Te responderemos lo antes posible.",
        priority=9
    ))

    # Agente de información general
    agents.append(RuleBasedAgent(
        name="info_general_fiscko",
        patterns=[
            "que es", "que hacen", "servicios", "informacion", "detalles",
            "conocer mas", "como funciona", "fiscko", "fizko", "empresa"
        ],
        response_template="ℹ️ Te cuento sobre {company_name}:\n\n"
                         "🏢 Somos la plataforma líder en automatización contable chilena:\n"
                         "• 🤖 Integración automática con SII\n"
                         "• 📄 Emisión y recepción de DTEs\n"
                         "• 📊 Declaraciones F29 y F3323 automáticas\n"
                         "• 📈 Dashboard financiero en tiempo real\n"
                         "• ⚖️ Cumplimiento normativo garantizado\n"
                         "• 👨‍💼 Asesoría contable especializada\n\n"
                         "📞 ¿Te interesa una demo de nuestra plataforma?",
        priority=6
    ))

    # Agente de agradecimiento
    agents.append(RuleBasedAgent(
        name="agradecimiento",
        patterns=[
            "gracias", "perfecto", "excelente", "ok", "muchas gracias",
            "thanks", "genial", "buenisimo", "muy bien"
        ],
        response_template="😊 ¡De nada {sender_name}!\n\n"
                         "Es un placer ayudarte con temas contables y tributarios.\n"
                         "{company_name} siempre está disponible para lo que necesites.\n\n"
                         "💡 Recuerda que puedes consultarme sobre:\n"
                         "• Documentos DTE • SII • IVA • Honorarios • Vencimientos\n\n"
                         "¡Que tengas un excelente día! 🌟",
        priority=5
    ))

    # Agente de horario no comercial
    agents.append(RuleBasedAgent(
        name="fuera_horario",
        patterns=[".*"],  # Cualquier mensaje
        response_template="🌙 Hola {sender_name}, gracias por contactar a {company_name}.\n\n"
                         "Actualmente estamos fuera del horario de atención comercial.\n"
                         "📞 Nuestro horario: Lunes a Viernes de 9:00 a 18:00 hrs.\n\n"
                         "💬 Tu mensaje es importante y te responderemos apenas "
                         "iniciemos nuestro horario de atención.\n\n"
                         "🚨 Si tienes una urgencia tributaria, puedes escribir 'URGENTE' "
                         "y evaluaremos tu caso.\n\n"
                         "¡Gracias por tu paciencia! 🙏",
        priority=2,
        conditions={'business_hours_only': False}
    ))

    # Agente genérico (fallback)
    agents.append(RuleBasedAgent(
        name="respuesta_general",
        patterns=[".*"],  # Cualquier mensaje
        response_template="👋 ¡Hola {sender_name}! Gracias por escribir a {company_name}.\n\n"
                         "✅ Tu mensaje ha sido recibido y nuestro equipo especializado "
                         "te responderá a la brevedad.\n\n"
                         "🔧 Somos expertos en:\n"
                         "• 📊 Automatización tributaria SII\n"
                         "• 📄 Documentos DTE (facturas, boletas)\n"
                         "• 📋 Formularios F29 y F3323\n"
                         "• 💰 Asesoría en IVA y renta\n"
                         "• 📈 Contabilidad digital\n\n"
                         "💬 ¿Necesitas ayuda específica con algún tema contable?",
        priority=1
    ))

    return agents


def create_custom_agent_from_template(template_data: dict) -> RuleBasedAgent:
    """
    Crea un agente personalizado desde datos de plantilla

    Args:
        template_data: Dict con datos de la plantilla

    Returns:
        Instancia de RuleBasedAgent
    """
    return RuleBasedAgent(
        name=f"custom_{template_data.get('id', 'unknown')}",
        patterns=template_data.get('activation_patterns', []),
        response_template=template_data.get('body_text', ''),
        priority=template_data.get('priority', 5),
        conditions=template_data.get('conditions', {}),
        variables=template_data.get('variables', {})
    )