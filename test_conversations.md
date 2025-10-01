# Sistema de Conversaciones Persistentes

Este documento describe cómo usar el nuevo sistema de conversaciones persistentes implementado en `/api/v1/chat/test-response/`.

## Endpoints Disponibles

### 1. Crear/Continuar Conversación
**POST** `/api/v1/chat/test-response/`

#### Parámetros:
```json
{
    "message": "Tu mensaje aquí",
    "conversation_id": "uuid-opcional", // Si se omite, se crea nueva conversación
    "company_info": {}, // Opcional
    "sender_info": {} // Opcional
}
```

#### Respuesta:
```json
{
    "message": "Tu mensaje",
    "response": "Respuesta del agente",
    "conversation_id": "uuid-de-la-conversacion",
    "selected_agent": "advanced_multi_agent_system",
    "metadata": {
        "conversation_messages_count": 2,
        "conversation_created": "2025-01-01T10:00:00Z",
        "conversation_title": "¿Cómo hago una factura?",
        // ... más metadata
    }
}
```

### 2. Obtener Historial de Conversaciones
**GET** `/api/v1/chat/conversations/`

#### Respuesta:
```json
{
    "conversations": [
        {
            "id": "uuid-conversacion",
            "title": "¿Cómo hago una factura?",
            "agent_name": "supervisor",
            "status": "active",
            "message_count": 4,
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:05:00Z",
            "last_message": {
                "content": "¿Necesitas más ayuda?",
                "role": "assistant",
                "created_at": "2025-01-01T10:05:00Z"
            }
        }
    ],
    "total": 1
}
```

### 3. Obtener Detalles de Conversación
**GET** `/api/v1/chat/conversations/{conversation_id}/`

#### Respuesta:
```json
{
    "conversation": {
        "id": "uuid-conversacion",
        "title": "¿Cómo hago una factura?",
        "agent_name": "supervisor",
        "status": "active",
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-01T10:05:00Z",
        "metadata": {}
    },
    "messages": [
        {
            "role": "user",
            "content": "¿Cómo hago una factura?",
            "agent_name": "",
            "created_at": "2025-01-01T10:00:00Z",
            "metadata": {}
        },
        {
            "role": "assistant",
            "content": "Para hacer una factura...",
            "agent_name": "supervisor",
            "created_at": "2025-01-01T10:01:00Z",
            "metadata": {}
        }
    ],
    "total_messages": 2
}
```

### 4. Archivar Conversación
**DELETE** `/api/v1/chat/conversations/{conversation_id}/archive/`

## Ejemplos de Uso

### Ejemplo 1: Nueva Conversación
```bash
curl -X POST http://localhost:8000/api/v1/chat/test-response/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"message": "¿Cómo emito una factura electrónica?"}'
```

### Ejemplo 2: Continuar Conversación
```bash
curl -X POST http://localhost:8000/api/v1/chat/test-response/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "¿Y qué datos necesito?",
    "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

### Ejemplo 3: Ver Historial
```bash
curl -X GET http://localhost:8000/api/v1/chat/conversations/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Características

### ✅ Funcionalidades Implementadas

1. **Persistencia Automática**: Cada mensaje se guarda automáticamente
2. **Historial Contextual**: Los agentes tienen acceso al historial completo
3. **Títulos Automáticos**: Se genera un título basado en el primer mensaje
4. **Metadata Rica**: Información detallada sobre la conversación
5. **Seguridad**: Cada usuario solo ve sus propias conversaciones
6. **Estados de Conversación**: active, ended, archived
7. **Admin Interface**: Panel de administración en Django

### 🔧 Características Técnicas

- **UUID**: Identificadores únicos para conversaciones
- **Transacciones Atómicas**: Garantía de consistencia de datos
- **Indexación**: Búsquedas optimizadas por usuario y fecha
- **Logging**: Registro detallado para debugging
- **Error Handling**: Manejo robusto de errores

### 🎯 Integración con Agentes

- Los agentes reciben el historial completo en `metadata['conversation_history']`
- Formato estándar: `[{"role": "user|assistant|system", "content": "..."}]`
- Compatible con LangChain y el sistema supervisor existente

## Migración desde Sistema Anterior

El endpoint `/api/v1/chat/test-response/` es **retrocompatible**:
- Sin `conversation_id`: Funciona como antes (crea nueva conversación)
- Con `conversation_id`: Usa la nueva funcionalidad persistente
- Respuesta mantiene la misma estructura con `conversation_id` adicional

## Base de Datos

### Modelos Creados

1. **Conversation**: Conversación principal
   - `id` (UUID)
   - `user` (ForeignKey)
   - `agent_name` (CharField)
   - `title` (CharField)
   - `status` (active/ended/archived)
   - `metadata` (JSONField)
   - Timestamps

2. **ConversationMessage**: Mensajes individuales
   - `conversation` (ForeignKey)
   - `role` (user/assistant/system)
   - `content` (TextField)
   - `agent_name` (CharField)
   - `token_count` (IntegerField)
   - `metadata` (JSONField)
   - Timestamp

### Administración Django

Disponible en `/admin/`:
- `chat/conversation/`: Gestión de conversaciones
- `chat/conversationmessage/`: Gestión de mensajes
- Acciones en lote: archivar, finalizar
- Búsqueda por usuario, título, contenido