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

### Ciclo mínimo de corte (RF6 parcial)

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| POST | `/api/extracciones/{id}/validar/` | ANALISTA_CARTERA, ADMINISTRADOR | Valida el corte en BORRADOR y lo pasa a VALIDADO |
| POST | `/api/extracciones/{id}/registrar-envio/` | ANALISTA_CARTERA, ADMINISTRADOR | Registra el envío a TransUnion y pasa a ENVIADO |

**POST /validar/**

No requiere cuerpo. Si hay filas con `SEVERIDAD='CORRECTIVA'` en `V_VALIDACION_CORTE`, responde `409` y **no** cambia el estado. Si no hay errores correctivos, cambia el estado a `VALIDADO` y devuelve el corte con las advertencias informativas.

Respuesta `200`:
```json
{
  "id": 1,
  "fecha_corte": "2026-09-30",
  "estado": "VALIDADO",
  "advertencias": [
    {"regla": "SIN_FECHA_LIMITE_PAGO", "mensaje": "No se encontró una factura..."}
  ]
}
```

Respuesta `409` con errores:
```json
{
  "detail": "El corte tiene errores correctivos que deben resolverse.",
  "errores": [
    {"regla": "SIN_IDENTIFICACION", "mensaje": "Falta el tipo o el número de identificación"}
  ]
}
```

**Errores específicos /validar/**
- `404 Not Found` — corte no encontrado
- `409 Conflict` — corte no está en BORRADOR; o tiene errores correctivos

**POST /registrar-envio/**

Cuerpo opcional:
```json
{"fecha_envio": "2026-10-01"}
```

`fecha_envio` no puede ser futura. Si no se envía, se usa la fecha de hoy. El archivo se carga a mano en el portal de TransUnion; no hay integración automática.

Respuesta `200`: resumen del corte con `"estado": "ENVIADO"`.

**Errores específicos /registrar-envio/**
- `400 Bad Request` — `fecha_envio` futura
- `404 Not Found` — corte no encontrado
- `409 Conflict` — corte no está en VALIDADO

### Historial de reportes enviados (RF6)

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/historial/reportes/` | ANALISTA_CARTERA, ADMINISTRADOR | Lista cortes enviados; filtros opcionales `?desde=` y `?hasta=` (fecha en AAAA-MM-DD) |
| GET | `/api/historial/reportes/{id}/detalle/` | ANALISTA_CARTERA, ADMINISTRADOR | Detalle de obligaciones de un reporte enviado con paginación |

**Respuesta 200 — Lista de reportes**

```json
[
  {
    "id": 1,
    "fecha_corte": "2026-09-30",
    "fecha_envio": "2026-10-01",
    "total_registros": 150,
    "saldo_consolidado": 45000000,
    "grupo": "Grupo A",
    "observacion": null
  }
]
```

`grupo` es el nombre del grupo usado en el corte, o `null` si no se usó grupo.

**Parámetros de paginación en `/detalle/`**

| Parámetro | Tipo | Defecto |
|---|---|---|
| `limite` | entero | 20 |
| `desplazamiento` | entero | 0 |

**Respuesta 200 — Detalle de reporte**

```json
{
  "total": 150,
  "resultados": [
    {
      "numero_obligacion": "OBL0001",
      "nombre_titular": "JUAN PÉREZ",
      "numero_identificacion": "12345678",
      "tipo_id_tu": "CC",
      "tipo_cartera": 2,
      "estado_tu": "01",
      "edad_mora": "00",
      "fecha_inicio": "2025-01-01",
      "cuotas_mora": 0,
      "valor_inicial": 500000,
      "valor_mora": 0,
      "valor_saldo": 500000,
      "valor_cuota": 50000,
      "dias_mora": 0,
      "origen_dias_mora": "SIN_MORA",
      "n_creditos": 1,
      "fecha_ultimo_pago": null
    }
  ]
}
```

**Errores específicos**
- `400 Bad Request` — fechas `desde`/`hasta` con formato inválido
- `404 Not Found` — corte no encontrado o no está en estado ENVIADO (detalle)

### Historial de deudores (RF8)

| Método | URL | Rol requerido | Descripción |
|---|---|---|---|
| GET | `/api/historial/deudores/` | ANALISTA_CARTERA, ADMINISTRADOR | Busca obligaciones; requiere `?cliente_id=` y/o `?numero_obligacion=`; máximo 50 resultados |
| GET | `/api/historial/deudores/{id}/` | ANALISTA_CARTERA, ADMINISTRADOR | Línea de tiempo de una obligación |

**Respuesta 200 — Lista de deudores**

```json
[
  {
    "obligacion_id": 1,
    "numero_obligacion": "OBL0001",
    "cliente_id": 900001,
    "numero_proceso": 1001,
    "fecha_inicio": "2025-01-01",
    "ultimo_estado_tu": "01",
    "ultimo_valor_saldo": 500000
  }
]
```

`ultimo_estado_tu` y `ultimo_valor_saldo` son `null` si la obligación no tiene reportes aún.

**Respuesta 200 — Línea de tiempo**

```json
[
  {
    "fecha_corte": "2026-09-30",
    "estado_tu": "01",
    "edad_mora": "00",
    "dias_mora": 0,
    "cuotas_mora": 0,
    "valor_mora": 0,
    "valor_saldo": 500000,
    "estado_corte": "ENVIADO"
  }
]
```

Incluye todos los cortes no anulados en los que aparece la obligación, ordenados por fecha de corte.

**Errores específicos**
- `400 Bad Request` — ningún parámetro de búsqueda proporcionado; `cliente_id` no es entero
- `404 Not Found` — obligación no encontrada (línea de tiempo)

### Procesos programados

| Comando | Descripción |
|---|---|
| `actualizar_estados_mensual` | Genera el corte mensual de cartera (RF9) |

**Argumentos**

| Argumento | Tipo | Defecto | Descripción |
|---|---|---|---|
| `--fecha-corte` | YYYY-MM-DD | Último día del mes anterior | Fecha del corte a generar |
| `--grupo` | entero | (ninguno) | ID del grupo de conceptos; sin él se usan todos los conceptos reportables |
| `--simular` | flag | false | Ejecuta la lógica completa dentro de una transacción y la revierte |

**Salida stdout (ejemplo)**

```
Fecha de corte : 2026-09-30
Grupo          : todos los conceptos reportables
Modo           : REAL
Obligaciones     : 150
Saldo consolidado: 45000000
Estado           : BORRADOR
Corte 7 generado correctamente.
```

**NV_BITACORA**: ACCION=`ACTUALIZACION_MENSUAL`, ENTIDAD=`NV_CORTE`, ENTIDAD_ID=id del corte, DETALLE con obligaciones/saldo/grupo. No se registra en modo `--simular`.

**Código de salida**: `0` en éxito; `1` en cualquier error (fecha inválida, grupo inexistente, conflicto de estado, etc.).

**Cron (Linux)**

```
# Día 1 de cada mes a las 02:00
0 2 1 * * /ruta/venv/bin/python /ruta/proyecto/manage.py actualizar_estados_mensual >> /var/log/nexovolt.log 2>&1
```

**Render Cron Job**

```
Command : python manage.py actualizar_estados_mensual
Schedule: 0 2 1 * *
```
