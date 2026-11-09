# Plan maestro de pruebas — Iteración 2

**NexoVolt · HU-B (ciclo de vida y estados) y HU-C (reporte, reclamos y novedades) · Responsable: Santiago (Líder de QA) · Versión 1, 09/11/2026**

Este plan dice qué se prueba en la Iteración 2, quién lo prueba, con qué datos y cuándo un RF se da por aceptado. Los casos salen de los «Listo cuando» de cada ficha (`docs/instrucciones/Distribucion_RF_Iteracion2_resumen_RF_y_prompts_v2.md`) y de los RF corregidos (`docs/iteracion2/RF_ITERACION2.md`). Los datos son **ficticios**: ningún dato de CENS aparece aquí.

La Iteración 1 tiene sus propias matrices: `docs/pruebas/matriz-HU-A.md` (este repo) y `docs/pruebas/matriz-HU-D.md` (frontend). Aquí se usan como regresión.

## 1. Alcance

| Incluye | No incluye |
|---|---|
| HU-B: RF10 a RF19 y RF45 a RF49 (15 RF) | RF56 (oportunidad y caducidad del dato negativo): va con RF36 en la Iteración 3 |
| HU-C: RF20 a RF24, RF50 a RF55 y RF57 (12 RF) | La regla jurídica de RF10 sin comunicación previa (C-42, RF36) |
| RNF-06: cobertura de la Matriz de cambios de estado | El módulo de Actualización en Línea de TransUnion: **nunca se usa para pruebas**, porque escribe en la base real (RF24) |
| Regresión de HU-A y HU-D | Cargas reales a STRANSFER: el archivo se valida contra el Manual, no contra TransUnion |

Roles de los RF: **RF48 y RF57 son del Administrador**; los otros 25 son del Analista de Cartera. Todo caso de un RF incluye además la comprobación del rol contrario («Acceso restringido» en pantalla, 403 en la API).

## 2. Niveles de prueba

| Nivel | Qué cubre | Quién | Herramienta | Dónde corre |
|---|---|---|---|---|
| Pruebas del dueño | El código que cada uno entrega, con los casos de su ficha. Es parte de «listo» | Quien implementa | pytest · vitest | CI de cada PR |
| Backend y SQL independiente | Endpoints, servicios y vistas del RF, sin tocar el código de producción | Dilan o Santiago (tabla 9) | pytest con el cursor simulado + un `SELECT` por caso en Oracle de desarrollo | CI + Oracle de desarrollo |
| Frontend independiente | Cada pantalla contra el mockup v3 (textos, columnas, estados vacío, de carga y de error, rol) y contra el contrato | Omar o Santiago | vitest + MSW, recorrido E2E con Playwright | CI + backend de desarrollo |
| Aceptación funcional | Lo que ve y hace el usuario, de punta a punta, con los datos de prueba v2 | Santiago, Omar o Dilan | Ejecución manual con evidencia | Ambiente de desarrollo (backend + Oracle + frontend) |
| Cobertura de la Matriz (RNF-06) | Las 400 combinaciones de estado de origen y destino, con y sin mora | Santiago | `tests/test_matriz_estados.py` + `config/sql/verificacion_matriz_transiciones.sql` | CI + Oracle de desarrollo |
| Regresión | Que la Iteración 2 no rompa HU-A ni HU-D | Santiago | Suites completas (`pytest -q`, `npm test`) + casos de `matriz-HU-A.md` y `matriz-HU-D.md` | CI + desarrollo, antes de pasar `dev` a `main` |

**Regla de independencia.** Nadie prueba lo que implementó. Quien prueba no corrige: describe el defecto y lo devuelve a su dueño. Quien corrige un defecto no lo vuelve a probar.

## 3. Ambientes y datos

