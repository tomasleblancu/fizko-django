# Chat Application

Sistema de mensajería integrado para Fizko, especializado en comunicación vía WhatsApp Business para servicios de contabilidad tributaria chilena.

## Descripción General

La aplicación `chat` proporciona una infraestructura completa para la comunicación automatizada con clientes a través de WhatsApp Business, incluyendo procesamiento inteligente de mensajes mediante agentes de IA especializados en contabilidad tributaria chilena.

## Arquitectura

### Componentes Principales

```
apps/chat/
├── models/                 # Modelos de datos
├── services/              # Lógica de negocio
│   ├── agents/           # Sistema de agentes IA
│   ├── whatsapp/         # Integración WhatsApp
│   └── chat_service.py   # Registro central de servicios
├── interfaces/            # Interfaces de comunicación
├── views/                 # API endpoints
├── serializers/           # Serialización de datos
├── management/commands/   # Comandos de administración
└── utils/                 # Utilidades
```

## Modelos de Datos

### WhatsAppConfig
Configuración de WhatsApp Business por empresa
- `company`: Empresa asociada
- `kapso_api_token`: Token de autenticación Kapso
- `webhook_url`: URL para webhooks
- `is_active`: Estado de activación

### WhatsAppConversation
Gestión de conversaciones
- `company`: Empresa asociada
- `phone_number`: Número del cliente
- `contact_name`: Nombre del contacto
- `status`: Estado (active/closed)
- `unread_count`: Mensajes no leídos
- `metadata`: Datos adicionales JSON

### WhatsAppMessage
Mensajes individuales
- `conversation`: Conversación asociada
- `message_type`: Tipo (text/image/audio/document/template)
- `direction`: Dirección (incoming/outgoing)
- `content`: Contenido del mensaje
- `status`: Estado de entrega
- `external_id`: ID externo de Kapso

### WebhookEvent
Eventos de webhook procesados
- `event_type`: Tipo de evento
- `idempotency_key`: Clave de idempotencia
- `status`: Estado de procesamiento
- `error_message`: Mensaje de error si aplica

### MessageTemplate
Plantillas de mensajes reutilizables
- `name`: Nombre identificador
- `content`: Contenido con variables
- `variables`: Variables disponibles
- `category`: Categoría del template

## Sistema de Agentes IA

### AgentManager
Gestor central de agentes con sistema de prioridades y confianza:

```python
# Registro de agente
agent_manager.register_agent(
    name="tax_reminder",
    agent=TaxReminderAgent(),
    priority=10
)

# Procesamiento de mensaje
response = agent_manager.process_message(message_content)
```

### Agentes Especializados

1. **TaxReminderAgent**: Recordatorios F29 y F3323
2. **DTEAgent**: Procesamiento de documentos tributarios
3. **HonorariosAgent**: Gestión de honorarios
4. **SIIIntegrationAgent**: Integración con SII
5. **InvoiceProcessingAgent**: Procesamiento de facturas
6. **SupportAgent**: Soporte general
7. **SalesAgent**: Información comercial
8. **UnrecognizedQuestionAgent**: Preguntas no reconocidas
9. **GreetingAgent**: Saludos y bienvenida
10. **BusinessHoursAgent**: Horario de atención
11. **FallbackAgent**: Respuesta por defecto

## API Endpoints

### Configuración
```
GET/POST    /api/chat/configs/           # Gestión de configuración
GET/PUT     /api/chat/configs/{id}/      # Detalle de configuración
```

### Conversaciones
```
GET/POST    /api/chat/conversations/     # Lista y creación
GET/PUT     /api/chat/conversations/{id}/# Detalle y actualización
POST        /api/chat/conversations/{id}/mark-as-read/
GET         /api/chat/conversations/{id}/messages/
```

### Mensajes
```
GET/POST    /api/chat/messages/          # Lista y creación
GET         /api/chat/messages/{id}/     # Detalle de mensaje
GET         /api/chat/messages/search/   # Búsqueda de mensajes
```

### Templates
```
GET/POST    /api/chat/templates/         # Gestión de templates
GET/PUT     /api/chat/templates/{id}/    # Detalle de template
POST        /api/chat/templates/{id}/preview/
```

### Acciones
```
POST        /api/chat/send-message/      # Enviar mensaje individual
POST        /api/chat/send-template/     # Enviar mensaje con template
POST        /api/chat/webhook/           # Recepción de webhooks
GET         /api/chat/test-response/     # Probar sistema de respuesta
GET         /api/chat/response-analytics/# Analíticas de respuestas
```

## Flujo de Mensajes

### Mensaje Entrante
1. Webhook recibido desde Kapso
2. Validación de evento e idempotencia
3. Creación/actualización de conversación y mensaje
4. Procesamiento por sistema de agentes
5. Generación de auto-respuesta si aplica
6. Almacenamiento de respuesta

