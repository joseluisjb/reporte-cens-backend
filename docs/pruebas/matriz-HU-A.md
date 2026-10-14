# Matriz de casos de prueba — HU-A (extracción, consolidación y trazabilidad)

**Iteración 1 · NexoVolt · Responsable: Santiago (Líder de QA, ficha 5.7) · Ejecuta: Santiago y Omar (fila 47)**

Cada caso sale de un criterio de aceptación del documento *Asignación de RF, Iteración 1* (sección 2) y
cubre los RF que ese criterio nombra. Los datos son **ficticios**: ningún dato de CENS aparece aquí.

La matriz de HU-D vive en el repositorio del frontend: `docs/pruebas/matriz-HU-D.md`.

## Cómo leer la matriz

| Columna | Qué significa |
|---|---|
| **ID** | `CP-A-nn`. Se cita igual en la evidencia, en los defectos, en el acta y en el FP-15 |
| **Tipo** | Positivo (camino feliz), Negativo (flujo alterno del RF) o Frontera (valor límite) |
| **Dónde** | `API` = backend · `UI` = frontend · `CMD` = comando de gestión · `SQL` = Oracle |
| **Estado** | `Listo` se puede ejecutar hoy · `Bloqueado` falta algo, con la causa escrita |

## Criterios de aceptación de HU-A (textuales del documento)

| # | Criterio | RF | Casos |
|---|---|---|---|
| CA-A1 | Se extraen solo deudores con financiación vigente, aislando exclusivamente conceptos de energía | RF1, RF2 | CP-A-01 a CP-A-08 |
| CA-A2 | Los abonos parciales se identifican y consolidan correctamente en un saldo neto único por deudor | RF3, RF4 | CP-A-09 a CP-A-14 |
| CA-A3 | Los distintos ID de crédito de un proceso se agrupan bajo un número único de obligación | RF5 | CP-A-15 a CP-A-17 |
| CA-A4 | Se mantiene historial de reportes y de deudores, actualizado mensualmente | RF6, RF8, RF9 | CP-A-18 a CP-A-25 |
| CA-A5 | La mora se calcula y codifica según los tramos de la Tabla 9 | RF7 | CP-A-26 a CP-A-30 |
| CA-A6 | Se puede agregar, editar y desactivar códigos desde la configuración | RF35 | CP-A-31 a CP-A-38 |

## Datos ficticios de referencia

| Dato | Valor | Para qué |
|---|---|---|
| Conceptos reportables | `30` CUOTA FINANCIACION ENERGIA · `94` INTERES FINANCIACION ENERGIA | Conceptos de energía activos |
| Concepto no reportable | `9002` CONCEPTO DE PRUEBA INACTIVO | Debe quedar fuera del corte |
| Grupo activo | `1` Energía financiada (conceptos 30 y 94) | Extracción por grupo |
| Grupo inactivo | `3` Grupo de prueba inactivo | Caso negativo |
| Proceso con varios créditos | `22574156` con 3 ID de crédito | RF5 y regla de abonos |
| Fecha de corte vigente | `2026-09-30` | Corte del mes |
| Fecha de corte ya enviada | `2026-08-31` | Conflicto de corte anterior |

---