| Ambiente | Datos | Para qué |
|---|---|---|
| CI (GitHub Actions) | Cursor simulado y SQLite en memoria (backend); MSW con las 12 obligaciones del mockup v3 (frontend) | Pruebas automáticas de cada PR |
| Oracle de desarrollo | **Datos de prueba v2** (`03_datos_prueba_v2.sql`, Omar): escenarios E1 a E18 sobre clientes ficticios desde 900101, con un corte anterior `ENVIADO` | Pruebas SQL, de integración y de aceptación |
| Frontend con mocks | `VITE_USE_MOCKS=true` y las cuentas ficticias de la guía | Pruebas de pantalla mientras no esté el endpoint |

Los scripts SQL se aplican solo en el esquema de desarrollo, en orden (10, 11, 12, vistas 16 a 18, datos v2). Los errores `ORA-` no aparecen con el cursor simulado: todo RF con SQL se prueba también contra Oracle antes de aceptarlo.

### Escenarios de los datos de prueba v2

| N.º | Escenario | Resultado esperado | RF |
|---|---|---|---|
| E1 | Vigente al día | Estado 01, mora 0, edad 00 | RF10, RF11 |
| E2 | Vigente con una cuota vencida (23 días) | 01, edad 00 y mora mayor a cero | RF10, RF11, RF19 |
| E3 | Vigente con dos cuotas vencidas de $70.000 (47 días) | 01, edad 01, 2 cuotas en mora | RF11, RF17, RF19 |
| E4 | Abono parcial que paga la cuota más antigua | Mora y cuotas recalculadas; la edad solo baja si paga las más antiguas | RF17 |
| E5 | Pago total estando en 01 | 02 con fecha de pago, modo 01 y tipo 01 | RF12, RF22 |
| E6 | Crédito caducado (6 atrasos con tope de 4) y con mora | 03 | RF14 |
| E7 | Marca de castigo con mora | 06 | RF45 |
| E8 | En 03 que paga todo | 07 con fecha de pago | RF15, RF22 |
| E9 | En 03 que paga toda la mora y conserva saldo | Vuelve a 01 y reporta el pago de la mora | RF46, RF47 |
| E10 | Refinanciación (proceso nuevo con `PROCESO_REFINANCIACION`) | Original en 02 modo 16; nueva en 01 reestructurada | RF18 |
| E11 | Obligación nueva caducada pero sin mora | Entra en 01 (no en 03) y queda marcada para revisión | RF10, RF14 |
| E12 | Obligación cerrada en un corte anterior con movimiento nuevo | No se reporta; alerta | RF13, RF16 |
| E13 | Crédito con estado B del SAC (sin homologar) | Bloquea la obligación | RF48, RF53 |
| E14 | Cliente sin tipo o número de documento | Correctiva | RF53 |
| E15 | Proceso negativo de migración con cliente de 10 dígitos (número de más de 20 caracteres) | Correctiva de número de obligación | RF53 |
| E16 | Valores de $9.000 y de $120 millones | Advertencias informativas | RF51, RF53 |
| E17 | Más de 730 días de mora | Edad 14 y años en mora | RF11, RF49 |
| E18 | Obligación eliminada ante TransUnion | No se incluye en el corte | RF50, RF21 |

## 4. Criterios de entrada y de salida

**Para empezar la prueba independiente de un RF**

- El RF está fusionado en `dev` en las capas que se prueban (base de datos, backend o pantalla) y su CI está en verde.
- Para pruebas SQL y de aceptación: los scripts 10 a 12 y los datos de prueba v2 están aplicados en Oracle de desarrollo.
- El contrato del endpoint está en `docs/contrato/openapi.yaml` y es idéntico en los dos repos.

**Para dar un RF por aceptado**

- Todos sus casos de este plan ejecutados, con estado `Cumple`, y su evidencia (captura o consulta) registrada.
- Sin defectos DF de severidad alta o media abiertos. Los de severidad baja, los MJ y los UX pueden quedar abiertos con dueño y fecha.
- Lo que depende de CENS o TransUnion está parametrizado y marcado «por confirmar» (Anexo A de la distribución), no inventado. Un caso que depende de una respuesta pendiente se ejecuta con la opción «Mientras tanto» y se marca `Parcial`.
- Comprobado el rol contrario (pantalla y API).

**Para cerrar la iteración (pasar `dev` a `main`)**

