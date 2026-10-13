# NexoVolt API — Referencia para el frontend

## Información general

| Campo | Valor |
|---|---|
| URL base | `/api/` |
| Formato | JSON |
| Autenticación | Sesión por cookie de Django (`sessionid`) y token CSRF (RF25, RF26) |
| Roles disponibles | `ANALISTA_CARTERA`, `ADMINISTRADOR` |

## Autenticación

La sesión viaja en la cookie `sessionid` (HttpOnly, `SameSite=Lax`, `Secure` fuera de desarrollo). No hay tokens ni cabeceras de autorización.

- **CSRF.** Todo `POST`, `PATCH`, `PUT` o `DELETE` debe enviar la cabecera `X-CSRFToken` con el valor de la cookie `csrftoken`, que entrega `GET /api/auth/csrf/`. Si falta o no coincide: `403` con `code: "csrf_failed"`.
- **Inactividad (RF26).** La sesión vence a los 10 minutos sin peticiones (`DJANGO_SESSION_MINUTES`). Cada petición la renueva. Al vencer, cualquier endpoint responde `401`.
- **Sin sesión.** `401` con `{"detail": "Tu sesión venció. Inicia sesión de nuevo.", "code": "not_authenticated"}`.
- **Roles (RF27).** Un rol sin permiso recibe `403` con `{"detail": "No tienes permiso para realizar esta acción.", "code": "permission_denied"}`.
- **Contraseña temporal.** Mientras `must_change_password` sea `true`, todo `/api/` fuera de `/api/auth/` y `/api/salud/` responde `403` con `code: "password_change_required"`.
- **Usuario desactivado.** Pierde la sesión abierta en la siguiente petición (`401`).
- **Contraseñas.** Se guardan con hash Argon2. Reglas: mínimo 8 caracteres, al menos una mayúscula y al menos un número; no puede ser una contraseña común ni parecerse al correo o al nombre.

El primer Administrador se crea con `python manage.py createsuperuser` (pide correo, nombre y contraseña).

## Formato de errores

Error simple (`code` es opcional e identifica el error de forma estable):

```json
{"detail": "Mensaje de error.", "code": "permission_denied"}
```

Error con lista (solo `/validar/`):

```json
{"detail": "El corte tiene errores correctivos que deben resolverse.", "errores": [{"regla": "SIN_IDENTIFICACION", "mensaje": "Falta el tipo o el número de identificación"}]}
```

Error de validación de campo (DRF estándar):

```json
{"campo": ["Este campo es requerido."]}
```

## Pendiente / Provisional

- Las reglas de negocio sobre reemplazo de BORRADOR y conflictos de estado (`409`) están marcadas como **pendiente de decisión del equipo** en todos los endpoints de extracción.
- `ejecutada_por` sigue en `null`: `NV_CORTE` y `NV_BITACORA` están ligadas a la tabla anterior `NV_USUARIO`, que aún no se une con `USUARIOS_USUARIO`.
- No hay paginación automática en el listado de cortes (sin límite). El endpoint de deudores acepta `limite` y `desplazamiento` (defecto 20/0, máximo 100).

---

## Endpoints

### Utilidades

#### GET /api/salud/

Verifica disponibilidad del servidor. No requiere autenticación.

**Respuesta 200**

```json
{"estado": "ok"}
```

---

### Autenticación (RF25, RF26)

El objeto `user` es `{"id", "nombre", "email", "rol", "is_active", "last_login", "must_change_password"}`. `last_login` es fecha y hora ISO 8601 con zona, o `null`.

#### GET /api/auth/csrf/

Entrega la cookie `csrftoken`. No requiere autenticación.

**Respuesta 204**: sin cuerpo.

#### POST /api/auth/login/

Abre la sesión. No requiere autenticación, pero sí la cabecera `X-CSRFToken`. El correo no distingue mayúsculas.

**Cuerpo**

```json
{"email": "jperez@example.com", "password": "..."}
```

**Respuesta 200**

```json
{
  "user": {
    "id": 2,
    "nombre": "Juan Pérez",
    "email": "jperez@example.com",
    "rol": "ANALISTA_CARTERA",
    "is_active": true,
    "last_login": "2026-10-12T21:00:00-05:00",
    "must_change_password": false
  }
}
```

**Errores**

- `400 Bad Request` — falta un campo o el correo no tiene formato válido (error por campo)
- `401 Unauthorized` — `{"detail": "Correo o contraseña incorrectos.", "code": "authentication_failed"}`; la respuesta es la misma si el correo no existe
- `403 Forbidden` — `{"detail": "Tu usuario está desactivado. Contacta al administrador.", "code": "user_inactive"}`, solo si la contraseña es correcta
- `403 Forbidden` — `code: "csrf_failed"`
- `429 Too Many Requests` — `{"detail": "Demasiados intentos. Intenta de nuevo en unos minutos.", "code": "throttled"}`; el límite es de 10 intentos por minuto por dirección IP (`DJANGO_LOGIN_RATE`)

