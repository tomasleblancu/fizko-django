# Sistema de Gestión de Procesos Tributarios

Sistema completo de configuración y asignación automática de procesos tributarios para Fizko.

## 📋 Descripción General

Este sistema permite:
- **Segmentar empresas** por características (tamaño, actividad, régimen tributario)
- **Configurar plantillas** de procesos reutilizables con tareas predefinidas
- **Asignar automáticamente** procesos a empresas según reglas de negocio
- **Gestionar** todo desde el admin de Django con interfaces intuitivas

## 🏗️ Arquitectura

### Modelos Principales

#### 1. CompanySegment
Segmentación de empresas para clasificación automática.

```python
CompanySegment(
    name="PYME con F29",
    segment_type="tax_regime",
    criteria={
        "tax_regime": ["f29_monthly"],
        "size": {"min_employees": 1, "max_employees": 50}
    }
)
```

**Tipos de segmento:**
- `size`: Por tamaño (número de empleados)
- `industry`: Por actividad económica
- `tax_regime`: Por régimen tributario
- `revenue`: Por ingresos anuales
- `custom`: Personalizado

#### 2. ProcessTemplateConfig
Plantilla configurable de procesos con toda la estructura predefinida.

```python
ProcessTemplateConfig(
    name="F29 - Declaración Mensual IVA",
    process_type="tax_monthly",
    status="active",
    default_recurrence_type="monthly",
    template_config={
        "form_type": "f29",
        "auto_sync_documents": True
    }
)
```

**Características:**
- Variables dinámicas y valores por defecto
- Configuración de recurrencia (mensual, trimestral, anual)
- Estadísticas de uso
- Estados: active, inactive, testing

#### 3. ProcessTemplateTask
Tareas predefinidas dentro de una plantilla.

```python
ProcessTemplateTask(
    template=template_f29,
    task_title="Sincronizar documentos del mes",
    execution_order=1,
    priority="high",
    due_date_offset_days=2,
    estimated_hours=1
)
```

**Características:**
- Orden de ejecución
- Dependencias entre tareas
- Plazos relativos o absolutos
- Opcionalidad y paralelización

#### 4. ProcessAssignmentRule
Reglas de asignación automática de plantillas a segmentos.

```python
ProcessAssignmentRule(
    template=template_f29,
    segment=segment_pyme,
    priority=100,
    auto_apply=True
)
```

**Características:**
- Prioridad de aplicación
- Vigencia temporal
- Condiciones adicionales
- Aplicación automática o manual

### Servicios

#### ProcessAssignmentService
Lógica de evaluación y asignación automática.

```python
# Asignar segmento y procesos a una empresa
ProcessAssignmentService.assign_segment_to_company(
    company,
    auto_assign_processes=True
)

# Obtener plantillas aplicables
templates = ProcessAssignmentService.get_applicable_templates(company)

# Asignación masiva
stats = ProcessAssignmentService.bulk_assign_segments(companies)
```

**Métodos principales:**
- `evaluate_company_segment()`: Evalúa segmento de empresa
- `assign_segment_to_company()`: Asigna segmento y procesos
- `assign_processes_by_rules()`: Aplica reglas de asignación
- `apply_template_to_company()`: Crea proceso desde plantilla
- `get_applicable_templates()`: Obtiene plantillas aplicables

#### ProcessTemplateFactory
Factory mejorado para crear procesos desde plantillas.

```python
# Crear proceso desde template
process = ProcessTemplateFactory.create_from_config(
    template=template_f29,
    company=company,
    created_by="admin@fizko.cl"
)

# Clonar plantilla
new_template = ProcessTemplateFactory.clone_template(
    template=template_f29,
    new_name="F29 - Copia",
    created_by="admin@fizko.cl"
)
```

## 🚀 Inicio Rápido

### 1. Configurar Sistema de Ejemplo

```bash
cd fizko_django
docker-compose exec django python manage.py setup_process_templates
```

Este comando crea:
- 2 segmentos de empresas (PYME con F29, Pro-Pyme con F3323)
- 2 plantillas de procesos (F29 mensual, F22 anual)
- 10 tareas predefinidas
- 2 reglas de asignación

### 2. Acceder al Admin

Navega a: `http://localhost:8000/admin/`