- Los 27 RF aceptados o con su bloqueo aprobado por Santiago y José Luis.
- RNF-06: las 400 casillas de la Matriz probadas, con al menos 98 % de aciertos en `NV_TRANSICION_ESTADO`.
- Regresión de HU-A y HU-D sin fallas nuevas: `pytest -q` y `npm test` en verde, y los casos manuales de `matriz-HU-A.md` y `matriz-HU-D.md` vueltos a ejecutar.

## 5. Manejo de defectos

Se usan los mismos códigos de la Iteración 1:

| Código | Qué es | Ejemplo |
|---|---|---|
| `DF-nn` | Defecto: el sistema no cumple el RF, el contrato o el Manual | Una obligación en 04 con saldo cero se cierra en 02 en vez de dar 713 |
| `MJ-nn` | Mejora: cumple, pero se puede hacer mejor | Un mensaje de error correcto pero poco claro |
| `UX-nn` | Usabilidad o accesibilidad | Contraste insuficiente, foco que no va al campo con error |

Severidad: **alta** (dato errado hacia TransUnion, pérdida de datos, acceso indebido por rol), **media** (regla del RF incumplida sin efecto en el archivo), **baja** (texto, formato).

Cada defecto se reporta así: código, RF y caso (`CP-B-nn`/`CP-C-nn`), entrada, pasos, resultado esperado, resultado obtenido, severidad, evidencia y dueño. Va como *issue* en el repo que corresponde, con el código en el título, y se anota en el FP-15. El dueño lo corrige en una rama `fix/...`; otra persona lo vuelve a probar.

## 6. Cobertura de la Matriz (RNF-06)

La Matriz de la p. 40 tiene 400 casillas: 10 estados de origen × con o sin mora × 10 estados de destino × con o sin mora. Se prueba en dos partes:

1. **En el CI** (`tests/test_matriz_estados.py`, 16 pruebas): compara casilla por casilla la transcripción del Manual (`docs/iteracion2/MATRIZ_ESTADOS_SERVICIOS.md`) con la constante `MX` del mockup v3, comprueba que el ciclo lee bien las 400 (`ciclo.servicios._transicion_permitida`), que 02 y 07 no tienen salidas y las casillas que nombran las fichas (RF12, RF14, RF15, RF45, RF46). Resultado del 09/11/2026: **400 de 400 coinciden**.
2. **En Oracle de desarrollo** (`config/sql/verificacion_matriz_transiciones.sql`): compara `NV_TRANSICION_ESTADO` con las 400 casillas esperadas. La primera consulta da el resumen (coinciden, difieren, faltan, sobran y porcentaje de aciertos); la segunda lista cada casilla distinta para reportarla como DF. Se corre después del script 12. Hoy la tabla solo trae la regla «02 y 07 no aceptan cambios», así que el resultado esperado antes del script 12 es un porcentaje bajo con casi todo en `FALTA_EN_TABLA`.

La prueba del CI también vigila que el SQL de verificación no se separe de la Matriz.

## 7. Estado al 09/11/2026

Revisado contra `dev` de los dos repos.