#### POST /api/auth/logout/

Cierra la sesión y la elimina del servidor.

**Rol requerido**: cualquier usuario con sesión

**Respuesta 204**: sin cuerpo.

**Errores**

- `401 Unauthorized` — sin sesión

#### GET /api/auth/me/

Devuelve el usuario de la sesión. También renueva la sesión.

**Rol requerido**: cualquier usuario con sesión

**Respuesta 200**: `{"user": {...}}`, igual que el login.

**Errores**

- `401 Unauthorized` — sin sesión o sesión vencida

#### POST /api/auth/change-password/

Cambia la contraseña propia y pone `must_change_password` en `false`. La sesión actual sigue abierta; las demás sesiones del usuario se cierran.

**Rol requerido**: cualquier usuario con sesión

**Cuerpo**

```json
{"current_password": "...", "new_password": "..."}
```

**Respuesta 204**: sin cuerpo.

**Errores**

- `400 Bad Request` — `{"current_password": ["La contraseña actual no es correcta."]}`
- `400 Bad Request` — `{"new_password": ["La contraseña debe tener al menos una mayúscula."]}` (un mensaje por cada regla incumplida; también si es igual a la actual)
- `401 Unauthorized` — sin sesión

---

### Conceptos de energía

#### GET /api/conceptos/

Lista conceptos de energía. Filtro opcional: `?activo=true|false`.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**

```json
[{"codigo": 1, "descripcion": "Energía activa", "activo": true, "observacion": null}]
```

#### POST /api/conceptos/

Crea un concepto.

**Rol requerido**: `ADMINISTRADOR`

**Cuerpo**

```json
{"codigo": 1, "descripcion": "Energía activa", "activo": true, "observacion": "Opcional"}
```

`activo` es opcional (defecto `true`). `observacion` es opcional.

**Respuesta 201**

```json
{"codigo": 1, "descripcion": "Energía activa", "activo": true, "observacion": null}
```

**Errores**

- `409 Conflict` — el código ya existe

#### PATCH /api/conceptos/{codigo}/

Actualiza `descripcion`, `observacion` y/o `activo`. Todos los campos son opcionales.

**Rol requerido**: `ADMINISTRADOR`

**Cuerpo**

```json
{"descripcion": "Nuevo nombre", "activo": false, "observacion": "Nueva obs"}
```

**Respuesta 200**

```json
{"codigo": 1, "descripcion": "Nuevo nombre", "activo": false, "observacion": "Nueva obs"}
```

**Errores**

- `404 Not Found` — código no encontrado

---

### Grupos de conceptos de energía

#### GET /api/grupos-conceptos/

Lista todos los grupos con sus conceptos.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**

```json
[
  {
    "id": 1,
    "nombre": "Grupo A",
    "activo": true,
    "conceptos": [{"codigo": 30, "descripcion": "Energía activa"}],
    "creado": "2026-10-10"
  }
]
```

#### GET /api/grupos-conceptos/{id}/

Detalle de un grupo.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**: igual que un elemento del listado.

**Errores**

- `404 Not Found` — grupo no encontrado

#### POST /api/grupos-conceptos/

Crea un grupo.

**Rol requerido**: `ADMINISTRADOR`

**Cuerpo**

```json
{"nombre": "Grupo A", "conceptos": [30, 61]}
```

**Respuesta 201**: igual que GET detalle.

**Errores**

- `400 Bad Request` — concepto inexistente o sin `REPORTABLE='S'`
- `409 Conflict` — nombre de grupo duplicado

#### PATCH /api/grupos-conceptos/{id}/

Actualiza nombre, activo y/o lista de conceptos. `conceptos` reemplaza la lista completa.

**Rol requerido**: `ADMINISTRADOR`

**Cuerpo** (todos los campos son opcionales)

```json
{"nombre": "Nuevo nombre", "activo": false, "conceptos": [30]}
```

**Respuesta 200**: igual que GET detalle.

**Errores**

- `400 Bad Request` — concepto inexistente o sin `REPORTABLE='S'`
- `404 Not Found` — grupo no encontrado
- `409 Conflict` — nombre de grupo duplicado

#### DELETE /api/grupos-conceptos/{id}/

Elimina el grupo.

**Rol requerido**: `ADMINISTRADOR`

**Respuesta 204**: sin cuerpo.

**Errores**

- `404 Not Found` — grupo no encontrado
- `409 Conflict` — hay un corte en BORRADOR que usa este grupo