En la sección **TASKS** encontrarás:
- **Segmentos de Empresas**
- **Configuraciones de Plantillas de Procesos**
- **Tareas de Plantilla**
- **Reglas de Asignación de Procesos**

### 3. Asignar Segmento a Empresa

Opción A - **Desde Admin de TaxPayers:**
1. Ir a `Taxpayers > Tax payers`
2. Seleccionar un taxpayer
3. En el campo "Segmento de Empresa" seleccionar el segmento
4. Guardar

Opción B - **Programáticamente:**
```python
from apps.companies.models import Company
from apps.tasks.services import ProcessAssignmentService

company = Company.objects.get(id=114)
segment = ProcessAssignmentService.assign_segment_to_company(
    company,
    auto_assign_processes=True  # Crea procesos automáticamente
)
```

## 📊 Interfaces de Administración

### CompanySegmentAdmin
- **List view**: Nombre, tipo, cantidad de empresas, estado
- **Acciones**: Activar/desactivar segmentos
- **Fieldsets**: Información básica, criterios, metadata

### ProcessTemplateConfigAdmin
- **List view**: Nombre, tipo, estado (con badge), tareas, uso
- **Inline**: Tareas de la plantilla
- **Acciones**:
  - Activar/desactivar plantillas
  - Cambiar estado (activo, inactivo, testing)
  - **Duplicar plantillas** (con todas sus tareas)
- **Fieldsets**: Básico, estado, recurrencia, configuración, estadísticas

### ProcessTemplateTaskAdmin
- **List view**: Título, plantilla, orden, prioridad, tipo
- **Fieldsets**: Información, orden/dependencias, plazos, configuración

### ProcessAssignmentRuleAdmin
- **List view**: Regla (template → segment), prioridad, vigencia, auto-apply
- **Acciones**: Activar/desactivar reglas
- **Fieldsets**: Asignación, condiciones, vigencia, metadata

## 💡 Casos de Uso

### Caso 1: Crear Nueva Plantilla de Proceso

1. Ir a `Tasks > Configuraciones de plantillas de procesos`
2. Click en "Agregar"
3. Completar información básica:
   - Nombre: "F3323 - Declaración Trimestral Pro-Pyme"
   - Tipo: "Declaración Mensual" (usar tax_monthly o custom)
   - Estado: "Activo"
4. Configurar recurrencia:
   - Tipo: "Trimestral"
   - Configuración: `{"months": [3, 6, 9, 12]}`
5. Agregar tareas en la sección inline
6. Guardar

### Caso 2: Duplicar y Modificar Plantilla

1. Ir a `Tasks > Configuraciones de plantillas de procesos`
2. Seleccionar plantilla a duplicar
3. En "Acciones" seleccionar "Duplicar plantillas"
4. Editar la plantilla duplicada con los cambios necesarios
5. Activar cuando esté lista

### Caso 3: Crear Segmento Personalizado

1. Ir a `Tasks > Segmentos de empresas`
2. Click en "Agregar"
3. Definir criterios:
```json
{
  "tax_regime": ["f29_monthly"],
  "annual_revenue": {"min": 50000000, "max": 200000000},
  "custom_conditions": ["has_exports"]
}
```
4. Guardar y activar

### Caso 4: Asignar Procesos a Nuevo Cliente

```python
from apps.companies.models import Company
from apps.tasks.services import ProcessAssignmentService

# Al crear nueva empresa
company = Company.objects.get(business_name="Nueva Empresa")

# 1. Evaluar y asignar segmento
segment = ProcessAssignmentService.assign_segment_to_company(
    company,
    auto_assign_processes=True
)

# Los procesos se crean automáticamente según las reglas
```

### Caso 5: Asignación Masiva

```python
from apps.companies.models import Company
from apps.tasks.services import ProcessAssignmentService

# Asignar segmentos a todas las empresas sin segmento
companies = Company.objects.filter(taxpayer__company_segment__isnull=True)
stats = ProcessAssignmentService.bulk_assign_segments(companies)

print(stats)
# {'total': 50, 'assigned': 45, 'failed': 0, 'no_segment': 5}
```

## 🔧 Configuración Avanzada

### Criterios de Segmentación

Los criterios se definen en JSON en el campo `criteria` de CompanySegment:

```json
{
  "size": {
    "min_employees": 10,
    "max_employees": 50
  },
  "tax_regime": ["14A", "14B", "f29_monthly"],
  "economic_activity": ["comercio", "servicios"],
  "annual_revenue": {
    "min": 50000000,
    "max": 200000000
  },
  "custom_conditions": [
    "has_exports",
    "requires_f3323",
    "high_transaction_volume"
  ]
}
```

### Variables de Plantilla

Las plantillas pueden tener variables dinámicas:

```python
template = ProcessTemplateConfig.objects.create(
    name="F29 Personalizado",
    available_variables=["period", "company_name", "rut", "tax_year"],
    default_values={
        "auto_calculate_iva": True,
        "include_credits": True,
        "tax_year": 2025
    }
)
```

### Configuración de Recurrencia

```python
# Mensual
default_recurrence_config={
    "day_of_month": 12,
    "months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
}

# Trimestral
default_recurrence_config={
    "day_of_month": 20,
    "months": [3, 6, 9, 12]  # Marzo, Junio, Septiembre, Diciembre
}

# Anual
default_recurrence_config={
    "month": 4,  # Abril
    "day": 30
}
```

## 📈 Próximas Mejoras

- [ ] Serializers DRF para API REST
- [ ] Endpoints API para frontend
- [ ] Signals para auto-asignación al crear empresa
- [ ] Interface frontend en React
- [ ] Evaluación dinámica de criterios personalizados
- [ ] Reportes y estadísticas de uso
- [ ] Sistema de notificaciones al crear procesos
- [ ] Versionado de plantillas

## 🤝 Integración con Sistema Existente

### Con create_processes_from_taxpayer_settings

El nuevo sistema es compatible con el sistema legacy:

```python
# Legacy (todavía funciona)
from apps.tasks.tasks.process_management import create_processes_from_taxpayer_settings
create_processes_from_taxpayer_settings.delay(company_id=114)

# Nuevo sistema (recomendado)
from apps.tasks.services import ProcessAssignmentService
company = Company.objects.get(id=114)
ProcessAssignmentService.assign_processes_by_rules(company)
```

### Con ProcessTemplateFactory

```python
# Legacy
from apps.tasks.services import ProcessTemplateFactory
ProcessTemplateFactory.create_monthly_f29_process(
    company_rut="77745293",
    company_dv="2",
    period="2025-10"
)

# Nuevo (usa templates si están configurados)
# Busca automáticamente template F29 y lo aplica
```

## 📝 Ejemplos de Código

### Crear Proceso Manualmente desde Template

```python
from apps.tasks.models import ProcessTemplateConfig
from apps.companies.models import Company
from apps.tasks.services import ProcessAssignmentService

template = ProcessTemplateConfig.objects.get(name="F29 - Declaración Mensual IVA")
company = Company.objects.get(id=114)

process = ProcessAssignmentService.apply_template_to_company(
    template=template,
    company=company,
    created_by="admin@fizko.cl",
    config_overrides={"period": "2025-10"}
)

print(f"Proceso creado: {process.name}")
print(f"Tareas: {process.process_tasks.count()}")
```

### Verificar Plantillas Aplicables

```python
from apps.companies.models import Company
from apps.tasks.services import ProcessAssignmentService

company = Company.objects.get(business_name="La Place")
templates = ProcessAssignmentService.get_applicable_templates(company)

for template in templates:
    print(f"- {template.name} ({template.process_type})")
    print(f"  Tareas: {template.template_tasks.count()}")
    print(f"  Usado: {template.usage_count} veces")
```

## 🎯 Mejores Prácticas

1. **Segmentación clara**: Define criterios específicos y no superpuestos
2. **Prioridad de reglas**: Usa prioridades para resolver conflictos
3. **Testing**: Usa estado "testing" antes de activar plantillas en producción
4. **Duplicación**: Duplica plantillas existentes en lugar de crear desde cero
5. **Monitoreo**: Revisa estadísticas de uso regularmente
6. **Documentación**: Describe claramente cada plantilla y segmento

## 📚 Referencias

- Modelos: `apps/tasks/models.py` (líneas 797-1113)
- Servicios: `apps/tasks/services/`
- Admin: `apps/tasks/admin.py` (líneas 119-376)
- TaxPayer: `apps/taxpayers/models.py` (líneas 49-167)
- Management Command: `apps/tasks/management/commands/setup_process_templates.py`

---

**Desarrollado por:** Fizko Team
**Fecha:** Octubre 2025
**Versión:** 1.0.0