| RF | Base de datos | Backend | Pantalla | Pruebas independientes que ya se pueden hacer | Bloqueo |
|---|---|---|---|---|---|
| RF10–RF17, RF19 | Vistas 16–18 y scripts 13–15 en `dev` | En `dev` | 9 y 10 en `dev` | Backend (cursor simulado) y frontend (mocks) | Aceptación y SQL: datos v2 y scripts 10 y 12 |
| RF18 | Script 11 en `dev` | **No existe** (Santiago) | 11 en `dev` | Frontend (mocks) | Backend: falta el número de proceso de la nueva obligación en `POST /refinanciaciones/` y `GET /catalogos/` |
| RF20–RF22, RF51–RF53 | Vistas 17 y 18 en `dev` | **No existe** (Dilan) | 12 en `dev` | Frontend (mocks); SQL de las vistas cuando haya datos v2 | Backend del generador y de las validaciones |
| RF23 | Script 11 en `dev` | Fusionado en **`main`, no en `dev`** | 13 **no existe** (Omar) | Ninguna | Llevar el backend a `dev` y la pantalla 13 |
| RF24, RF50 | Script 11 en `dev` | En `dev` | 14 en `dev` | Backend y frontend | Aceptación: datos v2 |
| RF45–RF47, RF49 | Vistas en `dev` | En `dev` | 9 y 10 en `dev` | Backend y frontend | Aceptación: datos v2 |
| RF48 | **Script 12 no existe** (Clara) | **No existe** (Santiago) | 16 en `dev` | Frontend (mocks) | Columnas `USADO` y `ACCION` del script 12 |
| RF54 | Script 11 en `dev` | En `dev` | 12 en `dev` | Backend y frontend | Aceptación: datos v2 |
| RF55 | Script 11 en `dev` | Rama sin fusionar (Clara) | 14 en `dev` | Frontend (mocks) | Revisión y fusión del backend |
| RF57 | Usa `NV_PARAMETRO` (marcadores del script 10 pendientes) | En `dev` | 15 en `dev` | Backend y frontend | Prueba contra Oracle |

## 8. Observaciones para revisar

No son defectos confirmados: se registran para que el dueño los mire antes de la prueba independiente.