### Mensaje Saliente
1. API call para enviar mensaje
2. Validación de empresa y configuración
3. Envío vía servicio de chat
4. Llamada a API de Kapso
5. Tracking de estado en base de datos

## Configuración

### Variables de Entorno
```bash
# Kapso API
KAPSO_API_BASE_URL=https://app.kapso.ai/api/v1
KAPSO_API_TOKEN=your-token-here

# Webhook
WHATSAPP_WEBHOOK_SECRET=webhook-secret

# OpenAI (para agentes IA)
OPENAI_API_KEY=your-openai-key
```

### Configuración Django
```python
# settings.py
INSTALLED_APPS = [
    ...
    'apps.chat',
]

# Celery queues
CELERY_TASK_ROUTES = {
    'apps.chat.tasks.*': {'queue': 'whatsapp'},
}
```

## Comandos de Administración

### setup_whatsapp_templates
Configura templates iniciales para WhatsApp:
```bash
python manage.py setup_whatsapp_templates --company_id=1
```

### test_responses
Prueba el sistema de auto-respuesta:
```bash
python manage.py test_responses "¿Cuándo debo presentar el F29?"
```

### cleanup_whatsapp_data
Limpia datos antiguos de WhatsApp:
```bash
python manage.py cleanup_whatsapp_data --days=90
```

## Integración con Kapso

### Configuración Inicial
1. Obtener token de API desde panel de Kapso
2. Configurar webhook URL en Kapso
3. Crear `WhatsAppConfig` para la empresa
4. Verificar webhook con comando de prueba

### Envío de Mensajes
```python
from apps.chat.services.chat_service import ChatService

# Obtener servicio
service = ChatService.get_service('whatsapp', company)

# Enviar mensaje de texto
service.send_message(
    to_phone="+56912345678",
    message="Hola, tu F29 está listo para revisión"
)

# Enviar template
service.send_template_message(
    to_phone="+56912345678",
    template_name="tax_reminder",
    variables={"month": "Noviembre", "form": "F29"}
)
```

## Testing

### Tests Unitarios
```bash
pytest apps/chat/tests/test_models.py
pytest apps/chat/tests/test_services.py
pytest apps/chat/tests/test_agents.py
```

### Tests de Integración
```bash
pytest apps/chat/tests/test_webhook.py
pytest apps/chat/tests/test_kapso_integration.py
```

### Test de Respuestas Automáticas
```python
# En Django shell
from apps.chat.services.agents.agent_manager import agent_manager

response = agent_manager.process_message(
    "¿Cuándo debo presentar el F29?"
)
print(response.content)
print(f"Confidence: {response.confidence}")
print(f"Agent: {response.agent_name}")
```

## Monitoreo

### Métricas Disponibles
- Total de mensajes enviados/recibidos
- Tasa de respuesta automática
- Tiempo de respuesta promedio
- Conversaciones activas
- Errores de webhook

### Logs
```python
import logging

logger = logging.getLogger('apps.chat')
logger.info('Mensaje procesado', extra={
    'conversation_id': conversation.id,
    'message_type': message.message_type,
    'auto_response': bool(response)
})
```

## Mejores Prácticas

### Seguridad
- Siempre validar firma de webhooks
- Sanitizar contenido de mensajes
- Implementar rate limiting
- Logs sin información sensible

### Performance
- Procesar webhooks de forma asíncrona
- Cachear configuraciones activas
- Batch processing para mensajes masivos
- Índices en campos de búsqueda frecuente

### Mantenimiento
- Limpieza periódica de eventos antiguos
- Monitoreo de webhooks fallidos
- Backup de conversaciones importantes
- Actualización de templates según necesidad

## Troubleshooting

### Webhook no recibe mensajes
1. Verificar URL en configuración de Kapso
2. Revisar logs de `WebhookEvent`
3. Validar token de autenticación
4. Comprobar firewall/proxy

### Auto-respuestas no funcionan
1. Verificar agentes registrados
2. Revisar logs de `AgentManager`
3. Comprobar configuración de OpenAI
4. Validar patrones en agentes

### Mensajes no se envían
1. Verificar saldo en Kapso
2. Revisar formato de número telefónico
3. Comprobar estado de `WhatsAppConfig`
4. Validar permisos de empresa

## Roadmap

### Próximas Funcionalidades
- [ ] Soporte para mensajes multimedia avanzados
- [ ] Integración con más proveedores de WhatsApp
- [ ] Sistema de campañas masivas
- [ ] Analytics avanzadas con dashboard
- [ ] Soporte para chatbots con flujos visuales
- [ ] Integración con CRM
- [ ] Soporte multiidioma

## Contribuir

1. Fork del repositorio
2. Crear branch para feature (`git checkout -b feature/AmazingFeature`)
3. Commit de cambios (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## Soporte

Para soporte técnico o preguntas:
- Documentación: `/docs/chat/`
- Issues: GitHub Issues
- Email: soporte@fizko.cl

## Licencia

Propiedad de Fizko SpA. Todos los derechos reservados.