# API Endpoints para Formularios Tributarios - CRUD

## Endpoints Disponibles

### 1. **Endpoints CRUD Básicos**

#### **GET /api/v1/forms/tax-forms/**
Lista todos los formularios tributarios con paginación.

**Query Parameters:**
- `company_id`: Filtrar por ID de empresa
- `company_rut`: Filtrar por RUT de empresa (legacy)
- `form_type`: Filtrar por tipo de formulario (f29, f3323, etc.)
- `tax_year`: Filtrar por año tributario
- `status`: Filtrar por estado del formulario

**Response includes:**
- Información básica del formulario
- Company y template relacionados
- `details_extracted`: Boolean indicando si tiene detalles extraídos
- `needs_detail_extraction`: Boolean indicando si necesita extracción
- `has_recent_details`: Boolean indicando si tiene detalles recientes

---

#### **GET /api/v1/forms/tax-forms/{id}/**
Obtiene un formulario específico con toda la información.

**Response includes:**
- Todos los campos del formulario
- `details_extracted`, `details_extracted_at`, `details_extraction_method`
- Company y template completos
- Campos y pagos relacionados

---

### 2. **Endpoints de Detalles Extraídos (NUEVOS)**

#### **GET /api/v1/forms/tax-forms/{id}/details/**
🆕 Obtiene los detalles extraídos de un formulario específico.

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 40,
    "company_name": "Atal",
    "company_tax_id": "77794858-K",
    "sii_folio": "8420514146",
    "tax_period": "2025-07",
    "template_name": "F29 - Declaración Mensual IVA",
    "form_type": "f29",
    "status": "submitted",
    "details_extracted": true,
    "details_extracted_at": "2025-09-23T08:23:23.738299-03:00",
    "details_extraction_method": "f29_rpa_service",
    "details_data": {
      "extraction_timestamp": "2025-09-23T11:23:23.738299",
      "folio": "8420514146",
      "periodo": "2025-07",
      "total_campos": 27,
      "campos_extraidos": [
        {
          "code": "732",
          "name": "Ventas con retención sobre el margen...",
          "value": "96",
          "value_formatted": 96.0,
          "value_original": "96",
          "subject": "Debito Fiscal"
        }
      ],
      "subtablas": [],
      "extraction_method": "f29_rpa"
    },
    "needs_detail_extraction": false,
    "has_recent_details": true,
    "created_at": "2025-09-23T08:15:45.123456-03:00",
    "updated_at": "2025-09-23T08:23:23.746789-03:00"
  },
  "timestamp": "2025-09-23T11:49:02.123456"
}
```

---

#### **GET /api/v1/forms/tax-forms/with_details/**
🆕 Lista formularios que tienen detalles extraídos.

**Query Parameters:**
- `company_id`: Filtrar por empresa
- `form_type`: Filtrar por tipo de formulario

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": 40,
      "company_name": "Atal",
      "sii_folio": "8420514146",
      "details_extracted": true,
      "details_data": { /* Raw extracted data */ }
    }
  ],
  "count": 25,
  "timestamp": "2025-09-23T11:49:02.123456"
}
```

---

#### **GET /api/v1/forms/tax-forms/extraction_status/**
🆕 Obtiene estadísticas de extracción de detalles.

**Query Parameters:**
- `company_id`: Estadísticas para empresa específica

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_forms": 25,
    "with_details": 25,
    "needing_extraction": 0,
    "extraction_percentage": 100.0,
    "by_form_type": {
      "f29": {
        "total": 25,
        "extracted": 25,
        "percentage": 100.0
      }
    },
    "recent_extractions": [
      {
        "id": 40,
        "sii_folio": "8420514146",
        "details_extracted_at": "2025-09-23T08:23:23.738299-03:00"
      }
    ]
  },
  "timestamp": "2025-09-23T11:49:02.123456"
}
```

---

### 3. **Endpoints CRUD Estándar**

#### **POST /api/v1/forms/tax-forms/**
Crea un nuevo formulario tributario.

#### **PUT /api/v1/forms/tax-forms/{id}/**
Actualiza un formulario existente completamente.

#### **PATCH /api/v1/forms/tax-forms/{id}/**
Actualiza parcialmente un formulario existente.

#### **DELETE /api/v1/forms/tax-forms/{id}/**
Elimina un formulario (soft delete recomendado).

---

### 4. **Endpoint de Resumen Legacy**

#### **GET /api/v1/forms/summary/**
Obtiene resumen de formularios por empresa.

**Query Parameters:**
- `company_rut`: RUT de la empresa (requerido)

---

## Estructura de Datos de Detalles Extraídos

### **details_data** contiene:

```json
{
  "extraction_timestamp": "2025-09-23T11:23:23.738299",
  "folio": "8420514146",
  "periodo": "2025-07",
  "total_campos": 27,
  "extraction_method": "f29_rpa",
  "campos_extraidos": [
    {
      "code": "732",
      "name": "Ventas con retención sobre el margen de comercialización",
      "value": "96",
      "value_formatted": 96.0,
      "value_original": "96",
      "subject": "Debito Fiscal"
    }
  ],
  "campos_extraidos_raw": [ /* Datos originales sin formatear */ ],
  "subtablas": [ /* Subtablas si existen */ ],
  "original_response": { /* Response completo del F29Service */ }
}
```

### **Campos Formateados:**
- `value`: Valor original como string del SII
- `value_formatted`: Valor convertido a float (ej: "1.023.785" → 1023785.0)
- `value_original`: Backup del valor original

---

## Ejemplos de Uso

### **1. Obtener formularios con detalles de una empresa:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/forms/tax-forms/with_details/?company_id=1"
```

### **2. Obtener detalles específicos de un formulario:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/forms/tax-forms/40/details/"
```

### **3. Crear un nuevo formulario:**
```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": 1,
    "template_id": 1,
    "tax_year": 2025,
    "tax_month": 7,
    "status": "draft"
  }' \
  "http://localhost:8000/api/v1/forms/tax-forms/"
```

### **4. Ver estadísticas de extracción:**
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/forms/tax-forms/extraction_status/"
```

---

## Notas Importantes

1. **Autenticación:** Todos los endpoints requieren autenticación JWT
2. **Permisos:** Usuario debe tener acceso a la empresa del formulario
3. **CRUD Puro:** Estos endpoints solo manejan operaciones de Create, Read, Update, Delete
4. **Formateo:** Los valores extraídos incluyen formato chileno convertido a numérico
5. **Caché:** Los detalles se almacenan en `details_data` (JSONField)
6. **Estado:** Use `needs_detail_extraction` para saber qué formularios necesitan extracción
7. **Sincronización:** Los procesos de sincronización con SII se manejan en módulos separados