| N.º | Observación | Dueño |
|---|---|---|
| OBS-01 | Las consultas del ciclo a `NV_TRANSICION_ESTADO` no filtran por tipo de cartera. Si el script 12 carga también Comercio en la misma tabla, el ciclo mezclaría las dos matrices. Confirmar el esquema de la tabla al escribir el script 12 | Clara · José Luis |
| OBS-02 | El backend de RF23 (PR #53) se fusionó en `main` y no en `dev`: `dev` no tiene reclamos y `main` no tiene RF45, RF57 ni el contrato 0.9.3 | Clara · Johan |
| OBS-03 | El catálogo `NV_NATURALEZA_REESTR` del script 11 carga 01, 02, 03 y 99 con `CONFIRMADO = 'N'`. Confirmar que los códigos salen de la Tabla 11 del Manual; si no, no deben cargarse | Angel · Santiago |
| OBS-04 | Los scripts 10 y 12 todavía no existen; sin ellos no hay marcadores `XXX` de la entidad, ni la matriz completa, ni la homologación con acción | Clara |

## 9. Trazabilidad RF a casos

| RF | Requerimiento | Casos | N.º | Backend y SQL | Frontend | Aceptación |
|---|---|---|---|---|---|---|
| RF10 | Primer reporte de una obligación | CP-B-01 a CP-B-06 | 6 | Dilan | Omar | Santiago |
| RF11 | Evolución mensual de la edad de mora | CP-B-07 a CP-B-11 | 5 | Dilan | Omar | Omar |
| RF12 | Cierre en estado Saldada | CP-B-12 a CP-B-15 | 4 | Dilan | Omar | Omar |
| RF13 | Saldada como cierre definitivo | CP-B-16 a CP-B-18 | 3 | Dilan | Omar | Omar |
| RF14 | Transición a Dudoso Recaudo | CP-B-19 a CP-B-22 | 4 | Dilan | Omar | Omar |
| RF15 | Cierre en Cartera Recuperada | CP-B-23 a CP-B-26 | 4 | Dilan | Omar | Omar |
| RF16 | Cartera Recuperada como cierre definitivo | CP-B-27 a CP-B-28 | 2 | Dilan | Omar | Omar |
| RF17 | Recálculo por abono parcial | CP-B-29 a CP-B-32 | 4 | Dilan | Omar | Santiago |
| RF18 | Refinanciación | CP-B-33 a CP-B-37 | 5 | Dilan | Santiago | Omar |
| RF19 | Cuotas en mora y coherencia de la mora | CP-B-38 a CP-B-41 | 4 | Dilan | Omar | Omar |
| RF45 | Transición a Castigada | CP-B-42 a CP-B-45 | 4 | Dilan | Omar | Omar |
| RF46 | Normalización sin pago total | CP-B-46 a CP-B-48 | 3 | Dilan | Omar | Omar |
| RF47 | Reporte del pago de la mora | CP-B-49 a CP-B-51 | 3 | Dilan | Omar | Omar |
| RF48 | Catálogo y homologación de estados (Administrador) | CP-B-52 a CP-B-56 | 5 | Dilan | Omar | Omar |
| RF49 | Fecha de exigibilidad y años en mora | CP-B-57 a CP-B-60 | 4 | Dilan | Omar | Omar |
| RF20 | Generación del archivo plano del reporte total | CP-C-01 a CP-C-07 | 7 | Santiago | Omar | Santiago |
| RF21 | Universo del reporte total | CP-C-08 a CP-C-11 | 4 | Santiago | Omar | Omar |
| RF22 | Validación de cierre | CP-C-12 a CP-C-16 | 5 | Santiago | Omar | Omar |
| RF23 | Registro de reclamos de Habeas Data | CP-C-17 a CP-C-22 | 6 | Dilan | Santiago | Santiago |
| RF24 | Registro de novedades de Actualización en Línea | CP-C-23 a CP-C-27 | 5 | Dilan | Omar | Omar |
| RF50 | Control de eliminaciones | CP-C-28 a CP-C-31 | 4 | Dilan | Omar | Omar |
| RF51 | Expresión de valores en miles de pesos | CP-C-32 a CP-C-36 | 5 | Santiago | Omar | Omar |
| RF52 | Composición de los valores de la obligación | CP-C-37 a CP-C-39 | 3 | Santiago | — | Omar |
| RF53 | Validación del corte contra el Manual | CP-C-40 a CP-C-46 | 7 | Santiago | Omar | Santiago |
| RF54 | Resultados del cargue de TransUnion | CP-C-47 a CP-C-51 | 5 | Dilan | Omar | Dilan |
| RF55 | Rectificación de información reportada | CP-C-52 a CP-C-55 | 4 | Dilan | Omar | Omar |
| RF57 | Datos de la entidad y código de sucursal (Administrador) | CP-C-56 a CP-C-60 | 5 | Dilan | Omar | Omar |
| | **Total** | | **120** | | | |

Las pruebas de frontend se hacen por pantalla, no por RF: pantalla 9 y 10 (Omar), 11 (Santiago), 12 (Omar), 13 (Santiago), 14 (Omar), 15 y 16 (Omar), y el control de acceso por rol en todas (Omar). Cada una cubre los casos de los RF que muestra.

## 10. Casos por RF

Cada caso se cita igual en la evidencia, en los defectos y en el FP-15. Los números de obligación (por ejemplo 2263-9004) son las obligaciones ficticias del mockup v3 y de los datos de prueba v2.

## 10.1 HU-B

### RF10 · Primer reporte de una obligación

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Santiago**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-01 | Obligación nueva al día (2263-9004) | Entra en 01, edad 00, marcada «Primer reporte» |
| CP-B-02 | Nueva con una cuota vencida de 23 días | Entra en 01 con edad 00 y valor de mora mayor a cero (válido) |
| CP-B-03 | Nueva con crédito caducado y con mora | Entra en 03 (válido) |
| CP-B-04 | Nueva caducada pero sin mora | Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14) |
| CP-B-05 | Nueva en estado 07 | Rechazada con el error 881 |
| CP-B-06 | Ejecutar el ciclo dos veces | No duplica obligaciones ni detalles |

### RF11 · Evolución mensual de la edad de mora

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-07 | Cuota más antigua sin pagar de 47 días | Edad 01 |
| CP-B-08 | Edad pasa de 00 a 03 en un corte | Marcada para revisión; el valor calculado no cambia |
| CP-B-09 | Edad baja de 02 a 00 sin abono | Marcada para revisión |
| CP-B-10 | Edad baja con un abono que paga las cuotas más antiguas | Sin marca de revisión |
| CP-B-11 | 730 días o más | Edad 14 y años en mora calculados |