---

### Extracción de cartera (RF44)

#### POST /api/extracciones/

Genera un corte de cartera.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Cuerpo**

```json
{"fecha_corte": "2026-09-30", "grupo_id": 1}
```

`grupo_id` es opcional. Sin él se usan todos los conceptos con `REPORTABLE='S'`.

**Respuesta 201**

```json
{
  "id": 1,
  "fecha_corte": "2026-09-30",
  "fecha_ejecucion": "2026-10-10T12:00:00-05:00",
  "grupo": {"id": 1, "nombre": "Grupo A"},
  "obligaciones": 150,
  "saldo_consolidado": 45000000,
  "estado": "BORRADOR",
  "ejecutada_por": null
}
```

`grupo` es `null` cuando no se usó grupo.

**Errores**

- `400 Bad Request` — `fecha_corte` ausente o futura
- `404 Not Found` — grupo no encontrado
- `409 Conflict` — grupo inactivo; corte con esa fecha en estado distinto de BORRADOR; ya existe un BORRADOR con distinta fecha (mensaje incluye `DELETE /api/extracciones/{id}/` para eliminarlo); `fecha_corte` no es posterior a la del último corte enviado

#### GET /api/extracciones/

Lista todos los cortes (excluye ANULADO), del más reciente al más antiguo.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**: lista de objetos con la misma estructura que POST 201.

#### GET /api/extracciones/ultima/

Devuelve el corte más reciente (excluye ANULADO).

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**: objeto con la misma estructura que POST 201.

**Respuesta 204**: sin cuerpo si no hay ningún corte.

#### GET /api/extracciones/{id}/

Detalle de un corte.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**: objeto con la misma estructura que POST 201.

**Errores**

- `404 Not Found` — corte no encontrado

#### DELETE /api/extracciones/{id}/

Elimina un corte en estado BORRADOR. Borra en cascada sus obligaciones e inconsistencias y registra la eliminación en `NV_BITACORA`.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 204**: sin cuerpo.

**Errores**

- `404 Not Found` — corte no encontrado
- `409 Conflict` — `{"detail": "Solo se puede eliminar un corte en estado BORRADOR."}`

#### GET /api/extracciones/{id}/obligaciones/

Obligaciones del corte con paginación.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Parámetros query**

| Parámetro | Tipo | Defecto | Descripción |
|---|---|---|---|
| `limite` | entero | 20 | Máximo de filas a devolver |
| `desplazamiento` | entero | 0 | Cuántas filas saltarse |

**Respuesta 200**