## CA-A1 · Extracción de vigentes y aislamiento de energía (RF1, RF2)

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-01 | Positivo | RF1 | API | Conexión Oracle activa; grupo 1 activo | `POST /api/extracciones/` con `fecha_corte=2026-09-30` y `grupo_id=1` | `201`; corte en estado `BORRADOR`, con número de obligaciones y saldo consolidado | Listo |
| CP-A-02 | Positivo | RF1 | API | Existe el corte de CP-A-01 | `GET /api/extracciones/{id}/obligaciones/` | Solo obligaciones vigentes con saldo mayor que cero | Listo |
| CP-A-03 | Positivo | RF2 | API | Conceptos 30 y 94 activos; 9002 inactivo | Ejecutar la extracción y revisar el saldo consolidado | El saldo suma únicamente los conceptos 30 y 94; el 9002 no aporta | Listo |
| CP-A-04 | Negativo | RF2 | API | Existe un concepto facturado que no está en la tabla de parámetros | Ejecutar la extracción | El concepto se excluye por defecto, sin error y sin detener el proceso | Listo |
| CP-A-05 | Negativo | RF1 | API | Credenciales de Oracle inválidas o VPN caída | `POST /api/extracciones/` | El proceso se detiene y responde un mensaje de error **en español**; no queda un corte a medias | Listo |
| CP-A-06 | Frontera | RF1 | API | Fecha de corte sin ningún deudor vigente | `POST /api/extracciones/` con esa fecha | Universo vacío notificado al Analista: `obligaciones = 0`. **No es un error** | Listo |
| CP-A-07 | Negativo | RF1 | API | — | `POST /api/extracciones/` con `fecha_corte` futura | `400` con mensaje claro en español | Listo |
| CP-A-08 | Negativo | RF1 | API | Grupo 3 inactivo; grupo 999 inexistente | `POST /api/extracciones/` con cada uno | Rechazo con mensaje en español: grupo inexistente y grupo inactivo se distinguen | Listo |

## CA-A2 · Abonos parciales y saldo neto único (RF3, RF4)

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-09 | Positivo | RF3 | SQL/API | Deudor con cuota de energía y un pago registrado | Ejecutar la extracción | El pago queda vinculado al concepto de cuota que amortiza | Listo |
| CP-A-10 | Positivo | RF4 | API | Deudor con dos conceptos de energía y un abono parcial | Consultar sus obligaciones del corte | **Una sola cifra neta** por deudor: suma de saldos menos pagos aplicados | Listo |
| CP-A-11 | Positivo | RF4 | API | Deudor sin ningún pago en el periodo | Consultar sus obligaciones | Saldo neto igual a la suma de los saldos de energía | Listo |
| CP-A-12 | Frontera | RF4 | API | Abono exactamente igual al saldo total | Consultar sus obligaciones | Saldo neto en cero, nunca negativo | Listo |
| CP-A-13 | Negativo | RF3 | SQL | Pago que no se puede asociar a un concepto | Ejecutar la extracción | Se marca como **pendiente de clasificación**; no se resta del saldo | Listo |
| CP-A-14 | Frontera | RF4 | SQL | Abono parcial que cubre unos conceptos y otros no (proceso 22574156) | Aplicar la regla de distribución | **Bloqueado:** la regla de aplicación de abonos está pendiente de confirmar con la contacto funcional de CENS | Bloqueado |

## CA-A3 · Número único de obligación (RF5)

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-15 | Positivo | RF5 | API | Proceso 22574156 con 3 ID de crédito (energía, mora, reconexión) | Consultar las obligaciones del corte | **Una sola fila** con un único número de obligación que agrupa los tres | Listo |
| CP-A-16 | Frontera | RF5 | API | El caso anterior | Revisar el `numero_obligacion` devuelto | Máximo 20 caracteres, solo caracteres permitidos por el manual, único y permanente entre cortes | Listo |
| CP-A-17 | Negativo | RF5 | SQL | Dos números de proceso distintos que parecen del mismo deudor | Ejecutar la extracción | **No se unen automáticamente**; se reportan como inconsistencia para revisión | Listo |

