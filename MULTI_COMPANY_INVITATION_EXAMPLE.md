# Multi-Company Invitation API - Ejemplos de Uso

## Resumen de Cambios Implementados

El endpoint `/api/v1/auth/users/invite_to_team/` ahora soporta invitaciones a múltiples empresas simultáneamente.

### Cambios en el Serializer

- ✅ **Campo actualizado**: `company_id` → `company_ids` (lista de IDs)
- ✅ **Validación de ownership**: Usuario debe ser owner de TODAS las empresas especificadas
- ✅ **Validación de membresía**: Email no puede ser miembro de NINGUNA de las empresas
- ✅ **Validación de invitaciones**: No debe haber invitaciones pendientes que incluyan alguna de estas empresas

### Cambios en la Vista

- ✅ **Creación de invitación única**: Una sola invitación asociada a múltiples empresas
- ✅ **Respuesta actualizada**: Incluye información de todas las empresas
- ✅ **Mensaje mejorado**: Menciona todas las empresas en el mensaje de respuesta

## Ejemplos de Uso

### 1. Invitación Exitosa a Múltiples Empresas

**Request:**
```bash
POST /api/v1/auth/users/invite_to_team/
Authorization: Bearer your-jwt-token
Content-Type: application/json

{
    "email": "nuevo.empleado@empresa.com",
    "company_ids": [1, 2, 3],
    "role_id": 2
}
```

**Response Exitosa (201 Created):**
```json
{
    "message": "Invitación enviada exitosamente a nuevo.empleado@empresa.com para Empresa A, Empresa B, Empresa C",
    "invitation": {
        "id": 123,
        "token": "550e8400-e29b-41d4-a716-446655440000",
        "email": "nuevo.empleado@empresa.com",
        "companies": [
            {
                "id": 1,
                "name": "Empresa A",
                "business_name": "Empresa A S.A."
            },
            {
                "id": 2,
                "name": "Empresa B",
                "business_name": "Empresa B Ltda."
            },
            {
                "id": 3,
                "name": "Empresa C",
                "business_name": "Empresa C SpA."
            }
        ],
        "role": {
            "id": 2,
            "name": "Admin"
        },
        "expires_at": "2025-10-03T10:30:00Z",
        "status": "pending"
    }
}
```

### 2. Error - No es Owner de Todas las Empresas

**Request:**
```json
{
    "email": "usuario@empresa.com",
    "company_ids": [1, 99],  // Usuario no es owner de empresa 99
    "role_id": 2
}
```

**Response de Error (400 Bad Request):**
```json
{
    "company_ids": ["Solo los propietarios pueden enviar invitaciones. No eres owner de Empresa Z"]
}
```

### 3. Error - Usuario ya es Miembro de una Empresa

**Request:**
```json
{
    "email": "miembro.existente@empresa.com", // Ya es miembro de empresa 1
    "company_ids": [1, 2],
    "role_id": 2
}
```

**Response de Error (400 Bad Request):**
```json
{
    "email": ["Este usuario ya es miembro de Empresa A"]
}
```

### 4. Error - Invitación Pendiente Existente

**Request:**
```json
{
    "email": "usuario.invitado@empresa.com", // Ya tiene invitación pendiente para empresa 1
    "company_ids": [1, 2],
    "role_id": 2
}
```

**Response de Error (400 Bad Request):**
```json
{
    "email": ["Ya existe una invitación pendiente para este email que incluye Empresa A"]
}
```

### 5. Error - Empresa No Existe

**Request:**
```json
{
    "email": "usuario@empresa.com",
    "company_ids": [1, 99999], // Empresa 99999 no existe
    "role_id": 2
}
```

**Response de Error (400 Bad Request):**
```json
{
    "company_ids": ["La empresa con ID 99999 no existe"]
}
```

## Validaciones Implementadas

### 1. Validación de Empresas
- ✅ Todas las empresas especificadas deben existir
- ✅ El usuario debe ser owner de TODAS las empresas

### 2. Validación de Email
- ✅ El email no debe ser miembro de NINGUNA de las empresas especificadas
- ✅ No debe haber invitaciones pendientes que incluyan ALGUNA de estas empresas

### 3. Validación de Rol
- ✅ El rol debe existir y estar activo

## Impacto en el Modelo TeamInvitation

El modelo ya soportaba múltiples empresas a través del campo `companies` (ManyToManyField). Los cambios fueron únicamente en:

1. **Serializer**: Acepta `company_ids` en lugar de `company_id`
2. **Vista**: Asocia múltiples empresas a la invitación usando `invitation.companies.set(companies)`
3. **Validaciones**: Verifican ownership y membresía en todas las empresas

## Comportamiento del Usuario Invitado

Cuando el usuario acepta la invitación:
- Se crean UserRole entries para TODAS las empresas asociadas a la invitación
- El usuario obtiene el mismo rol en todas las empresas
- Se puede unir a múltiples empresas con una sola aceptación

## Compatibilidad

✅ **Backward Compatibility**: El frontend puede seguir enviando un solo ID en un array `[1]` para mantener compatibilidad
✅ **Escalabilidad**: El endpoint puede manejar desde 1 hasta múltiples empresas sin problemas
✅ **Validación Robusta**: Todas las validaciones de seguridad se mantienen y se extienden a múltiples empresas

## Testing

Se han implementado tests completos que verifican:
- ✅ Invitación exitosa a múltiples empresas
- ✅ Validación de ownership en todas las empresas
- ✅ Validación de membresía existente
- ✅ Validación de invitaciones pendientes
- ✅ Manejo de empresas inexistentes
- ✅ Permisos de usuario no-owner