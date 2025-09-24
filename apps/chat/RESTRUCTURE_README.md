# Restructuración de WhatsApp a Chat

Este documento explica la restructuración de la aplicación `whatsapp` hacia una arquitectura modular de `chat`.

## Cambios Principales

### 1. Renombrado de Aplicación
- **Antes**: `apps.whatsapp`
- **Ahora**: `apps.chat`
- **Descripción**: La aplicación ha sido renombrada para reflejar su propósito más amplio de manejar múltiples canales de comunicación.

### 2. Nueva Arquitectura Modular

```
apps/chat/
├── interfaces/                 # Interfaces abstratas y específicas
│   ├── base/
│   │   └── chat_interface.py   # Interface base para todos los servicios
│   └── whatsapp/
│       └── whatsapp_interface.py # Implementación específica de WhatsApp
├── services/                   # Servicios de negocio
│   ├── agents/                 # Sistema de agentes inteligentes
│   │   ├── base_agent.py       # Clase base para agentes
│   │   ├── agent_manager.py    # Gestor de agentes
│   │   └── fiscko_agents.py    # Agentes específicos de Fizko
│   ├── whatsapp/              # Servicios específicos de WhatsApp
│   │   ├── kapso_service.py    # API service para Kapso
│   │   └── whatsapp_processor.py # Procesador de webhooks
│   └── chat_service.py         # Servicio principal unificado
├── models.py                   # Modelos de datos (sin cambios)
├── views.py                    # APIs REST actualizadas
├── serializers.py              # Serializadores (sin cambios)
└── urls.py                     # URLs actualizadas
```

### 3. Sistema de Agentes

El nuevo sistema reemplaza el `response_engine` anterior con un sistema más flexible:

#### Características:
- **Agentes especializados**: Cada agente maneja un tipo específico de consulta
- **Prioridades configurables**: Los agentes se ejecutan según prioridad
- **Condiciones inteligentes**: Horario comercial, frecuencia, etc.
- **Variables dinámicas**: Personalización automática de respuestas
- **Gestión centralizada**: AgentManager coordina todos los agentes

#### Agentes Incluidos:
1. **saludo_fiscko** - Saludos profesionales
2. **documentos_dte** - Consultas sobre documentos electrónicos
3. **tributario_sii** - Información del SII y tributación
4. **iva_especialista** - Consultas específicas de IVA
5. **regimen_simplificado** - PyMEs y régimen simplificado
6. **honorarios_profesionales** - Trabajadores independientes
7. **vencimientos_fiscales** - Fechas y plazos tributarios
8. **comercial_fiscko** - Información comercial y ventas
9. **soporte_tecnico** - Soporte técnico
10. **info_general_fiscko** - Información general de Fizko
11. **agradecimiento** - Respuestas de cortesía
12. **fuera_horario** - Respuestas fuera de horario comercial
13. **respuesta_general** - Fallback general

### 4. Interface Unificada

El `ChatService` proporciona una interfaz unificada para todos los canales:

```python
# Enviar mensaje
chat_service.send_message(
    service_type='whatsapp',
    recipient='+56912345678',
    message='Hola',
    config_id='config-id'
)

# Procesar mensaje entrante
chat_service.process_incoming_message(
    service_type='whatsapp',
    payload=webhook_data
)

# Obtener historial
chat_service.get_conversation_history(
    service_type='whatsapp',
    conversation_id='conv-id'
)
```

### 5. Preparación para Futuros Canales

La arquitectura está preparada para agregar fácilmente nuevos canales:
- **Telegram**: `TelegramInterface`
- **SMS**: `SMSInterface`
- **Email**: `EmailInterface`
- **Web Chat**: `WebChatInterface`

## Migración de APIs

### URLs Actualizadas
- **Antes**: `/api/v1/whatsapp/`
- **Ahora**: `/api/v1/chat/`

### Endpoints Principales
- `GET /api/v1/chat/configs/` - Configuraciones de WhatsApp
- `GET /api/v1/chat/conversations/` - Conversaciones
- `GET /api/v1/chat/messages/` - Mensajes
- `POST /api/v1/chat/webhook/` - Webhook de Kapso
- `POST /api/v1/chat/send-message/` - Enviar mensaje
- `POST /api/v1/chat/test-response/` - Probar respuestas automáticas
- `GET /api/v1/chat/response-rules/` - Gestión de agentes
- `GET /api/v1/chat/response-analytics/` - Analíticas

### Cambios en Response Engine

**Antes (response_engine):**
```python
from apps.whatsapp.response_engine import response_engine
result = response_engine.test_response(message, company)
```

**Ahora (agent_manager):**
```python
from apps.chat.services import chat_service
result = chat_service.test_agent_response(
    message_content=message,
    company_info={'name': company.name}
)
```

## Comandos de Gestión

Los comandos de management han sido actualizados:

```bash
# Limpiar datos antiguos
python manage.py cleanup_whatsapp_data

# Configurar plantillas
python manage.py setup_whatsapp_templates

# Probar respuestas
python manage.py test_responses --message "hola"
```

## Archivos Legacy

Los siguientes archivos se mantienen como referencia:
- `services/legacy_whatsapp_service.py` - Servicio original
- `services/agents/legacy_response_engine.py` - Motor de respuestas original

## Configuración

### Settings.py
```python
INSTALLED_APPS = [
    # ...
    'apps.chat',  # Antes era 'apps.whatsapp'
]
```

### URLs principales
```python
urlpatterns = [
    path('api/v1/chat/', include('apps.chat.urls')),  # Antes whatsapp/
]
```

## Beneficios de la Restructuración

1. **Escalabilidad**: Fácil agregar nuevos canales de comunicación
2. **Mantenibilidad**: Código más organizado y modular
3. **Flexibilidad**: Sistema de agentes configurable
4. **Reutilización**: Interfaces comunes para todos los servicios
5. **Testing**: Mejor separación de responsabilidades
6. **Futuro**: Preparado para IA avanzada y múltiples canales

## Notas de Migración

- Las migraciones de base de datos permanecen intactas
- Los modelos no han cambiado
- La funcionalidad existente se mantiene
- Las APIs son backwards compatible (excepto URLs)
- El sistema legacy puede ejecutarse en paralelo durante la transición