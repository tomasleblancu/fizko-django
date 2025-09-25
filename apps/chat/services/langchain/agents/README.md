# Agents - Sistema Multi-Agente

Sistema de agentes especializados para el chat bot de Fizko, organizado por carpetas para una mejor administración.

## 🗂️ Estructura

```
agents/
├── __init__.py              # Exporta todos los agentes
├── README.md                # Esta documentación
├── dte/                     # 📄 Documentos Tributarios Electrónicos
│   ├── __init__.py
│   ├── agent.py             # Agente principal con herramientas
│   ├── tools.py             # Herramientas base de DTE
│   ├── tools_context.py     # Herramientas con contexto de usuario
│   └── README.md
├── tax/                     # 💰 Tributación Chilena
│   ├── __init__.py
│   ├── agent.py             # F29, F3323, renta, PPM
│   └── README.md
├── sii/                     # 🏛️ Servicios del SII
│   ├── __init__.py
│   ├── agent.py             # Portal, certificados, trámites
│   └── README.md
└── general/                 # 📚 Contabilidad General
    ├── __init__.py
    ├── agent.py             # Consultas generales y derivación
    └── README.md
```

## 🤖 Agentes Disponibles

### 1. **DTEAgent** (`dte/`)
- **Especialidad**: Documentos Tributarios Electrónicos
- **Herramientas**: 6 herramientas especializadas con restricciones de usuario
- **Casos de uso**: Facturas, boletas, notas de crédito/débito, estadísticas
- **Seguridad**: ✅ Restricciones por empresa implementadas

### 2. **TaxAgent** (`tax/`)
- **Especialidad**: Tributación chilena
- **Conocimiento**: F29, F3323, renta, PPM, plazos tributarios
- **Casos de uso**: Consultas sobre declaraciones y fechas límite
- **Seguridad**: ❌ Sin herramientas de acceso a datos

### 3. **SIIAgent** (`sii/`)
- **Especialidad**: Servicios del Servicio de Impuestos Internos
- **Conocimiento**: Portal MiSII, certificados, trámites
- **Casos de uso**: Procedimientos oficiales, inicio de actividades
- **Seguridad**: ❌ Sin herramientas de acceso a datos

### 4. **GeneralAgent** (`general/`)
- **Especialidad**: Contabilidad general y derivación
- **Función**: Maneja consultas básicas y deriva a especialistas
- **Casos de uso**: Conceptos generales, saludos, explicaciones simples
- **Seguridad**: ❌ Sin herramientas de acceso a datos

## 🔧 Agregar Nuevos Agentes

Para agregar un nuevo agente especializado:

### 1. Crear estructura de carpeta
```bash
mkdir apps/chat/services/langchain/agents/nuevo_agente
```

### 2. Archivos básicos
```
nuevo_agente/
├── __init__.py      # from .agent import NuevoAgente
├── agent.py         # Implementación del agente
├── tools.py         # (Opcional) Herramientas del agente
└── README.md        # Documentación específica
```

### 3. Implementar el agente
```python
# agent.py
class NuevoAgente:
    def __init__(self):
        self.llm = ChatOpenAI(...)
        self.tools = [...]  # Si tiene herramientas

    def run(self, state: AgentState) -> Dict:
        # Lógica del agente
        pass
```

### 4. Registrar en supervisor
```python
# supervisor.py
from .agents import NuevoAgente

self.agents = {
    # ... agentes existentes
    "nuevo": NuevoAgente()
}
```

### 5. Actualizar routing
```python
# En routing_prompt del supervisor
- nuevo: Para [descripción del dominio]
```

## 🛡️ Seguridad y Herramientas

### Herramientas con Restricciones de Usuario

Solo el **DTEAgent** actualmente implementa restricciones de seguridad:

- **Autenticación requerida**: `user_id` obligatorio
- **Filtrado por empresa**: Solo datos de empresas del usuario
- **Validación de roles**: Via modelo `UserRole`

### Patrón de Herramientas Seguras

```python
# tools_context.py
def set_user_context(user_id: Optional[int]):
    """Establece el contexto del usuario"""
    global _current_user_id
    _current_user_id = user_id

@tool
def herramienta_segura_secured(parametros) -> Dict:
    """Herramienta que respeta el contexto del usuario"""
    user_id = get_user_context()
    if not user_id:
        return {"error": "Autenticación requerida"}

    # Filtrar datos por usuario...
```

## 🚀 Desarrollo y Testing

### Probar un agente específico
```python
from apps.chat.services.langchain.agents.dte import DTEAgent

agent = DTEAgent()
result = agent.run({
    "messages": [...],
    "metadata": {"user_id": 123}
})
```

### Ejecutar todo el sistema
```python
from apps.chat.services.langchain.supervisor import multi_agent_system

response = multi_agent_system.process(
    "consulta del usuario",
    metadata={"user_id": 123}
)
```

## 📈 Métricas y Monitoreo

- **Logs estructurados** por agente
- **Tracking de herramientas** utilizadas
- **Métricas de performance** por especialidad
- **Auditoría de acceso** a datos sensibles

---

Esta estructura modular permite:
- ✅ **Mantenimiento independiente** de cada agente
- ✅ **Escalabilidad** para nuevos dominios
- ✅ **Testing aislado** por funcionalidad
- ✅ **Documentación específica** y clara
- ✅ **Seguridad granular** por tipo de datos