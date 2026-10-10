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
