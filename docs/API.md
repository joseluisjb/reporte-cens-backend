# NexoVolt API

## Información general

| Campo | Valor |
|---|---|
| URL base | `/api/` |
| Formato | JSON |
| Autenticación | Pendiente de RF25 |
| Roles disponibles | `ANALISTA_CARTERA`, `ADMINISTRADOR` |

## Formato de errores (estándar DRF)

Error simple:

```json
{"detail": "Mensaje de error."}
```

Error de validación:

```json
{"campo": ["Mensaje de error."]}
```

## Endpoints

### Utilidades

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/salud/` | Ninguno | Verifica disponibilidad del servidor |

### Conceptos de energía

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/conceptos/` | ANALISTA_CARTERA, ADMINISTRADOR | Lista conceptos; filtro opcional `?activo=true\|false` |
| POST | `/api/conceptos/` | ANALISTA_CARTERA, ADMINISTRADOR | Crea un concepto; `409` si el código ya existe |
| PATCH | `/api/conceptos/{codigo}/` | ANALISTA_CARTERA, ADMINISTRADOR | Actualiza `descripcion`, `observacion` y/o `activo` |

**Cuerpo POST**

```json
{"codigo": 1, "descripcion": "Energía activa", "activo": true, "observacion": "Opcional"}
```

`activo` es opcional (defecto `true`). `observacion` es opcional.

**Cuerpo PATCH** (todos los campos son opcionales)

```json
{"descripcion": "Nuevo nombre", "activo": false, "observacion": "Nueva obs"}
```

**Respuesta 200/201**

```json
{"codigo": 1, "descripcion": "Energía activa", "activo": true, "observacion": null}
```

**Errores específicos**

- `409 Conflict` — el código de concepto ya existe (POST)
- `404 Not Found` — código no encontrado (PATCH)

### Grupos de conceptos de energía

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/grupos-conceptos/` | ANALISTA_CARTERA, ADMINISTRADOR | Lista todos los grupos con sus conceptos |
| POST | `/api/grupos-conceptos/` | ANALISTA_CARTERA, ADMINISTRADOR | Crea un grupo; `409` si el nombre ya existe |
| GET | `/api/grupos-conceptos/{id}/` | ANALISTA_CARTERA, ADMINISTRADOR | Detalle de un grupo |
| PATCH | `/api/grupos-conceptos/{id}/` | ANALISTA_CARTERA, ADMINISTRADOR | Actualiza nombre, activo y/o lista de conceptos |
| DELETE | `/api/grupos-conceptos/{id}/` | ANALISTA_CARTERA, ADMINISTRADOR | Elimina el grupo; `409` si hay un corte en BORRADOR |

**Cuerpo POST**

```json
{"nombre": "Grupo A", "conceptos": [30, 61]}
```

**Cuerpo PATCH** (todos los campos son opcionales; `conceptos` reemplaza la lista completa)

```json
{"nombre": "Nuevo nombre", "activo": false, "conceptos": [30]}
```

**Respuesta 200/201**

```json
{
  "id": 1,
  "nombre": "Grupo A",
  "activo": true,
  "conceptos": [{"codigo": 30, "descripcion": "Energía activa"}],
  "creado": "2026-10-10"
}
```

**Errores específicos**

- `400 Bad Request` — concepto inexistente o sin `REPORTABLE='S'` (mensaje incluye el código problemático)
- `409 Conflict` — nombre de grupo duplicado (POST/PATCH) o grupo en uso por corte en BORRADOR (DELETE)
- `404 Not Found` — grupo no encontrado (GET, PATCH, DELETE)