```json
{
  "total": 150,
  "resultados": [
    {
      "numero_obligacion": "OBL0001",
      "nombre_titular": "JUAN PÉREZ",
      "numero_identificacion": "******5678",
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

Nota: `numero_identificacion` se devuelve enmascarado (últimos 4 dígitos visibles, prefijados con `******`). Identificaciones con menos de 4 dígitos se muestran como asteriscos completos.

**Errores**

- `400 Bad Request` — `limite` o `desplazamiento` no son enteros
- `404 Not Found` — corte no encontrado

---

### Ciclo de corte

#### POST /api/extracciones/{id}/validar/

Valida el corte en BORRADOR y lo pasa a VALIDADO. No requiere cuerpo.

Si hay filas con `SEVERIDAD='CORRECTIVA'` en `V_VALIDACION_CORTE`, responde `409` sin cambiar el estado. Si no hay errores correctivos, cambia el estado a `VALIDADO` y devuelve el corte con advertencias informativas.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**

```json
{
  "id": 1,
  "fecha_corte": "2026-09-30",
  "fecha_ejecucion": "2026-10-10T12:00:00-05:00",
  "grupo": null,
  "obligaciones": 150,
  "saldo_consolidado": 45000000,
  "estado": "VALIDADO",
  "ejecutada_por": null,
  "advertencias": [
    {"regla": "SIN_FECHA_LIMITE_PAGO", "mensaje": "No se encontró una factura con fecha de vencimiento."}
  ]
}
```

`advertencias` puede ser lista vacía `[]`.

**Respuesta 409 con errores correctivos**

```json
{
  "detail": "El corte tiene errores correctivos que deben resolverse.",
  "errores": [{"regla": "SIN_IDENTIFICACION", "mensaje": "Falta el tipo o el número de identificación"}]
}
```

**Errores**

- `404 Not Found` — corte no encontrado
- `409 Conflict` — corte no está en BORRADOR; o tiene errores correctivos

#### POST /api/extracciones/{id}/registrar-envio/

Registra el envío a TransUnion y pasa el corte a ENVIADO. El archivo se carga manualmente en el portal de TransUnion.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Cuerpo** (opcional)

```json
{"fecha_envio": "2026-10-01"}
```

`fecha_envio` no puede ser futura ni anterior a `fecha_corte`. Si no se envía, se usa la fecha de hoy. La existencia del corte se verifica antes de aplicar cualquier validación de fecha.

**Respuesta 200**: objeto con la misma estructura que POST /extracciones/ con `"estado": "ENVIADO"`. No incluye lista `errores`.

**Errores**

- `400 Bad Request` — `fecha_envio` futura; o `fecha_envio` anterior a `fecha_corte`
- `404 Not Found` — corte no encontrado
- `409 Conflict` — corte no está en VALIDADO

---

### Historial de reportes enviados (RF6)

#### GET /api/historial/reportes/

Lista cortes en estado ENVIADO. Filtros opcionales: `?desde=AAAA-MM-DD` y `?hasta=AAAA-MM-DD` (filtran por `fecha_envio`).

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**

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

`grupo` es el nombre del grupo o `null` si no se usó grupo.

**Errores**

- `400 Bad Request` — `desde` o `hasta` con formato inválido

#### GET /api/historial/reportes/{id}/detalle/

Detalle de obligaciones de un reporte enviado con paginación.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Parámetros query**

| Parámetro | Tipo | Defecto |
|---|---|---|
| `limite` | entero | 20 |
| `desplazamiento` | entero | 0 |

**Respuesta 200**

```json
{
  "total": 150,
  "resultados": [
    {
      "numero_obligacion": "OBL0001",
      "nombre_titular": "JUAN PÉREZ",
      "numero_identificacion": "******5678",
      "tipo_id_tu": "01",
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

Notas de campo: `tipo_id_tu` código de 2 caracteres (Tabla 4a SSR, e.g. `"01"`). `estado_tu` código de 2 caracteres (Tabla 4b SSR, e.g. `"01"`). `edad_mora` código de 2 caracteres `"00"`–`"14"` (Tabla SSR). `valor_mora` y `valor_saldo` pueden ser `null`. `numero_identificacion` se devuelve enmascarado (últimos 4 dígitos visibles, prefijados con `******`).

**Errores**

- `404 Not Found` — reporte no encontrado o no está en estado ENVIADO

---

### Historial de deudores (RF8)

#### GET /api/historial/deudores/

Busca obligaciones con paginación. Requiere al menos uno de: `?cliente_id=` o `?numero_obligacion=`.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Parámetros query**

| Parámetro | Tipo | Defecto | Descripción |
|---|---|---|---|
| `cliente_id` | entero | | ID del cliente |
| `numero_obligacion` | texto | | Número de obligación TU |
| `limite` | entero | 20 | Máximo de filas (tope 100) |
| `desplazamiento` | entero | 0 | Filas a saltarse |

**Respuesta 200**

```json
{
  "total": 1,
  "resultados": [
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
}
```

`ultimo_estado_tu` y `ultimo_valor_saldo` son `null` si la obligación no tiene reportes aún (excluye cortes ANULADO).

**Errores**

- `400 Bad Request` — ningún parámetro proporcionado; `cliente_id` no es entero; `limite`/`desplazamiento` inválidos

#### GET /api/historial/deudores/{id}/

Línea de tiempo de una obligación: todos los cortes no anulados en los que aparece, ordenados por fecha de corte.

**Rol requerido**: `ANALISTA_CARTERA`, `ADMINISTRADOR`

**Respuesta 200**

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

**Errores**

- `404 Not Found` — obligación no encontrada

---

### Procesos programados (RF9)

No es un endpoint HTTP; es un comando de gestión de Django.

**Comando**

```
python manage.py actualizar_estados_mensual
```

**Argumentos**

| Argumento | Tipo | Defecto | Descripción |
|---|---|---|---|
| `--fecha-corte` | YYYY-MM-DD | Último día del mes anterior | Fecha del corte a generar |
| `--grupo` | entero | (ninguno) | ID del grupo de conceptos; sin él se usan todos los conceptos reportables |
| `--simular` | flag | false | Ejecuta la lógica dentro de una transacción y la revierte al final |

**Salida stdout**

```
Fecha de corte : 2026-09-30
Grupo          : todos los conceptos reportables
Modo           : REAL
Obligaciones     : 150
Saldo consolidado: 45000000
Estado           : BORRADOR
Corte 7 generado correctamente.
```

En modo `--simular` la línea de modo dice `SIMULACIÓN` y no se registra en `NV_BITACORA`.

**Código de salida**: `0` en éxito; `1` en cualquier error.

**Cron (Render)**

```
Command : python manage.py actualizar_estados_mensual
Schedule: 0 2 1 * *
```