### RF12 · Cierre en estado Saldada

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-12 | 2259-1092: pago total estando en 01 | Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte |
| CP-B-13 | Obligación en 04 con saldo cero | No cierra; inconsistencia 713 |
| CP-B-14 | Obligación en 03 con saldo cero | No va a 02: cierra en 07 (RF15) |
| CP-B-15 | Cierre sin fecha de pago | No se reporta el cierre (RF22) |

### RF13 · Saldada como cierre definitivo

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-16 | Obligación 02 reportada en el corte anterior | No aparece en el archivo nuevo ni cuenta como omitida |
| CP-B-17 | Intentar reutilizar el número de una cerrada | 409 con mensaje claro |
| CP-B-18 | Cerrada que vuelve a mostrar movimiento en SAC | No se reporta; alerta al Analista |

### RF14 · Transición a Dudoso Recaudo

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-19 | 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora | Estado 03 |
| CP-B-20 | Caducado pero con mora cero | No reporta 03; marcada para revisión |
| CP-B-21 | 3 de 4 atrasos permitidos | Sigue en 01 |
| CP-B-22 | Estado anterior 02 y crédito caducado | No cambia: inconsistencia 713 |

### RF15 · Cierre en Cartera Recuperada

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-23 | 2241-3302: en 03 paga todo | Pasa a 07 con fecha de pago |
| CP-B-24 | Origen 01 con pago total | Va a 02 (RF12), no a 07 |
| CP-B-25 | Origen 03 sin mora en el corte anterior | Inconsistencia 713 |
| CP-B-26 | Cierre por refinanciación desde 03 | Cierra en 07 con modo 16 |

### RF16 · Cartera Recuperada como cierre definitivo

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-27 | Obligación 07 reportada en el corte anterior | No aparece en el archivo nuevo ni cuenta como omitida |
| CP-B-28 | Intentar reutilizar su número | 409 con mensaje claro |

### RF17 · Recálculo por abono parcial

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Santiago**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-29 | 2258-7731: 2 cuotas de $70.000; abono de $70.000 | Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante |
| CP-B-30 | Abono menor a una cuota | La cuota sigue vencida; la edad no baja |
| CP-B-31 | Abono que cubre toda la mora y hay saldo | Pasa a RF47 (pago de la mora) |
| CP-B-32 | Abono por todo el saldo | Cierre (RF12 o RF15) |

### RF18 · Refinanciación

Independientes: backend y SQL **Dilan** · frontend **Santiago** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-33 | 2255-7788 refinanciada en 2271-5502 | Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado |
| CP-B-34 | Original en 03 en mora | Original en 07 con modo 16 |
| CP-B-35 | Original en 04 | No se cierra; aviso al Analista (409 en el registro manual) |
| CP-B-36 | Cuotas 0 o 121 en el registro manual | 400 con mensaje en español |
| CP-B-37 | Siguiente ciclo | La nueva sigue marcada como reestructurada |

### RF19 · Cuotas en mora y coherencia de la mora

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-38 | Edad 01 con valor de mora cero | Bloquea con la regla 707 |
| CP-B-39 | Valor de mora cero con 2 cuotas en mora | Alerta informativa |
| CP-B-40 | Cuota aún no facturada | No cuenta como cuota en mora |
| CP-B-41 | Resumen con 12 obligaciones de prueba | Las 4 agrupaciones suman las obligaciones abiertas |

### RF45 · Transición a Castigada

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-42 | 2244-6410: con marca de castigo y mora | Estado 06 |
| CP-B-43 | Marca de castigo con mora cero | No reporta 06; marcada para revisión |
| CP-B-44 | Primer reporte castigada con edad 00 | Rechazada (881) |
| CP-B-45 | Estado anterior 02 con marca de castigo | Inconsistencia 713 |

### RF46 · Normalización sin pago total

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-46 | Obligación en 03 que paga toda la mora y conserva saldo | Vuelve a 01 y se reporta el pago de la mora |
| CP-B-47 | Obligación en 06 con mora pendiente | Mantiene 06 |
| CP-B-48 | Obligación en estado de ley que retoma su curso | Vuelve a 01 |