## CA-A4 · Historial de reportes y de deudores (RF6, RF8, RF9)

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-18 | Positivo | RF6 | API | Corte validado sin errores correctivos | `POST /api/extracciones/{id}/registrar-envio/` | El corte queda `ENVIADO` con su fecha de envío | Listo |
| CP-A-19 | Positivo | RF6 | API | El envío de CP-A-18 | `GET /api/historial/reportes/` | El envío aparece con fecha, estado y valores reportados | Listo |
| CP-A-20 | Positivo | RF6 | API | El envío de CP-A-18 | `GET /api/historial/reportes/{id}/detalle/?limite=20&desplazamiento=0` | Detalle paginado con la forma `{ total, resultados }` | Listo |
| CP-A-21 | Positivo | RF8 | API | Deudor presente en dos cortes consecutivos | `GET /api/historial/deudores/{id}/` | Se conservan los estados anteriores: la línea de tiempo no pierde registros | Listo |
| CP-A-22 | Positivo | RF9 | CMD | Existe el corte del mes anterior | `python manage.py actualizar_estados_mensual --fecha-corte 2026-09-30` | Recalcula el estado, genera el corte y deja registro en bitácora | Listo |
| CP-A-23 | Negativo | RF9 | CMD | La misma precondición | Ejecutar el comando con `--simular` | Muestra el resultado y **revierte**: no se guarda ningún cambio | Listo |
| CP-A-24 | Negativo | RF6 | API | Ya existe un corte enviado con fecha 2026-08-31 | `POST /api/extracciones/` con una fecha anterior o igual | Rechazo por conflicto: la fecha de corte debe ser posterior al último corte enviado | Listo |
| CP-A-25 | Negativo | RF6 | API | Envío rechazado por TransUnion | Registrar el intento fallido y su motivo | **Bloqueado:** el ciclo del contrato termina en `ENVIADO`; no existe el registro de intento fallido que pide el flujo alterno de RF6 | Bloqueado |

## CA-A5 · Cálculo y codificación de la mora (RF7)

> **Criterio bloqueado por completo.** La codificación de la Tabla 9 no está implementada: la vista
> `V_DEUDOR_VIGENTE` no calcula días de mora y `edad_mora` se lee como una columna ya codificada.
> Además, el documento de asignación solo define los tramos **00 a 04**, mientras el contrato de la API
> exige los **15 códigos** de la Tabla 9. Hay que cerrar la decisión *"Tabla 9 completa, verificada en el
> manual de TransUnion v34"* antes de ejecutar estos casos.

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-26 | Positivo | RF7 | SQL | Deudor sin facturas vencidas | Calcular la edad de mora al corte | Código `00` (Normal) y valor de mora en cero | Bloqueado |
| CP-A-27 | Frontera | RF7 | SQL | Fecha límite de pago a 29 y a 30 días del corte | Calcular la edad de mora en ambos | 29 días da `00`; 30 días da `01` | Bloqueado |
| CP-A-28 | Frontera | RF7 | SQL | 59 y 60 días | Calcular la edad de mora en ambos | 59 da `01`; 60 da `02` | Bloqueado |
| CP-A-29 | Frontera | RF7 | SQL | 89 y 90 días; 119 y 120 días; 149 y 150 días | Calcular la edad de mora en cada par | 89 da `02` y 90 da `03`; 119 da `03` y 120 da `04`; 149 da `04` y 150 da el tramo siguiente | Bloqueado |
| CP-A-30 | Frontera | RF7 | SQL | Mora superior a 149 días | Calcular la edad de mora | El código del tramo correspondiente de la Tabla 9 completa | Bloqueado |

## CA-A6 · Parametrización de códigos de energía (RF35)

| ID | Tipo | RF | Dónde | Precondición | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|---|---|---|
| CP-A-31 | Positivo | RF35 | API | Sesión de Administrador | `POST /api/conceptos/` con código `9100` y descripción `CONCEPTO FICTICIO` | `201`; el concepto queda activo y aparece en el listado | Listo |
| CP-A-32 | Positivo | RF35 | API | Existe el concepto 9100 | `PATCH /api/conceptos/9100/` cambiando la descripción | `200` con la descripción nueva | Listo |
| CP-A-33 | Positivo | RF35 | API | Existe el concepto 9100 activo | `PATCH /api/conceptos/9100/` con `activo=false` | `200`; el concepto queda inactivo | Listo |
| CP-A-34 | Positivo | RF35 | API | CP-A-33 ejecutado; el concepto pertenecía a un grupo usado en la extracción | Ejecutar un corte nuevo | **El corte ya no incluye ese concepto, sin tocar una línea de código.** Es el corazón del criterio | Listo |
| CP-A-35 | Negativo | RF35 | API | Existe el concepto 30 | `POST /api/conceptos/` con código `30` | Rechazo por código duplicado, con mensaje en español | Listo |
| CP-A-36 | Negativo | RF35, RF31 | API | Sesión de Administrador | `POST /api/conceptos/` sin descripción | `400` indicando el campo que falta, **en español** | Listo |
| CP-A-37 | Negativo | RF35, RF27 | API | Sesión de Analista de Cartera | `POST /api/conceptos/` | `403`: la parametrización es solo del Administrador | Listo |
| CP-A-38 | Positivo | RF35 | UI | Sesión de Administrador en la pantalla de Parametrización | Agregar, editar y desactivar un concepto desde la pantalla | La tabla refleja los tres cambios, con textos en español | Listo |

