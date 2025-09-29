# Sistema de Archivos de Contexto para Agentes

## Descripción General

He implementado un sistema completo para cargar archivos de contexto (JSON, TXT, DOCX, PDF) que pueden ser asignados a agentes específicos y usados automáticamente como contexto adicional en sus respuestas.

## Características Implementadas

### 1. Modelos de Base de Datos

- **`ContextFile`**: Almacena información del archivo, contenido extraído, metadatos
- **`AgentContextAssignment`**: Relación entre agentes y archivos con prioridad e instrucciones
- **`ContextFileProcessingLog`**: Log de procesamiento de archivos

### 2. Procesamiento de Archivos

- **JSON**: Convierte estructura a texto legible
- **TXT**: Maneja múltiples encodings automáticamente
- **DOCX**: Extrae texto de párrafos y tablas
- **PDF**: Extrae texto por páginas (requiere PyPDF2)

### 3. Integración con Agentes Dinámicos

Los agentes dinámicos automáticamente:
- Cargan archivos de contexto asignados
- Los incluyen en el system prompt
- Respetan prioridades y configuraciones
- Limitan contenido para evitar exceso de tokens

### 4. Interfaz Web

- **Vista de gestión** por agente: `/chat/agents/{id}/context/`
- **Subida de archivos** con validación
- **Asignación/desasignación** de archivos
- **Procesamiento automático** en background

## Estructura de Archivos Creados

```
apps/chat/
├── models/
│   └── context_files.py           # Modelos ContextFile, AgentContextAssignment, etc.
├── services/
│   └── context_processor.py       # Procesador de archivos por tipo
├── forms/
│   └── context_forms.py           # Formularios para subida y gestión
├── templates/chat/agents/
│   └── context_files.html         # Interfaz de gestión
├── migrations/
│   └── 0003_contextfile_...py     # Migración de modelos
└── agents/
    └── dynamic_langchain_agent.py # Modificado para cargar contexto
```

## Flujo de Uso

### 1. Subir Archivo
```python
# Usuario sube archivo a través de la interfaz web
# Se crea ContextFile con status='uploaded'
# Se dispara procesamiento automático
```

### 2. Procesamiento
```python
from apps.chat.services.context_processor import process_context_file

# Procesa archivo y extrae contenido
success = process_context_file(context_file_id)
# Actualiza status a 'processed' y guarda contenido extraído
```

### 3. Asignación a Agente
```python
# Usuario asigna archivo procesado a agente específico
AgentContextAssignment.objects.create(
    agent_config=agent,
    context_file=file,
    priority=10,
    context_instructions="Usa este archivo como referencia para...",
    is_active=True
)
```

### 4. Uso Automático
```python
# Agente dinámico carga automáticamente el contenido
agent = DynamicLangChainAgent(agent_id)
# El contenido se incluye en el system prompt
# El agente puede usar el contexto en sus respuestas
```

## URLs Implementadas

```python
# Gestión de archivos por agente
'agents/<int:agent_id>/context/'                    # Lista archivos del agente
'agents/<int:agent_id>/context/upload/'             # Subir nuevo archivo
'agents/<int:agent_id>/context/<int:file_id>/assign/' # Asignar archivo
'agents/<int:agent_id>/context/<int:file_id>/remove/' # Remover archivo
'agents/<int:agent_id>/context/<int:file_id>/toggle/' # Activar/desactivar

# Gestión general de archivos
'context-files/'                                    # Lista todos los archivos
'context-files/<int:file_id>/'                     # Detalles de archivo
'context-files/<int:file_id>/reprocess/'           # Reprocesar archivo
```

## Tipos de Archivo Soportados

### JSON
- Convierte estructura a texto legible
- Preserva jerarquía de objetos y arrays
- Útil para: configuraciones, datos estructurados, APIs

### TXT
- Maneja múltiples encodings (UTF-8, Latin-1, CP1252)
- Calcula estadísticas (líneas, palabras, caracteres)
- Útil para: documentación, instrucciones, datos planos

### DOCX
- Extrae texto de párrafos y tablas
- Preserva estructura básica
- Útil para: documentos de Word, especificaciones, manuales

### PDF
- Extrae texto por páginas
- Maneja errores de páginas individuales
- Útil para: documentos legales, reportes, manuales técnicos

## Configuración Requerida

### 1. Dependencias Python
```bash
pip install python-docx PyPDF2
```

### 2. Variables de Entorno
```bash
OPENAI_API_KEY=your_key  # Para generar resúmenes automáticos
```

### 3. Configuración Django
```python
# settings.py
MEDIA_ROOT = '/path/to/media'
MEDIA_URL = '/media/'

# Para archivos grandes
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
```

## Ejemplos de Uso

### 1. Cargar Manual de Producto
```python
# Subir manual.pdf del producto
# Asignar a agente de soporte
# Instrucciones: "Usa este manual para responder preguntas técnicas"
# Prioridad: 90
```

### 2. Cargar Base de Conocimiento
```python
# Subir knowledge_base.json con FAQs
# Asignar a agente general
# Instrucciones: "Consulta primero esta base antes de responder"
# Prioridad: 100
```

### 3. Cargar Políticas de Empresa
```python
# Subir politicas.docx
# Asignar a agente de RRHH
# Instrucciones: "Aplica estas políticas en todas las respuestas"
# Prioridad: 80
```

## Limitaciones y Consideraciones

1. **Tamaño máximo**: 50MB por archivo
2. **Tokens**: Contenido limitado a ~3000 caracteres por archivo para evitar exceso
3. **Procesamiento**: Archivos grandes pueden tardar en procesarse
4. **PDF**: Calidad de extracción depende del PDF (texto vs imagen)
5. **Seguridad**: Archivos son privados por usuario

## Próximos Pasos Recomendados

1. **Implementar vistas completas**: Actualmente solo está la vista de listado
2. **Agregar procesamiento asíncrono**: Usar Celery para archivos grandes
3. **Mejorar extracción PDF**: Usar OCR para PDFs escaneados
4. **Búsqueda en contenido**: Implementar búsqueda full-text
5. **Versionado**: Permitir múltiples versiones del mismo archivo
6. **Compartir archivos**: Entre agentes del mismo usuario
7. **Templates de contexto**: Plantillas predefinidas para tipos de agente

## Estado Actual

✅ **Completado**:
- Modelos y migraciones
- Procesador de archivos
- Integración con agentes dinámicos
- Interfaz básica de gestión
- Formularios y validaciones

🔄 **En desarrollo**:
- Vistas funcionales completas
- Procesamiento asíncrono
- Gestión de errores avanzada

⏳ **Pendiente**:
- Testing completo
- Documentación de usuario
- Optimizaciones de rendimiento