### RF47 · Reporte del pago de la mora

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-49 | Obligación con mora que queda al día | Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte |
| CP-B-50 | Queda al día sin fecha de pago | Marcada para revisión |
| CP-B-51 | Obligación sin mora previa | No genera pago de mora |

### RF48 · Catálogo y homologación de estados

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-52 | Administrador cambia A | 01 → Se guarda y queda en bitácora |
| CP-B-53 | Analista intenta PUT | 403 en español |
| CP-B-54 | Asignar estado 08 (no usado) | 400 |
| CP-B-55 | Crédito con estado B sin homologar | La obligación se bloquea en RF53 |
| CP-B-56 | Matriz cargada | 400 filas; 02 y 07 sin salidas |

### RF49 · Fecha de exigibilidad y años en mora

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-B-57 | Dos cuotas sin pagar (primera del 14/08) | Fecha de exigibilidad 14/08 |
| CP-B-58 | Edad 14 con 800 días | Años en mora 2 |
| CP-B-59 | Obligación al día | Fecha de exigibilidad vacía |
| CP-B-60 | Fecha de exigibilidad mayor a la fecha del sistema | Bloquea la obligación |

## 10.2 HU-C

### RF20 · Generación del archivo plano del reporte total

Independientes: backend y SQL **Santiago** · frontend **Omar** · aceptación **Santiago**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-01 | Corte validado con 9 obligaciones | Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo |
| CP-C-02 | Nombre del archivo con marcadores XXX, XXX | SSRXXXXXX + fecha de corte; APTO_ENVIO = N |
| CP-C-03 | Nombre con tipo 001 y código 123 de prueba | SSR001123 + fecha; APTO_ENVIO = S |
| CP-C-04 | Nombre con una tilde (Ñ, Á) | Se codifica en cp1252 sin romper la longitud |
| CP-C-05 | Campo más largo que su posición | No genera; error con obligación y campo |
| CP-C-06 | Corte en BORRADOR | 409: debe estar validado |
| CP-C-07 | Conteos del tipo 9 | Coinciden con los registros generados |

### RF21 · Universo del reporte total

Independientes: backend y SQL **Santiago** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-08 | Obligación en 03 del último corte que ya no aparece vigente en SAC | Se incluye en el nuevo corte |
| CP-C-09 | Obligación 02 del corte anterior | Se excluye sin contarla como omitida |
| CP-C-10 | Obligación activa del último corte sin registro en el nuevo | Bloquea la validación |
| CP-C-11 | Obligación eliminada (RF50) | No se incluye |

### RF22 · Validación de cierre

Independientes: backend y SQL **Santiago** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-12 | Cierre completo (2259-1092) | Pasa la validación |
| CP-C-13 | Cierre sin fecha de pago | Correctiva; no se reporta el cierre |
| CP-C-14 | Cierre con cuota distinta de cero | Correctiva; el valor NO se cambia a cero |
| CP-C-15 | Tipo de pago 01 con modo distinto de 01 (sin refinanciación) | Correctiva |
| CP-C-16 | Cierre por refinanciación con modo 16 | Pasa |

### RF23 · Registro de reclamos de Habeas Data

Independientes: backend y SQL **Dilan** · frontend **Santiago** · aceptación **Santiago**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-17 | Registrar un reclamo «Pago no reflejado» (2260-5543) | Queda EN_RECLAMO con plazo; la obligación sigue en el archivo |
| CP-C-18 | Segundo reclamo abierto sobre la misma obligación | 409 en español |
| CP-C-19 | Tipología fuera del catálogo | 400 |
| CP-C-20 | Cerrar con fecha anterior a la radicación | 400 en el campo fecha_cierre |
| CP-C-21 | Generar el insumo de marcación | Incluye solo los reclamos pendientes; luego el botón queda en 0 |
| CP-C-22 | Reclamo con plazo vencido | Alerta en el listado |