## Cobertura y bloqueos

| Criterio | Casos | Listos | Bloqueados |
|---|---|---|---|
| CA-A1 | 8 | 8 | 0 |
| CA-A2 | 6 | 5 | 1 |
| CA-A3 | 3 | 3 | 0 |
| CA-A4 | 8 | 7 | 1 |
| CA-A5 | 5 | 0 | **5** |
| CA-A6 | 8 | 8 | 0 |
| **Total** | **38** | **31** | **7** |

| Bloqueo | Casos | Quién lo desbloquea |
|---|---|---|
| Regla de aplicación de abonos sin confirmar con CENS | CP-A-14 | Clara · contacto funcional de CENS |
| RF6 no registra envíos fallidos ni su motivo | CP-A-25 | José Luis |
| Tabla 9 incompleta y sin implementar (RF7) | CP-A-26 a CP-A-30 | Clara (PL/SQL) · José Luis (revisión) · decisión con Santiago |

> **Rama de referencia: `dev`.** Esta matriz describe el backend de `dev`, que va adelante de
> `main` e incluye RF25, RF26 y RF27 (sesión, roles y Argon2). Por eso CP-A-37 ya se puede
> ejecutar: existe la sesión de Analista con la que comprobar el 403.

## Qué está automatizado

Las pruebas de `tests/aceptacion/` cubren los casos marcados abajo. Se diferencian de las pruebas
unitarias de cada app en dónde simulan: las unitarias reemplazan la capa de servicios, estas
reemplazan solo la base de datos Oracle, así que la petición atraviesa la vista, el serializer y
el servicio reales.

| Archivo | Casos cubiertos | Pruebas |
|---|---|---|
| `test_hu_a_ca_a1_extraccion.py` | CP-A-01, CP-A-03, CP-A-06, CP-A-07, CP-A-08, CP-A-24 | 8 |
| `test_hu_a_ca_a4_ciclo_de_corte.py` | CP-A-18, CP-A-22, CP-A-23 | 8 |
| `test_hu_a_ca_a6_parametros.py` | CP-A-31 a CP-A-37 | 9 |
| | | **25** |

Pendientes de automatizar: CP-A-02, CP-A-04, CP-A-05 y CP-A-09 a CP-A-17, que dependen de la
capa SQL y del ambiente de pruebas (fila 46). CP-A-38 es de interfaz y va con Playwright.

## Trazabilidad RF a casos

| RF | Criterio | Casos |
|---|---|---|
| RF1 | CA-A1 | CP-A-01, CP-A-02, CP-A-05, CP-A-06, CP-A-07, CP-A-08 |
| RF2 | CA-A1 | CP-A-03, CP-A-04 |
| RF3 | CA-A2 | CP-A-09, CP-A-13 |
| RF4 | CA-A2 | CP-A-10, CP-A-11, CP-A-12, CP-A-14 |
| RF5 | CA-A3 | CP-A-15, CP-A-16, CP-A-17 |
| RF6 | CA-A4 | CP-A-18, CP-A-19, CP-A-20, CP-A-24, CP-A-25 |
| RF7 | CA-A5 | CP-A-26, CP-A-27, CP-A-28, CP-A-29, CP-A-30 |
| RF8 | CA-A4 | CP-A-21 |
| RF9 | CA-A4 | CP-A-22, CP-A-23 |
| RF35 | CA-A6 | CP-A-31 a CP-A-38 |
