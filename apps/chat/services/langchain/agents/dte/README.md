# DTE Agent

Agente especializado en **Documentos Tributarios Electrónicos (DTE)** de Chile.

## Estructura

```
dte/
├── __init__.py          # Exporta DTEAgent
├── agent.py             # Implementación del agente principal
├── tools.py             # Herramientas base para acceso a datos DTE
├── tools_context.py     # Herramientas con contexto de usuario (seguras)
└── README.md            # Esta documentación
```

## Funcionalidades

### 🔧 **Herramientas Disponibles**

1. **`get_document_types_info_secured`**
   - Consulta tipos de documentos DTE disponibles
   - Sin restricciones de usuario

2. **`validate_dte_code_secured`**
   - Valida códigos DTE específicos (33, 39, 61, etc.)
   - Sin restricciones de usuario

3. **`search_documents_by_criteria_secured`**
   - Búsqueda avanzada con filtros múltiples
   - **RESTRINGIDA** por empresas del usuario

4. **`get_document_stats_summary_secured`**
   - Estadísticas generales de documentos
   - **RESTRINGIDA** por empresas del usuario

5. **`calculate_dte_tax_impact_secured`**
   - Cálculos de IVA y impacto tributario
   - Sin restricciones de usuario (cálculos teóricos)

6. **`get_recent_documents_summary_secured`**
   - Resumen detallado de documentos recientes
   - **RESTRINGIDA** por empresas del usuario

### 🔒 **Seguridad**

- **Autenticación requerida**: Herramientas críticas requieren `user_id`
- **Restricción por empresa**: Solo acceso a documentos de empresas del usuario
- **Validación de permisos**: Via modelo `UserRole`

### 📊 **Tipos de DTE Soportados**

| Código | Nombre | Categoría |
|--------|--------|-----------|
| 33 | Factura Electrónica | Afecta a IVA |
| 34 | Factura Exenta | Exenta |
| 39 | Boleta Electrónica | Consumidor final |
| 61 | Nota de Crédito | Anulaciones |
| 56 | Nota de Débito | Cargos adicionales |
| 52 | Guía de Despacho | Traslado |
| 110 | Factura de Exportación | Exportación |

### 💬 **Ejemplos de Consultas**

- *"¿Qué tipos de documentos DTE existen?"*
- *"Dame un resumen de mis últimos DTEs"*
- *"¿Cuánto IVA debo cobrar por una factura de $100,000?"*
- *"¿Qué es un documento DTE código 33?"*
- *"Estadísticas de documentos de los últimos 30 días"*

### 🛠 **Uso Programático**

```python
from apps.chat.services.langchain.agents.dte import DTEAgent

# Crear instancia
dte_agent = DTEAgent()

# Ejecutar con contexto de usuario
state = {
    "messages": [HumanMessage(content="Dame mis documentos recientes")],
    "metadata": {"user_id": user_id}
}

result = dte_agent.run(state)
```

### 📝 **Notas de Implementación**

- Usa **LangGraph** con patrón React Agent
- Modelo: `gpt-4o-mini` (temperatura 0.3)
- Respuestas limitadas a 4-5 líneas para concisión
- Manejo de errores robusto con fallbacks