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

### Extracción de cartera (RF44)

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| POST | `/api/extracciones/` | ANALISTA_CARTERA, ADMINISTRADOR | Genera un corte de cartera |
| GET | `/api/extracciones/` | ANALISTA_CARTERA, ADMINISTRADOR | Lista cortes (excluye ANULADO), del más reciente al más antiguo |
| GET | `/api/extracciones/ultima/` | ANALISTA_CARTERA, ADMINISTRADOR | Devuelve el corte más reciente; `204` si no hay ninguno |
| GET | `/api/extracciones/{id}/` | ANALISTA_CARTERA, ADMINISTRADOR | Detalle de un corte |
| GET | `/api/extracciones/{id}/obligaciones/` | ANALISTA_CARTERA, ADMINISTRADOR | Obligaciones del corte con paginación |

**Cuerpo POST**

```json
{"fecha_corte": "2026-09-30", "grupo_id": 1}
```

`grupo_id` es opcional. Sin él se usan todos los conceptos con `REPORTABLE='S'`.

**Respuesta 200/201 — Resumen de corte**

```json
{
  "id": 1,
  "fecha_corte": "2026-09-30",
  "fecha_ejecucion": "2026-10-10T12:00:00",
  "grupo": {"id": 1, "nombre": "Grupo A"},
  "obligaciones": 150,
  "saldo_consolidado": 45000000,
  "estado": "BORRADOR",
  "ejecutada_por": null
}
```

`grupo` es `null` cuando no se usó grupo. `ejecutada_por` es `null` hasta que se implemente RF25 (autenticación).

**Parámetros de paginación en `/obligaciones/`**

| Parámetro | Tipo | Defecto | Descripción |
|---|---|---|---|
| `limite` | entero | 20 | Máximo de filas a devolver |
| `desplazamiento` | entero | 0 | Cuántas filas saltarse |

**Respuesta 200 — Obligaciones**

```json
{
  "total": 150,
  "resultados": [
    {
      "numero_obligacion": "OBL0001",
      "nombre_titular": "JUAN PÉREZ",
      "numero_identificacion": "12345678",
      "estado_tu": "01",
      "edad_mora": "00",
      "dias_mora": 0,
      "cuotas_mora": 0,
      "valor_mora": 0,
      "valor_saldo": 500000,
      "n_creditos": 1
    }
  ]
}
```

**Errores específicos**

- `400 Bad Request` — `fecha_corte` ausente o futura
- `404 Not Found` — grupo o corte no encontrado
- `409 Conflict` — grupo inactivo; corte de esa fecha en estado distinto de BORRADOR **[pendiente de decisión del equipo]**; ya existe un BORRADOR con distinta fecha **[pendiente de decisión del equipo]**

**Notas sobre reglas de corte [pendiente de decisión del equipo]**

- Si ya existe un corte con la misma `fecha_corte` en estado `BORRADOR`, se reemplaza: se borran su detalle (`NV_REPORTE_DETALLE`) y sus inconsistencias (`NV_INCONSISTENCIA`), y se actualiza el mismo registro.
- Si existe un corte con esa fecha en cualquier otro estado (`VALIDADO`, `ENVIADO`, `ANULADO`), se devuelve `409`.
- Si existe un `BORRADOR` de otra fecha, se devuelve `409` con un mensaje que indica la fecha en conflicto.