### RF24 · Registro de novedades de Actualización en Línea

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-23 | Registrar una Actualización sobre 2262-3318 | Queda PENDIENTE y aparece en la pestaña Pendientes |
| CP-C-24 | Gestionar sin número de transacción | 400 en el campo de confirmación |
| CP-C-25 | Gestionar con número TU-AL-001532 | Pasa a GESTIONADA con fecha |
| CP-C-26 | Novedad sobre una obligación que no existe | Error claro (no Inclusión) |
| CP-C-27 | Rechazar con motivo | ESTADO = RECHAZADA y queda registrado |

### RF50 · Control de eliminaciones

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-28 | Gestionar la eliminación de 2249-1180 | Obligación eliminada: sale del siguiente corte |
| CP-C-29 | Corte siguiente | La eliminada no cuenta como omitida (RF21) |
| CP-C-30 | Reactivar sin número de activación | 400 |
| CP-C-31 | Reactivar con número | Vuelve a poder reportarse |

### RF51 · Expresión de valores en miles de pesos

Independientes: backend y SQL **Santiago** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-32 | Mora de $400 | Reporta 1 (no 0) |
| CP-C-33 | Saldo de $1.276.016 | Reporta 1276 |
| CP-C-34 | Valor de $9.000 | Advertencia informativa |
| CP-C-35 | Valor de $120 millones | Advertencia informativa |
| CP-C-36 | Valores sin decimales | Todos enteros |

### RF52 · Composición de los valores de la obligación

Independientes: backend y SQL **Santiago** · frontend **—** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-37 | Crédito con deuda inicial 1.500.000 y saldo 1.276.016 | Valor inicial y saldo distintos |
| CP-C-38 | Saldo mayor al valor inicial | Advertencia informativa |
| CP-C-39 | Obligación con 2 cuotas vencidas de $70.000 | Valor de mora $140.000 distinto del saldo |

### RF53 · Validación del corte contra el Manual

Independientes: backend y SQL **Santiago** · frontend **Omar** · aceptación **Santiago**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-40 | Obligación sin identificación | Correctiva SIN_IDENTIFICACION; no valida |
| CP-C-41 | Número de obligación de 21 caracteres | Correctiva |
| CP-C-42 | Entidad con marcadores XXX | Solo advertencia: el archivo se genera, no apto |
| CP-C-43 | Obligación activa del último corte omitida | Correctiva OMISION_VS_ULTIMO_CORTE |
| CP-C-44 | Saldo mayor al valor inicial | Informativa; no bloquea |
| CP-C-45 | Corte sin ninguna correctiva | Pasa a VALIDADO |
| CP-C-46 | Fecha de corte igual a la del último corte enviado | Correctiva |

### RF54 · Resultados del cargue de TransUnion

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Dilan**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-47 | Cargar el archivo de correctivas de un corte enviado | Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS |
| CP-C-48 | Cargar un archivo sin correctivas | El corte queda ENVIADO |
| CP-C-49 | Archivo de otro corte | 422 con el motivo |
| CP-C-50 | Archivo con estructura distinta a la esperada | 422; no se guarda nada |
| CP-C-51 | Archivo norep con una obligación | Aparece como no reportada del corte |

### RF55 · Rectificación de información reportada

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-52 | Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 | Guarda anterior y corregido; el original no se borra |
| CP-C-53 | Corte que aún no está ENVIADO | 409: se corrige en el origen, no por rectificación |
| CP-C-54 | Obligación Saldada con movimiento nuevo | Solo admite el cambio por esta vía |
| CP-C-55 | Confirmar sin número de TransUnion | 400 |

### RF57 · Datos de la entidad y código de sucursal

Independientes: backend y SQL **Dilan** · frontend **Omar** · aceptación **Omar**.

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-C-56 | Administrador guarda 001 / 123 / A1B2C3 | Se guarda; los archivos nuevos salen aptos |
| CP-C-57 | Guardar 12 en el tipo de entidad | 400 (deben ser 3 dígitos) |
| CP-C-58 | Analista intenta PUT | 403 en español |
| CP-C-59 | Con marcadores | Archivo generado, no apto para envío y advertencia en la validación |
| CP-C-60 | «Volver al relleno» | Los tres valores vuelven a XXX, XXX y XXXXXX |
