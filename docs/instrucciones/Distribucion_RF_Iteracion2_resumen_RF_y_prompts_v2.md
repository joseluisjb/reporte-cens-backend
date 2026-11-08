# NexoVolt · Iteración 2 · Requerimientos y prompts

Resumen de `Distribucion_RF_Iteracion2_por_integrante_v2.md`: solo los nombres de los RF y los prompts de cada tarea.

> **Versión 2 (07/11/2026).** Corregida contra los repos: fuentes de los prompts en `docs/iteracion2/`, rama `dev` en los dos repos, permiso EsAnalista, RequireRole real, carpetas en inglés, contrato 0.9 sin el prefijo /api y copiado al backend, casos de prueba de RF10 y RF51, y filas C-54 a C-56 en el Anexo A.

## Índice de RF

- **RF10** · Primer reporte de una obligación
- **RF11** · Evolución mensual de la edad de mora
- **RF12** · Cierre en estado Saldada
- **RF13** · Saldada como cierre definitivo
- **RF14** · Transición a Dudoso Recaudo
- **RF15** · Cierre en Cartera Recuperada
- **RF16** · Cartera Recuperada como cierre definitivo
- **RF17** · Recálculo por abono parcial
- **RF18** · Refinanciación
- **RF19** · Cuotas en mora y coherencia de la mora
- **RF20** · Generación del archivo plano del reporte total
- **RF21** · Universo del reporte total
- **RF22** · Validación de cierre
- **RF23** · Registro de reclamos de Habeas Data
- **RF24** · Registro de novedades de Actualización en Línea
- **RF45** · Transición a Castigada
- **RF46** · Normalización sin pago total
- **RF47** · Reporte del pago de la mora
- **RF48** · Catálogo y homologación de estados
- **RF49** · Fecha de exigibilidad y años en mora
- **RF50** · Control de eliminaciones
- **RF51** · Expresión de valores en miles de pesos
- **RF52** · Composición de los valores de la obligación
- **RF53** · Validación del corte contra el Manual
- **RF54** · Resultados del cargue de TransUnion
- **RF55** · Rectificación de información reportada
- **RF57** · Datos de la entidad y código de sucursal

---

## RF10 · Primer reporte de una obligación

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF10 · Primer reporte de una obligación. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación sin corte ENVIADO previo es «primer reporte» (en el primer corte de CENS lo será toda la cartera). Se calcula su estado real y se valida la combinación estado/comportamiento.
Reglas del RF:
- Primer reporte = la obligación no aparece en V_ULTIMO_REPORTE (ningún corte ENVIADO).
- Se calculan estado (RF48), edad de mora (RF7), valor de mora y cuotas en mora reales; ya no se fuerza Vigente sin mora. Un crédito caducado sin mora no pasa a 03: entra en 01 y queda marcado para revisión (RF14).
- Combinaciones válidas: 01 con o sin mora; 03 solo en mora; 06 solo con edad de mora mayor a 00 y mora mayor a cero; 07 nunca.
- Si no cumple: no entra al archivo y se registra la inconsistencia «Estado y comportamiento no permitido en primer reporte» (equivale al error 881 de TransUnion).

Haz esto:
1. Agregar a V_CALCULO_CORTE la columna PRIMER_REPORTE: S cuando la obligación no tiene fila en V_ULTIMO_REPORTE.
2. Verificar que INCLUIR no excluya las obligaciones nuevas con mora (solo se excluyen las cerradas, por MOTIVO_EXCLUSION).
3. Coordinar con Angel (dueño de V_VALIDACION_CORTE) la regla PRIMER_REPORTE_INVALIDO: hoy incluye el estado 04 y no exige edad mayor a 00 en 06; debe quedar con las 4 combinaciones del RF y el mensaje del RF.

Usa estos objetos: V_CALCULO_CORTE; V_ULTIMO_REPORTE; NV_REPORTE_DETALLE.PRIMER_REPORTE (script 10); NV_ESTADO_TU; NV_INCONSISTENCIA.

Comprueba con estos casos (datos de prueba v2):
- Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
- Nueva con una cuota vencida de 23 días → Entra en 01 con edad 00 y valor de mora mayor a cero (válido)
- Nueva con crédito caducado y con mora → Entra en 03 (válido)
- Nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF10 · Primer reporte de una obligación. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación sin corte ENVIADO previo es «primer reporte» (en el primer corte de CENS lo será toda la cartera). Se calcula su estado real y se valida la combinación estado/comportamiento.
Reglas del RF:
- Primer reporte = la obligación no aparece en V_ULTIMO_REPORTE (ningún corte ENVIADO).
- Se calculan estado (RF48), edad de mora (RF7), valor de mora y cuotas en mora reales; ya no se fuerza Vigente sin mora. Un crédito caducado sin mora no pasa a 03: entra en 01 y queda marcado para revisión (RF14).
- Combinaciones válidas: 01 con o sin mora; 03 solo en mora; 06 solo con edad de mora mayor a 00 y mora mayor a cero; 07 nunca.
- Si no cumple: no entra al archivo y se registra la inconsistencia «Estado y comportamiento no permitido en primer reporte» (equivale al error 881 de TransUnion).

Endpoints a implementar o ajustar: POST /api/ciclos/ (la respuesta trae primer_reporte); GET /api/ciclos/{corte_id}/.

Haz esto:
1. En el ciclo, crear en NV_OBLIGACION las obligaciones nuevas (número según RF5: máximo 20 caracteres y solo ( ) * , - . / \ _ ¯ ·) e insertar su NV_REPORTE_DETALLE con PRIMER_REPORTE = S.
2. Las que no pasen la validación 881 quedan en NV_INCONSISTENCIA (CORRECTIVA) y se devuelven en «rechazados» con el motivo «Error 881: estado no permitido en primer reporte».
3. Idempotente: ejecutar el ciclo dos veces para el mismo corte no duplica obligaciones ni detalles.

Usa estas tablas, vistas y módulos: cartera/servicios.py (generar_corte, validar_corte); V_CALCULO_CORTE; NV_OBLIGACION; NV_REPORTE_DETALLE; NV_INCONSISTENCIA; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
- Nueva con una cuota vencida de 23 días → Entra en 01 con edad 00 y valor de mora mayor a cero (válido)
- Nueva con crédito caducado y con mora → Entra en 03 (válido)
- Nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14)
- Nueva en estado 07 → Rechazada con el error 881
- Ejecutar el ciclo dos veces → No duplica obligaciones ni detalles

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF10 · Primer reporte de una obligación. Parte de frontend: pantalla 9 y 10 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación sin corte ENVIADO previo es «primer reporte» (en el primer corte de CENS lo será toda la cartera). Se calcula su estado real y se valida la combinación estado/comportamiento.

Implementa:
1. Pantalla 10: tarjeta con el conteo «Primer reporte» en el historial de actualizaciones, chips «Obligaciones nuevas por ingresar» y tabla de rechazados (Número, Deudor, Cambio calculado, Motivo).
2. Pantalla 9: etiqueta «Primer reporte» bajo el número de la obligación y campo «Primer reporte: Sí/No» en el detalle.

Consume estos endpoints (según el contrato): POST /api/ciclos/; GET /api/obligaciones/; GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
- Nueva con una cuota vencida de 23 días → Entra en 01 con edad 00 y valor de mora mayor a cero (válido)
- Nueva con crédito caducado y con mora → Entra en 03 (válido)
- Nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14)
- Nueva en estado 07 → Rechazada con el error 881

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF10 · Primer reporte de una obligación. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación sin corte ENVIADO previo es «primer reporte» (en el primer corte de CENS lo será toda la cartera). Se calcula su estado real y se valida la combinación estado/comportamiento.
Reglas del RF:
- Primer reporte = la obligación no aparece en V_ULTIMO_REPORTE (ningún corte ENVIADO).
- Se calculan estado (RF48), edad de mora (RF7), valor de mora y cuotas en mora reales; ya no se fuerza Vigente sin mora. Un crédito caducado sin mora no pasa a 03: entra en 01 y queda marcado para revisión (RF14).
- Combinaciones válidas: 01 con o sin mora; 03 solo en mora; 06 solo con edad de mora mayor a 00 y mora mayor a cero; 07 nunca.
- Si no cumple: no entra al archivo y se registra la inconsistencia «Estado y comportamiento no permitido en primer reporte» (equivale al error 881 de TransUnion).

Qué probar:
- Vistas y tablas: V_CALCULO_CORTE; V_ULTIMO_REPORTE; NV_REPORTE_DETALLE.PRIMER_REPORTE (script 10); NV_ESTADO_TU; NV_INCONSISTENCIA
- Endpoints: POST /api/ciclos/ (la respuesta trae primer_reporte); GET /api/ciclos/{corte_id}/

Casos mínimos (automatiza todos):
1. Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
2. Nueva con una cuota vencida de 23 días → Entra en 01 con edad 00 y valor de mora mayor a cero (válido)
3. Nueva con crédito caducado y con mora → Entra en 03 (válido)
4. Nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14)
5. Nueva en estado 07 → Rechazada con el error 881
6. Ejecutar el ciclo dos veces → No duplica obligaciones ni detalles

Entrega: tests/test_rf10_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF10 · Primer reporte de una obligación (rol del RF: Analista de Cartera; pantalla del mockup v3: 9 y 10). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 10: tarjeta con el conteo «Primer reporte» en el historial de actualizaciones, chips «Obligaciones nuevas por ingresar» y tabla de rechazados (Número, Deudor, Cambio calculado, Motivo).
- Pantalla 9: etiqueta «Primer reporte» bajo el número de la obligación y campo «Primer reporte: Sí/No» en el detalle.

Reglas del RF:
- Primer reporte = la obligación no aparece en V_ULTIMO_REPORTE (ningún corte ENVIADO).
- Se calculan estado (RF48), edad de mora (RF7), valor de mora y cuotas en mora reales; ya no se fuerza Vigente sin mora. Un crédito caducado sin mora no pasa a 03: entra en 01 y queda marcado para revisión (RF14).
- Combinaciones válidas: 01 con o sin mora; 03 solo en mora; 06 solo con edad de mora mayor a 00 y mora mayor a cero; 07 nunca.
- Si no cumple: no entra al archivo y se registra la inconsistencia «Estado y comportamiento no permitido en primer reporte» (equivale al error 881 de TransUnion).

Casos mínimos:
1. Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
2. Nueva con una cuota vencida de 23 días → Entra en 01 con edad 00 y valor de mora mayor a cero (válido)
3. Nueva con crédito caducado y con mora → Entra en 03 (válido)
4. Nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14)
5. Nueva en estado 07 → Rechazada con el error 881
6. Ejecutar el ciclo dos veces → No duplica obligaciones ni detalles

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF11 · Evolución mensual de la edad de mora

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF11 · Evolución mensual de la edad de mora. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: En cada corte se recalcula la edad de mora de toda obligación no cerrada con los días reales (RF7) y la Tabla 9. «Gradual» deja de ser regla y pasa a ser una alerta de calidad.
Reglas del RF:
- Días de mora reales = fecha de corte − fecha límite de pago de la cuota vencida más antigua sin pagar completa (RF7).
- Código de la Tabla 9 (00 a 14): 00 a 11 en tramos de 30 días; 12 = 360–539; 13 = 540–729; 14 = 730 o más (tabla NV_EDAD_MORA).
- Si la edad es 14 se calculan los años en mora (RF49).
- Si la edad avanza más de un tramo frente al último corte enviado, o baja sin un abono registrado (RF17), la obligación se marca para revisión sin modificar el valor calculado.

Haz esto:
1. La edad sale de NV_EDAD_MORA con DIAS_MORA tomado de V_MORA_OBLIGACION (Angel). No limitar el avance a un tramo.
2. Agregar EDAD_ANTERIOR (edad del último corte ENVIADO) y REQUIERE_REVISION / MOTIVO_REVISION con dos alertas: salto de más de un tramo, y baja de edad sin abono en el periodo.

Usa estos objetos: NV_EDAD_MORA; V_ULTIMO_REPORTE (EDAD_MORA); V_MORA_OBLIGACION (DIAS_MORA, VALOR_PAGADO_PERIODO); NV_REPORTE_DETALLE (EDAD_MORA, EDAD_ANTERIOR, REQUIERE_REVISION).

Comprueba con estos casos (datos de prueba v2):
- Cuota más antigua sin pagar de 47 días → Edad 01
- Edad pasa de 00 a 03 en un corte → Marcada para revisión; el valor calculado no cambia
- Edad baja de 02 a 00 sin abono → Marcada para revisión
- Edad baja con un abono que paga las cuotas más antiguas → Sin marca de revisión

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF11 · Evolución mensual de la edad de mora. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: En cada corte se recalcula la edad de mora de toda obligación no cerrada con los días reales (RF7) y la Tabla 9. «Gradual» deja de ser regla y pasa a ser una alerta de calidad.
Reglas del RF:
- Días de mora reales = fecha de corte − fecha límite de pago de la cuota vencida más antigua sin pagar completa (RF7).
- Código de la Tabla 9 (00 a 14): 00 a 11 en tramos de 30 días; 12 = 360–539; 13 = 540–729; 14 = 730 o más (tabla NV_EDAD_MORA).
- Si la edad es 14 se calculan los años en mora (RF49).
- Si la edad avanza más de un tramo frente al último corte enviado, o baja sin un abono registrado (RF17), la obligación se marca para revisión sin modificar el valor calculado.

Endpoints a implementar o ajustar: POST /api/ciclos/ (lista de cambios de edad); GET /api/obligaciones/ y /{id}/ (edad_mora, dias_mora, requiere_revision).

Haz esto:
1. Exponer la edad como {codigo, descripcion} de la Tabla 9, los días de mora y la bandera de revisión con su motivo.
2. En el resultado del ciclo devolver la regla aplicada: «RF11 · N días desde la cuota más antigua sin pagar (fecha): edad AA → BB».

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE; NV_REPORTE_DETALLE; NV_EDAD_MORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Cuota más antigua sin pagar de 47 días → Edad 01
- Edad pasa de 00 a 03 en un corte → Marcada para revisión; el valor calculado no cambia
- Edad baja de 02 a 00 sin abono → Marcada para revisión
- Edad baja con un abono que paga las cuotas más antiguas → Sin marca de revisión
- 730 días o más → Edad 14 y años en mora calculados

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF11 · Evolución mensual de la edad de mora. Parte de frontend: pantalla 9 y 10 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: En cada corte se recalcula la edad de mora de toda obligación no cerrada con los días reales (RF7) y la Tabla 9. «Gradual» deja de ser regla y pasa a ser una alerta de calidad.

Implementa:
1. Pantalla 9: columna «Edad de Mora (Tabla 9)» con los días de mora debajo y una marca «Revisar» cuando requiere_revision.
2. Pantalla 10: en el resultado, columna «Qué pasó» con la regla de RF11 y la edad «antes → después».

Consume estos endpoints (según el contrato): GET /api/obligaciones/; POST /api/ciclos/.

Pruebas con vitest (y MSW) para estos casos:
- Cuota más antigua sin pagar de 47 días → Edad 01
- Edad pasa de 00 a 03 en un corte → Marcada para revisión; el valor calculado no cambia
- Edad baja de 02 a 00 sin abono → Marcada para revisión
- Edad baja con un abono que paga las cuotas más antiguas → Sin marca de revisión
- 730 días o más → Edad 14 y años en mora calculados

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF11 · Evolución mensual de la edad de mora. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: En cada corte se recalcula la edad de mora de toda obligación no cerrada con los días reales (RF7) y la Tabla 9. «Gradual» deja de ser regla y pasa a ser una alerta de calidad.
Reglas del RF:
- Días de mora reales = fecha de corte − fecha límite de pago de la cuota vencida más antigua sin pagar completa (RF7).
- Código de la Tabla 9 (00 a 14): 00 a 11 en tramos de 30 días; 12 = 360–539; 13 = 540–729; 14 = 730 o más (tabla NV_EDAD_MORA).
- Si la edad es 14 se calculan los años en mora (RF49).
- Si la edad avanza más de un tramo frente al último corte enviado, o baja sin un abono registrado (RF17), la obligación se marca para revisión sin modificar el valor calculado.

Qué probar:
- Vistas y tablas: NV_EDAD_MORA; V_ULTIMO_REPORTE (EDAD_MORA); V_MORA_OBLIGACION (DIAS_MORA, VALOR_PAGADO_PERIODO); NV_REPORTE_DETALLE (EDAD_MORA, EDAD_ANTERIOR, REQUIERE_REVISION)
- Endpoints: POST /api/ciclos/ (lista de cambios de edad); GET /api/obligaciones/ y /{id}/ (edad_mora, dias_mora, requiere_revision)

Casos mínimos (automatiza todos):
1. Cuota más antigua sin pagar de 47 días → Edad 01
2. Edad pasa de 00 a 03 en un corte → Marcada para revisión; el valor calculado no cambia
3. Edad baja de 02 a 00 sin abono → Marcada para revisión
4. Edad baja con un abono que paga las cuotas más antiguas → Sin marca de revisión
5. 730 días o más → Edad 14 y años en mora calculados

Entrega: tests/test_rf11_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF11 · Evolución mensual de la edad de mora (rol del RF: Analista de Cartera; pantalla del mockup v3: 9 y 10). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: columna «Edad de Mora (Tabla 9)» con los días de mora debajo y una marca «Revisar» cuando requiere_revision.
- Pantalla 10: en el resultado, columna «Qué pasó» con la regla de RF11 y la edad «antes → después».

Reglas del RF:
- Días de mora reales = fecha de corte − fecha límite de pago de la cuota vencida más antigua sin pagar completa (RF7).
- Código de la Tabla 9 (00 a 14): 00 a 11 en tramos de 30 días; 12 = 360–539; 13 = 540–729; 14 = 730 o más (tabla NV_EDAD_MORA).
- Si la edad es 14 se calculan los años en mora (RF49).
- Si la edad avanza más de un tramo frente al último corte enviado, o baja sin un abono registrado (RF17), la obligación se marca para revisión sin modificar el valor calculado.

Casos mínimos:
1. Cuota más antigua sin pagar de 47 días → Edad 01
2. Edad pasa de 00 a 03 en un corte → Marcada para revisión; el valor calculado no cambia
3. Edad baja de 02 a 00 sin abono → Marcada para revisión
4. Edad baja con un abono que paga las cuotas más antiguas → Sin marca de revisión
5. 730 días o más → Edad 14 y años en mora calculados

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF12 · Cierre en estado Saldada

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF12 · Cierre en estado Saldada. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación que se extingue por completo se reporta Saldada (02) si en el último corte enviado estaba en Vigente (01) o Inactivo (08) y pasa las validaciones de cierre (RF22).
Reglas del RF:
- Precondición: saldo en cero a la fecha de corte, por pago total o por refinanciación (RF18).
- Reporta 02 con comportamiento normal, fecha de pago, modo de extinción (Tabla 10) y tipo de pago (Tabla 31).
- Si el último estado es 03 o 06, el cierre es en Cartera Recuperada (RF15).
- Si el último estado es 04 o de ley (10, 11, 12), la Matriz no permite el cierre: se muestra como inconsistencia «Cambio de estado inválido» (713).
- Si falla alguna validación de RF22 no se reporta el cierre.

Haz esto:
1. Cuando VALOR_SALDO = 0 y el estado anterior es 01 u 08: ESTADO_TU = 02 con edad 00, mora 0 y cuotas en mora 0 (la base ya existe con NV_ESTADO_TU.CIERRE_AL_PAGAR; revisarla contra el RF).
2. Llenar FECHA_PAGO (fecha en que el saldo llegó a cero, menor o igual a la fecha de corte), MODO_EXTINCION y TIPO_PAGO (01 y 01 por defecto, salvo proceso judicial).

Usa estos objetos: NV_ESTADO_TU; NV_TRANSICION_ESTADO; NV_MODO_EXTINCION y NV_TIPO_PAGO (script 10); NV_REPORTE_DETALLE.

Comprueba con estos casos (datos de prueba v2):
- 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
- Obligación en 04 con saldo cero → No cierra; inconsistencia 713
- Obligación en 03 con saldo cero → No va a 02: cierra en 07 (RF15)
- Cierre sin fecha de pago → No se reporta el cierre (RF22)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF12 · Cierre en estado Saldada. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación que se extingue por completo se reporta Saldada (02) si en el último corte enviado estaba en Vigente (01) o Inactivo (08) y pasa las validaciones de cierre (RF22).
Reglas del RF:
- Precondición: saldo en cero a la fecha de corte, por pago total o por refinanciación (RF18).
- Reporta 02 con comportamiento normal, fecha de pago, modo de extinción (Tabla 10) y tipo de pago (Tabla 31).
- Si el último estado es 03 o 06, el cierre es en Cartera Recuperada (RF15).
- Si el último estado es 04 o de ley (10, 11, 12), la Matriz no permite el cierre: se muestra como inconsistencia «Cambio de estado inválido» (713).
- Si falla alguna validación de RF22 no se reporta el cierre.

Endpoints a implementar o ajustar: POST /api/ciclos/; GET /api/obligaciones/{id}/ (bloque cierre).

Haz esto:
1. Guardar los campos de cierre en NV_REPORTE_DETALLE. Si la Matriz no permite el cierre, no emitirlo e insertar la inconsistencia CAMBIO_ESTADO_INVALIDO (713) en NV_INCONSISTENCIA.
2. Devolver en el detalle: cierre {fecha_pago, modo_extincion, tipo_pago} y en el resultado del ciclo «RF12 · Pago total: Saldada».

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE; NV_REPORTE_DETALLE; NV_INCONSISTENCIA; NV_TRANSICION_ESTADO.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
- Obligación en 04 con saldo cero → No cierra; inconsistencia 713
- Obligación en 03 con saldo cero → No va a 02: cierra en 07 (RF15)
- Cierre sin fecha de pago → No se reporta el cierre (RF22)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF12 · Cierre en estado Saldada. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación que se extingue por completo se reporta Saldada (02) si en el último corte enviado estaba en Vigente (01) o Inactivo (08) y pasa las validaciones de cierre (RF22).

Implementa:
1. Pantalla 9, detalle: bloque «Cierre» («Pagó el dd/mm/aaaa · Modo · Tipo de pago»), candado junto al estado y la posible transición «Pago total → 02 · Saldada (RF12)».

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
- Obligación en 04 con saldo cero → No cierra; inconsistencia 713
- Obligación en 03 con saldo cero → No va a 02: cierra en 07 (RF15)
- Cierre sin fecha de pago → No se reporta el cierre (RF22)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF12 · Cierre en estado Saldada. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación que se extingue por completo se reporta Saldada (02) si en el último corte enviado estaba en Vigente (01) o Inactivo (08) y pasa las validaciones de cierre (RF22).
Reglas del RF:
- Precondición: saldo en cero a la fecha de corte, por pago total o por refinanciación (RF18).
- Reporta 02 con comportamiento normal, fecha de pago, modo de extinción (Tabla 10) y tipo de pago (Tabla 31).
- Si el último estado es 03 o 06, el cierre es en Cartera Recuperada (RF15).
- Si el último estado es 04 o de ley (10, 11, 12), la Matriz no permite el cierre: se muestra como inconsistencia «Cambio de estado inválido» (713).
- Si falla alguna validación de RF22 no se reporta el cierre.

Qué probar:
- Vistas y tablas: NV_ESTADO_TU; NV_TRANSICION_ESTADO; NV_MODO_EXTINCION y NV_TIPO_PAGO (script 10); NV_REPORTE_DETALLE
- Endpoints: POST /api/ciclos/; GET /api/obligaciones/{id}/ (bloque cierre)

Casos mínimos (automatiza todos):
1. 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
2. Obligación en 04 con saldo cero → No cierra; inconsistencia 713
3. Obligación en 03 con saldo cero → No va a 02: cierra en 07 (RF15)
4. Cierre sin fecha de pago → No se reporta el cierre (RF22)

Entrega: tests/test_rf12_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF12 · Cierre en estado Saldada (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: bloque «Cierre» («Pagó el dd/mm/aaaa · Modo · Tipo de pago»), candado junto al estado y la posible transición «Pago total → 02 · Saldada (RF12)».

Reglas del RF:
- Precondición: saldo en cero a la fecha de corte, por pago total o por refinanciación (RF18).
- Reporta 02 con comportamiento normal, fecha de pago, modo de extinción (Tabla 10) y tipo de pago (Tabla 31).
- Si el último estado es 03 o 06, el cierre es en Cartera Recuperada (RF15).
- Si el último estado es 04 o de ley (10, 11, 12), la Matriz no permite el cierre: se muestra como inconsistencia «Cambio de estado inválido» (713).
- Si falla alguna validación de RF22 no se reporta el cierre.

Casos mínimos:
1. 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
2. Obligación en 04 con saldo cero → No cierra; inconsistencia 713
3. Obligación en 03 con saldo cero → No va a 02: cierra en 07 (RF15)
4. Cierre sin fecha de pago → No se reporta el cierre (RF22)

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF13 · Saldada como cierre definitivo

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF13 · Saldada como cierre definitivo. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación Saldada se reporta una sola vez, en el corte en que cierra, y se excluye de los cortes siguientes sin contarla como omitida.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes (no cuenta como omitida en RF21).
- Su número de obligación no se reutiliza.
- Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, no se reporta y se muestra al Analista: solo puede corregirse por rectificación (RF55).

Haz esto:
1. INCLUIR = S solo si la obligación no tenía un corte ENVIADO con estado de cierre (CIERRE_ANTERIOR); MOTIVO_EXCLUSION = YA_CERRADA_EN_TU en caso contrario.
2. Agregar la columna MOVIMIENTO_POSTERIOR: S cuando una obligación cerrada vuelve a mostrar saldo o pagos en SAC.

Usa estos objetos: V_CALCULO_CORTE; V_ULTIMO_REPORTE; NV_OBLIGACION.CIERRE_DEFINITIVO (script 10).

Comprueba con estos casos (datos de prueba v2):
- Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar el número de una cerrada → 409 con mensaje claro
- Cerrada que vuelve a mostrar movimiento en SAC → No se reporta; alerta al Analista

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF13 · Saldada como cierre definitivo. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación Saldada se reporta una sola vez, en el corte en que cierra, y se excluye de los cortes siguientes sin contarla como omitida.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes (no cuenta como omitida en RF21).
- Su número de obligación no se reutiliza.
- Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, no se reporta y se muestra al Analista: solo puede corregirse por rectificación (RF55).

Endpoints a implementar o ajustar: POST /api/extracciones/{id}/registrar-envio/ (existente, ajustar); GET /api/obligaciones/{id}/.

Haz esto:
1. Al registrar el envío del corte, marcar NV_OBLIGACION.CIERRE_DEFINITIVO = S y FECHA_CIERRE para lo reportado en 02.
2. Impedir reutilizar el número: UK_NV_OBLIGACION_TU ya lo exige; atrapar el error y responder 409 con mensaje en español.
3. Devolver la alerta «Movimiento posterior al cierre» en el detalle y en el resultado del ciclo.

Usa estas tablas, vistas y módulos: cartera/servicios.py (registrar_envio); NV_OBLIGACION; V_CALCULO_CORTE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar el número de una cerrada → 409 con mensaje claro
- Cerrada que vuelve a mostrar movimiento en SAC → No se reporta; alerta al Analista

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF13 · Saldada como cierre definitivo. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación Saldada se reporta una sola vez, en el corte en que cierra, y se excluye de los cortes siguientes sin contarla como omitida.

Implementa:
1. Pantalla 9: candado junto al estado, pie «Saldada (02) y Cartera Recuperada (07) se reportan una sola vez…», filtro por estado y alerta de movimiento posterior en el detalle.

Consume estos endpoints (según el contrato): GET /api/obligaciones/; GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar el número de una cerrada → 409 con mensaje claro
- Cerrada que vuelve a mostrar movimiento en SAC → No se reporta; alerta al Analista

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF13 · Saldada como cierre definitivo. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación Saldada se reporta una sola vez, en el corte en que cierra, y se excluye de los cortes siguientes sin contarla como omitida.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes (no cuenta como omitida en RF21).
- Su número de obligación no se reutiliza.
- Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, no se reporta y se muestra al Analista: solo puede corregirse por rectificación (RF55).

Qué probar:
- Vistas y tablas: V_CALCULO_CORTE; V_ULTIMO_REPORTE; NV_OBLIGACION.CIERRE_DEFINITIVO (script 10)
- Endpoints: POST /api/extracciones/{id}/registrar-envio/ (existente, ajustar); GET /api/obligaciones/{id}/

Casos mínimos (automatiza todos):
1. Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
2. Intentar reutilizar el número de una cerrada → 409 con mensaje claro
3. Cerrada que vuelve a mostrar movimiento en SAC → No se reporta; alerta al Analista

Entrega: tests/test_rf13_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF13 · Saldada como cierre definitivo (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: candado junto al estado, pie «Saldada (02) y Cartera Recuperada (07) se reportan una sola vez…», filtro por estado y alerta de movimiento posterior en el detalle.

Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes (no cuenta como omitida en RF21).
- Su número de obligación no se reutiliza.
- Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, no se reporta y se muestra al Analista: solo puede corregirse por rectificación (RF55).

Casos mínimos:
1. Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
2. Intentar reutilizar el número de una cerrada → 409 con mensaje claro
3. Cerrada que vuelve a mostrar movimiento en SAC → No se reporta; alerta al Analista

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF14 · Transición a Dudoso Recaudo

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF14 · Transición a Dudoso Recaudo. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación se reporta en Dudoso Recaudo (03) cuando su crédito está caducado en el sistema comercial de CENS y su valor de mora es mayor a cero.
Reglas del RF:
- Caducado en el SAC: CREDITOS.CONTATRASOS = CREDITOS.ATRASOS_PERMITIDOS. [Confirmar con CENS que el crédito caducado se reporta en 03 (C-53) y el código de estado.]
- El estado sale de la homologación (RF48: C → 03).
- La Matriz debe permitir el cambio desde el estado del último corte (01, 08 en mora, 04 en mora, 03 en mora o estado de ley).
- Si el valor de mora es cero: no se reporta 03 y se marca para revisión. Si la Matriz no permite el cambio: inconsistencia 713.

Haz esto:
1. Traer ATRASOS_PERMITIDOS a V_CREDITO_REPORTABLE si falta y calcular CADUCADO = CONTATRASOS >= ATRASOS_PERMITIDOS.
2. En V_CALCULO_CORTE: ESTADO_TU = 03 solo si CADUCADO y VALOR_MORA > 0. Si VALOR_MORA = 0 conservar el estado y poner REQUIERE_REVISION.

Usa estos objetos: SAC.CREDITOS (CONTATRASOS, ATRASOS_PERMITIDOS, ESTADO); V_CREDITO_REPORTABLE; NV_HOMOLOGA_ESTADO; NV_TRANSICION_ESTADO.

Comprueba con estos casos (datos de prueba v2):
- 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
- Caducado pero con mora cero → No reporta 03; marcada para revisión
- 3 de 4 atrasos permitidos → Sigue en 01
- Estado anterior 02 y crédito caducado → No cambia: inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF14 · Transición a Dudoso Recaudo. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación se reporta en Dudoso Recaudo (03) cuando su crédito está caducado en el sistema comercial de CENS y su valor de mora es mayor a cero.
Reglas del RF:
- Caducado en el SAC: CREDITOS.CONTATRASOS = CREDITOS.ATRASOS_PERMITIDOS. [Confirmar con CENS que el crédito caducado se reporta en 03 (C-53) y el código de estado.]
- El estado sale de la homologación (RF48: C → 03).
- La Matriz debe permitir el cambio desde el estado del último corte (01, 08 en mora, 04 en mora, 03 en mora o estado de ley).
- Si el valor de mora es cero: no se reporta 03 y se marca para revisión. Si la Matriz no permite el cambio: inconsistencia 713.

Endpoints a implementar o ajustar: POST /api/ciclos/; GET /api/obligaciones/{id}/ (bloque en_sac).

Haz esto:
1. Reflejar en el ciclo las transiciones a 03 con la regla «RF14 · Crédito caducado en el SAC (N cuotas en mora)» y los rechazos 713.
2. Exponer en el detalle en_sac {caducado, atrasos_permitidos, cuotas_atrasadas}.

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE; NV_TRANSICION_ESTADO; NV_INCONSISTENCIA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
- Caducado pero con mora cero → No reporta 03; marcada para revisión
- 3 de 4 atrasos permitidos → Sigue en 01
- Estado anterior 02 y crédito caducado → No cambia: inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF14 · Transición a Dudoso Recaudo. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación se reporta en Dudoso Recaudo (03) cuando su crédito está caducado en el sistema comercial de CENS y su valor de mora es mayor a cero.

Implementa:
1. Pantalla 9: etiqueta «Caducado en el SAC» en la fila (si no está cerrada) y bloque «En el SAC» en el detalle («Crédito caducado» o «No caducado · Caduca a las N cuotas atrasadas»).

Consume estos endpoints (según el contrato): GET /api/obligaciones/; GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
- Caducado pero con mora cero → No reporta 03; marcada para revisión
- 3 de 4 atrasos permitidos → Sigue en 01
- Estado anterior 02 y crédito caducado → No cambia: inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF14 · Transición a Dudoso Recaudo. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación se reporta en Dudoso Recaudo (03) cuando su crédito está caducado en el sistema comercial de CENS y su valor de mora es mayor a cero.
Reglas del RF:
- Caducado en el SAC: CREDITOS.CONTATRASOS = CREDITOS.ATRASOS_PERMITIDOS. [Confirmar con CENS que el crédito caducado se reporta en 03 (C-53) y el código de estado.]
- El estado sale de la homologación (RF48: C → 03).
- La Matriz debe permitir el cambio desde el estado del último corte (01, 08 en mora, 04 en mora, 03 en mora o estado de ley).
- Si el valor de mora es cero: no se reporta 03 y se marca para revisión. Si la Matriz no permite el cambio: inconsistencia 713.

Qué probar:
- Vistas y tablas: SAC.CREDITOS (CONTATRASOS, ATRASOS_PERMITIDOS, ESTADO); V_CREDITO_REPORTABLE; NV_HOMOLOGA_ESTADO; NV_TRANSICION_ESTADO
- Endpoints: POST /api/ciclos/; GET /api/obligaciones/{id}/ (bloque en_sac)

Casos mínimos (automatiza todos):
1. 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
2. Caducado pero con mora cero → No reporta 03; marcada para revisión
3. 3 de 4 atrasos permitidos → Sigue en 01
4. Estado anterior 02 y crédito caducado → No cambia: inconsistencia 713

Entrega: tests/test_rf14_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF14 · Transición a Dudoso Recaudo (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: etiqueta «Caducado en el SAC» en la fila (si no está cerrada) y bloque «En el SAC» en el detalle («Crédito caducado» o «No caducado · Caduca a las N cuotas atrasadas»).

Reglas del RF:
- Caducado en el SAC: CREDITOS.CONTATRASOS = CREDITOS.ATRASOS_PERMITIDOS. [Confirmar con CENS que el crédito caducado se reporta en 03 (C-53) y el código de estado.]
- El estado sale de la homologación (RF48: C → 03).
- La Matriz debe permitir el cambio desde el estado del último corte (01, 08 en mora, 04 en mora, 03 en mora o estado de ley).
- Si el valor de mora es cero: no se reporta 03 y se marca para revisión. Si la Matriz no permite el cambio: inconsistencia 713.

Casos mínimos:
1. 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
2. Caducado pero con mora cero → No reporta 03; marcada para revisión
3. 3 de 4 atrasos permitidos → Sigue en 01
4. Estado anterior 02 y crédito caducado → No cambia: inconsistencia 713

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF15 · Cierre en Cartera Recuperada

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF15 · Cierre en Cartera Recuperada. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación que estaba en Castigada (06) o Dudoso Recaudo (03) en mora y recibe el pago total, o se cierra por refinanciación, se reporta en Cartera Recuperada (07).
Reglas del RF:
- Precondición: el último corte enviado la tiene en 03 o 06 en mora y su saldo es cero a la fecha de corte.
- Aplica las validaciones de cierre (RF22) y reporta comportamiento normal, modo de extinción (Tabla 10; 16 si es refinanciación) y tipo de pago.
- Si el pago es parcial se aplica RF17. Si el origen no es 03 o 06 en mora: inconsistencia 713.
- [Confirmar con TransUnion el cierre por refinanciación desde 03 o 06 (P-TU-06).]

Haz esto:
1. Cuando VALOR_SALDO = 0 y el estado anterior es 03 o 06 en mora: ESTADO_TU = 07, con los campos de cierre (igual que RF12). Si el estado anterior es 01, el cierre es 02.
2. Para cierre por refinanciación, MODO_EXTINCION = 16 (usa la detección de RF18).

Usa estos objetos: NV_ESTADO_TU (CIERRE_AL_PAGAR); NV_TRANSICION_ESTADO; NV_REPORTE_DETALLE.

Comprueba con estos casos (datos de prueba v2):
- 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
- Origen 01 con pago total → Va a 02 (RF12), no a 07
- Origen 03 sin mora en el corte anterior → Inconsistencia 713
- Cierre por refinanciación desde 03 → Cierra en 07 con modo 16

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF15 · Cierre en Cartera Recuperada. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación que estaba en Castigada (06) o Dudoso Recaudo (03) en mora y recibe el pago total, o se cierra por refinanciación, se reporta en Cartera Recuperada (07).
Reglas del RF:
- Precondición: el último corte enviado la tiene en 03 o 06 en mora y su saldo es cero a la fecha de corte.
- Aplica las validaciones de cierre (RF22) y reporta comportamiento normal, modo de extinción (Tabla 10; 16 si es refinanciación) y tipo de pago.
- Si el pago es parcial se aplica RF17. Si el origen no es 03 o 06 en mora: inconsistencia 713.
- [Confirmar con TransUnion el cierre por refinanciación desde 03 o 06 (P-TU-06).]

Endpoints a implementar o ajustar: POST /api/ciclos/; GET /api/obligaciones/{id}/.

Haz esto:
1. Reutilizar el mismo servicio de cierre de RF12 (una sola función de cierre con el estado destino como parámetro) y devolver «RF15 · Pago total: Cartera Recuperada».
2. Si el origen no es 03 o 06 en mora: inconsistencia 713 en NV_INCONSISTENCIA.

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE; NV_INCONSISTENCIA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
- Origen 01 con pago total → Va a 02 (RF12), no a 07
- Origen 03 sin mora en el corte anterior → Inconsistencia 713
- Cierre por refinanciación desde 03 → Cierra en 07 con modo 16

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF15 · Cierre en Cartera Recuperada. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación que estaba en Castigada (06) o Dudoso Recaudo (03) en mora y recibe el pago total, o se cierra por refinanciación, se reporta en Cartera Recuperada (07).

Implementa:
1. Pantalla 9, detalle: «Pago total → 07 · Cartera Recuperada (RF15)» en las posibles transiciones desde 03 y 06, y bloque «Cierre» con modo 01 o 16.

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
- Origen 01 con pago total → Va a 02 (RF12), no a 07
- Origen 03 sin mora en el corte anterior → Inconsistencia 713
- Cierre por refinanciación desde 03 → Cierra en 07 con modo 16

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF15 · Cierre en Cartera Recuperada. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación que estaba en Castigada (06) o Dudoso Recaudo (03) en mora y recibe el pago total, o se cierra por refinanciación, se reporta en Cartera Recuperada (07).
Reglas del RF:
- Precondición: el último corte enviado la tiene en 03 o 06 en mora y su saldo es cero a la fecha de corte.
- Aplica las validaciones de cierre (RF22) y reporta comportamiento normal, modo de extinción (Tabla 10; 16 si es refinanciación) y tipo de pago.
- Si el pago es parcial se aplica RF17. Si el origen no es 03 o 06 en mora: inconsistencia 713.
- [Confirmar con TransUnion el cierre por refinanciación desde 03 o 06 (P-TU-06).]

Qué probar:
- Vistas y tablas: NV_ESTADO_TU (CIERRE_AL_PAGAR); NV_TRANSICION_ESTADO; NV_REPORTE_DETALLE
- Endpoints: POST /api/ciclos/; GET /api/obligaciones/{id}/

Casos mínimos (automatiza todos):
1. 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
2. Origen 01 con pago total → Va a 02 (RF12), no a 07
3. Origen 03 sin mora en el corte anterior → Inconsistencia 713
4. Cierre por refinanciación desde 03 → Cierra en 07 con modo 16

Entrega: tests/test_rf15_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF15 · Cierre en Cartera Recuperada (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: «Pago total → 07 · Cartera Recuperada (RF15)» en las posibles transiciones desde 03 y 06, y bloque «Cierre» con modo 01 o 16.

Reglas del RF:
- Precondición: el último corte enviado la tiene en 03 o 06 en mora y su saldo es cero a la fecha de corte.
- Aplica las validaciones de cierre (RF22) y reporta comportamiento normal, modo de extinción (Tabla 10; 16 si es refinanciación) y tipo de pago.
- Si el pago es parcial se aplica RF17. Si el origen no es 03 o 06 en mora: inconsistencia 713.
- [Confirmar con TransUnion el cierre por refinanciación desde 03 o 06 (P-TU-06).]

Casos mínimos:
1. 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
2. Origen 01 con pago total → Va a 02 (RF12), no a 07
3. Origen 03 sin mora en el corte anterior → Inconsistencia 713
4. Cierre por refinanciación desde 03 → Cierra en 07 con modo 16

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF16 · Cartera Recuperada como cierre definitivo

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF16 · Cartera Recuperada como cierre definitivo. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Igual que RF13, pero para Cartera Recuperada (07): se reporta una sola vez y se excluye de los cortes siguientes.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes sin contarla como omitida (RF21).
- Su número de obligación no se reutiliza.
- Si el SAC vuelve a mostrar movimiento: no se reporta y solo se corrige por rectificación (RF55).

Haz esto:
1. Misma lógica de RF13 aplicada al estado 07 (el cierre se detecta con NV_ESTADO_TU.ES_CIERRE = S, que cubre 02 y 07). No duplicar código: una sola regla.

Usa estos objetos: V_CALCULO_CORTE; NV_ESTADO_TU.ES_CIERRE.

Comprueba con estos casos (datos de prueba v2):
- Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar su número → 409 con mensaje claro

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF16 · Cartera Recuperada como cierre definitivo. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Igual que RF13, pero para Cartera Recuperada (07): se reporta una sola vez y se excluye de los cortes siguientes.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes sin contarla como omitida (RF21).
- Su número de obligación no se reutiliza.
- Si el SAC vuelve a mostrar movimiento: no se reporta y solo se corrige por rectificación (RF55).

Endpoints a implementar o ajustar: POST /api/extracciones/{id}/registrar-envio/; GET /api/obligaciones/{id}/.

Haz esto:
1. Reutilizar la función «obligación cerrada» de RF13 para 02 y 07 y la misma alerta de movimiento posterior.

Usa estas tablas, vistas y módulos: NV_OBLIGACION.CIERRE_DEFINITIVO.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar su número → 409 con mensaje claro

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF16 · Cartera Recuperada como cierre definitivo. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Igual que RF13, pero para Cartera Recuperada (07): se reporta una sola vez y se excluye de los cortes siguientes.

Implementa:
1. Pantalla 9: candado y nota «Cartera Recuperada (07) se reporta una sola vez» (misma presentación que RF13).

Consume estos endpoints (según el contrato): GET /api/obligaciones/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
- Intentar reutilizar su número → 409 con mensaje claro

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF16 · Cartera Recuperada como cierre definitivo. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Igual que RF13, pero para Cartera Recuperada (07): se reporta una sola vez y se excluye de los cortes siguientes.
Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes sin contarla como omitida (RF21).
- Su número de obligación no se reutiliza.
- Si el SAC vuelve a mostrar movimiento: no se reporta y solo se corrige por rectificación (RF55).

Qué probar:
- Vistas y tablas: V_CALCULO_CORTE; NV_ESTADO_TU.ES_CIERRE
- Endpoints: POST /api/extracciones/{id}/registrar-envio/; GET /api/obligaciones/{id}/

Casos mínimos (automatiza todos):
1. Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
2. Intentar reutilizar su número → 409 con mensaje claro

Entrega: tests/test_rf16_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF16 · Cartera Recuperada como cierre definitivo (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: candado y nota «Cartera Recuperada (07) se reporta una sola vez» (misma presentación que RF13).

Reglas del RF:
- Se marca como cierre definitivo y se excluye de los cortes siguientes sin contarla como omitida (RF21).
- Su número de obligación no se reutiliza.
- Si el SAC vuelve a mostrar movimiento: no se reporta y solo se corrige por rectificación (RF55).

Casos mínimos:
1. Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
2. Intentar reutilizar su número → 409 con mensaje claro

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF17 · Recálculo por abono parcial

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF17 · Recálculo por abono parcial. Parte de base de datos (V_MORA_OBLIGACION).
Resumen del RF: Cuando un abono no cubre toda la mora, se aplica según la regla de imputación de CENS y se recalculan mora, edad, cuotas en mora, cuotas pagadas y saldo.
Reglas del RF:
- El abono sale de SAC.CLI_PAGOS (RF3) y se aplica por concepto y por cuota con la regla de CENS. [Regla pendiente (C-29); propuesta de trabajo: de la cuota más antigua a la más reciente.]
- Valor de mora = lo vencido que sigue sin pagar. Edad de mora desde la cuota vencida más antigua que quede sin pagar completa: solo baja si el abono paga completas las cuotas más antiguas.
- Se actualizan cuotas en mora (RF19), cuotas pagadas y saldo. Sin reducciones proporcionales ni estimadas.
- Si el abono cubre toda la mora pero hay saldo: RF47. Si cubre todo el saldo: cierre (RF12 o RF15).

Haz esto:
1. Crear V_MORA_OBLIGACION (clave CLIENTE_ID + NUMERO_PROCESO): arma las cuotas vencidas desde SAC.CLI_FACTURACION (FECHA_VENCIMIENTO, TOTAL_FACTURADO; las fechas del SAC son números julianos) y aplica SAC.CLI_PAGOS de la más antigua a la más reciente con funciones analíticas (SUM() OVER).
2. Salida por obligación: VALOR_MORA, CUOTAS_MORA, CUOTAS_PAGADAS, FECHA_EXIGIBILIDAD (vencimiento de la cuota impaga más antigua), DIAS_MORA, VALOR_PAGADO_PERIODO y ORIGEN_DIAS_MORA.
3. Limitación a documentar: la copia del SAC no tiene detalle por concepto de facturas. Si CLI_FACTURACION no alcanza, usar el respaldo actual (CONTATRASOS × VALOR_CUOTA) marcando ORIGEN_DIAS_MORA = ESTIMADO.
4. La regla de imputación debe quedar en un solo bloque, fácil de cambiar cuando CENS responda.

Usa estos objetos: SAC.CLI_FACTURACION; SAC.CLI_PAGOS; SAC.CREDITOS; V_CREDITO_REPORTABLE; V_OBLIGACION_SAC; NV_REPORTE_DETALLE (DIAS_MORA, ORIGEN_DIAS_MORA, VALOR_REAL_PAGADO).

Comprueba con estos casos (datos de prueba v2):
- 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
- Abono menor a una cuota → La cuota sigue vencida; la edad no baja
- Abono que cubre toda la mora y hay saldo → Pasa a RF47 (pago de la mora)
- Abono por todo el saldo → Cierre (RF12 o RF15)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF17 · Recálculo por abono parcial. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Cuando un abono no cubre toda la mora, se aplica según la regla de imputación de CENS y se recalculan mora, edad, cuotas en mora, cuotas pagadas y saldo.
Reglas del RF:
- El abono sale de SAC.CLI_PAGOS (RF3) y se aplica por concepto y por cuota con la regla de CENS. [Regla pendiente (C-29); propuesta de trabajo: de la cuota más antigua a la más reciente.]
- Valor de mora = lo vencido que sigue sin pagar. Edad de mora desde la cuota vencida más antigua que quede sin pagar completa: solo baja si el abono paga completas las cuotas más antiguas.
- Se actualizan cuotas en mora (RF19), cuotas pagadas y saldo. Sin reducciones proporcionales ni estimadas.
- Si el abono cubre toda la mora pero hay saldo: RF47. Si cubre todo el saldo: cierre (RF12 o RF15).

Endpoints a implementar o ajustar: GET /api/obligaciones/{id}/ (cuotas_vencidas y pagos); POST /api/ciclos/.

Haz esto:
1. Reemplazar en el ciclo el cálculo de mora por lo que entrega V_MORA_OBLIGACION.
2. Detalle: cuotas_vencidas [{vencimiento, pendiente, dias}] y pagos [{corte, valor, aplicado_a, nota}].
3. Resultado del ciclo: «RF17 · Pago de $X aplicado a: cuota dd/mm».

Usa estas tablas, vistas y módulos: V_MORA_OBLIGACION; NV_REPORTE_DETALLE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
- Abono menor a una cuota → La cuota sigue vencida; la edad no baja
- Abono que cubre toda la mora y hay saldo → Pasa a RF47 (pago de la mora)
- Abono por todo el saldo → Cierre (RF12 o RF15)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF17 · Recálculo por abono parcial. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Cuando un abono no cubre toda la mora, se aplica según la regla de imputación de CENS y se recalculan mora, edad, cuotas en mora, cuotas pagadas y saldo.

Implementa:
1. Pantalla 9, detalle: tablas «Cuotas vencidas sin pagar» (Vencimiento, Pendiente, Días) y «Pagos extraídos del sistema comercial» (Corte, Valor, Se aplicó a) con la nota «por confirmar» de la imputación.
2. No hay botón para registrar pagos: los pagos vienen del SAC (la maqueta lo aclara en el texto).

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
- Abono menor a una cuota → La cuota sigue vencida; la edad no baja
- Abono que cubre toda la mora y hay saldo → Pasa a RF47 (pago de la mora)
- Abono por todo el saldo → Cierre (RF12 o RF15)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF17 · Recálculo por abono parcial. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: Cuando un abono no cubre toda la mora, se aplica según la regla de imputación de CENS y se recalculan mora, edad, cuotas en mora, cuotas pagadas y saldo.
Reglas del RF:
- El abono sale de SAC.CLI_PAGOS (RF3) y se aplica por concepto y por cuota con la regla de CENS. [Regla pendiente (C-29); propuesta de trabajo: de la cuota más antigua a la más reciente.]
- Valor de mora = lo vencido que sigue sin pagar. Edad de mora desde la cuota vencida más antigua que quede sin pagar completa: solo baja si el abono paga completas las cuotas más antiguas.
- Se actualizan cuotas en mora (RF19), cuotas pagadas y saldo. Sin reducciones proporcionales ni estimadas.
- Si el abono cubre toda la mora pero hay saldo: RF47. Si cubre todo el saldo: cierre (RF12 o RF15).

Qué probar:
- Vistas y tablas: SAC.CLI_FACTURACION; SAC.CLI_PAGOS; SAC.CREDITOS; V_CREDITO_REPORTABLE; V_OBLIGACION_SAC; NV_REPORTE_DETALLE (DIAS_MORA, ORIGEN_DIAS_MORA, VALOR_REAL_PAGADO)
- Endpoints: GET /api/obligaciones/{id}/ (cuotas_vencidas y pagos); POST /api/ciclos/

Casos mínimos (automatiza todos):
1. 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
2. Abono menor a una cuota → La cuota sigue vencida; la edad no baja
3. Abono que cubre toda la mora y hay saldo → Pasa a RF47 (pago de la mora)
4. Abono por todo el saldo → Cierre (RF12 o RF15)

Entrega: tests/test_rf17_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF17 · Recálculo por abono parcial (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Angel, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: tablas «Cuotas vencidas sin pagar» (Vencimiento, Pendiente, Días) y «Pagos extraídos del sistema comercial» (Corte, Valor, Se aplicó a) con la nota «por confirmar» de la imputación.
- No hay botón para registrar pagos: los pagos vienen del SAC (la maqueta lo aclara en el texto).

Reglas del RF:
- El abono sale de SAC.CLI_PAGOS (RF3) y se aplica por concepto y por cuota con la regla de CENS. [Regla pendiente (C-29); propuesta de trabajo: de la cuota más antigua a la más reciente.]
- Valor de mora = lo vencido que sigue sin pagar. Edad de mora desde la cuota vencida más antigua que quede sin pagar completa: solo baja si el abono paga completas las cuotas más antiguas.
- Se actualizan cuotas en mora (RF19), cuotas pagadas y saldo. Sin reducciones proporcionales ni estimadas.
- Si el abono cubre toda la mora pero hay saldo: RF47. Si cubre todo el saldo: cierre (RF12 o RF15).

Casos mínimos:
1. 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
2. Abono menor a una cuota → La cuota sigue vencida; la edad no baja
3. Abono que cubre toda la mora y hay saldo → Pasa a RF47 (pago de la mora)
4. Abono por todo el saldo → Cierre (RF12 o RF15)

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF18 · Refinanciación

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF18 · Refinanciación. Parte de base de datos (V_CALCULO_CORTE v2 y V_REFINANCIACION).
Resumen del RF: Cuando CENS refinancia una obligación, se cierra la original y se registra la nueva con número propio, guardando el vínculo entre ambas en NexoVolt.
Reglas del RF:
- Se identifica por CREDITOS.PROCESO_REFINANCIACION. [Confirmar con CENS que el campo se diligencia.]
- En el mismo corte la original se cierra con modo de extinción 16 «Refinanciación» (Tabla 10): en 02 si estaba en 01 u 08 (RF12) o en 07 si estaba en 03 o 06 en mora (RF15).
- La nueva lleva número nuevo (RF5), «Obligación reestructurada» = 01, la naturaleza de la reestructuración (Tabla 11, por definir con CENS) y el número de reestructuraciones, y se mantiene reestructurada en todos los cortes siguientes (Manual, p. 17).
- El vínculo original → nueva se guarda en NexoVolt (el archivo de TransUnion no tiene campo para ello).
- Si la original está en 04 o de ley (10, 11, 12) no se cierra: se muestra al Analista para definir el tratamiento con CENS.

Haz esto:
1. Detección en V_CALCULO_CORTE: una obligación nueva cuyo NUMERO_PROCESO aparece como PROCESO_REFINANCIACION en un crédito de otro proceso del mismo cliente: columnas OBLIGACION_ORIGEN y REFINANCIACION = S.
2. Vista V_REFINANCIACION (origen, nueva, saldo refinanciado, N_REFINANCIACIONES) con SAC.CREDITOS (PROCESO_REFINANCIACION, NRO_REFINANCIACIONES).
3. OBLIGACION_REFINANCIADA = 01 desde el primer reporte de la nueva en adelante (el parámetro actual 02 solo aplica a las no reestructuradas).

Usa estos objetos: SAC.CREDITOS (PROCESO_REFINANCIACION, NRO_REFINANCIACIONES); NV_OBLIGACION.OBLIGACION_ANTERIOR_ID; NV_REFINANCIACION y NV_NATURALEZA_REESTR (scripts 11 y 10).

Comprueba con estos casos (datos de prueba v2):
- 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado
- Original en 03 en mora → Original en 07 con modo 16
- Original en 04 → No se cierra; aviso al Analista (409 en el registro manual)
- Cuotas 0 o 121 en el registro manual → 400 con mensaje en español

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF18 · Refinanciación. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Cuando CENS refinancia una obligación, se cierra la original y se registra la nueva con número propio, guardando el vínculo entre ambas en NexoVolt.
Reglas del RF:
- Se identifica por CREDITOS.PROCESO_REFINANCIACION. [Confirmar con CENS que el campo se diligencia.]
- En el mismo corte la original se cierra con modo de extinción 16 «Refinanciación» (Tabla 10): en 02 si estaba en 01 u 08 (RF12) o en 07 si estaba en 03 o 06 en mora (RF15).
- La nueva lleva número nuevo (RF5), «Obligación reestructurada» = 01, la naturaleza de la reestructuración (Tabla 11, por definir con CENS) y el número de reestructuraciones, y se mantiene reestructurada en todos los cortes siguientes (Manual, p. 17).
- El vínculo original → nueva se guarda en NexoVolt (el archivo de TransUnion no tiene campo para ello).
- Si la original está en 04 o de ley (10, 11, 12) no se cierra: se muestra al Analista para definir el tratamiento con CENS.

Endpoints a implementar o ajustar: GET /api/refinanciaciones/; POST /api/refinanciaciones/ (registro manual de respaldo); GET /api/catalogos/naturalezas-reestructuracion/.

Haz esto:
1. En el ciclo, por cada refinanciación detectada: cerrar la original con modo 16, crear la nueva enlazada con OBLIGACION_ANTERIOR_ID y escribir la fila de NV_REFINANCIACION con ORIGEN = SAC.
2. POST manual (respaldo si el SAC no diligencia el campo): valida original existente y no cerrada, cuotas entre 1 y 120, fecha menor o igual al corte y naturaleza del catálogo; ORIGEN = MANUAL; todo en la misma transacción.
3. Si la original está en 04, 10, 11 o 12 responder 409 con el mensaje para definir el tratamiento con CENS. Registrar en bitácora.

Usa estas tablas, vistas y módulos: NV_OBLIGACION; NV_REFINANCIACION; NV_NATURALEZA_REESTR; NV_REPORTE_DETALLE; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado
- Original en 03 en mora → Original en 07 con modo 16
- Original en 04 → No se cierra; aviso al Analista (409 en el registro manual)
- Cuotas 0 o 121 en el registro manual → 400 con mensaje en español
- Siguiente ciclo → La nueva sigue marcada como reestructurada

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF18 · Refinanciación. Parte de frontend: pantalla 11 y 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Cuando CENS refinancia una obligación, se cierra la original y se registra la nueva con número propio, guardando el vínculo entre ambas en NexoVolt.

Implementa:
1. Pantalla 11 «Refinanciaciones»: explicación en pasos, tabla (Fecha y registrada por | Obligación original y cierre | Saldo refinanciado | Nueva obligación | Naturaleza (Tabla 11)), botón «Registrar refinanciación» y modal con Obligación original, Naturaleza, Número de cuotas y Fecha, con error por campo.
2. Pantalla 9, detalle: bloque «Obligación reestructurada: 01 · Sí (n) · naturaleza · viene de …» y botón «Registrar refinanciación» solo si la obligación no está cerrada ni eliminada.

Consume estos endpoints (según el contrato): GET /api/refinanciaciones/; POST /api/refinanciaciones/; GET /api/catalogos/naturalezas-reestructuracion/; GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado
- Original en 03 en mora → Original en 07 con modo 16
- Original en 04 → No se cierra; aviso al Analista (409 en el registro manual)
- Cuotas 0 o 121 en el registro manual → 400 con mensaje en español
- Siguiente ciclo → La nueva sigue marcada como reestructurada

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF18 · Refinanciación. Lo implementaron: base de datos Clara y backend Santiago (tú no).
Resumen del RF: Cuando CENS refinancia una obligación, se cierra la original y se registra la nueva con número propio, guardando el vínculo entre ambas en NexoVolt.
Reglas del RF:
- Se identifica por CREDITOS.PROCESO_REFINANCIACION. [Confirmar con CENS que el campo se diligencia.]
- En el mismo corte la original se cierra con modo de extinción 16 «Refinanciación» (Tabla 10): en 02 si estaba en 01 u 08 (RF12) o en 07 si estaba en 03 o 06 en mora (RF15).
- La nueva lleva número nuevo (RF5), «Obligación reestructurada» = 01, la naturaleza de la reestructuración (Tabla 11, por definir con CENS) y el número de reestructuraciones, y se mantiene reestructurada en todos los cortes siguientes (Manual, p. 17).
- El vínculo original → nueva se guarda en NexoVolt (el archivo de TransUnion no tiene campo para ello).
- Si la original está en 04 o de ley (10, 11, 12) no se cierra: se muestra al Analista para definir el tratamiento con CENS.

Qué probar:
- Vistas y tablas: SAC.CREDITOS (PROCESO_REFINANCIACION, NRO_REFINANCIACIONES); NV_OBLIGACION.OBLIGACION_ANTERIOR_ID; NV_REFINANCIACION y NV_NATURALEZA_REESTR (scripts 11 y 10)
- Endpoints: GET /api/refinanciaciones/; POST /api/refinanciaciones/ (registro manual de respaldo); GET /api/catalogos/naturalezas-reestructuracion/

Casos mínimos (automatiza todos):
1. 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado
2. Original en 03 en mora → Original en 07 con modo 16
3. Original en 04 → No se cierra; aviso al Analista (409 en el registro manual)
4. Cuotas 0 o 121 en el registro manual → 400 con mensaje en español
5. Siguiente ciclo → La nueva sigue marcada como reestructurada

Entrega: tests/test_rf18_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF18 · Refinanciación (rol del RF: Analista de Cartera; pantalla del mockup v3: 11 y 9). Lo implementaron Clara, Santiago, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 11 «Refinanciaciones»: explicación en pasos, tabla (Fecha y registrada por | Obligación original y cierre | Saldo refinanciado | Nueva obligación | Naturaleza (Tabla 11)), botón «Registrar refinanciación» y modal con Obligación original, Naturaleza, Número de cuotas y Fecha, con error por campo.
- Pantalla 9, detalle: bloque «Obligación reestructurada: 01 · Sí (n) · naturaleza · viene de …» y botón «Registrar refinanciación» solo si la obligación no está cerrada ni eliminada.

Reglas del RF:
- Se identifica por CREDITOS.PROCESO_REFINANCIACION. [Confirmar con CENS que el campo se diligencia.]
- En el mismo corte la original se cierra con modo de extinción 16 «Refinanciación» (Tabla 10): en 02 si estaba en 01 u 08 (RF12) o en 07 si estaba en 03 o 06 en mora (RF15).
- La nueva lleva número nuevo (RF5), «Obligación reestructurada» = 01, la naturaleza de la reestructuración (Tabla 11, por definir con CENS) y el número de reestructuraciones, y se mantiene reestructurada en todos los cortes siguientes (Manual, p. 17).
- El vínculo original → nueva se guarda en NexoVolt (el archivo de TransUnion no tiene campo para ello).
- Si la original está en 04 o de ley (10, 11, 12) no se cierra: se muestra al Analista para definir el tratamiento con CENS.

Casos mínimos:
1. 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado
2. Original en 03 en mora → Original en 07 con modo 16
3. Original en 04 → No se cierra; aviso al Analista (409 en el registro manual)
4. Cuotas 0 o 121 en el registro manual → 400 con mensaje en español
5. Siguiente ciclo → La nueva sigue marcada como reestructurada

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF19 · Cuotas en mora y coherencia de la mora

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF19 · Cuotas en mora y coherencia de la mora. Parte de base de datos (V_MORA_OBLIGACION y V_VALIDACION_CORTE).
Resumen del RF: En cada corte se cuentan las cuotas en mora de cada obligación y se garantiza su coherencia con la edad y el valor de mora.
Reglas del RF:
- Cuenta las cuotas facturadas, vencidas y no pagadas completas (sin cuotas aún no facturadas).
- Si la edad es mayor a 00, el valor de mora y las cuotas en mora deben ser mayores a cero. Si el valor de mora es cero, las cuotas son cero y la edad es 00.
- Edad mayor a 00 con valor de mora cero: bloquea la obligación en la validación del corte (correctiva 707, RF53). Cuotas incoherentes: alerta informativa.

Haz esto:
1. En V_MORA_OBLIGACION: CUOTAS_MORA = cuotas vencidas con pendiente mayor a cero (reutiliza lo de RF17).
2. En V_VALIDACION_CORTE: mantener EDAD_SIN_VALOR_MORA (CORRECTIVA, 707) y agregar CUOTAS_MORA_INCOHERENTE (INFORMATIVA).

Usa estos objetos: V_MORA_OBLIGACION; V_VALIDACION_CORTE; NV_REPORTE_DETALLE.CUOTAS_MORA.

Comprueba con estos casos (datos de prueba v2):
- Edad 01 con valor de mora cero → Bloquea con la regla 707
- Valor de mora cero con 2 cuotas en mora → Alerta informativa
- Cuota aún no facturada → No cuenta como cuota en mora
- Resumen con 12 obligaciones de prueba → Las 4 agrupaciones suman las obligaciones abiertas

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF19 · Cuotas en mora y coherencia de la mora. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: En cada corte se cuentan las cuotas en mora de cada obligación y se garantiza su coherencia con la edad y el valor de mora.
Reglas del RF:
- Cuenta las cuotas facturadas, vencidas y no pagadas completas (sin cuotas aún no facturadas).
- Si la edad es mayor a 00, el valor de mora y las cuotas en mora deben ser mayores a cero. Si el valor de mora es cero, las cuotas son cero y la edad es 00.
- Edad mayor a 00 con valor de mora cero: bloquea la obligación en la validación del corte (correctiva 707, RF53). Cuotas incoherentes: alerta informativa.

Endpoints a implementar o ajustar: GET /api/obligaciones/resumen/; GET /api/obligaciones/ (cuotas_mora).

Haz esto:
1. Resumen: agrupación al día | 1 cuota | 2 a 3 cuotas | 4 o más, solo de obligaciones abiertas y no eliminadas, a partir del último corte.
2. Incluir cuotas_mora en el listado y en el detalle.

Usa estas tablas, vistas y módulos: NV_REPORTE_DETALLE; V_ULTIMO_REPORTE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Edad 01 con valor de mora cero → Bloquea con la regla 707
- Valor de mora cero con 2 cuotas en mora → Alerta informativa
- Cuota aún no facturada → No cuenta como cuota en mora
- Resumen con 12 obligaciones de prueba → Las 4 agrupaciones suman las obligaciones abiertas

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF19 · Cuotas en mora y coherencia de la mora. Parte de frontend: pantalla 9 y 4 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: En cada corte se cuentan las cuotas en mora de cada obligación y se garantiza su coherencia con la edad y el valor de mora.

Implementa:
1. Pantalla 9: tarjeta «Cuotas en mora por obligación» con las 4 agrupaciones y columna «Valor en Mora y Cuotas en Mora» con insignia (Al día, 1 cuota en mora, N cuotas en mora).
2. Panel (pantalla 4): tarjeta «Obligaciones con 2 o más cuotas en mora» que enlaza a la pantalla 9.

Consume estos endpoints (según el contrato): GET /api/obligaciones/resumen/; GET /api/obligaciones/; GET /api/panel/resumen/.

Pruebas con vitest (y MSW) para estos casos:
- Edad 01 con valor de mora cero → Bloquea con la regla 707
- Valor de mora cero con 2 cuotas en mora → Alerta informativa
- Cuota aún no facturada → No cuenta como cuota en mora
- Resumen con 12 obligaciones de prueba → Las 4 agrupaciones suman las obligaciones abiertas

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF19 · Cuotas en mora y coherencia de la mora. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: En cada corte se cuentan las cuotas en mora de cada obligación y se garantiza su coherencia con la edad y el valor de mora.
Reglas del RF:
- Cuenta las cuotas facturadas, vencidas y no pagadas completas (sin cuotas aún no facturadas).
- Si la edad es mayor a 00, el valor de mora y las cuotas en mora deben ser mayores a cero. Si el valor de mora es cero, las cuotas son cero y la edad es 00.
- Edad mayor a 00 con valor de mora cero: bloquea la obligación en la validación del corte (correctiva 707, RF53). Cuotas incoherentes: alerta informativa.

Qué probar:
- Vistas y tablas: V_MORA_OBLIGACION; V_VALIDACION_CORTE; NV_REPORTE_DETALLE.CUOTAS_MORA
- Endpoints: GET /api/obligaciones/resumen/; GET /api/obligaciones/ (cuotas_mora)

Casos mínimos (automatiza todos):
1. Edad 01 con valor de mora cero → Bloquea con la regla 707
2. Valor de mora cero con 2 cuotas en mora → Alerta informativa
3. Cuota aún no facturada → No cuenta como cuota en mora
4. Resumen con 12 obligaciones de prueba → Las 4 agrupaciones suman las obligaciones abiertas

Entrega: tests/test_rf19_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF19 · Cuotas en mora y coherencia de la mora (rol del RF: Analista de Cartera; pantalla del mockup v3: 9 y 4). Lo implementaron Angel, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: tarjeta «Cuotas en mora por obligación» con las 4 agrupaciones y columna «Valor en Mora y Cuotas en Mora» con insignia (Al día, 1 cuota en mora, N cuotas en mora).
- Panel (pantalla 4): tarjeta «Obligaciones con 2 o más cuotas en mora» que enlaza a la pantalla 9.

Reglas del RF:
- Cuenta las cuotas facturadas, vencidas y no pagadas completas (sin cuotas aún no facturadas).
- Si la edad es mayor a 00, el valor de mora y las cuotas en mora deben ser mayores a cero. Si el valor de mora es cero, las cuotas son cero y la edad es 00.
- Edad mayor a 00 con valor de mora cero: bloquea la obligación en la validación del corte (correctiva 707, RF53). Cuotas incoherentes: alerta informativa.

Casos mínimos:
1. Edad 01 con valor de mora cero → Bloquea con la regla 707
2. Valor de mora cero con 2 cuotas en mora → Alerta informativa
3. Cuota aún no facturada → No cuenta como cuota en mora
4. Resumen con 12 obligaciones de prueba → Las 4 agrupaciones suman las obligaciones abiertas

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF20 · Generación del archivo plano del reporte total

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF20 · Generación del archivo plano del reporte total. Parte de base de datos (V_REPORTE_TU v2).
Resumen del RF: Cada mes se genera el archivo del reporte total con la estructura completa del Manual (págs. 44 a 52): registro tipo 1, registros tipo 2 y registro tipo 9, en texto plano de longitud fija y codificación ANSI (Windows-1252).
Reglas del RF:
- Precondición: el corte está VALIDADO sin inconsistencias correctivas (RF53) y la entidad está parametrizada o con marcador (RF57).
- Registro tipo 1 (29 caracteres): «1», código de paquete 11 (Sector Real Servicios), tipo de entidad, código de entidad, 10 espacios reservados, tipo de reporte 01 (total) y fecha de corte AAAAMMDD.
- Registro tipo 2: uno por obligación y titular, cada campo en su posición y longitud (Tabla 2 del Manual, columna Real Servicios). Lo que no aplica va en espacios, incluida la línea de crédito; la categoría de servicios es 04. [El Manual declara 930 caracteres y sus campos suman 929: confirmar con TransUnion.]
- Registro tipo 9 (33 caracteres): total de registros (incluye el 1 y el 9), número de registros tipo 2, tipo 3 y tipo 4.
- Formato: números sin decimales, a la derecha y con ceros a la izquierda; alfanuméricos de tabla en mayúsculas, a la izquierda con espacios a la derecha; número de obligación a la derecha con espacios a la izquierda; identificación con ceros a la izquierda; fechas AAAAMMDD; campo vacío en espacios (no es cero).
- Nombre del archivo: SSR + tipo de entidad (3) + código de entidad (3) + fecha de corte (AAAAMMDD).
- Si un campo excede su longitud o no es de su tipo, no se genera y se indica la obligación y el campo. Si los conteos del tipo 9 no coinciden, no se genera.

Haz esto:
1. Ampliar V_REPORTE_TU con todo lo que necesita el registro tipo 2: FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO, FECHA_EXIGIBILIDAD, ANIOS_MORA, CUOTAS_PAGADAS, ESTADO_CONTRATO, OBLIGACION_REESTRUCTURADA, NATURALEZA_REESTR y N_REESTRUCTURACIONES (columnas de NV_REPORTE_DETALLE, script 10).
2. Dejar en la vista los valores en PESOS y que el backend los convierta a miles (RF51): una sola conversión. Acordarlo con Dilan y quitar el ROUND(/DIVISOR_VALORES) de la vista solo cuando Dilan lo confirme.
3. La vista devuelve únicamente obligaciones con INCLUIR = S del corte, una fila por obligación y titular.

Usa estos objetos: V_REPORTE_TU; NV_REPORTE_DETALLE; NV_OBLIGACION; V_CONFIG; NV_PARAMETRO (TIPO_ENTIDAD, CODIGO_ENTIDAD, CODIGO_SUCURSAL, CODIGO_PAQUETE, TIPO_REPORTE).

Comprueba con estos casos (datos de prueba v2):
- Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
- Nombre del archivo con marcadores XXX, XXX → SSRXXXXXX + fecha de corte; APTO_ENVIO = N
- Nombre con tipo 001 y código 123 de prueba → SSR001123 + fecha; APTO_ENVIO = S
- Nombre con una tilde (Ñ, Á) → Se codifica en cp1252 sin romper la longitud

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF20 · Generación del archivo plano del reporte total. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Cada mes se genera el archivo del reporte total con la estructura completa del Manual (págs. 44 a 52): registro tipo 1, registros tipo 2 y registro tipo 9, en texto plano de longitud fija y codificación ANSI (Windows-1252).
Reglas del RF:
- Precondición: el corte está VALIDADO sin inconsistencias correctivas (RF53) y la entidad está parametrizada o con marcador (RF57).
- Registro tipo 1 (29 caracteres): «1», código de paquete 11 (Sector Real Servicios), tipo de entidad, código de entidad, 10 espacios reservados, tipo de reporte 01 (total) y fecha de corte AAAAMMDD.
- Registro tipo 2: uno por obligación y titular, cada campo en su posición y longitud (Tabla 2 del Manual, columna Real Servicios). Lo que no aplica va en espacios, incluida la línea de crédito; la categoría de servicios es 04. [El Manual declara 930 caracteres y sus campos suman 929: confirmar con TransUnion.]
- Registro tipo 9 (33 caracteres): total de registros (incluye el 1 y el 9), número de registros tipo 2, tipo 3 y tipo 4.
- Formato: números sin decimales, a la derecha y con ceros a la izquierda; alfanuméricos de tabla en mayúsculas, a la izquierda con espacios a la derecha; número de obligación a la derecha con espacios a la izquierda; identificación con ceros a la izquierda; fechas AAAAMMDD; campo vacío en espacios (no es cero).
- Nombre del archivo: SSR + tipo de entidad (3) + código de entidad (3) + fecha de corte (AAAAMMDD).
- Si un campo excede su longitud o no es de su tipo, no se genera y se indica la obligación y el campo. Si los conteos del tipo 9 no coinciden, no se genera.

Endpoints a implementar o ajustar: POST /api/extracciones/{id}/archivo/; GET /api/archivos/; GET /api/archivos/{id}/descarga/.

Haz esto:
1. Crear un módulo generador con una tabla de layout (campo, posición inicial, longitud, tipo, relleno, alineación, columna origen) transcrita de la Tabla 2 del Manual v34. Nada de números sueltos en el código.
2. Armar tipo 1, tipo 2 y tipo 9; codificar en cp1252; terminar cada línea con CRLF; validar la longitud de cada campo y que todas las líneas tipo 2 midan exactamente lo mismo.
3. Nombrar el archivo (SSR + tipo + código + fecha) y guardarlo en NV_ARCHIVO con el contenido, N_REGISTROS, N_EXCLUIDAS, SALDO_TOTAL y APTO_ENVIO = N si algún parámetro de la entidad tiene marcador (RF57).
4. Solo si el corte está VALIDADO (409 con mensaje si no). Si un campo no cabe, 422 con {obligacion, campo, valor}. Bitácora «Archivo plano generado».

Usa estas tablas, vistas y módulos: V_REPORTE_TU; NV_ARCHIVO; NV_CORTE; NV_PARAMETRO; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
- Nombre del archivo con marcadores XXX, XXX → SSRXXXXXX + fecha de corte; APTO_ENVIO = N
- Nombre con tipo 001 y código 123 de prueba → SSR001123 + fecha; APTO_ENVIO = S
- Nombre con una tilde (Ñ, Á) → Se codifica en cp1252 sin romper la longitud
- Campo más largo que su posición → No genera; error con obligación y campo
- Corte en BORRADOR → 409: debe estar validado

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF20 · Generación del archivo plano del reporte total. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Cada mes se genera el archivo del reporte total con la estructura completa del Manual (págs. 44 a 52): registro tipo 1, registros tipo 2 y registro tipo 9, en texto plano de longitud fija y codificación ANSI (Windows-1252).

Implementa:
1. Pantalla 12 «Reporte a TransUnion»: selector de fecha de corte, botón «Generar archivo plano» con el avance por pasos, tarjeta «Archivo generado» con «Descargar archivo» y la tabla «Archivos generados» (Fecha y hora, Usuario, Fecha de corte, Obligaciones, Saldo, Archivo, Estado, Acciones).
2. Aviso persistente cuando la entidad tiene marcador: «no apto para envío» (RF57) y el botón «Registrar envío» deshabilitado en ese caso.

Consume estos endpoints (según el contrato): POST /api/extracciones/{id}/archivo/; GET /api/archivos/; GET /api/archivos/{id}/descarga/; GET /api/entidad/.

Pruebas con vitest (y MSW) para estos casos:
- Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
- Nombre del archivo con marcadores XXX, XXX → SSRXXXXXX + fecha de corte; APTO_ENVIO = N
- Nombre con tipo 001 y código 123 de prueba → SSR001123 + fecha; APTO_ENVIO = S
- Nombre con una tilde (Ñ, Á) → Se codifica en cp1252 sin romper la longitud
- Campo más largo que su posición → No genera; error con obligación y campo

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF20 · Generación del archivo plano del reporte total. Lo implementaron: base de datos Angel y backend Dilan (tú no).
Resumen del RF: Cada mes se genera el archivo del reporte total con la estructura completa del Manual (págs. 44 a 52): registro tipo 1, registros tipo 2 y registro tipo 9, en texto plano de longitud fija y codificación ANSI (Windows-1252).
Reglas del RF:
- Precondición: el corte está VALIDADO sin inconsistencias correctivas (RF53) y la entidad está parametrizada o con marcador (RF57).
- Registro tipo 1 (29 caracteres): «1», código de paquete 11 (Sector Real Servicios), tipo de entidad, código de entidad, 10 espacios reservados, tipo de reporte 01 (total) y fecha de corte AAAAMMDD.
- Registro tipo 2: uno por obligación y titular, cada campo en su posición y longitud (Tabla 2 del Manual, columna Real Servicios). Lo que no aplica va en espacios, incluida la línea de crédito; la categoría de servicios es 04. [El Manual declara 930 caracteres y sus campos suman 929: confirmar con TransUnion.]
- Registro tipo 9 (33 caracteres): total de registros (incluye el 1 y el 9), número de registros tipo 2, tipo 3 y tipo 4.
- Formato: números sin decimales, a la derecha y con ceros a la izquierda; alfanuméricos de tabla en mayúsculas, a la izquierda con espacios a la derecha; número de obligación a la derecha con espacios a la izquierda; identificación con ceros a la izquierda; fechas AAAAMMDD; campo vacío en espacios (no es cero).
- Nombre del archivo: SSR + tipo de entidad (3) + código de entidad (3) + fecha de corte (AAAAMMDD).
- Si un campo excede su longitud o no es de su tipo, no se genera y se indica la obligación y el campo. Si los conteos del tipo 9 no coinciden, no se genera.

Qué probar:
- Vistas y tablas: V_REPORTE_TU; NV_REPORTE_DETALLE; NV_OBLIGACION; V_CONFIG; NV_PARAMETRO (TIPO_ENTIDAD, CODIGO_ENTIDAD, CODIGO_SUCURSAL, CODIGO_PAQUETE, TIPO_REPORTE)
- Endpoints: POST /api/extracciones/{id}/archivo/; GET /api/archivos/; GET /api/archivos/{id}/descarga/

Casos mínimos (automatiza todos):
1. Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
2. Nombre del archivo con marcadores XXX, XXX → SSRXXXXXX + fecha de corte; APTO_ENVIO = N
3. Nombre con tipo 001 y código 123 de prueba → SSR001123 + fecha; APTO_ENVIO = S
4. Nombre con una tilde (Ñ, Á) → Se codifica en cp1252 sin romper la longitud
5. Campo más largo que su posición → No genera; error con obligación y campo
6. Corte en BORRADOR → 409: debe estar validado
7. Conteos del tipo 9 → Coinciden con los registros generados

Entrega: tests/test_rf20_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF20 · Generación del archivo plano del reporte total (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Angel, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12 «Reporte a TransUnion»: selector de fecha de corte, botón «Generar archivo plano» con el avance por pasos, tarjeta «Archivo generado» con «Descargar archivo» y la tabla «Archivos generados» (Fecha y hora, Usuario, Fecha de corte, Obligaciones, Saldo, Archivo, Estado, Acciones).
- Aviso persistente cuando la entidad tiene marcador: «no apto para envío» (RF57) y el botón «Registrar envío» deshabilitado en ese caso.

Reglas del RF:
- Precondición: el corte está VALIDADO sin inconsistencias correctivas (RF53) y la entidad está parametrizada o con marcador (RF57).
- Registro tipo 1 (29 caracteres): «1», código de paquete 11 (Sector Real Servicios), tipo de entidad, código de entidad, 10 espacios reservados, tipo de reporte 01 (total) y fecha de corte AAAAMMDD.
- Registro tipo 2: uno por obligación y titular, cada campo en su posición y longitud (Tabla 2 del Manual, columna Real Servicios). Lo que no aplica va en espacios, incluida la línea de crédito; la categoría de servicios es 04. [El Manual declara 930 caracteres y sus campos suman 929: confirmar con TransUnion.]
- Registro tipo 9 (33 caracteres): total de registros (incluye el 1 y el 9), número de registros tipo 2, tipo 3 y tipo 4.
- Formato: números sin decimales, a la derecha y con ceros a la izquierda; alfanuméricos de tabla en mayúsculas, a la izquierda con espacios a la derecha; número de obligación a la derecha con espacios a la izquierda; identificación con ceros a la izquierda; fechas AAAAMMDD; campo vacío en espacios (no es cero).
- Nombre del archivo: SSR + tipo de entidad (3) + código de entidad (3) + fecha de corte (AAAAMMDD).
- Si un campo excede su longitud o no es de su tipo, no se genera y se indica la obligación y el campo. Si los conteos del tipo 9 no coinciden, no se genera.

Casos mínimos:
1. Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
2. Nombre del archivo con marcadores XXX, XXX → SSRXXXXXX + fecha de corte; APTO_ENVIO = N
3. Nombre con tipo 001 y código 123 de prueba → SSR001123 + fecha; APTO_ENVIO = S
4. Nombre con una tilde (Ñ, Á) → Se codifica en cp1252 sin romper la longitud
5. Campo más largo que su posición → No genera; error con obligación y campo
6. Corte en BORRADOR → 409: debe estar validado
7. Conteos del tipo 9 → Coinciden con los registros generados

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF21 · Universo del reporte total

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF21 · Universo del reporte total. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: El archivo mensual incluye todas las obligaciones vigentes a la fecha de corte, más las reportadas antes que no estén cerradas ni eliminadas, aunque ya no aparezcan vigentes en el sistema comercial.
Reglas del RF:
- Incluye las vigentes del sistema comercial.
- Incluye las del último corte enviado que no estén cerradas (estado distinto de 02 y 07) ni eliminadas (RF50): las que se pagaron en el periodo con su estado de cierre (RF12, RF15) y las que están en 03, 04, 06 o de ley.
- Excluye las cerradas en cortes anteriores (RF13, RF16) y las eliminadas (RF50).
- Antes de validar compara contra el último corte enviado: si una obligación activa no tiene registro en el nuevo corte, bloquea la validación y la muestra (TransUnion la marcaría como no reportada, R).

Haz esto:
1. El universo hoy sale solo de V_OBLIGACION_SAC (créditos vigentes en el SAC). Agregar las obligaciones del último corte ENVIADO que no estén cerradas (NV_ESTADO_TU.ES_CIERRE = N) ni eliminadas (NV_OBLIGACION.ELIMINADA = N) aunque el SAC ya no las muestre como vigentes.
2. Mantener INCLUIR/MOTIVO_EXCLUSION para las cerradas y eliminadas (YA_CERRADA_EN_TU, ELIMINADA).
3. La regla que bloquea por omisión (OMISION_VS_ULTIMO_CORTE) es de V_VALIDACION_CORTE: la escribe Angel en RF53; esta parte deja listo el universo.

Usa estos objetos: V_CALCULO_CORTE; V_ULTIMO_REPORTE; V_OBLIGACION_SAC; NV_OBLIGACION.ELIMINADA; NV_ESTADO_TU.

Comprueba con estos casos (datos de prueba v2):
- Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
- Obligación 02 del corte anterior → Se excluye sin contarla como omitida
- Obligación activa del último corte sin registro en el nuevo → Bloquea la validación
- Obligación eliminada (RF50) → No se incluye

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF21 · Universo del reporte total. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: El archivo mensual incluye todas las obligaciones vigentes a la fecha de corte, más las reportadas antes que no estén cerradas ni eliminadas, aunque ya no aparezcan vigentes en el sistema comercial.
Reglas del RF:
- Incluye las vigentes del sistema comercial.
- Incluye las del último corte enviado que no estén cerradas (estado distinto de 02 y 07) ni eliminadas (RF50): las que se pagaron en el periodo con su estado de cierre (RF12, RF15) y las que están en 03, 04, 06 o de ley.
- Excluye las cerradas en cortes anteriores (RF13, RF16) y las eliminadas (RF50).
- Antes de validar compara contra el último corte enviado: si una obligación activa no tiene registro en el nuevo corte, bloquea la validación y la muestra (TransUnion la marcaría como no reportada, R).

Endpoints a implementar o ajustar: GET /api/extracciones/{id}/validaciones/ (incluye omisiones); POST /api/extracciones/{id}/validar/.

Haz esto:
1. Antes de validar el corte, ejecutar la comparación contra el último corte enviado y devolver las omisiones como correctivas.
2. Devolver en el resumen del corte: incluidas, excluidas por cerradas, excluidas por eliminadas y omitidas.

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE; V_VALIDACION_CORTE; cartera/servicios.py (validar_corte).
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
- Obligación 02 del corte anterior → Se excluye sin contarla como omitida
- Obligación activa del último corte sin registro en el nuevo → Bloquea la validación
- Obligación eliminada (RF50) → No se incluye

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF21 · Universo del reporte total. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: El archivo mensual incluye todas las obligaciones vigentes a la fecha de corte, más las reportadas antes que no estén cerradas ni eliminadas, aunque ya no aparezcan vigentes en el sistema comercial.

Implementa:
1. Pantalla 12, «Validaciones antes de generar»: ítem de omisiones («N de N obligaciones activas del último corte incluidas») y, si falta alguna, la lista con enlace a la obligación.

Consume estos endpoints (según el contrato): GET /api/extracciones/{id}/validaciones/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
- Obligación 02 del corte anterior → Se excluye sin contarla como omitida
- Obligación activa del último corte sin registro en el nuevo → Bloquea la validación
- Obligación eliminada (RF50) → No se incluye

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF21 · Universo del reporte total. Lo implementaron: base de datos Clara y backend Dilan (tú no).
Resumen del RF: El archivo mensual incluye todas las obligaciones vigentes a la fecha de corte, más las reportadas antes que no estén cerradas ni eliminadas, aunque ya no aparezcan vigentes en el sistema comercial.
Reglas del RF:
- Incluye las vigentes del sistema comercial.
- Incluye las del último corte enviado que no estén cerradas (estado distinto de 02 y 07) ni eliminadas (RF50): las que se pagaron en el periodo con su estado de cierre (RF12, RF15) y las que están en 03, 04, 06 o de ley.
- Excluye las cerradas en cortes anteriores (RF13, RF16) y las eliminadas (RF50).
- Antes de validar compara contra el último corte enviado: si una obligación activa no tiene registro en el nuevo corte, bloquea la validación y la muestra (TransUnion la marcaría como no reportada, R).

Qué probar:
- Vistas y tablas: V_CALCULO_CORTE; V_ULTIMO_REPORTE; V_OBLIGACION_SAC; NV_OBLIGACION.ELIMINADA; NV_ESTADO_TU
- Endpoints: GET /api/extracciones/{id}/validaciones/ (incluye omisiones); POST /api/extracciones/{id}/validar/

Casos mínimos (automatiza todos):
1. Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
2. Obligación 02 del corte anterior → Se excluye sin contarla como omitida
3. Obligación activa del último corte sin registro en el nuevo → Bloquea la validación
4. Obligación eliminada (RF50) → No se incluye

Entrega: tests/test_rf21_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF21 · Universo del reporte total (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Clara, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12, «Validaciones antes de generar»: ítem de omisiones («N de N obligaciones activas del último corte incluidas») y, si falta alguna, la lista con enlace a la obligación.

Reglas del RF:
- Incluye las vigentes del sistema comercial.
- Incluye las del último corte enviado que no estén cerradas (estado distinto de 02 y 07) ni eliminadas (RF50): las que se pagaron en el periodo con su estado de cierre (RF12, RF15) y las que están en 03, 04, 06 o de ley.
- Excluye las cerradas en cortes anteriores (RF13, RF16) y las eliminadas (RF50).
- Antes de validar compara contra el último corte enviado: si una obligación activa no tiene registro en el nuevo corte, bloquea la validación y la muestra (TransUnion la marcaría como no reportada, R).

Casos mínimos:
1. Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
2. Obligación 02 del corte anterior → Se excluye sin contarla como omitida
3. Obligación activa del último corte sin registro en el nuevo → Bloquea la validación
4. Obligación eliminada (RF50) → No se incluye

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF22 · Validación de cierre

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF22 · Validación de cierre. Parte de base de datos (V_VALIDACION_CORTE v2).
Resumen del RF: Antes de reportar una obligación como Saldada (02) o Cartera Recuperada (07) se validan todos los campos de cierre del Manual, sin corregir ningún dato automáticamente.
Reglas del RF:
- Saldo, valor de mora, cuotas en mora y valor de la cuota en cero, y edad de mora 00.
- Número de cuotas pagadas mayor a cero y estado del contrato 002 (No vigente).
- Fecha de pago menor o igual a la fecha de corte y mayor o igual a la fecha de inicio.
- Modo de extinción (Tabla 10) y tipo de pago (Tabla 31) diligenciados; si el tipo de pago es Voluntario (01), el modo debe ser Voluntario (01), salvo en refinanciación (16).
- Si alguna falla: no se reporta el cierre, no se modifica ningún valor y se registra la inconsistencia. El Analista corrige en el origen.

Haz esto:
1. Reemplazar la regla CIERRE_CON_SALDO por CIERRE_INCOMPLETO (CORRECTIVA) con cada condición del RF (una regla por condición, con mensaje que diga cuál falla): saldo/mora/cuota/cuotas en cero, edad 00, cuotas pagadas > 0, estado del contrato 002, fecha de pago entre inicio y corte, modo y tipo diligenciados y su coherencia.
2. No corregir nada en la vista: solo detectar.

Usa estos objetos: V_VALIDACION_CORTE; NV_REPORTE_DETALLE (CUOTAS_PAGADAS, ESTADO_CONTRATO, FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO); NV_ESTADO_TU.ES_CIERRE.

Comprueba con estos casos (datos de prueba v2):
- Cierre completo (2259-1092) → Pasa la validación
- Cierre sin fecha de pago → Correctiva; no se reporta el cierre
- Cierre con cuota distinta de cero → Correctiva; el valor NO se cambia a cero
- Tipo de pago 01 con modo distinto de 01 (sin refinanciación) → Correctiva

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF22 · Validación de cierre. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Antes de reportar una obligación como Saldada (02) o Cartera Recuperada (07) se validan todos los campos de cierre del Manual, sin corregir ningún dato automáticamente.
Reglas del RF:
- Saldo, valor de mora, cuotas en mora y valor de la cuota en cero, y edad de mora 00.
- Número de cuotas pagadas mayor a cero y estado del contrato 002 (No vigente).
- Fecha de pago menor o igual a la fecha de corte y mayor o igual a la fecha de inicio.
- Modo de extinción (Tabla 10) y tipo de pago (Tabla 31) diligenciados; si el tipo de pago es Voluntario (01), el modo debe ser Voluntario (01), salvo en refinanciación (16).
- Si alguna falla: no se reporta el cierre, no se modifica ningún valor y se registra la inconsistencia. El Analista corrige en el origen.

Endpoints a implementar o ajustar: GET /api/extracciones/{id}/validaciones/; POST /api/extracciones/{id}/validar/.

Haz esto:
1. Mostrar las fallas de cierre por obligación (REGLA, MENSAJE) dentro de la lista de correctivas del corte y bloquear la validación si existen.
2. Confirmar que el servicio de cierre (RF12 y RF15) no modifique ningún valor cuando falla una condición.

Usa estas tablas, vistas y módulos: V_VALIDACION_CORTE; NV_INCONSISTENCIA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Cierre completo (2259-1092) → Pasa la validación
- Cierre sin fecha de pago → Correctiva; no se reporta el cierre
- Cierre con cuota distinta de cero → Correctiva; el valor NO se cambia a cero
- Tipo de pago 01 con modo distinto de 01 (sin refinanciación) → Correctiva
- Cierre por refinanciación con modo 16 → Pasa

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF22 · Validación de cierre. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Antes de reportar una obligación como Saldada (02) o Cartera Recuperada (07) se validan todos los campos de cierre del Manual, sin corregir ningún dato automáticamente.

Implementa:
1. Pantalla 12, «Validaciones antes de generar»: ítem «Campos de cierre (RF22)» con el estado correcto o error y la lista de obligaciones que fallan indicando qué campo falta.

Consume estos endpoints (según el contrato): GET /api/extracciones/{id}/validaciones/.

Pruebas con vitest (y MSW) para estos casos:
- Cierre completo (2259-1092) → Pasa la validación
- Cierre sin fecha de pago → Correctiva; no se reporta el cierre
- Cierre con cuota distinta de cero → Correctiva; el valor NO se cambia a cero
- Tipo de pago 01 con modo distinto de 01 (sin refinanciación) → Correctiva
- Cierre por refinanciación con modo 16 → Pasa

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF22 · Validación de cierre. Lo implementaron: base de datos Angel y backend Dilan (tú no).
Resumen del RF: Antes de reportar una obligación como Saldada (02) o Cartera Recuperada (07) se validan todos los campos de cierre del Manual, sin corregir ningún dato automáticamente.
Reglas del RF:
- Saldo, valor de mora, cuotas en mora y valor de la cuota en cero, y edad de mora 00.
- Número de cuotas pagadas mayor a cero y estado del contrato 002 (No vigente).
- Fecha de pago menor o igual a la fecha de corte y mayor o igual a la fecha de inicio.
- Modo de extinción (Tabla 10) y tipo de pago (Tabla 31) diligenciados; si el tipo de pago es Voluntario (01), el modo debe ser Voluntario (01), salvo en refinanciación (16).
- Si alguna falla: no se reporta el cierre, no se modifica ningún valor y se registra la inconsistencia. El Analista corrige en el origen.

Qué probar:
- Vistas y tablas: V_VALIDACION_CORTE; NV_REPORTE_DETALLE (CUOTAS_PAGADAS, ESTADO_CONTRATO, FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO); NV_ESTADO_TU.ES_CIERRE
- Endpoints: GET /api/extracciones/{id}/validaciones/; POST /api/extracciones/{id}/validar/

Casos mínimos (automatiza todos):
1. Cierre completo (2259-1092) → Pasa la validación
2. Cierre sin fecha de pago → Correctiva; no se reporta el cierre
3. Cierre con cuota distinta de cero → Correctiva; el valor NO se cambia a cero
4. Tipo de pago 01 con modo distinto de 01 (sin refinanciación) → Correctiva
5. Cierre por refinanciación con modo 16 → Pasa

Entrega: tests/test_rf22_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF22 · Validación de cierre (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Angel, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12, «Validaciones antes de generar»: ítem «Campos de cierre (RF22)» con el estado correcto o error y la lista de obligaciones que fallan indicando qué campo falta.

Reglas del RF:
- Saldo, valor de mora, cuotas en mora y valor de la cuota en cero, y edad de mora 00.
- Número de cuotas pagadas mayor a cero y estado del contrato 002 (No vigente).
- Fecha de pago menor o igual a la fecha de corte y mayor o igual a la fecha de inicio.
- Modo de extinción (Tabla 10) y tipo de pago (Tabla 31) diligenciados; si el tipo de pago es Voluntario (01), el modo debe ser Voluntario (01), salvo en refinanciación (16).
- Si alguna falla: no se reporta el cierre, no se modifica ningún valor y se registra la inconsistencia. El Analista corrige en el origen.

Casos mínimos:
1. Cierre completo (2259-1092) → Pasa la validación
2. Cierre sin fecha de pago → Correctiva; no se reporta el cierre
3. Cierre con cuota distinta de cero → Correctiva; el valor NO se cambia a cero
4. Tipo de pago 01 con modo distinto de 01 (sin refinanciación) → Correctiva
5. Cierre por refinanciación con modo 16 → Pasa

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF23 · Registro de reclamos de Habeas Data

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF23 · Registro de reclamos de Habeas Data. Parte de base de datos (Script 11 (NV_RECLAMO)).
Resumen del RF: El Analista registra los reclamos de los titulares y el sistema prepara el insumo para el proceso de «Marcación de obligaciones (Reclamos Batch)» de TransUnion. La obligación en reclamo se sigue reportando en el archivo total.
Reglas del RF:
- El Analista registra tipología (válida según la Ley 1266 y la lista de TransUnion), fecha de radicación y obligación.
- El sistema genera el insumo para la marcación batch de TransUnion y mantiene la obligación en el reporte total (no se «aísla»).
- Al cerrar el reclamo se registran la respuesta y el cierre, y se genera el insumo de desmarcación.
- Los archivos de radicación, cierre e inconsistencias los devuelve TransUnion y se cargan con RF54.
- Si la tipología no es válida no se registra. Si supera el plazo legal (15 días hábiles, prorrogables 8) se alerta al Analista.

Haz esto:
1. Crear NV_RECLAMO y NV_TIPOLOGIA_RECLAMO con las llaves, los CHECK de ESTADO y los índices (OBLIGACION_ID, ESTADO) y (FECHA_LIMITE_RESPUESTA).
2. Una obligación puede tener varios reclamos a lo largo del tiempo, pero solo uno EN_RECLAMO a la vez (índice único parcial por OBLIGACION_ID donde ESTADO = EN_RECLAMO).

Usa estos objetos: NV_RECLAMO; NV_TIPOLOGIA_RECLAMO; NV_OBLIGACION.

Comprueba con estos casos (datos de prueba v2):
- Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo
- Segundo reclamo abierto sobre la misma obligación → 409 en español
- Tipología fuera del catálogo → 400
- Cerrar con fecha anterior a la radicación → 400 en el campo fecha_cierre

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF23 · Registro de reclamos de Habeas Data. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: El Analista registra los reclamos de los titulares y el sistema prepara el insumo para el proceso de «Marcación de obligaciones (Reclamos Batch)» de TransUnion. La obligación en reclamo se sigue reportando en el archivo total.
Reglas del RF:
- El Analista registra tipología (válida según la Ley 1266 y la lista de TransUnion), fecha de radicación y obligación.
- El sistema genera el insumo para la marcación batch de TransUnion y mantiene la obligación en el reporte total (no se «aísla»).
- Al cerrar el reclamo se registran la respuesta y el cierre, y se genera el insumo de desmarcación.
- Los archivos de radicación, cierre e inconsistencias los devuelve TransUnion y se cargan con RF54.
- Si la tipología no es válida no se registra. Si supera el plazo legal (15 días hábiles, prorrogables 8) se alerta al Analista.

Endpoints a implementar o ajustar: GET /api/reclamos/; POST /api/reclamos/; POST /api/reclamos/{id}/cerrar/; GET /api/reclamos/insumo/?tipo=marcacion|desmarcacion.

Haz esto:
1. POST: valida tipología del catálogo, fecha no futura y que la obligación exista y no tenga ya un reclamo abierto; calcula FECHA_LIMITE_RESPUESTA (15 días hábiles); bitácora.
2. Cerrar: resultado y fecha de cierre no anterior a la radicación; deja pendiente el insumo de desmarcación.
3. Insumo: texto delimitado con los reclamos pendientes (marcación) o cerrados pendientes (desmarcación); al generarlo marca MARCACION_GENERADA / DESMARCACION_GENERADA. El formato exacto queda en una sola función.
4. El listado devuelve la alerta de plazo vencido o por vencer. La obligación sigue en el archivo total (no tocar INCLUIR).

Usa estas tablas, vistas y módulos: NV_RECLAMO; NV_TIPOLOGIA_RECLAMO; NV_OBLIGACION; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo
- Segundo reclamo abierto sobre la misma obligación → 409 en español
- Tipología fuera del catálogo → 400
- Cerrar con fecha anterior a la radicación → 400 en el campo fecha_cierre
- Generar el insumo de marcación → Incluye solo los reclamos pendientes; luego el botón queda en 0
- Reclamo con plazo vencido → Alerta en el listado

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF23 · Registro de reclamos de Habeas Data. Parte de frontend: pantalla 13 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: El Analista registra los reclamos de los titulares y el sistema prepara el insumo para el proceso de «Marcación de obligaciones (Reclamos Batch)» de TransUnion. La obligación en reclamo se sigue reportando en el archivo total.

Implementa:
1. Pantalla 13 «Reclamos Habeas Data»: tarjetas de conteo, botones «Archivo de marcación (N)» y «Archivo de desmarcación (N)» (deshabilitados si N = 0), tabla (Obligación | Tipología y observación | Fecha del reclamo | Estado | Archivo | Acciones) y botón «Cerrar reclamo» por fila.
2. Modales «Registrar reclamo» (Obligación, Tipología, Fecha, Observación opcional) y «Cerrar reclamo» (Resultado, Fecha de cierre, Observación) con error por campo. Insignia «En reclamo Habeas Data» en la pantalla 9 y panel (tarjeta «Obligaciones en reclamo»).

Consume estos endpoints (según el contrato): GET /api/reclamos/; POST /api/reclamos/; POST /api/reclamos/{id}/cerrar/; GET /api/reclamos/insumo/; GET /api/catalogos/tipologias-reclamo/.

Pruebas con vitest (y MSW) para estos casos:
- Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo
- Segundo reclamo abierto sobre la misma obligación → 409 en español
- Tipología fuera del catálogo → 400
- Cerrar con fecha anterior a la radicación → 400 en el campo fecha_cierre
- Generar el insumo de marcación → Incluye solo los reclamos pendientes; luego el botón queda en 0

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF23 · Registro de reclamos de Habeas Data. Lo implementaron: base de datos Angel y backend Clara (tú no).
Resumen del RF: El Analista registra los reclamos de los titulares y el sistema prepara el insumo para el proceso de «Marcación de obligaciones (Reclamos Batch)» de TransUnion. La obligación en reclamo se sigue reportando en el archivo total.
Reglas del RF:
- El Analista registra tipología (válida según la Ley 1266 y la lista de TransUnion), fecha de radicación y obligación.
- El sistema genera el insumo para la marcación batch de TransUnion y mantiene la obligación en el reporte total (no se «aísla»).
- Al cerrar el reclamo se registran la respuesta y el cierre, y se genera el insumo de desmarcación.
- Los archivos de radicación, cierre e inconsistencias los devuelve TransUnion y se cargan con RF54.
- Si la tipología no es válida no se registra. Si supera el plazo legal (15 días hábiles, prorrogables 8) se alerta al Analista.

Qué probar:
- Vistas y tablas: NV_RECLAMO; NV_TIPOLOGIA_RECLAMO; NV_OBLIGACION
- Endpoints: GET /api/reclamos/; POST /api/reclamos/; POST /api/reclamos/{id}/cerrar/; GET /api/reclamos/insumo/?tipo=marcacion|desmarcacion

Casos mínimos (automatiza todos):
1. Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo
2. Segundo reclamo abierto sobre la misma obligación → 409 en español
3. Tipología fuera del catálogo → 400
4. Cerrar con fecha anterior a la radicación → 400 en el campo fecha_cierre
5. Generar el insumo de marcación → Incluye solo los reclamos pendientes; luego el botón queda en 0
6. Reclamo con plazo vencido → Alerta en el listado

Entrega: tests/test_rf23_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF23 · Registro de reclamos de Habeas Data (rol del RF: Analista de Cartera; pantalla del mockup v3: 13). Lo implementaron Angel, Clara, Omar (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 13 «Reclamos Habeas Data»: tarjetas de conteo, botones «Archivo de marcación (N)» y «Archivo de desmarcación (N)» (deshabilitados si N = 0), tabla (Obligación | Tipología y observación | Fecha del reclamo | Estado | Archivo | Acciones) y botón «Cerrar reclamo» por fila.
- Modales «Registrar reclamo» (Obligación, Tipología, Fecha, Observación opcional) y «Cerrar reclamo» (Resultado, Fecha de cierre, Observación) con error por campo. Insignia «En reclamo Habeas Data» en la pantalla 9 y panel (tarjeta «Obligaciones en reclamo»).

Reglas del RF:
- El Analista registra tipología (válida según la Ley 1266 y la lista de TransUnion), fecha de radicación y obligación.
- El sistema genera el insumo para la marcación batch de TransUnion y mantiene la obligación en el reporte total (no se «aísla»).
- Al cerrar el reclamo se registran la respuesta y el cierre, y se genera el insumo de desmarcación.
- Los archivos de radicación, cierre e inconsistencias los devuelve TransUnion y se cargan con RF54.
- Si la tipología no es válida no se registra. Si supera el plazo legal (15 días hábiles, prorrogables 8) se alerta al Analista.

Casos mínimos:
1. Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo
2. Segundo reclamo abierto sobre la misma obligación → 409 en español
3. Tipología fuera del catálogo → 400
4. Cerrar con fecha anterior a la radicación → 400 en el campo fecha_cierre
5. Generar el insumo de marcación → Incluye solo los reclamos pendientes; luego el botón queda en 0
6. Reclamo con plazo vencido → Alerta en el listado

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF24 · Registro de novedades de Actualización en Línea

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF24 · Registro de novedades de Actualización en Línea. Parte de base de datos (Script 11 (NV_NOVEDAD)).
Resumen del RF: NexoVolt registra toda transacción hecha en el módulo de Actualización en Línea de TransUnion (que opera una persona en su web) y la tiene en cuenta en el siguiente reporte total.
Reglas del RF:
- El Analista hace la transacción en TransUnion y la registra en NexoVolt: tipo, número de obligación, número de transacción de TransUnion, fecha, usuario, motivo (en eliminaciones, con el catálogo homologado a la Tabla 28) y valores enviados.
- En el siguiente corte la novedad se aplica: una obligación saldada o recuperada en línea no recibe más comportamientos, y una eliminada no se vuelve a reportar (RF50).
- Si TransUnion rechaza la transacción, el Analista registra el rechazo y lo gestiona con TransUnion.
- Importante: ese módulo escribe en la base real de TransUnion; nunca se usa para pruebas.

Haz esto:
1. Crear NV_NOVEDAD con CHECK de TIPO, SUJETO, ORIGEN y ESTADO, FK a NV_MOTIVO_ELIMINACION (solo para eliminaciones) e índices (ESTADO, FECHA_DETECCION) y (OBLIGACION_ID).

Usa estos objetos: NV_NOVEDAD; NV_MOTIVO_ELIMINACION; NV_OBLIGACION.

Comprueba con estos casos (datos de prueba v2):
- Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
- Gestionar sin número de transacción → 400 en el campo de confirmación
- Gestionar con número TU-AL-001532 → Pasa a GESTIONADA con fecha
- Novedad sobre una obligación que no existe → Error claro (no Inclusión)

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF24 · Registro de novedades de Actualización en Línea. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: NexoVolt registra toda transacción hecha en el módulo de Actualización en Línea de TransUnion (que opera una persona en su web) y la tiene en cuenta en el siguiente reporte total.
Reglas del RF:
- El Analista hace la transacción en TransUnion y la registra en NexoVolt: tipo, número de obligación, número de transacción de TransUnion, fecha, usuario, motivo (en eliminaciones, con el catálogo homologado a la Tabla 28) y valores enviados.
- En el siguiente corte la novedad se aplica: una obligación saldada o recuperada en línea no recibe más comportamientos, y una eliminada no se vuelve a reportar (RF50).
- Si TransUnion rechaza la transacción, el Analista registra el rechazo y lo gestiona con TransUnion.
- Importante: ese módulo escribe en la base real de TransUnion; nunca se usa para pruebas.

Endpoints a implementar o ajustar: GET /api/novedades/?estado=; POST /api/novedades/; POST /api/novedades/{id}/gestionar/; POST /api/novedades/{id}/rechazar/.

Haz esto:
1. POST: tipo, sujeto, referencia (número de obligación o identificación del titular), motivo y, según el tipo, motivo de eliminación o corte a rectificar; si el sujeto es una obligación y el tipo no es Inclusión, la obligación debe existir (404 con mensaje).
2. gestionar: exige el número de transacción de TransUnion (400 si falta); ESTADO = GESTIONADA y fecha de gestión; si es una eliminación de obligación, delega en RF50.
3. rechazar: registra el motivo del rechazo (ESTADO = RECHAZADA).
4. Detección automática (ORIGEN = AUTOMATICA): crear una novedad de Actualización cuando haya un pago posterior al corte en una obligación en mora (caso del mockup). Toda acción en bitácora.

Usa estas tablas, vistas y módulos: NV_NOVEDAD; NV_OBLIGACION; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
- Gestionar sin número de transacción → 400 en el campo de confirmación
- Gestionar con número TU-AL-001532 → Pasa a GESTIONADA con fecha
- Novedad sobre una obligación que no existe → Error claro (no Inclusión)
- Rechazar con motivo → ESTADO = RECHAZADA y queda registrado

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF24 · Registro de novedades de Actualización en Línea. Parte de frontend: pantalla 14 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: NexoVolt registra toda transacción hecha en el módulo de Actualización en Línea de TransUnion (que opera una persona en su web) y la tiene en cuenta en el siguiente reporte total.

Implementa:
1. Pantalla 14 «Novedades Urgentes»: aviso de que el módulo en línea escribe en la base real, pestañas Todas/Pendientes/Gestionadas con contador, tabla (Tipo | Referencia | Motivo | Detectada y origen | Estado | Acciones) y botón «Gestionar en línea».
2. Modal «Registrar novedad urgente» (Tipo, Sujeto, Número de obligación o identificación, Motivo; si es Corrección, el corte que se rectifica y el medio) y modal «Gestionar en Actualización en Línea» (botón «Abrir Actualización en Línea» y campo obligatorio «Número de confirmación de TransUnion»).

Consume estos endpoints (según el contrato): GET /api/novedades/; POST /api/novedades/; POST /api/novedades/{id}/gestionar/; POST /api/novedades/{id}/rechazar/.

Pruebas con vitest (y MSW) para estos casos:
- Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
- Gestionar sin número de transacción → 400 en el campo de confirmación
- Gestionar con número TU-AL-001532 → Pasa a GESTIONADA con fecha
- Novedad sobre una obligación que no existe → Error claro (no Inclusión)
- Rechazar con motivo → ESTADO = RECHAZADA y queda registrado

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF24 · Registro de novedades de Actualización en Línea. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: NexoVolt registra toda transacción hecha en el módulo de Actualización en Línea de TransUnion (que opera una persona en su web) y la tiene en cuenta en el siguiente reporte total.
Reglas del RF:
- El Analista hace la transacción en TransUnion y la registra en NexoVolt: tipo, número de obligación, número de transacción de TransUnion, fecha, usuario, motivo (en eliminaciones, con el catálogo homologado a la Tabla 28) y valores enviados.
- En el siguiente corte la novedad se aplica: una obligación saldada o recuperada en línea no recibe más comportamientos, y una eliminada no se vuelve a reportar (RF50).
- Si TransUnion rechaza la transacción, el Analista registra el rechazo y lo gestiona con TransUnion.
- Importante: ese módulo escribe en la base real de TransUnion; nunca se usa para pruebas.

Qué probar:
- Vistas y tablas: NV_NOVEDAD; NV_MOTIVO_ELIMINACION; NV_OBLIGACION
- Endpoints: GET /api/novedades/?estado=; POST /api/novedades/; POST /api/novedades/{id}/gestionar/; POST /api/novedades/{id}/rechazar/

Casos mínimos (automatiza todos):
1. Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
2. Gestionar sin número de transacción → 400 en el campo de confirmación
3. Gestionar con número TU-AL-001532 → Pasa a GESTIONADA con fecha
4. Novedad sobre una obligación que no existe → Error claro (no Inclusión)
5. Rechazar con motivo → ESTADO = RECHAZADA y queda registrado

Entrega: tests/test_rf24_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF24 · Registro de novedades de Actualización en Línea (rol del RF: Analista de Cartera; pantalla del mockup v3: 14). Lo implementaron Angel, Jose Luis (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 14 «Novedades Urgentes»: aviso de que el módulo en línea escribe en la base real, pestañas Todas/Pendientes/Gestionadas con contador, tabla (Tipo | Referencia | Motivo | Detectada y origen | Estado | Acciones) y botón «Gestionar en línea».
- Modal «Registrar novedad urgente» (Tipo, Sujeto, Número de obligación o identificación, Motivo; si es Corrección, el corte que se rectifica y el medio) y modal «Gestionar en Actualización en Línea» (botón «Abrir Actualización en Línea» y campo obligatorio «Número de confirmación de TransUnion»).

Reglas del RF:
- El Analista hace la transacción en TransUnion y la registra en NexoVolt: tipo, número de obligación, número de transacción de TransUnion, fecha, usuario, motivo (en eliminaciones, con el catálogo homologado a la Tabla 28) y valores enviados.
- En el siguiente corte la novedad se aplica: una obligación saldada o recuperada en línea no recibe más comportamientos, y una eliminada no se vuelve a reportar (RF50).
- Si TransUnion rechaza la transacción, el Analista registra el rechazo y lo gestiona con TransUnion.
- Importante: ese módulo escribe en la base real de TransUnion; nunca se usa para pruebas.

Casos mínimos:
1. Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
2. Gestionar sin número de transacción → 400 en el campo de confirmación
3. Gestionar con número TU-AL-001532 → Pasa a GESTIONADA con fecha
4. Novedad sobre una obligación que no existe → Error claro (no Inclusión)
5. Rechazar con motivo → ESTADO = RECHAZADA y queda registrado

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF45 · Transición a Castigada

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF45 · Transición a Castigada. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Una obligación se reporta Castigada (06) cuando CENS la castigó contablemente (marca de castigo del sistema comercial) y su valor de mora es mayor a cero.
Reglas del RF:
- Marca de castigo del SAC. [Campo o tabla: confirmar con CENS (P-CENS-05).]
- Si es primer reporte, la edad de mora debe ser mayor a 00 (RF10).
- La Matriz debe permitir el cambio desde 01, 08, 04 en mora, 03 en mora, 06 en mora o estado de ley.
- Valor de mora cero: no se reporta 06 y se marca para revisión. La Matriz no lo permite: inconsistencia 713.

Haz esto:
1. Fuente provisional de la marca: NV_MARCA_CASTIGO (script 11). En V_CALCULO_CORTE: ESTADO_TU = 06 si existe la marca y VALOR_MORA > 0; si la mora es cero, REQUIERE_REVISION.
2. Dejar la marca en un único bloque (CTE marca_castigo) para reemplazar la fuente cuando CENS confirme el campo del SAC.

Usa estos objetos: NV_MARCA_CASTIGO; NV_TRANSICION_ESTADO; V_CALCULO_CORTE.

Comprueba con estos casos (datos de prueba v2):
- 2244-6410: con marca de castigo y mora → Estado 06
- Marca de castigo con mora cero → No reporta 06; marcada para revisión
- Primer reporte castigada con edad 00 → Rechazada (881)
- Estado anterior 02 con marca de castigo → Inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF45 · Transición a Castigada. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Una obligación se reporta Castigada (06) cuando CENS la castigó contablemente (marca de castigo del sistema comercial) y su valor de mora es mayor a cero.
Reglas del RF:
- Marca de castigo del SAC. [Campo o tabla: confirmar con CENS (P-CENS-05).]
- Si es primer reporte, la edad de mora debe ser mayor a 00 (RF10).
- La Matriz debe permitir el cambio desde 01, 08, 04 en mora, 03 en mora, 06 en mora o estado de ley.
- Valor de mora cero: no se reporta 06 y se marca para revisión. La Matriz no lo permite: inconsistencia 713.

Endpoints a implementar o ajustar: POST /api/ciclos/; POST /api/castigos/ (opcional, mientras no exista el campo en el SAC).

Haz esto:
1. Reflejar la transición en el ciclo: «RF45 · CENS la castigó contablemente: Castigada» y los rechazos 713.
2. Opcional: endpoint para registrar la marca de castigo (número de obligación y fecha) en NV_MARCA_CASTIGO con bitácora.

Usa estas tablas, vistas y módulos: NV_MARCA_CASTIGO; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- 2244-6410: con marca de castigo y mora → Estado 06
- Marca de castigo con mora cero → No reporta 06; marcada para revisión
- Primer reporte castigada con edad 00 → Rechazada (881)
- Estado anterior 02 con marca de castigo → Inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF45 · Transición a Castigada. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Una obligación se reporta Castigada (06) cuando CENS la castigó contablemente (marca de castigo del sistema comercial) y su valor de mora es mayor a cero.

Implementa:
1. Pantalla 9: insignia 06 · Castigada y, en el detalle, «Sigue en Castigada mientras tenga mora».

Consume estos endpoints (según el contrato): GET /api/obligaciones/; GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- 2244-6410: con marca de castigo y mora → Estado 06
- Marca de castigo con mora cero → No reporta 06; marcada para revisión
- Primer reporte castigada con edad 00 → Rechazada (881)
- Estado anterior 02 con marca de castigo → Inconsistencia 713

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF45 · Transición a Castigada. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Una obligación se reporta Castigada (06) cuando CENS la castigó contablemente (marca de castigo del sistema comercial) y su valor de mora es mayor a cero.
Reglas del RF:
- Marca de castigo del SAC. [Campo o tabla: confirmar con CENS (P-CENS-05).]
- Si es primer reporte, la edad de mora debe ser mayor a 00 (RF10).
- La Matriz debe permitir el cambio desde 01, 08, 04 en mora, 03 en mora, 06 en mora o estado de ley.
- Valor de mora cero: no se reporta 06 y se marca para revisión. La Matriz no lo permite: inconsistencia 713.

Qué probar:
- Vistas y tablas: NV_MARCA_CASTIGO; NV_TRANSICION_ESTADO; V_CALCULO_CORTE
- Endpoints: POST /api/ciclos/; POST /api/castigos/ (opcional, mientras no exista el campo en el SAC)

Casos mínimos (automatiza todos):
1. 2244-6410: con marca de castigo y mora → Estado 06
2. Marca de castigo con mora cero → No reporta 06; marcada para revisión
3. Primer reporte castigada con edad 00 → Rechazada (881)
4. Estado anterior 02 con marca de castigo → Inconsistencia 713

Entrega: tests/test_rf45_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF45 · Transición a Castigada (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9: insignia 06 · Castigada y, en el detalle, «Sigue en Castigada mientras tenga mora».

Reglas del RF:
- Marca de castigo del SAC. [Campo o tabla: confirmar con CENS (P-CENS-05).]
- Si es primer reporte, la edad de mora debe ser mayor a 00 (RF10).
- La Matriz debe permitir el cambio desde 01, 08, 04 en mora, 03 en mora, 06 en mora o estado de ley.
- Valor de mora cero: no se reporta 06 y se marca para revisión. La Matriz no lo permite: inconsistencia 713.

Casos mínimos:
1. 2244-6410: con marca de castigo y mora → Estado 06
2. Marca de castigo con mora cero → No reporta 06; marcada para revisión
3. Primer reporte castigada con edad 00 → Rechazada (881)
4. Estado anterior 02 con marca de castigo → Inconsistencia 713

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF46 · Normalización sin pago total

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF46 · Normalización sin pago total. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Si una obligación en 03 o 06 en mora, o en estado de ley, paga lo vencido pero conserva saldo, vuelve a Vigente (01) con los datos del pago de la mora (RF47).
Reglas del RF:
- Detecta que el valor de mora quedó en cero y el saldo es mayor a cero.
- Reporta 01, cambio permitido por la Matriz desde 03, 06 y estados de ley, y aplica RF47.
- Si conserva valor de mora, mantiene su estado.
- [Confirmar con CENS si el caso ocurre o si toda normalización se hace como refinanciación (RF18).]

Haz esto:
1. Si el estado anterior es 03, 06, 10, 11 o 12 y VALOR_MORA = 0 con saldo mayor a cero: ESTADO_TU = 01 y marcar el pago de la mora (RF47). Verificar que la Matriz lo permita.

Usa estos objetos: V_CALCULO_CORTE; NV_TRANSICION_ESTADO.

Comprueba con estos casos (datos de prueba v2):
- Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
- Obligación en 06 con mora pendiente → Mantiene 06
- Obligación en estado de ley que retoma su curso → Vuelve a 01

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF46 · Normalización sin pago total. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Si una obligación en 03 o 06 en mora, o en estado de ley, paga lo vencido pero conserva saldo, vuelve a Vigente (01) con los datos del pago de la mora (RF47).
Reglas del RF:
- Detecta que el valor de mora quedó en cero y el saldo es mayor a cero.
- Reporta 01, cambio permitido por la Matriz desde 03, 06 y estados de ley, y aplica RF47.
- Si conserva valor de mora, mantiene su estado.
- [Confirmar con CENS si el caso ocurre o si toda normalización se hace como refinanciación (RF18).]

Endpoints a implementar o ajustar: POST /api/ciclos/.

Haz esto:
1. Devolver en el ciclo «RF46 · Pagó la mora sin cancelar el saldo: vuelve a Vigente» (marcada por confirmar) y contarla como «normalizada».

Usa estas tablas, vistas y módulos: V_CALCULO_CORTE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
- Obligación en 06 con mora pendiente → Mantiene 06
- Obligación en estado de ley que retoma su curso → Vuelve a 01

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF46 · Normalización sin pago total. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Si una obligación en 03 o 06 en mora, o en estado de ley, paga lo vencido pero conserva saldo, vuelve a Vigente (01) con los datos del pago de la mora (RF47).

Implementa:
1. Pantalla 9, detalle: «Paga la mora sin cancelar el saldo → 01 · Vigente (RF46)» con la etiqueta «por confirmar»; pantalla 10: regla en «Qué pasó».

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/; POST /api/ciclos/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
- Obligación en 06 con mora pendiente → Mantiene 06
- Obligación en estado de ley que retoma su curso → Vuelve a 01

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF46 · Normalización sin pago total. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Si una obligación en 03 o 06 en mora, o en estado de ley, paga lo vencido pero conserva saldo, vuelve a Vigente (01) con los datos del pago de la mora (RF47).
Reglas del RF:
- Detecta que el valor de mora quedó en cero y el saldo es mayor a cero.
- Reporta 01, cambio permitido por la Matriz desde 03, 06 y estados de ley, y aplica RF47.
- Si conserva valor de mora, mantiene su estado.
- [Confirmar con CENS si el caso ocurre o si toda normalización se hace como refinanciación (RF18).]

Qué probar:
- Vistas y tablas: V_CALCULO_CORTE; NV_TRANSICION_ESTADO
- Endpoints: POST /api/ciclos/

Casos mínimos (automatiza todos):
1. Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
2. Obligación en 06 con mora pendiente → Mantiene 06
3. Obligación en estado de ley que retoma su curso → Vuelve a 01

Entrega: tests/test_rf46_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF46 · Normalización sin pago total (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: «Paga la mora sin cancelar el saldo → 01 · Vigente (RF46)» con la etiqueta «por confirmar»; pantalla 10: regla en «Qué pasó».

Reglas del RF:
- Detecta que el valor de mora quedó en cero y el saldo es mayor a cero.
- Reporta 01, cambio permitido por la Matriz desde 03, 06 y estados de ley, y aplica RF47.
- Si conserva valor de mora, mantiene su estado.
- [Confirmar con CENS si el caso ocurre o si toda normalización se hace como refinanciación (RF18).]

Casos mínimos:
1. Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
2. Obligación en 06 con mora pendiente → Mantiene 06
3. Obligación en estado de ley que retoma su curso → Vuelve a 01

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF47 · Reporte del pago de la mora

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF47 · Reporte del pago de la mora. Parte de base de datos (V_CALCULO_CORTE v2).
Resumen del RF: Cuando una obligación que tenía mora queda al día sin cerrarse, se reportan la fecha de pago, el modo de extinción y el tipo de pago.
Reglas del RF:
- Precondición: tenía valor de mora mayor a cero en el último corte enviado y sigue con saldo; ahora tiene mora 0, edad 00 y cuotas en mora 0.
- Fecha de pago = fecha en que quedó al día (menor o igual a la fecha de corte). Modo de extinción (Tabla 10) y tipo de pago (Tabla 31): Voluntario (01) en ambos, salvo proceso judicial [confirmar con CENS]. También el valor real pagado en el corte.
- Sin fecha de pago disponible: se marca para revisión, porque TransUnion tomaría la fecha de corte y alteraría la permanencia del dato negativo (Manual, p. 26).

Haz esto:
1. Detectar «quedó al día»: V_ULTIMO_REPORTE.VALOR_MORA > 0 y VALOR_MORA actual = 0 con saldo > 0. Llenar FECHA_PAGO, MODO_EXTINCION = 01 y TIPO_PAGO = 01 (parametrizable).
2. Si no hay fecha de pago, REQUIERE_REVISION con motivo «Pago de mora sin fecha de pago».

Usa estos objetos: V_ULTIMO_REPORTE; NV_MODO_EXTINCION y NV_TIPO_PAGO; NV_REPORTE_DETALLE (FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO, VALOR_REAL_PAGADO).

Comprueba con estos casos (datos de prueba v2):
- Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
- Queda al día sin fecha de pago → Marcada para revisión
- Obligación sin mora previa → No genera pago de mora

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF47 · Reporte del pago de la mora. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Cuando una obligación que tenía mora queda al día sin cerrarse, se reportan la fecha de pago, el modo de extinción y el tipo de pago.
Reglas del RF:
- Precondición: tenía valor de mora mayor a cero en el último corte enviado y sigue con saldo; ahora tiene mora 0, edad 00 y cuotas en mora 0.
- Fecha de pago = fecha en que quedó al día (menor o igual a la fecha de corte). Modo de extinción (Tabla 10) y tipo de pago (Tabla 31): Voluntario (01) en ambos, salvo proceso judicial [confirmar con CENS]. También el valor real pagado en el corte.
- Sin fecha de pago disponible: se marca para revisión, porque TransUnion tomaría la fecha de corte y alteraría la permanencia del dato negativo (Manual, p. 26).

Endpoints a implementar o ajustar: GET /api/obligaciones/{id}/ (pago_mora); POST /api/ciclos/.

Haz esto:
1. Exponer pago_mora {fecha, modo, tipo} en el detalle y devolver «RF47 · Quedó al día: se reportan fecha de pago, modo de extinción y tipo de pago» en el ciclo.

Usa estas tablas, vistas y módulos: NV_REPORTE_DETALLE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
- Queda al día sin fecha de pago → Marcada para revisión
- Obligación sin mora previa → No genera pago de mora

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF47 · Reporte del pago de la mora. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Cuando una obligación que tenía mora queda al día sin cerrarse, se reportan la fecha de pago, el modo de extinción y el tipo de pago.

Implementa:
1. Pantalla 9, detalle: bloque «Pago de la mora (RF47): dd/mm/aaaa · Modo · Tipo de pago».

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
- Queda al día sin fecha de pago → Marcada para revisión
- Obligación sin mora previa → No genera pago de mora

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF47 · Reporte del pago de la mora. Lo implementaron: base de datos Clara y backend Jose Luis (tú no).
Resumen del RF: Cuando una obligación que tenía mora queda al día sin cerrarse, se reportan la fecha de pago, el modo de extinción y el tipo de pago.
Reglas del RF:
- Precondición: tenía valor de mora mayor a cero en el último corte enviado y sigue con saldo; ahora tiene mora 0, edad 00 y cuotas en mora 0.
- Fecha de pago = fecha en que quedó al día (menor o igual a la fecha de corte). Modo de extinción (Tabla 10) y tipo de pago (Tabla 31): Voluntario (01) en ambos, salvo proceso judicial [confirmar con CENS]. También el valor real pagado en el corte.
- Sin fecha de pago disponible: se marca para revisión, porque TransUnion tomaría la fecha de corte y alteraría la permanencia del dato negativo (Manual, p. 26).

Qué probar:
- Vistas y tablas: V_ULTIMO_REPORTE; NV_MODO_EXTINCION y NV_TIPO_PAGO; NV_REPORTE_DETALLE (FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO, VALOR_REAL_PAGADO)
- Endpoints: GET /api/obligaciones/{id}/ (pago_mora); POST /api/ciclos/

Casos mínimos (automatiza todos):
1. Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
2. Queda al día sin fecha de pago → Marcada para revisión
3. Obligación sin mora previa → No genera pago de mora

Entrega: tests/test_rf47_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF47 · Reporte del pago de la mora (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Clara, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: bloque «Pago de la mora (RF47): dd/mm/aaaa · Modo · Tipo de pago».

Reglas del RF:
- Precondición: tenía valor de mora mayor a cero en el último corte enviado y sigue con saldo; ahora tiene mora 0, edad 00 y cuotas en mora 0.
- Fecha de pago = fecha en que quedó al día (menor o igual a la fecha de corte). Modo de extinción (Tabla 10) y tipo de pago (Tabla 31): Voluntario (01) en ambos, salvo proceso judicial [confirmar con CENS]. También el valor real pagado en el corte.
- Sin fecha de pago disponible: se marca para revisión, porque TransUnion tomaría la fecha de corte y alteraría la permanencia del dato negativo (Manual, p. 26).

Casos mínimos:
1. Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
2. Queda al día sin fecha de pago → Marcada para revisión
3. Obligación sin mora previa → No genera pago de mora

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF48 · Catálogo y homologación de estados

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF48 · Catálogo y homologación de estados. Parte de base de datos (Script 12).
Resumen del RF: El sistema soporta los 10 estados de la Tabla 4b y homologa cada estado del sistema comercial a uno de ellos. Lo parametriza el Administrador.
Reglas del RF:
- Estados usados: 01, 02, 03, 06 y 07. No se usa 08 Inactivo (Acta 3). 04 Suspendida: propuesta de no usarla. 10, 11 y 12: solo si el cliente está admitido en el proceso de ley (fuente por confirmar).
- Homologación del SAC: A → 01, C → 03, F → cierre (RF12 o RF15). B y D: pendientes de CENS.
- El Administrador registra y actualiza la homologación.
- Un crédito con estado del SAC sin homologar bloquea la obligación en la validación del corte (RF53).

Haz esto:
1. Script 12: NV_ESTADO_TU.USADO (08 y 04 en N); NV_HOMOLOGA_ESTADO.ACCION (ESTADO o CIERRE), USUARIO_ID y FECHA_ACTUALIZACION; F pasa a ACCION = CIERRE con ESTADO_TU nulo.
2. Recargar NV_TRANSICION_ESTADO completa (400 filas) con la Matriz de la p. 40 del Manual. La constante MX del mockup v3 sirve para verificar la transcripción celda por celda.

Usa estos objetos: NV_ESTADO_TU; NV_HOMOLOGA_ESTADO; NV_TRANSICION_ESTADO; V_CREDITO_REPORTABLE.

Comprueba con estos casos (datos de prueba v2):
- Administrador cambia A → 01 → Se guarda y queda en bitácora
- Analista intenta PUT → 403 en español
- Asignar estado 08 (no usado) → 400
- Crédito con estado B sin homologar → La obligación se bloquea en RF53

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF48 · Catálogo y homologación de estados. Parte de backend (rol del RF: Administrador).
Resumen del RF: El sistema soporta los 10 estados de la Tabla 4b y homologa cada estado del sistema comercial a uno de ellos. Lo parametriza el Administrador.
Reglas del RF:
- Estados usados: 01, 02, 03, 06 y 07. No se usa 08 Inactivo (Acta 3). 04 Suspendida: propuesta de no usarla. 10, 11 y 12: solo si el cliente está admitido en el proceso de ley (fuente por confirmar).
- Homologación del SAC: A → 01, C → 03, F → cierre (RF12 o RF15). B y D: pendientes de CENS.
- El Administrador registra y actualiza la homologación.
- Un crédito con estado del SAC sin homologar bloquea la obligación en la validación del corte (RF53).

Endpoints a implementar o ajustar: GET /api/estados/; GET /api/homologacion-estados/; PUT /api/homologacion-estados/{estado_sac}/.

Haz esto:
1. Rol ADMINISTRADOR en los tres (403 con mensaje en español para el Analista). Los listados devuelven estado, nombre, usado, y por cada estado del SAC: descripción, estado TU o «cierre», confirmado.
2. PUT valida que el estado destino exista y esté USADO = S, que ACCION = CIERRE solo se use para el estado F, y deja la bitácora «Homologación de estados actualizada».

Usa estas tablas, vistas y módulos: NV_ESTADO_TU; NV_HOMOLOGA_ESTADO; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Administrador cambia A → 01 → Se guarda y queda en bitácora
- Analista intenta PUT → 403 en español
- Asignar estado 08 (no usado) → 400
- Crédito con estado B sin homologar → La obligación se bloquea en RF53
- Matriz cargada → 400 filas; 02 y 07 sin salidas

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF48 · Catálogo y homologación de estados. Parte de frontend: pantalla 16 (nueva, sin mockup) (rol del RF: Administrador; el Analista ve «Acceso restringido»).
Resumen del RF: El sistema soporta los 10 estados de la Tabla 4b y homologa cada estado del sistema comercial a uno de ellos. Lo parametriza el Administrador.

Implementa:
1. Pantalla 16 NUEVA «Homologación de estados» (Johan primero la dibuja como pantalla del mockup v3 y Santiago la aprueba): tabla de los 10 estados (código, nombre, usado sí/no) y tabla de homologación del SAC (estado SAC, descripción, estado TransUnion o «cierre», confirmado) con edición en línea y aviso de estados sin homologar.
2. Solo ADMINISTRADOR: RequireRole y un ítem de menú bajo «Administración». El Analista ve «Acceso restringido».

Consume estos endpoints (según el contrato): GET /api/estados/; GET /api/homologacion-estados/; PUT /api/homologacion-estados/{estado_sac}/.

Pruebas con vitest (y MSW) para estos casos:
- Administrador cambia A → 01 → Se guarda y queda en bitácora
- Analista intenta PUT → 403 en español
- Asignar estado 08 (no usado) → 400
- Crédito con estado B sin homologar → La obligación se bloquea en RF53
- Matriz cargada → 400 filas; 02 y 07 sin salidas

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF48 · Catálogo y homologación de estados. Lo implementaron: base de datos Clara y backend Santiago (tú no).
Resumen del RF: El sistema soporta los 10 estados de la Tabla 4b y homologa cada estado del sistema comercial a uno de ellos. Lo parametriza el Administrador.
Reglas del RF:
- Estados usados: 01, 02, 03, 06 y 07. No se usa 08 Inactivo (Acta 3). 04 Suspendida: propuesta de no usarla. 10, 11 y 12: solo si el cliente está admitido en el proceso de ley (fuente por confirmar).
- Homologación del SAC: A → 01, C → 03, F → cierre (RF12 o RF15). B y D: pendientes de CENS.
- El Administrador registra y actualiza la homologación.
- Un crédito con estado del SAC sin homologar bloquea la obligación en la validación del corte (RF53).

Qué probar:
- Vistas y tablas: NV_ESTADO_TU; NV_HOMOLOGA_ESTADO; NV_TRANSICION_ESTADO; V_CREDITO_REPORTABLE
- Endpoints: GET /api/estados/; GET /api/homologacion-estados/; PUT /api/homologacion-estados/{estado_sac}/

Casos mínimos (automatiza todos):
1. Administrador cambia A → 01 → Se guarda y queda en bitácora
2. Analista intenta PUT → 403 en español
3. Asignar estado 08 (no usado) → 400
4. Crédito con estado B sin homologar → La obligación se bloquea en RF53
5. Matriz cargada → 400 filas; 02 y 07 sin salidas

Entrega: tests/test_rf48_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF48 · Catálogo y homologación de estados (rol del RF: Administrador; pantalla del mockup v3: 16 (nueva, sin mockup)). Lo implementaron Clara, Santiago, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 16 NUEVA «Homologación de estados» (Johan primero la dibuja como pantalla del mockup v3 y Santiago la aprueba): tabla de los 10 estados (código, nombre, usado sí/no) y tabla de homologación del SAC (estado SAC, descripción, estado TransUnion o «cierre», confirmado) con edición en línea y aviso de estados sin homologar.
- Solo ADMINISTRADOR: RequireRole y un ítem de menú bajo «Administración». El Analista ve «Acceso restringido».

Reglas del RF:
- Estados usados: 01, 02, 03, 06 y 07. No se usa 08 Inactivo (Acta 3). 04 Suspendida: propuesta de no usarla. 10, 11 y 12: solo si el cliente está admitido en el proceso de ley (fuente por confirmar).
- Homologación del SAC: A → 01, C → 03, F → cierre (RF12 o RF15). B y D: pendientes de CENS.
- El Administrador registra y actualiza la homologación.
- Un crédito con estado del SAC sin homologar bloquea la obligación en la validación del corte (RF53).

Casos mínimos:
1. Administrador cambia A → 01 → Se guarda y queda en bitácora
2. Analista intenta PUT → 403 en español
3. Asignar estado 08 (no usado) → 400
4. Crédito con estado B sin homologar → La obligación se bloquea en RF53
5. Matriz cargada → 400 filas; 02 y 07 sin salidas

Además: entra con el rol Analista de Cartera y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF49 · Fecha de exigibilidad y años en mora

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF49 · Fecha de exigibilidad y años en mora. Parte de base de datos (V_MORA_OBLIGACION y V_VALIDACION_CORTE).
Resumen del RF: Para toda obligación con valor de mora mayor a cero se reporta la fecha de exigibilidad y, con edad 14, los años en mora.
Reglas del RF:
- Fecha de exigibilidad = fecha límite de pago de la cuota impaga más antigua (RF7), en AAAAMMDD.
- Si la edad es 14 se calculan y reportan los años en mora.
- Al quedar al día se envía la fecha de exigibilidad vacía.
- Si la fecha de exigibilidad es mayor a la fecha del sistema, la obligación se bloquea en la validación del corte (correctiva, RF53).

Haz esto:
1. V_MORA_OBLIGACION: FECHA_EXIGIBILIDAD (nula si está al día) y ANIOS_MORA = TRUNC(DIAS_MORA / 365) cuando la edad es 14.
2. V_VALIDACION_CORTE: regla FECHA_EXIGIBILIDAD_FUTURA (CORRECTIVA) y EDAD_ALTA_SIN_EXIGIBILIDAD (INFORMATIVA, edad 12 a 14 sin fecha).

Usa estos objetos: V_MORA_OBLIGACION; V_VALIDACION_CORTE; NV_REPORTE_DETALLE (FECHA_EXIGIBILIDAD, ANIOS_MORA).

Comprueba con estos casos (datos de prueba v2):
- Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08
- Edad 14 con 800 días → Años en mora 2
- Obligación al día → Fecha de exigibilidad vacía
- Fecha de exigibilidad mayor a la fecha del sistema → Bloquea la obligación

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF49 · Fecha de exigibilidad y años en mora. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Para toda obligación con valor de mora mayor a cero se reporta la fecha de exigibilidad y, con edad 14, los años en mora.
Reglas del RF:
- Fecha de exigibilidad = fecha límite de pago de la cuota impaga más antigua (RF7), en AAAAMMDD.
- Si la edad es 14 se calculan y reportan los años en mora.
- Al quedar al día se envía la fecha de exigibilidad vacía.
- Si la fecha de exigibilidad es mayor a la fecha del sistema, la obligación se bloquea en la validación del corte (correctiva, RF53).

Endpoints a implementar o ajustar: GET /api/obligaciones/{id}/ (fecha_exigibilidad, anios_mora).

Haz esto:
1. Exponer fecha_exigibilidad (AAAA-MM-DD en la API) y anios_mora. Al día: fecha nula.

Usa estas tablas, vistas y módulos: NV_REPORTE_DETALLE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08
- Edad 14 con 800 días → Años en mora 2
- Obligación al día → Fecha de exigibilidad vacía
- Fecha de exigibilidad mayor a la fecha del sistema → Bloquea la obligación

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF49 · Fecha de exigibilidad y años en mora. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Para toda obligación con valor de mora mayor a cero se reporta la fecha de exigibilidad y, con edad 14, los años en mora.

Implementa:
1. Pantalla 9, detalle: «Fecha de exigibilidad» con la nota «Cuota más antigua sin pagar (RF49)» y, con edad 14, «Años en mora: N».

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08
- Edad 14 con 800 días → Años en mora 2
- Obligación al día → Fecha de exigibilidad vacía
- Fecha de exigibilidad mayor a la fecha del sistema → Bloquea la obligación

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF49 · Fecha de exigibilidad y años en mora. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: Para toda obligación con valor de mora mayor a cero se reporta la fecha de exigibilidad y, con edad 14, los años en mora.
Reglas del RF:
- Fecha de exigibilidad = fecha límite de pago de la cuota impaga más antigua (RF7), en AAAAMMDD.
- Si la edad es 14 se calculan y reportan los años en mora.
- Al quedar al día se envía la fecha de exigibilidad vacía.
- Si la fecha de exigibilidad es mayor a la fecha del sistema, la obligación se bloquea en la validación del corte (correctiva, RF53).

Qué probar:
- Vistas y tablas: V_MORA_OBLIGACION; V_VALIDACION_CORTE; NV_REPORTE_DETALLE (FECHA_EXIGIBILIDAD, ANIOS_MORA)
- Endpoints: GET /api/obligaciones/{id}/ (fecha_exigibilidad, anios_mora)

Casos mínimos (automatiza todos):
1. Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08
2. Edad 14 con 800 días → Años en mora 2
3. Obligación al día → Fecha de exigibilidad vacía
4. Fecha de exigibilidad mayor a la fecha del sistema → Bloquea la obligación

Entrega: tests/test_rf49_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF49 · Fecha de exigibilidad y años en mora (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Angel, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: «Fecha de exigibilidad» con la nota «Cuota más antigua sin pagar (RF49)» y, con edad 14, «Años en mora: N».

Reglas del RF:
- Fecha de exigibilidad = fecha límite de pago de la cuota impaga más antigua (RF7), en AAAAMMDD.
- Si la edad es 14 se calculan y reportan los años en mora.
- Al quedar al día se envía la fecha de exigibilidad vacía.
- Si la fecha de exigibilidad es mayor a la fecha del sistema, la obligación se bloquea en la validación del corte (correctiva, RF53).

Casos mínimos:
1. Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08
2. Edad 14 con 800 días → Años en mora 2
3. Obligación al día → Fecha de exigibilidad vacía
4. Fecha de exigibilidad mayor a la fecha del sistema → Bloquea la obligación

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF50 · Control de eliminaciones

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF50 · Control de eliminaciones. Parte de base de datos (Script 11 (NV_ELIMINACION)).
Resumen del RF: Toda obligación o titular eliminado ante TransUnion se registra y se excluye de los cortes siguientes.
Reglas del RF:
- Precondición: se eliminó una obligación o un titular por Actualización en Línea (RF24) o por registro tipo 4.
- Se registra la eliminación con fecha, motivo (Tabla 28) y número de transacción, y el número de obligación se excluye de los cortes siguientes.
- Si hay que volver a reportar una obligación eliminada, queda bloqueada hasta que se registre el proceso de activación hecho con TransUnion.
- TransUnion rechaza las eliminadas con la correctiva 117 (Manual, págs. 19, 24 y 57).

Haz esto:
1. Crear NV_ELIMINACION con índice único parcial por OBLIGACION_ID mientras BLOQUEADA = S y FK a NV_NOVEDAD. NV_OBLIGACION.ELIMINADA (script 10) se actualiza desde el backend.

Usa estos objetos: NV_ELIMINACION; NV_OBLIGACION.ELIMINADA; NV_MOTIVO_ELIMINACION.

Comprueba con estos casos (datos de prueba v2):
- Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
- Corte siguiente → La eliminada no cuenta como omitida (RF21)
- Reactivar sin número de activación → 400
- Reactivar con número → Vuelve a poder reportarse

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF50 · Control de eliminaciones. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Toda obligación o titular eliminado ante TransUnion se registra y se excluye de los cortes siguientes.
Reglas del RF:
- Precondición: se eliminó una obligación o un titular por Actualización en Línea (RF24) o por registro tipo 4.
- Se registra la eliminación con fecha, motivo (Tabla 28) y número de transacción, y el número de obligación se excluye de los cortes siguientes.
- Si hay que volver a reportar una obligación eliminada, queda bloqueada hasta que se registre el proceso de activación hecho con TransUnion.
- TransUnion rechaza las eliminadas con la correctiva 117 (Manual, págs. 19, 24 y 57).

Endpoints a implementar o ajustar: GET /api/eliminaciones/; POST /api/eliminaciones/{id}/reactivar/; POST /api/novedades/{id}/gestionar/ (cuando es Eliminación).

Haz esto:
1. Al gestionar una novedad de Eliminación sobre una obligación: crear la fila de NV_ELIMINACION (BLOQUEADA = S), poner NV_OBLIGACION.ELIMINADA = S y dejar el evento en bitácora, en una sola transacción.
2. reactivar: exige el número de la activación hecha con TransUnion; BLOQUEADA = N, FECHA_ACTIVACION y ELIMINADA = N.
3. El ciclo y el corte excluyen siempre las ELIMINADA = S (MOTIVO_EXCLUSION = ELIMINADA) y no las cuentan como omitidas.

Usa estas tablas, vistas y módulos: NV_ELIMINACION; NV_NOVEDAD; NV_OBLIGACION; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
- Corte siguiente → La eliminada no cuenta como omitida (RF21)
- Reactivar sin número de activación → 400
- Reactivar con número → Vuelve a poder reportarse

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF50 · Control de eliminaciones. Parte de frontend: pantalla 14 y 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Toda obligación o titular eliminado ante TransUnion se registra y se excluye de los cortes siguientes.

Implementa:
1. Pantalla 14, sección «Obligaciones eliminadas en TransUnion (RF50)»: tabla (Obligación | Motivo | Fecha | Confirmación) y acción «Reactivar» con el número de la activación.
2. Pantalla 9: insignia «Eliminada en TransUnion», filtro «Eliminadas» y el texto del detalle «no se vuelve a reportar y su número no se reutiliza».

Consume estos endpoints (según el contrato): GET /api/eliminaciones/; POST /api/eliminaciones/{id}/reactivar/; GET /api/obligaciones/?estado=ELIM.

Pruebas con vitest (y MSW) para estos casos:
- Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
- Corte siguiente → La eliminada no cuenta como omitida (RF21)
- Reactivar sin número de activación → 400
- Reactivar con número → Vuelve a poder reportarse

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF50 · Control de eliminaciones. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: Toda obligación o titular eliminado ante TransUnion se registra y se excluye de los cortes siguientes.
Reglas del RF:
- Precondición: se eliminó una obligación o un titular por Actualización en Línea (RF24) o por registro tipo 4.
- Se registra la eliminación con fecha, motivo (Tabla 28) y número de transacción, y el número de obligación se excluye de los cortes siguientes.
- Si hay que volver a reportar una obligación eliminada, queda bloqueada hasta que se registre el proceso de activación hecho con TransUnion.
- TransUnion rechaza las eliminadas con la correctiva 117 (Manual, págs. 19, 24 y 57).

Qué probar:
- Vistas y tablas: NV_ELIMINACION; NV_OBLIGACION.ELIMINADA; NV_MOTIVO_ELIMINACION
- Endpoints: GET /api/eliminaciones/; POST /api/eliminaciones/{id}/reactivar/; POST /api/novedades/{id}/gestionar/ (cuando es Eliminación)

Casos mínimos (automatiza todos):
1. Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
2. Corte siguiente → La eliminada no cuenta como omitida (RF21)
3. Reactivar sin número de activación → 400
4. Reactivar con número → Vuelve a poder reportarse

Entrega: tests/test_rf50_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF50 · Control de eliminaciones (rol del RF: Analista de Cartera; pantalla del mockup v3: 14 y 9). Lo implementaron Angel, Jose Luis (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 14, sección «Obligaciones eliminadas en TransUnion (RF50)»: tabla (Obligación | Motivo | Fecha | Confirmación) y acción «Reactivar» con el número de la activación.
- Pantalla 9: insignia «Eliminada en TransUnion», filtro «Eliminadas» y el texto del detalle «no se vuelve a reportar y su número no se reutiliza».

Reglas del RF:
- Precondición: se eliminó una obligación o un titular por Actualización en Línea (RF24) o por registro tipo 4.
- Se registra la eliminación con fecha, motivo (Tabla 28) y número de transacción, y el número de obligación se excluye de los cortes siguientes.
- Si hay que volver a reportar una obligación eliminada, queda bloqueada hasta que se registre el proceso de activación hecho con TransUnion.
- TransUnion rechaza las eliminadas con la correctiva 117 (Manual, págs. 19, 24 y 57).

Casos mínimos:
1. Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
2. Corte siguiente → La eliminada no cuenta como omitida (RF21)
3. Reactivar sin número de activación → 400
4. Reactivar con número → Vuelve a poder reportarse

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF51 · Expresión de valores en miles de pesos

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF51 · Expresión de valores en miles de pesos. Parte de base de datos (V_REPORTE_TU v2).
Resumen del RF: Se reportan en miles de pesos, como enteros sin decimales, el valor inicial, la mora, el saldo, la cuota, el cargo fijo y el valor real pagado. Ningún valor en mora se reporta como cero por el redondeo.
Reglas del RF:
- Cada valor se convierte a miles con la regla de redondeo aprobada. [Propuesta: al millar más cercano y, si un valor mayor a cero redondea a cero, reportar 1 (P-TU-02).]
- Los valores en pesos se conservan en NexoVolt para consulta y auditoría (NV_REPORTE_DETALLE ya los guarda en pesos).
- Alerta informativa si un valor es menor a $10.000 o mayor a $99 millones (Manual, p. 19).

Haz esto:
1. Coordinar con Dilan: la vista entrega los valores en pesos y el backend convierte a miles. Retirar el ROUND(/DIVISOR_VALORES) de V_REPORTE_TU solo cuando Dilan lo confirme; el parámetro DIVISOR_VALORES = 1000 sigue siendo la fuente.

Usa estos objetos: V_REPORTE_TU; V_CONFIG.DIVISOR_VALORES; NV_REPORTE_DETALLE.

Comprueba con estos casos (datos de prueba v2):
- Mora de $400 → Reporta 1 (no 0)
- Saldo de $1.276.016 → Reporta 1276
- Valor de $9.000 → Advertencia informativa
- Valor de $120 millones → Advertencia informativa

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF51 · Expresión de valores en miles de pesos. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Se reportan en miles de pesos, como enteros sin decimales, el valor inicial, la mora, el saldo, la cuota, el cargo fijo y el valor real pagado. Ningún valor en mora se reporta como cero por el redondeo.
Reglas del RF:
- Cada valor se convierte a miles con la regla de redondeo aprobada. [Propuesta: al millar más cercano y, si un valor mayor a cero redondea a cero, reportar 1 (P-TU-02).]
- Los valores en pesos se conservan en NexoVolt para consulta y auditoría (NV_REPORTE_DETALLE ya los guarda en pesos).
- Alerta informativa si un valor es menor a $10.000 o mayor a $99 millones (Manual, p. 19).

Endpoints a implementar o ajustar: POST /api/extracciones/{id}/archivo/ (conversión); GET /api/extracciones/{id}/validaciones/ (alerta informativa).

Haz esto:
1. Función única a_miles(valor_en_pesos, divisor) con la regla de redondeo en un solo lugar y la salvaguarda «mayor a cero no puede dar cero».
2. Usarla en el generador (RF20) para valor inicial, mora, saldo, cuota, cargo fijo y valor real pagado; sin decimales.
3. Alerta informativa si el valor está fuera de $10.000 a $99 millones.

Usa estas tablas, vistas y módulos: V_REPORTE_TU; V_CONFIG; NV_PARAMETRO (DIVISOR_VALORES).
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Mora de $400 → Reporta 1 (no 0)
- Saldo de $1.276.016 → Reporta 1276
- Valor de $9.000 → Advertencia informativa
- Valor de $120 millones → Advertencia informativa
- Valores sin decimales → Todos enteros

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF51 · Expresión de valores en miles de pesos. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Se reportan en miles de pesos, como enteros sin decimales, el valor inicial, la mora, el saldo, la cuota, el cargo fijo y el valor real pagado. Ningún valor en mora se reporta como cero por el redondeo.

Implementa:
1. Pantalla 12: ítem informativo «Valores en miles de pesos (RF51)» con la nota «Regla de redondeo por confirmar con TransUnion» y la lista de valores fuera de rango como advertencia.

Consume estos endpoints (según el contrato): GET /api/extracciones/{id}/validaciones/.

Pruebas con vitest (y MSW) para estos casos:
- Mora de $400 → Reporta 1 (no 0)
- Saldo de $1.276.016 → Reporta 1276
- Valor de $9.000 → Advertencia informativa
- Valor de $120 millones → Advertencia informativa
- Valores sin decimales → Todos enteros

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF51 · Expresión de valores en miles de pesos. Lo implementaron: base de datos Angel y backend Dilan (tú no).
Resumen del RF: Se reportan en miles de pesos, como enteros sin decimales, el valor inicial, la mora, el saldo, la cuota, el cargo fijo y el valor real pagado. Ningún valor en mora se reporta como cero por el redondeo.
Reglas del RF:
- Cada valor se convierte a miles con la regla de redondeo aprobada. [Propuesta: al millar más cercano y, si un valor mayor a cero redondea a cero, reportar 1 (P-TU-02).]
- Los valores en pesos se conservan en NexoVolt para consulta y auditoría (NV_REPORTE_DETALLE ya los guarda en pesos).
- Alerta informativa si un valor es menor a $10.000 o mayor a $99 millones (Manual, p. 19).

Qué probar:
- Vistas y tablas: V_REPORTE_TU; V_CONFIG.DIVISOR_VALORES; NV_REPORTE_DETALLE
- Endpoints: POST /api/extracciones/{id}/archivo/ (conversión); GET /api/extracciones/{id}/validaciones/ (alerta informativa)

Casos mínimos (automatiza todos):
1. Mora de $400 → Reporta 1 (no 0)
2. Saldo de $1.276.016 → Reporta 1276
3. Valor de $9.000 → Advertencia informativa
4. Valor de $120 millones → Advertencia informativa
5. Valores sin decimales → Todos enteros

Entrega: tests/test_rf51_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF51 · Expresión de valores en miles de pesos (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Angel, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12: ítem informativo «Valores en miles de pesos (RF51)» con la nota «Regla de redondeo por confirmar con TransUnion» y la lista de valores fuera de rango como advertencia.

Reglas del RF:
- Cada valor se convierte a miles con la regla de redondeo aprobada. [Propuesta: al millar más cercano y, si un valor mayor a cero redondea a cero, reportar 1 (P-TU-02).]
- Los valores en pesos se conservan en NexoVolt para consulta y auditoría (NV_REPORTE_DETALLE ya los guarda en pesos).
- Alerta informativa si un valor es menor a $10.000 o mayor a $99 millones (Manual, p. 19).

Casos mínimos:
1. Mora de $400 → Reporta 1 (no 0)
2. Saldo de $1.276.016 → Reporta 1276
3. Valor de $9.000 → Advertencia informativa
4. Valor de $120 millones → Advertencia informativa
5. Valores sin decimales → Todos enteros

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF52 · Composición de los valores de la obligación

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF52 · Composición de los valores de la obligación. Parte de base de datos (V_MORA_OBLIGACION).
Resumen del RF: Para cada obligación se calculan valor inicial, saldo, valor de mora y valor de la cuota con los conceptos aprobados por CENS, parametrizables en RF35.
Reglas del RF:
- Valor inicial: monto total financiado (CREDITOS.DEUDA_INICIAL_CAP). [Confirmar si suma intereses.]
- Saldo: capital pendiente a la fecha de corte (CREDITOS.DEUDA_ACTUAL_CAP). [Confirmar si incluye intereses (DEUDA_ACTUAL_INT).]
- Valor de mora: lo facturado, vencido y no pagado a la fecha de corte.
- Valor de la cuota: la cuota periódica de la financiación. [Confirmar conceptos: 30 y, si aplica, 241.] Intereses de mora (concepto 472): [se incluyen o no, por confirmar].
- Si el saldo es mayor al valor inicial: alerta informativa (Manual, p. 18). Saldo, mora y cuota son tres valores distintos.

Haz esto:
1. En V_OBLIGACION_SAC / V_MORA_OBLIGACION dejar cada valor en una columna con su origen documentado: VALOR_INICIAL, VALOR_SALDO, VALOR_MORA (de V_MORA_OBLIGACION) y VALOR_CUOTA, sin mezclarlos.
2. La inclusión de intereses queda como parámetro (NV_PARAMETRO) y no como un cambio de código.

Usa estos objetos: V_OBLIGACION_SAC; V_MORA_OBLIGACION; SAC.CREDITOS; NV_CONCEPTO_REPORTABLE; NV_PARAMETRO.

Comprueba con estos casos (datos de prueba v2):
- Crédito con deuda inicial 1.500.000 y saldo 1.276.016 → Valor inicial y saldo distintos
- Saldo mayor al valor inicial → Advertencia informativa
- Obligación con 2 cuotas vencidas de $70.000 → Valor de mora $140.000 distinto del saldo

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF52 · Composición de los valores de la obligación. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Para cada obligación se calculan valor inicial, saldo, valor de mora y valor de la cuota con los conceptos aprobados por CENS, parametrizables en RF35.
Reglas del RF:
- Valor inicial: monto total financiado (CREDITOS.DEUDA_INICIAL_CAP). [Confirmar si suma intereses.]
- Saldo: capital pendiente a la fecha de corte (CREDITOS.DEUDA_ACTUAL_CAP). [Confirmar si incluye intereses (DEUDA_ACTUAL_INT).]
- Valor de mora: lo facturado, vencido y no pagado a la fecha de corte.
- Valor de la cuota: la cuota periódica de la financiación. [Confirmar conceptos: 30 y, si aplica, 241.] Intereses de mora (concepto 472): [se incluyen o no, por confirmar].
- Si el saldo es mayor al valor inicial: alerta informativa (Manual, p. 18). Saldo, mora y cuota son tres valores distintos.

Endpoints a implementar o ajustar: GET /api/obligaciones/{id}/ (valor_inicial, saldo, valor_mora, valor_cuota); GET /api/extracciones/{id}/validaciones/.

Haz esto:
1. Exponer los cuatro valores por separado en el detalle y en el listado (saldo y mora).
2. La alerta «saldo mayor al valor inicial» sale como informativa (regla SALDO_MAYOR_VALOR_INICIAL de V_VALIDACION_CORTE).

Usa estas tablas, vistas y módulos: V_MORA_OBLIGACION; NV_REPORTE_DETALLE.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Crédito con deuda inicial 1.500.000 y saldo 1.276.016 → Valor inicial y saldo distintos
- Saldo mayor al valor inicial → Advertencia informativa
- Obligación con 2 cuotas vencidas de $70.000 → Valor de mora $140.000 distinto del saldo

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF52 · Composición de los valores de la obligación. Parte de frontend: pantalla 9 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Para cada obligación se calculan valor inicial, saldo, valor de mora y valor de la cuota con los conceptos aprobados por CENS, parametrizables en RF35.

Implementa:
1. Pantalla 9, detalle: «Saldo», «Valor en mora» y «Valor de la cuota» como campos separados (al cerrar, «Antes $X: al cerrar se reporta en $0» según la maqueta).

Consume estos endpoints (según el contrato): GET /api/obligaciones/{id}/.

Pruebas con vitest (y MSW) para estos casos:
- Crédito con deuda inicial 1.500.000 y saldo 1.276.016 → Valor inicial y saldo distintos
- Saldo mayor al valor inicial → Advertencia informativa
- Obligación con 2 cuotas vencidas de $70.000 → Valor de mora $140.000 distinto del saldo

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF52 · Composición de los valores de la obligación. Lo implementaron: base de datos Angel y backend Dilan (tú no).
Resumen del RF: Para cada obligación se calculan valor inicial, saldo, valor de mora y valor de la cuota con los conceptos aprobados por CENS, parametrizables en RF35.
Reglas del RF:
- Valor inicial: monto total financiado (CREDITOS.DEUDA_INICIAL_CAP). [Confirmar si suma intereses.]
- Saldo: capital pendiente a la fecha de corte (CREDITOS.DEUDA_ACTUAL_CAP). [Confirmar si incluye intereses (DEUDA_ACTUAL_INT).]
- Valor de mora: lo facturado, vencido y no pagado a la fecha de corte.
- Valor de la cuota: la cuota periódica de la financiación. [Confirmar conceptos: 30 y, si aplica, 241.] Intereses de mora (concepto 472): [se incluyen o no, por confirmar].
- Si el saldo es mayor al valor inicial: alerta informativa (Manual, p. 18). Saldo, mora y cuota son tres valores distintos.

Qué probar:
- Vistas y tablas: V_OBLIGACION_SAC; V_MORA_OBLIGACION; SAC.CREDITOS; NV_CONCEPTO_REPORTABLE; NV_PARAMETRO
- Endpoints: GET /api/obligaciones/{id}/ (valor_inicial, saldo, valor_mora, valor_cuota); GET /api/extracciones/{id}/validaciones/

Casos mínimos (automatiza todos):
1. Crédito con deuda inicial 1.500.000 y saldo 1.276.016 → Valor inicial y saldo distintos
2. Saldo mayor al valor inicial → Advertencia informativa
3. Obligación con 2 cuotas vencidas de $70.000 → Valor de mora $140.000 distinto del saldo

Entrega: tests/test_rf52_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF52 · Composición de los valores de la obligación (rol del RF: Analista de Cartera; pantalla del mockup v3: 9). Lo implementaron Angel, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 9, detalle: «Saldo», «Valor en mora» y «Valor de la cuota» como campos separados (al cerrar, «Antes $X: al cerrar se reporta en $0» según la maqueta).

Reglas del RF:
- Valor inicial: monto total financiado (CREDITOS.DEUDA_INICIAL_CAP). [Confirmar si suma intereses.]
- Saldo: capital pendiente a la fecha de corte (CREDITOS.DEUDA_ACTUAL_CAP). [Confirmar si incluye intereses (DEUDA_ACTUAL_INT).]
- Valor de mora: lo facturado, vencido y no pagado a la fecha de corte.
- Valor de la cuota: la cuota periódica de la financiación. [Confirmar conceptos: 30 y, si aplica, 241.] Intereses de mora (concepto 472): [se incluyen o no, por confirmar].
- Si el saldo es mayor al valor inicial: alerta informativa (Manual, p. 18). Saldo, mora y cuota son tres valores distintos.

Casos mínimos:
1. Crédito con deuda inicial 1.500.000 y saldo 1.276.016 → Valor inicial y saldo distintos
2. Saldo mayor al valor inicial → Advertencia informativa
3. Obligación con 2 cuotas vencidas de $70.000 → Valor de mora $140.000 distinto del saldo

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF53 · Validación del corte contra el Manual

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF53 · Validación del corte contra el Manual. Parte de base de datos (V_VALIDACION_CORTE v2).
Resumen del RF: Antes de pasar un corte a VALIDADO se aplican las reglas del Manual: toda regla correctiva de TransUnion bloquea la validación y toda regla informativa se muestra como advertencia.
Reglas del RF:
- Correctivas (bloquean): campos obligatorios de Servicios (tipo y número de identificación, nombre, número de obligación, sucursal, calidad, estado, edad de mora, fecha de corte, valor de mora); fecha límite de pago (salvo castigadas); edad de mora mayor a 00 sin valor de mora; primer reporte inválido (RF10); cambio de estado no permitido por la Matriz; cierre incompleto (RF22); número de obligación de más de 20 caracteres o con caracteres no permitidos; fecha de corte no posterior a la del último corte enviado; fecha de exigibilidad futura; estado sin homologar (RF48); omisiones frente al último corte (RF21).
- Informativas (advierten): cuotas en mora incoherentes; saldo mayor al valor inicial; valores fuera de $10.000 a $99 millones; pago de mora sin fecha de pago; edad 12 a 14 sin fecha de exigibilidad; valor real pagado no reportado; tipo de entidad, código de entidad o sucursal con marcador (el archivo se genera, pero queda no apto para envío).
- Si hay al menos una correctiva: no se valida el corte y se muestra la lista por obligación.

Haz esto:
1. Agregar a V_VALIDACION_CORTE las reglas que faltan, cada una con REGLA, SEVERIDAD y MENSAJE en español: SIN_NOMBRE, SIN_NUMERO_OBLIGACION, NUMERO_OBLIGACION_INVALIDO (más de 20 caracteres o fuera de [A-Za-z0-9()*,-./\_¯·], con REGEXP_LIKE), SIN_SUCURSAL, SIN_CALIDAD, SIN_ESTADO, SIN_EDAD, FECHA_CORTE_NO_POSTERIOR, FECHA_EXIGIBILIDAD_FUTURA, ESTADO_SIN_HOMOLOGAR, OMISION_VS_ULTIMO_CORTE (obligación activa del último corte sin fila en el nuevo) y las informativas del RF.
2. Cambiar SUCURSAL_PENDIENTE (hoy CORRECTIVA, LIKE PEND%) por ENTIDAD_CON_MARCADOR (INFORMATIVA) cuando TIPO_ENTIDAD, CODIGO_ENTIDAD o CODIGO_SUCURSAL empiecen por X.
3. SIN_FECHA_LIMITE_PAGO pasa a CORRECTIVA salvo estado 06. CAMBIO_ESTADO_SIN_REGLA debe desaparecer cuando la matriz esté completa (Clara, script 12).
4. Coordinar con Clara (V_CALCULO_CORTE) los nombres de columna nuevos.

Usa estos objetos: V_VALIDACION_CORTE; NV_REPORTE_DETALLE; V_ULTIMO_REPORTE; NV_TRANSICION_ESTADO; NV_PARAMETRO; NV_ESTADO_TU.

Comprueba con estos casos (datos de prueba v2):
- Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
- Número de obligación de 21 caracteres → Correctiva
- Entidad con marcadores XXX → Solo advertencia: el archivo se genera, no apto
- Obligación activa del último corte omitida → Correctiva OMISION_VS_ULTIMO_CORTE

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF53 · Validación del corte contra el Manual. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Antes de pasar un corte a VALIDADO se aplican las reglas del Manual: toda regla correctiva de TransUnion bloquea la validación y toda regla informativa se muestra como advertencia.
Reglas del RF:
- Correctivas (bloquean): campos obligatorios de Servicios (tipo y número de identificación, nombre, número de obligación, sucursal, calidad, estado, edad de mora, fecha de corte, valor de mora); fecha límite de pago (salvo castigadas); edad de mora mayor a 00 sin valor de mora; primer reporte inválido (RF10); cambio de estado no permitido por la Matriz; cierre incompleto (RF22); número de obligación de más de 20 caracteres o con caracteres no permitidos; fecha de corte no posterior a la del último corte enviado; fecha de exigibilidad futura; estado sin homologar (RF48); omisiones frente al último corte (RF21).
- Informativas (advierten): cuotas en mora incoherentes; saldo mayor al valor inicial; valores fuera de $10.000 a $99 millones; pago de mora sin fecha de pago; edad 12 a 14 sin fecha de exigibilidad; valor real pagado no reportado; tipo de entidad, código de entidad o sucursal con marcador (el archivo se genera, pero queda no apto para envío).
- Si hay al menos una correctiva: no se valida el corte y se muestra la lista por obligación.

Endpoints a implementar o ajustar: GET /api/extracciones/{id}/validaciones/; POST /api/extracciones/{id}/validar/ (existente, ajustar).

Haz esto:
1. GET validaciones: devuelve {correctivas: [...], informativas: [...], resumen} agrupando por regla y obligación (identificación enmascarada), sin cambiar el estado del corte.
2. POST validar: si hay correctivas responde 409 con esa misma lista y el corte sigue en BORRADOR; si no hay, pasa a VALIDADO y copia el resultado a NV_INCONSISTENCIA.
3. Avisar «archivo no apto para envío» cuando alguna regla de marcador de la entidad esté activa.

Usa estas tablas, vistas y módulos: V_VALIDACION_CORTE; NV_INCONSISTENCIA; NV_CORTE; cartera/servicios.py (validar_corte).
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
- Número de obligación de 21 caracteres → Correctiva
- Entidad con marcadores XXX → Solo advertencia: el archivo se genera, no apto
- Obligación activa del último corte omitida → Correctiva OMISION_VS_ULTIMO_CORTE
- Saldo mayor al valor inicial → Informativa; no bloquea
- Corte sin ninguna correctiva → Pasa a VALIDADO

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF53 · Validación del corte contra el Manual. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Antes de pasar un corte a VALIDADO se aplican las reglas del Manual: toda regla correctiva de TransUnion bloquea la validación y toda regla informativa se muestra como advertencia.

Implementa:
1. Pantalla 12, tarjeta «Validaciones antes de generar (RF53)»: lista con icono por nivel (correcto, error, advertencia, informativo), título y detalle de cada regla (actualización mensual del corte, cambios de estado y primer reporte, números de obligación, campos de cierre, valores en miles, datos de la entidad, mora de más de 18 meses).
2. Las correctivas deshabilitan «Generar archivo plano» y llevan enlace a la obligación; las informativas no bloquean.

Consume estos endpoints (según el contrato): GET /api/extracciones/{id}/validaciones/; POST /api/extracciones/{id}/validar/.

Pruebas con vitest (y MSW) para estos casos:
- Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
- Número de obligación de 21 caracteres → Correctiva
- Entidad con marcadores XXX → Solo advertencia: el archivo se genera, no apto
- Obligación activa del último corte omitida → Correctiva OMISION_VS_ULTIMO_CORTE
- Saldo mayor al valor inicial → Informativa; no bloquea

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF53 · Validación del corte contra el Manual. Lo implementaron: base de datos Angel y backend Dilan (tú no).
Resumen del RF: Antes de pasar un corte a VALIDADO se aplican las reglas del Manual: toda regla correctiva de TransUnion bloquea la validación y toda regla informativa se muestra como advertencia.
Reglas del RF:
- Correctivas (bloquean): campos obligatorios de Servicios (tipo y número de identificación, nombre, número de obligación, sucursal, calidad, estado, edad de mora, fecha de corte, valor de mora); fecha límite de pago (salvo castigadas); edad de mora mayor a 00 sin valor de mora; primer reporte inválido (RF10); cambio de estado no permitido por la Matriz; cierre incompleto (RF22); número de obligación de más de 20 caracteres o con caracteres no permitidos; fecha de corte no posterior a la del último corte enviado; fecha de exigibilidad futura; estado sin homologar (RF48); omisiones frente al último corte (RF21).
- Informativas (advierten): cuotas en mora incoherentes; saldo mayor al valor inicial; valores fuera de $10.000 a $99 millones; pago de mora sin fecha de pago; edad 12 a 14 sin fecha de exigibilidad; valor real pagado no reportado; tipo de entidad, código de entidad o sucursal con marcador (el archivo se genera, pero queda no apto para envío).
- Si hay al menos una correctiva: no se valida el corte y se muestra la lista por obligación.

Qué probar:
- Vistas y tablas: V_VALIDACION_CORTE; NV_REPORTE_DETALLE; V_ULTIMO_REPORTE; NV_TRANSICION_ESTADO; NV_PARAMETRO; NV_ESTADO_TU
- Endpoints: GET /api/extracciones/{id}/validaciones/; POST /api/extracciones/{id}/validar/ (existente, ajustar)

Casos mínimos (automatiza todos):
1. Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
2. Número de obligación de 21 caracteres → Correctiva
3. Entidad con marcadores XXX → Solo advertencia: el archivo se genera, no apto
4. Obligación activa del último corte omitida → Correctiva OMISION_VS_ULTIMO_CORTE
5. Saldo mayor al valor inicial → Informativa; no bloquea
6. Corte sin ninguna correctiva → Pasa a VALIDADO
7. Fecha de corte igual a la del último corte enviado → Correctiva

Entrega: tests/test_rf53_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF53 · Validación del corte contra el Manual (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Angel, Dilan, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12, tarjeta «Validaciones antes de generar (RF53)»: lista con icono por nivel (correcto, error, advertencia, informativo), título y detalle de cada regla (actualización mensual del corte, cambios de estado y primer reporte, números de obligación, campos de cierre, valores en miles, datos de la entidad, mora de más de 18 meses).
- Las correctivas deshabilitan «Generar archivo plano» y llevan enlace a la obligación; las informativas no bloquean.

Reglas del RF:
- Correctivas (bloquean): campos obligatorios de Servicios (tipo y número de identificación, nombre, número de obligación, sucursal, calidad, estado, edad de mora, fecha de corte, valor de mora); fecha límite de pago (salvo castigadas); edad de mora mayor a 00 sin valor de mora; primer reporte inválido (RF10); cambio de estado no permitido por la Matriz; cierre incompleto (RF22); número de obligación de más de 20 caracteres o con caracteres no permitidos; fecha de corte no posterior a la del último corte enviado; fecha de exigibilidad futura; estado sin homologar (RF48); omisiones frente al último corte (RF21).
- Informativas (advierten): cuotas en mora incoherentes; saldo mayor al valor inicial; valores fuera de $10.000 a $99 millones; pago de mora sin fecha de pago; edad 12 a 14 sin fecha de exigibilidad; valor real pagado no reportado; tipo de entidad, código de entidad o sucursal con marcador (el archivo se genera, pero queda no apto para envío).
- Si hay al menos una correctiva: no se valida el corte y se muestra la lista por obligación.

Casos mínimos:
1. Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
2. Número de obligación de 21 caracteres → Correctiva
3. Entidad con marcadores XXX → Solo advertencia: el archivo se genera, no apto
4. Obligación activa del último corte omitida → Correctiva OMISION_VS_ULTIMO_CORTE
5. Saldo mayor al valor inicial → Informativa; no bloquea
6. Corte sin ninguna correctiva → Pasa a VALIDADO
7. Fecha de corte igual a la del último corte enviado → Correctiva

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF54 · Resultados del cargue de TransUnion

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF54 · Resultados del cargue de TransUnion. Parte de base de datos (Script 11 (NV_CARGUE_*)).
Resumen del RF: El Analista carga los archivos que devuelve TransUnion después de cada cargue; el sistema asocia cada inconsistencia y cada obligación no reportada al corte correspondiente.
Reglas del RF:
- Archivos de resultado delimitados por pipes (|): estadísticos y detalle de correctivas y de alertas; Especiales y 953_Detalle; no reportados (norep). Estructura y nombres en el Manual, págs. 42-43 y 52-54.
- El sistema asocia cada inconsistencia (código, descripción y tipo) a la obligación del corte.
- Marca el corte ENVIADO o, si hay correctivas, ENVIADO_CON_INCONSISTENCIAS.
- Muestra al Analista las obligaciones con inconsistencias y las no reportadas para corregirlas en el siguiente corte. Si el archivo no corresponde al corte o no tiene la estructura esperada, lo rechaza e indica el motivo.
- Con 6 meses seguidos de X o R, TransUnion inactiva el registro.

Haz esto:
1. Crear NV_CARGUE_RESULTADO y NV_CARGUE_INCONSISTENCIA con los CHECK de TIPO_ARCHIVO y TIPO, índices por (CORTE_ID, OBLIGACION_ID) y (CARGUE_ID). Ampliar CK_NV_CORTE_ESTADO con ENVIADO_CON_INCONSISTENCIAS (script 10).

Usa estos objetos: NV_CARGUE_RESULTADO; NV_CARGUE_INCONSISTENCIA; NV_CORTE; NV_ARCHIVO.

Comprueba con estos casos (datos de prueba v2):
- Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS
- Cargar un archivo sin correctivas → El corte queda ENVIADO
- Archivo de otro corte → 422 con el motivo
- Archivo con estructura distinta a la esperada → 422; no se guarda nada

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF54 · Resultados del cargue de TransUnion. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: El Analista carga los archivos que devuelve TransUnion después de cada cargue; el sistema asocia cada inconsistencia y cada obligación no reportada al corte correspondiente.
Reglas del RF:
- Archivos de resultado delimitados por pipes (|): estadísticos y detalle de correctivas y de alertas; Especiales y 953_Detalle; no reportados (norep). Estructura y nombres en el Manual, págs. 42-43 y 52-54.
- El sistema asocia cada inconsistencia (código, descripción y tipo) a la obligación del corte.
- Marca el corte ENVIADO o, si hay correctivas, ENVIADO_CON_INCONSISTENCIAS.
- Muestra al Analista las obligaciones con inconsistencias y las no reportadas para corregirlas en el siguiente corte. Si el archivo no corresponde al corte o no tiene la estructura esperada, lo rechaza e indica el motivo.
- Con 6 meses seguidos de X o R, TransUnion inactiva el registro.

Endpoints a implementar o ajustar: POST /api/archivos/{id}/resultados/ (multipart, uno o varios archivos); GET /api/archivos/{id}/resultados/.

Haz esto:
1. Parser por tipo de archivo (pipes, codificación del Manual): ESTADISTICOS, CORRECTIVAS, ALERTAS, ESPECIALES, DETALLE_953, NOREP. Cada parser en una función aparte y con pruebas con archivos de ejemplo.
2. Validar que el archivo corresponda al corte (nombre y fecha) y a un archivo ya ENVIADO; si no, 422 con el motivo.
3. Asociar cada fila a la obligación por NUMERO_OBLIGACION_TU, guardar en NV_CARGUE_INCONSISTENCIA y actualizar el estado del corte (ENVIADO o ENVIADO_CON_INCONSISTENCIAS).
4. GET: resumen (recibidos, cargados, no reportados) y lista de inconsistencias por obligación. Procesar también los archivos de radicación y cierre de reclamos (RF23).

Usa estas tablas, vistas y módulos: NV_CARGUE_RESULTADO; NV_CARGUE_INCONSISTENCIA; NV_ARCHIVO; NV_CORTE; NV_OBLIGACION; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS
- Cargar un archivo sin correctivas → El corte queda ENVIADO
- Archivo de otro corte → 422 con el motivo
- Archivo con estructura distinta a la esperada → 422; no se guarda nada
- Archivo norep con una obligación → Aparece como no reportada del corte

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF54 · Resultados del cargue de TransUnion. Parte de frontend: pantalla 12 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: El Analista carga los archivos que devuelve TransUnion después de cada cargue; el sistema asocia cada inconsistencia y cada obligación no reportada al corte correspondiente.

Implementa:
1. Pantalla 12, tabla «Archivos generados»: acciones «Registrar envío» (solo si es apto), «Cargar resultados» (solo si fue enviado) y «Ver resultados».
2. Vista «Resultados del cargue · corte dd/mm/aaaa»: resumen (recibidos, cargados, no reportados) y tabla (Obligación | Tipo | Inconsistencia), con carga de uno o varios archivos y mensaje de rechazo cuando no corresponden al corte.

Consume estos endpoints (según el contrato): POST /api/extracciones/{id}/registrar-envio/; POST /api/archivos/{id}/resultados/; GET /api/archivos/{id}/resultados/.

Pruebas con vitest (y MSW) para estos casos:
- Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS
- Cargar un archivo sin correctivas → El corte queda ENVIADO
- Archivo de otro corte → 422 con el motivo
- Archivo con estructura distinta a la esperada → 422; no se guarda nada
- Archivo norep con una obligación → Aparece como no reportada del corte

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF54 · Resultados del cargue de TransUnion. Lo implementaron: base de datos Angel y backend Jose Luis (tú no).
Resumen del RF: El Analista carga los archivos que devuelve TransUnion después de cada cargue; el sistema asocia cada inconsistencia y cada obligación no reportada al corte correspondiente.
Reglas del RF:
- Archivos de resultado delimitados por pipes (|): estadísticos y detalle de correctivas y de alertas; Especiales y 953_Detalle; no reportados (norep). Estructura y nombres en el Manual, págs. 42-43 y 52-54.
- El sistema asocia cada inconsistencia (código, descripción y tipo) a la obligación del corte.
- Marca el corte ENVIADO o, si hay correctivas, ENVIADO_CON_INCONSISTENCIAS.
- Muestra al Analista las obligaciones con inconsistencias y las no reportadas para corregirlas en el siguiente corte. Si el archivo no corresponde al corte o no tiene la estructura esperada, lo rechaza e indica el motivo.
- Con 6 meses seguidos de X o R, TransUnion inactiva el registro.

Qué probar:
- Vistas y tablas: NV_CARGUE_RESULTADO; NV_CARGUE_INCONSISTENCIA; NV_CORTE; NV_ARCHIVO
- Endpoints: POST /api/archivos/{id}/resultados/ (multipart, uno o varios archivos); GET /api/archivos/{id}/resultados/

Casos mínimos (automatiza todos):
1. Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS
2. Cargar un archivo sin correctivas → El corte queda ENVIADO
3. Archivo de otro corte → 422 con el motivo
4. Archivo con estructura distinta a la esperada → 422; no se guarda nada
5. Archivo norep con una obligación → Aparece como no reportada del corte

Entrega: tests/test_rf54_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF54 · Resultados del cargue de TransUnion (rol del RF: Analista de Cartera; pantalla del mockup v3: 12). Lo implementaron Angel, Jose Luis, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 12, tabla «Archivos generados»: acciones «Registrar envío» (solo si es apto), «Cargar resultados» (solo si fue enviado) y «Ver resultados».
- Vista «Resultados del cargue · corte dd/mm/aaaa»: resumen (recibidos, cargados, no reportados) y tabla (Obligación | Tipo | Inconsistencia), con carga de uno o varios archivos y mensaje de rechazo cuando no corresponden al corte.

Reglas del RF:
- Archivos de resultado delimitados por pipes (|): estadísticos y detalle de correctivas y de alertas; Especiales y 953_Detalle; no reportados (norep). Estructura y nombres en el Manual, págs. 42-43 y 52-54.
- El sistema asocia cada inconsistencia (código, descripción y tipo) a la obligación del corte.
- Marca el corte ENVIADO o, si hay correctivas, ENVIADO_CON_INCONSISTENCIAS.
- Muestra al Analista las obligaciones con inconsistencias y las no reportadas para corregirlas en el siguiente corte. Si el archivo no corresponde al corte o no tiene la estructura esperada, lo rechaza e indica el motivo.
- Con 6 meses seguidos de X o R, TransUnion inactiva el registro.

Casos mínimos:
1. Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS
2. Cargar un archivo sin correctivas → El corte queda ENVIADO
3. Archivo de otro corte → 422 con el motivo
4. Archivo con estructura distinta a la esperada → 422; no se guarda nada
5. Archivo norep con una obligación → Aparece como no reportada del corte

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF55 · Rectificación de información reportada

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF55 · Rectificación de información reportada. Parte de base de datos (Script 11 (NV_RECTIFICACION)).
Resumen del RF: Cuando se detecta que un corte ya enviado traía información errada, se registra la corrección y se prepara el insumo para hacerla en TransUnion por Actualización en Línea (Corrección) o por proceso especial masivo.
Reglas del RF:
- El Analista registra obligación, fecha de corte afectada, campo, valor anterior, valor corregido y justificación.
- El sistema guarda la corrección sin borrar el valor original, genera el insumo para TransUnion y registra la confirmación cuando el Analista la carga.
- Si la obligación está cerrada (Saldada, Recuperada), prescrita o insoluta, solo admite su modificación por esta vía.
- El histórico de NexoVolt refleja el valor corregido.

Haz esto:
1. Crear NV_RECTIFICACION con FK a NV_OBLIGACION y NV_CORTE, CHECK de MEDIO y ESTADO, y que VALOR_ANTERIOR sea obligatorio (el original no se borra).

Usa estos objetos: NV_RECTIFICACION; NV_REPORTE_DETALLE; NV_NOVEDAD.

Comprueba con estos casos (datos de prueba v2):
- Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra
- Corte que aún no está ENVIADO → 409: se corrige en el origen, no por rectificación
- Obligación Saldada con movimiento nuevo → Solo admite el cambio por esta vía
- Confirmar sin número de TransUnion → 400

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF55 · Rectificación de información reportada. Parte de backend (rol del RF: Analista de Cartera).
Resumen del RF: Cuando se detecta que un corte ya enviado traía información errada, se registra la corrección y se prepara el insumo para hacerla en TransUnion por Actualización en Línea (Corrección) o por proceso especial masivo.
Reglas del RF:
- El Analista registra obligación, fecha de corte afectada, campo, valor anterior, valor corregido y justificación.
- El sistema guarda la corrección sin borrar el valor original, genera el insumo para TransUnion y registra la confirmación cuando el Analista la carga.
- Si la obligación está cerrada (Saldada, Recuperada), prescrita o insoluta, solo admite su modificación por esta vía.
- El histórico de NexoVolt refleja el valor corregido.

Endpoints a implementar o ajustar: GET /api/rectificaciones/; POST /api/rectificaciones/; POST /api/rectificaciones/{id}/confirmar/.

Haz esto:
1. POST: valida que el corte esté ENVIADO, que la obligación exista y que el campo sea corregible; toma el valor anterior de NV_REPORTE_DETALLE (no lo recibe del cliente) y guarda el corregido y la justificación; crea la novedad de Corrección asociada.
2. Devuelve el insumo de la corrección (texto para TransUnion) y aplica el valor corregido en el histórico sin borrar el original.
3. confirmar: exige la confirmación de TransUnion (ESTADO = CONFIRMADA). Bitácora en cada paso.

Usa estas tablas, vistas y módulos: NV_RECTIFICACION; NV_NOVEDAD; NV_REPORTE_DETALLE; NV_CORTE; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra
- Corte que aún no está ENVIADO → 409: se corrige en el origen, no por rectificación
- Obligación Saldada con movimiento nuevo → Solo admite el cambio por esta vía
- Confirmar sin número de TransUnion → 400

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF55 · Rectificación de información reportada. Parte de frontend: pantalla 14 (rol del RF: Analista de Cartera; el Administrador ve «Acceso restringido»).
Resumen del RF: Cuando se detecta que un corte ya enviado traía información errada, se registra la corrección y se prepara el insumo para hacerla en TransUnion por Actualización en Línea (Corrección) o por proceso especial masivo.

Implementa:
1. Pantalla 14: en el modal «Registrar novedad urgente», al elegir «Corrección» aparecen «Corte que se rectifica (RF55)» y «Medio» (Actualización en Línea o proceso especial) y, además, campo, valor corregido y justificación; la novedad registrada muestra el estado de la rectificación.

Consume estos endpoints (según el contrato): POST /api/rectificaciones/; GET /api/rectificaciones/; POST /api/rectificaciones/{id}/confirmar/.

Pruebas con vitest (y MSW) para estos casos:
- Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra
- Corte que aún no está ENVIADO → 409: se corrige en el origen, no por rectificación
- Obligación Saldada con movimiento nuevo → Solo admite el cambio por esta vía
- Confirmar sin número de TransUnion → 400

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF55 · Rectificación de información reportada. Lo implementaron: base de datos Angel y backend Clara (tú no).
Resumen del RF: Cuando se detecta que un corte ya enviado traía información errada, se registra la corrección y se prepara el insumo para hacerla en TransUnion por Actualización en Línea (Corrección) o por proceso especial masivo.
Reglas del RF:
- El Analista registra obligación, fecha de corte afectada, campo, valor anterior, valor corregido y justificación.
- El sistema guarda la corrección sin borrar el valor original, genera el insumo para TransUnion y registra la confirmación cuando el Analista la carga.
- Si la obligación está cerrada (Saldada, Recuperada), prescrita o insoluta, solo admite su modificación por esta vía.
- El histórico de NexoVolt refleja el valor corregido.

Qué probar:
- Vistas y tablas: NV_RECTIFICACION; NV_REPORTE_DETALLE; NV_NOVEDAD
- Endpoints: GET /api/rectificaciones/; POST /api/rectificaciones/; POST /api/rectificaciones/{id}/confirmar/

Casos mínimos (automatiza todos):
1. Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra
2. Corte que aún no está ENVIADO → 409: se corrige en el origen, no por rectificación
3. Obligación Saldada con movimiento nuevo → Solo admite el cambio por esta vía
4. Confirmar sin número de TransUnion → 400

Entrega: tests/test_rf55_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF55 · Rectificación de información reportada (rol del RF: Analista de Cartera; pantalla del mockup v3: 14). Lo implementaron Angel, Clara (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 14: en el modal «Registrar novedad urgente», al elegir «Corrección» aparecen «Corte que se rectifica (RF55)» y «Medio» (Actualización en Línea o proceso especial) y, además, campo, valor corregido y justificación; la novedad registrada muestra el estado de la rectificación.

Reglas del RF:
- El Analista registra obligación, fecha de corte afectada, campo, valor anterior, valor corregido y justificación.
- El sistema guarda la corrección sin borrar el valor original, genera el insumo para TransUnion y registra la confirmación cuando el Analista la carga.
- Si la obligación está cerrada (Saldada, Recuperada), prescrita o insoluta, solo admite su modificación por esta vía.
- El histórico de NexoVolt refleja el valor corregido.

Casos mínimos:
1. Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra
2. Corte que aún no está ENVIADO → 409: se corrige en el origen, no por rectificación
3. Obligación Saldada con movimiento nuevo → Solo admite el cambio por esta vía
4. Confirmar sin número de TransUnion → 400

Además: entra con el rol Administrador y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

## RF57 · Datos de la entidad y código de sucursal

### Base de datos

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: RF57 · Datos de la entidad y código de sucursal. Parte de base de datos (Script 10).
Resumen del RF: El Administrador parametriza el tipo de entidad, el código de entidad y el código de sucursal de CENS ante TransUnion; se usan en el registro tipo 1, en el nombre del archivo y en cada registro tipo 2. Mientras no haya contrato, los tres llevan un marcador.
Reglas del RF:
- Marcadores por defecto del mismo largo del campo: tipo de entidad XXX, código de entidad XXX y código de sucursal XXXXXX. El archivo conserva su estructura y se corrige con buscar y reemplazar.
- Cuando haya contrato: tipo de entidad (3 dígitos), código de entidad (3 dígitos) y código de sucursal (hasta 6 caracteres).
- Si algún parámetro conserva el marcador, el archivo se genera pero queda «no apto para envío» y la validación del corte lo avisa (RF53).
- Si el valor no cumple la longitud o el tipo del campo, no se guarda. Si hay varias sucursales, cada obligación recibe la que corresponda según la regla de CENS (por definir al contratar).

Haz esto:
1. En el script 10, dejar NV_PARAMETRO con TIPO_ENTIDAD = XXX, CODIGO_ENTIDAD = XXX, CODIGO_SUCURSAL = XXXXXX y CONFIRMADO = N (hoy PENDIENTE y PEND).
2. Quitar de V_CONFIG / V_VALIDACION_CORTE cualquier comparación con PENDIENTE o PEND y reemplazarla por «empieza por X» (coordinar con Angel).

Usa estos objetos: NV_PARAMETRO; V_CONFIG; V_VALIDACION_CORTE.

Comprueba con estos casos (datos de prueba v2):
- Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos
- Guardar 12 en el tipo de entidad → 400 (deben ser 3 dígitos)
- Analista intenta PUT → 403 en español
- Con marcadores → Archivo generado, no apto para envío y advertencia en la validación

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Backend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: RF57 · Datos de la entidad y código de sucursal. Parte de backend (rol del RF: Administrador).
Resumen del RF: El Administrador parametriza el tipo de entidad, el código de entidad y el código de sucursal de CENS ante TransUnion; se usan en el registro tipo 1, en el nombre del archivo y en cada registro tipo 2. Mientras no haya contrato, los tres llevan un marcador.
Reglas del RF:
- Marcadores por defecto del mismo largo del campo: tipo de entidad XXX, código de entidad XXX y código de sucursal XXXXXX. El archivo conserva su estructura y se corrige con buscar y reemplazar.
- Cuando haya contrato: tipo de entidad (3 dígitos), código de entidad (3 dígitos) y código de sucursal (hasta 6 caracteres).
- Si algún parámetro conserva el marcador, el archivo se genera pero queda «no apto para envío» y la validación del corte lo avisa (RF53).
- Si el valor no cumple la longitud o el tipo del campo, no se guarda. Si hay varias sucursales, cada obligación recibe la que corresponda según la regla de CENS (por definir al contratar).

Endpoints a implementar o ajustar: GET /api/entidad/; PUT /api/entidad/.

Haz esto:
1. GET (Analista y Administrador): devuelve tipo_entidad, codigo_entidad, codigo_sucursal y completo (true si ninguno tiene marcador).
2. PUT (solo ADMINISTRADOR; 403 en español para el Analista): valida que el tipo y el código sean 3 dígitos (o XXX) y la sucursal hasta 6 caracteres alfanuméricos (o XXXXXX), guarda en NV_PARAMETRO con CONFIRMADO = S solo si ya no hay marcador, y deja la bitácora «Datos de la entidad actualizados».
3. Todo el código que arma el archivo (RF20) lee estos valores a través de una sola función.

Usa estas tablas, vistas y módulos: NV_PARAMETRO; V_CONFIG; NV_BITACORA.
Si el contrato docs/contrato/openapi.yaml no tiene lo que necesitas, avísame en lugar de inventarlo.

Pruebas con pytest para estos casos:
- Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos
- Guardar 12 en el tipo de entidad → 400 (deben ser 3 dígitos)
- Analista intenta PUT → 403 en español
- Con marcadores → Archivo generado, no apto para envío y advertencia en la validación
- «Volver al relleno» → Los tres valores vuelven a XXX, XXX y XXXXXX

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Frontend

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: RF57 · Datos de la entidad y código de sucursal. Parte de frontend: pantalla 15 (rol del RF: Administrador; el Analista ve «Acceso restringido»).
Resumen del RF: El Administrador parametriza el tipo de entidad, el código de entidad y el código de sucursal de CENS ante TransUnion; se usan en el registro tipo 1, en el nombre del archivo y en cada registro tipo 2. Mientras no haya contrato, los tres llevan un marcador.

Implementa:
1. Pantalla 15 «Datos de la Entidad ante TransUnion» (solo ADMINISTRADOR): aviso del estado (con relleno: «los archivos salen no aptos para envío»; completos: «aptos»), campos Tipo de entidad (3), Código de entidad (3) y Código de sucursal (6) con ayuda y error por campo, y los botones «Guardar datos» y «Volver al relleno».
2. Ítem de menú «Datos de la Entidad» con candado para el Analista. En el panel y en la pantalla 12, aviso para el Analista cuando la entidad tiene relleno.

Consume estos endpoints (según el contrato): GET /api/entidad/; PUT /api/entidad/.

Pruebas con vitest (y MSW) para estos casos:
- Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos
- Guardar 12 en el tipo de entidad → 400 (deben ser 3 dígitos)
- Analista intenta PUT → 403 en español
- Con marcadores → Archivo generado, no apto para envío y advertencia en la validación
- «Volver al relleno» → Los tres valores vuelven a XXX, XXX y XXXXXX

No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Prueba de backend y SQL

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de backend. Escribe pruebas con pytest sin tocar el código de producción: usa el mock de cursor de tests/ayudas.py (valida los marcadores %s) y deja pasar tests/test_sql_marcadores.py; las vistas SQL se prueban además contra la base Oracle de desarrollo con los datos de prueba v2. Si encuentras un defecto, no lo corrijas: descríbelo (entrada, resultado esperado y obtenido) con un código DF-xx.

TAREA: pruebas de backend y SQL del RF57 · Datos de la entidad y código de sucursal. Lo implementaron: base de datos Clara y backend Santiago (tú no).
Resumen del RF: El Administrador parametriza el tipo de entidad, el código de entidad y el código de sucursal de CENS ante TransUnion; se usan en el registro tipo 1, en el nombre del archivo y en cada registro tipo 2. Mientras no haya contrato, los tres llevan un marcador.
Reglas del RF:
- Marcadores por defecto del mismo largo del campo: tipo de entidad XXX, código de entidad XXX y código de sucursal XXXXXX. El archivo conserva su estructura y se corrige con buscar y reemplazar.
- Cuando haya contrato: tipo de entidad (3 dígitos), código de entidad (3 dígitos) y código de sucursal (hasta 6 caracteres).
- Si algún parámetro conserva el marcador, el archivo se genera pero queda «no apto para envío» y la validación del corte lo avisa (RF53).
- Si el valor no cumple la longitud o el tipo del campo, no se guarda. Si hay varias sucursales, cada obligación recibe la que corresponda según la regla de CENS (por definir al contratar).

Qué probar:
- Vistas y tablas: NV_PARAMETRO; V_CONFIG; V_VALIDACION_CORTE
- Endpoints: GET /api/entidad/; PUT /api/entidad/

Casos mínimos (automatiza todos):
1. Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos
2. Guardar 12 en el tipo de entidad → 400 (deben ser 3 dígitos)
3. Analista intenta PUT → 403 en español
4. Con marcadores → Archivo generado, no apto para envío y advertencia en la validación
5. «Volver al relleno» → Los tres valores vuelven a XXX, XXX y XXXXXX

Entrega: tests/test_rf57_*.py, un script SQL de verificación contra la base de desarrollo (un SELECT por caso) y la lista de defectos DF-xx.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Aceptación funcional

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: QA. Redacta y ejecuta casos de aceptación funcional del RF contra el ambiente de desarrollo con los datos de prueba v2. Entrega una tabla con: caso, datos de entrada, pasos, resultado esperado, resultado obtenido, estado (cumple, no cumple o parcial) y evidencia (captura o consulta). Reporta los defectos con un código DF-xx.

TAREA: aceptación funcional del RF57 · Datos de la entidad y código de sucursal (rol del RF: Administrador; pantalla del mockup v3: 15). Lo implementaron Clara, Santiago, Johan (tú no).
Qué debe ver y poder hacer el usuario:
- Pantalla 15 «Datos de la Entidad ante TransUnion» (solo ADMINISTRADOR): aviso del estado (con relleno: «los archivos salen no aptos para envío»; completos: «aptos»), campos Tipo de entidad (3), Código de entidad (3) y Código de sucursal (6) con ayuda y error por campo, y los botones «Guardar datos» y «Volver al relleno».
- Ítem de menú «Datos de la Entidad» con candado para el Analista. En el panel y en la pantalla 12, aviso para el Analista cuando la entidad tiene relleno.

Reglas del RF:
- Marcadores por defecto del mismo largo del campo: tipo de entidad XXX, código de entidad XXX y código de sucursal XXXXXX. El archivo conserva su estructura y se corrige con buscar y reemplazar.
- Cuando haya contrato: tipo de entidad (3 dígitos), código de entidad (3 dígitos) y código de sucursal (hasta 6 caracteres).
- Si algún parámetro conserva el marcador, el archivo se genera pero queda «no apto para envío» y la validación del corte lo avisa (RF53).
- Si el valor no cumple la longitud o el tipo del campo, no se guarda. Si hay varias sucursales, cada obligación recibe la que corresponda según la regla de CENS (por definir al contratar).

Casos mínimos:
1. Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos
2. Guardar 12 en el tipo de entidad → 400 (deben ser 3 dígitos)
3. Analista intenta PUT → 403 en español
4. Con marcadores → Archivo generado, no apto para envío y advertencia en la validación
5. «Volver al relleno» → Los tres valores vuelven a XXX, XXX y XXXXXX

Además: entra con el rol Analista de Cartera y comprueba que ve «Acceso restringido» (pantalla) o recibe 403 (API) donde corresponda.
Entrega: la tabla de casos ejecutados con evidencia y los defectos DF-xx.
```

---

## Pruebas de frontend por pantalla

### Pantalla 11 · Refinanciaciones

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 11 · Refinanciaciones». Lo implementó Johan (tú no). RF cubiertos: RF18.
Qué verificar:
- RF18: Pantalla 11 «Refinanciaciones»: explicación en pasos, tabla (Fecha y registrada por | Obligación original y cierre | Saldo refinanciado | Nueva obligación | Naturaleza (Tabla 11)), botón «Registrar refinanciación» y modal con Obligación original, Naturaleza, Número de cuotas y Fecha, con error por campo.
- RF18: Pantalla 9, detalle: bloque «Obligación reestructurada: 01 · Sí (n) · naturaleza · viene de …» y botón «Registrar refinanciación» solo si la obligación no está cerrada ni eliminada.

Casos mínimos:
1. 2255-7788 refinanciada en 2271-5502 → Original en 02 con modo 16; nueva en 01 reestructurada n = 1; vínculo guardado

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantalla 13 · Reclamos Habeas Data

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 13 · Reclamos Habeas Data». Lo implementó Omar (tú no). RF cubiertos: RF23.
Qué verificar:
- RF23: Pantalla 13 «Reclamos Habeas Data»: tarjetas de conteo, botones «Archivo de marcación (N)» y «Archivo de desmarcación (N)» (deshabilitados si N = 0), tabla (Obligación | Tipología y observación | Fecha del reclamo | Estado | Archivo | Acciones) y botón «Cerrar reclamo» por fila.
- RF23: Modales «Registrar reclamo» (Obligación, Tipología, Fecha, Observación opcional) y «Cerrar reclamo» (Resultado, Fecha de cierre, Observación) con error por campo. Insignia «En reclamo Habeas Data» en la pantalla 9 y panel (tarjeta «Obligaciones en reclamo»).

Casos mínimos:
1. Registrar un reclamo «Pago no reflejado» (2260-5543) → Queda EN_RECLAMO con plazo; la obligación sigue en el archivo

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantalla 9 · Obligaciones y Estados

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 9 · Obligaciones y Estados». Lo implementó Johan (tú no). RF cubiertos: RF10, RF11, RF12, RF13, RF14, RF15, RF16, RF17, RF19, RF45, RF46, RF47, RF49.
Qué verificar:
- RF10: Pantalla 9: etiqueta «Primer reporte» bajo el número de la obligación y campo «Primer reporte: Sí/No» en el detalle.
- RF11: Pantalla 9: columna «Edad de Mora (Tabla 9)» con los días de mora debajo y una marca «Revisar» cuando requiere_revision.
- RF12: Pantalla 9, detalle: bloque «Cierre» («Pagó el dd/mm/aaaa · Modo · Tipo de pago»), candado junto al estado y la posible transición «Pago total → 02 · Saldada (RF12)».
- RF13: Pantalla 9: candado junto al estado, pie «Saldada (02) y Cartera Recuperada (07) se reportan una sola vez…», filtro por estado y alerta de movimiento posterior en el detalle.
- RF14: Pantalla 9: etiqueta «Caducado en el SAC» en la fila (si no está cerrada) y bloque «En el SAC» en el detalle («Crédito caducado» o «No caducado · Caduca a las N cuotas atrasadas»).
- RF15: Pantalla 9, detalle: «Pago total → 07 · Cartera Recuperada (RF15)» en las posibles transiciones desde 03 y 06, y bloque «Cierre» con modo 01 o 16.
- RF16: Pantalla 9: candado y nota «Cartera Recuperada (07) se reporta una sola vez» (misma presentación que RF13).
- RF17: Pantalla 9, detalle: tablas «Cuotas vencidas sin pagar» (Vencimiento, Pendiente, Días) y «Pagos extraídos del sistema comercial» (Corte, Valor, Se aplicó a) con la nota «por confirmar» de la imputación.
- RF19: Pantalla 9: tarjeta «Cuotas en mora por obligación» con las 4 agrupaciones y columna «Valor en Mora y Cuotas en Mora» con insignia (Al día, 1 cuota en mora, N cuotas en mora).
- RF45: Pantalla 9: insignia 06 · Castigada y, en el detalle, «Sigue en Castigada mientras tenga mora».
- RF46: Pantalla 9, detalle: «Paga la mora sin cancelar el saldo → 01 · Vigente (RF46)» con la etiqueta «por confirmar»; pantalla 10: regla en «Qué pasó».
- RF47: Pantalla 9, detalle: bloque «Pago de la mora (RF47): dd/mm/aaaa · Modo · Tipo de pago».
- RF49: Pantalla 9, detalle: «Fecha de exigibilidad» con la nota «Cuota más antigua sin pagar (RF49)» y, con edad 14, «Años en mora: N».

Casos mínimos:
1. Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
2. Cuota más antigua sin pagar de 47 días → Edad 01
3. 2259-1092: pago total estando en 01 → Pasa a 02; saldo, mora, cuota y cuotas en mora en 0; fecha de pago menor o igual al corte
4. Obligación 02 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
5. 2250-0987: 6 cuotas atrasadas con tope de 4 y con mora → Estado 03
6. 2241-3302: en 03 paga todo → Pasa a 07 con fecha de pago
7. Obligación 07 reportada en el corte anterior → No aparece en el archivo nuevo ni cuenta como omitida
8. 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
9. Edad 01 con valor de mora cero → Bloquea con la regla 707
10. 2244-6410: con marca de castigo y mora → Estado 06
11. Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
12. Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
13. Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantalla 12 · Reporte a TransUnion

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 12 · Reporte a TransUnion». Lo implementó Johan (tú no). RF cubiertos: RF20, RF21, RF22, RF51, RF53, RF54.
Qué verificar:
- RF20: Pantalla 12 «Reporte a TransUnion»: selector de fecha de corte, botón «Generar archivo plano» con el avance por pasos, tarjeta «Archivo generado» con «Descargar archivo» y la tabla «Archivos generados» (Fecha y hora, Usuario, Fecha de corte, Obligaciones, Saldo, Archivo, Estado, Acciones).
- RF20: Aviso persistente cuando la entidad tiene marcador: «no apto para envío» (RF57) y el botón «Registrar envío» deshabilitado en ese caso.
- RF21: Pantalla 12, «Validaciones antes de generar»: ítem de omisiones («N de N obligaciones activas del último corte incluidas») y, si falta alguna, la lista con enlace a la obligación.
- RF22: Pantalla 12, «Validaciones antes de generar»: ítem «Campos de cierre (RF22)» con el estado correcto o error y la lista de obligaciones que fallan indicando qué campo falta.
- RF51: Pantalla 12: ítem informativo «Valores en miles de pesos (RF51)» con la nota «Regla de redondeo por confirmar con TransUnion» y la lista de valores fuera de rango como advertencia.
- RF53: Pantalla 12, tarjeta «Validaciones antes de generar (RF53)»: lista con icono por nivel (correcto, error, advertencia, informativo), título y detalle de cada regla (actualización mensual del corte, cambios de estado y primer reporte, números de obligación, campos de cierre, valores en miles, datos de la entidad, mora de más de 18 meses).
- RF53: Las correctivas deshabilitan «Generar archivo plano» y llevan enlace a la obligación; las informativas no bloquean.
- RF54: Pantalla 12, tabla «Archivos generados»: acciones «Registrar envío» (solo si es apto), «Cargar resultados» (solo si fue enviado) y «Ver resultados».
- RF54: Vista «Resultados del cargue · corte dd/mm/aaaa»: resumen (recibidos, cargados, no reportados) y tabla (Obligación | Tipo | Inconsistencia), con carga de uno o varios archivos y mensaje de rechazo cuando no corresponden al corte.

Casos mínimos:
1. Corte validado con 9 obligaciones → Archivo con 1 tipo 1, 9 tipo 2 y 1 tipo 9 (11 registros); todas las líneas tipo 2 miden lo mismo
2. Obligación en 03 del último corte que ya no aparece vigente en SAC → Se incluye en el nuevo corte
3. Cierre completo (2259-1092) → Pasa la validación
4. Mora de $400 → Reporta 1 (no 0)
5. Obligación sin identificación → Correctiva SIN_IDENTIFICACION; no valida
6. Cargar el archivo de correctivas de un corte enviado → Cada inconsistencia queda asociada a su obligación y el corte pasa a ENVIADO_CON_INCONSISTENCIAS

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantalla 10 · Actualización Mensual de Estados

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 10 · Actualización Mensual de Estados». Lo implementó Johan (tú no). RF cubiertos: RF10, RF11, RF17, RF19, RF45, RF46, RF47, RF49.
Qué verificar:
- RF10: Pantalla 10: tarjeta con el conteo «Primer reporte» en el historial de actualizaciones, chips «Obligaciones nuevas por ingresar» y tabla de rechazados (Número, Deudor, Cambio calculado, Motivo).
- RF11: Pantalla 10: en el resultado, columna «Qué pasó» con la regla de RF11 y la edad «antes → después».

Casos mínimos:
1. Obligación nueva al día (2263-9004) → Entra en 01, edad 00, marcada «Primer reporte»
2. Cuota más antigua sin pagar de 47 días → Edad 01
3. 2258-7731: 2 cuotas de $70.000; abono de $70.000 → Se paga la más antigua; mora $70.000; 1 cuota en mora; edad por la cuota restante
4. Edad 01 con valor de mora cero → Bloquea con la regla 707
5. 2244-6410: con marca de castigo y mora → Estado 06
6. Obligación en 03 que paga toda la mora y conserva saldo → Vuelve a 01 y se reporta el pago de la mora
7. Obligación con mora que queda al día → Se reportan fecha de pago, modo 01 y tipo 01; valor real pagado del corte
8. Dos cuotas sin pagar (primera del 14/08) → Fecha de exigibilidad 14/08

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantalla 14 · Novedades Urgentes

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantalla 14 · Novedades Urgentes». Lo implementó Angel (tú no). RF cubiertos: RF24, RF50, RF55.
Qué verificar:
- RF24: Pantalla 14 «Novedades Urgentes»: aviso de que el módulo en línea escribe en la base real, pestañas Todas/Pendientes/Gestionadas con contador, tabla (Tipo | Referencia | Motivo | Detectada y origen | Estado | Acciones) y botón «Gestionar en línea».
- RF24: Modal «Registrar novedad urgente» (Tipo, Sujeto, Número de obligación o identificación, Motivo; si es Corrección, el corte que se rectifica y el medio) y modal «Gestionar en Actualización en Línea» (botón «Abrir Actualización en Línea» y campo obligatorio «Número de confirmación de TransUnion»).
- RF50: Pantalla 14, sección «Obligaciones eliminadas en TransUnion (RF50)»: tabla (Obligación | Motivo | Fecha | Confirmación) y acción «Reactivar» con el número de la activación.
- RF50: Pantalla 9: insignia «Eliminada en TransUnion», filtro «Eliminadas» y el texto del detalle «no se vuelve a reportar y su número no se reutiliza».
- RF55: Pantalla 14: en el modal «Registrar novedad urgente», al elegir «Corrección» aparecen «Corte que se rectifica (RF55)» y «Medio» (Actualización en Línea o proceso especial) y, además, campo, valor corregido y justificación; la novedad registrada muestra el estado de la rectificación.

Casos mínimos:
1. Registrar una Actualización sobre 2262-3318 → Queda PENDIENTE y aparece en la pestaña Pendientes
2. Gestionar la eliminación de 2249-1180 → Obligación eliminada: sale del siguiente corte
3. Rectificar el valor de mora del corte 31/08/2026 de 2258-7731 → Guarda anterior y corregido; el original no se borra

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Pantallas 15 y 16 · Datos de la entidad y Homologación (Administrador)

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Pantallas 15 y 16 · Datos de la entidad y Homologación (Administrador)». Lo implementó Johan (tú no). RF cubiertos: RF48, RF57.
Qué verificar:
- RF48: Pantalla 16 NUEVA «Homologación de estados» (Johan primero la dibuja como pantalla del mockup v3 y Santiago la aprueba): tabla de los 10 estados (código, nombre, usado sí/no) y tabla de homologación del SAC (estado SAC, descripción, estado TransUnion o «cierre», confirmado) con edición en línea y aviso de estados sin homologar.
- RF48: Solo ADMINISTRADOR: RequireRole y un ítem de menú bajo «Administración». El Analista ve «Acceso restringido».
- RF57: Pantalla 15 «Datos de la Entidad ante TransUnion» (solo ADMINISTRADOR): aviso del estado (con relleno: «los archivos salen no aptos para envío»; completos: «aptos»), campos Tipo de entidad (3), Código de entidad (3) y Código de sucursal (6) con ayuda y error por campo, y los botones «Guardar datos» y «Volver al relleno».
- RF57: Ítem de menú «Datos de la Entidad» con candado para el Analista. En el panel y en la pantalla 12, aviso para el Analista cuando la entidad tiene relleno.

Casos mínimos:
1. Administrador cambia A → 01 → Se guarda y queda en bitácora
2. Administrador guarda 001 / 123 / A1B2C3 → Se guarda; los archivos nuevos salen aptos

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

### Control de acceso por rol en todas las pantallas

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: tester de frontend. Escribe pruebas con vitest (componentes, servicios y mappers, incluida la conformidad con docs/contrato/openapi.yaml) y un recorrido E2E con Playwright contra el backend de desarrollo. Compara cada pantalla con NexoVolt_Mockups_Iteracion2_v3.html (textos, columnas, estados vacío y de error, rol). No corrijas el código de producción: reporta los defectos con un código DF-xx.

TAREA: pruebas de frontend de «Control de acceso por rol en todas las pantallas». Lo implementó — (tú no). RF cubiertos: RF48, RF57, RF23.
Qué verificar:
- Analista de Cartera: pantallas 4 (con las tarjetas de HU-B y HU-C), 9, 10, 11, 12, 13 y 14. Administrador: pantallas 15 y 16 y el panel sin tarjetas de HU-B ni HU-C.
- Cada pantalla del otro rol muestra «Acceso restringido» (el botón «Cambiar de perfil» solo existe en modo demostración); en el menú el ítem sale bloqueado con la etiqueta ANALISTA o ADMIN.

Casos mínimos:
1. Analista abre /entidad y /homologacion → «Acceso restringido»
2. Administrador abre /obligaciones, /ciclo, /reporte, /reclamos y /novedades → «Acceso restringido»
3. Panel del Administrador → Sin tarjetas de cartera, archivo, reclamos ni novedades
4. Menú del Administrador → Ítems del Analista bloqueados con la etiqueta ANALISTA
5. API: Analista hace PUT /api/entidad/ → 403 en español

Roles: comprueba con el rol que sí corresponde y con el contrario («Acceso restringido»).
Entrega: pruebas vitest y E2E (Playwright), capturas comparadas con el mockup v3 y los defectos DF-xx.
```

---

## Tareas transversales y scripts

### Plan maestro de pruebas y cobertura de la matriz

```text
Lee docs/iteracion2/RF_ITERACION2.md y NexoVolt_Mockups_Iteracion2_v3.html. Redacta el plan maestro de pruebas de la Iteración 2 de NexoVolt con: alcance (RF10 a RF24 y RF45 a RF55 sin RF56, más RF57), niveles de prueba, roles, criterios de entrada y salida, manejo de defectos (DF, MJ, UX) y la matriz de trazabilidad RF → caso → responsable.
Después escribe una prueba automática que recorra las 400 combinaciones (10 estados de origen × con o sin mora × 10 estados de destino × con o sin mora) de NV_TRANSICION_ESTADO para TIPO_CARTERA = 2 y compare cada una con la constante MX del mockup v3 (que reproduce la Matriz de la p. 40 del Manual). Reporta cuántas celdas coinciden y cuáles no.
Incluye los datos de prueba v2 (escenarios E1 a E18). No inventes resultados: si algo depende de CENS o TransUnion, márcalo como pendiente.
```

### Decisiones de arquitectura y revisión de PR

```text
Lee CLAUDE.md y docs/ARQUITECTURA_BACKEND.md (las 5 decisiones de la Ola 0). Revisa este cambio como revisor de código de NexoVolt: [pega el diff o el enlace al PR].
Verifica: SQL con marcadores %s; transaction.atomic en escrituras y operaciones idempotentes; errores {"detail": "…"} en español; identificación enmascarada; bitácora; permisos por rol del RF (RF48 y RF57 son del Administrador; el resto del Analista); que la regla esté en un solo lugar (vista o servicio); que las pruebas cubran los casos del RF; que no se inventen valores pendientes de CENS o TransUnion.
Lista los problemas por gravedad (bloquea, debe corregirse, sugerencia) y propón la corrección mínima. No reescribas el cambio.
```

### Núcleo del ciclo mensual (POST y GET /api/ciclos/ y GET /api/matriz-estados/)

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: núcleo del ciclo mensual. Implementa ejecutar_ciclo(fecha_corte, usuario) en un módulo nuevo (propuesta: app ciclo) reutilizando generar_corte de cartera/servicios.py, y estos endpoints: POST /api/ciclos/, GET /api/ciclos/, GET /api/ciclos/{corte_id}/ y GET /api/matriz-estados/ (rol ANALISTA_CARTERA). Crea en usuarios/permisos.py el permiso EsAnalista (solo ANALISTA_CARTERA), que hoy no existe, y úsalo en estos endpoints.
Flujo: ubica o crea el corte BORRADOR; lee NEXOVOLT.V_CALCULO_CORTE; crea NV_OBLIGACION de las obligaciones nuevas; inserta NV_REPORTE_DETALLE y NV_INCONSISTENCIA; registra la bitácora. Todo en una transacción e idempotente por fecha de corte.
Respuesta del POST: {corte_id, fecha_corte, primer_reporte, cambios, cierres, rechazados, transiciones: [{numero, deudor, de, a, edad_antes, edad_despues, reglas}], rechazos: [{numero, deudor, de, a, motivo}]}. 400 si la fecha no es fin de mes; 409 si el corte ya está VALIDADO o ENVIADO.
Orden de las reglas por obligación: primer reporte (RF10) → mora, cuotas, exigibilidad (RF7, RF19, RF49) → caducado y castigo (RF14, RF45) → estado nuevo (cierres RF12 y RF15, normalización RF46, 03 RF14, 06 RF45) → validar contra la Matriz y rechazar con 713 conservando el estado anterior → pago de la mora (RF47) y cambio de edad (RF11). Cada regla es una función pura con su prueba.
GET /api/matriz-estados/: {estados, filas: [{origen, con_mora, destinos: [{estado, con_mora, permitido}]}]} leído de NV_TRANSICION_ESTADO.
Pruebas con pytest para cada regla y para los dos casos de idempotencia y de fecha inválida. Si el contrato no tiene lo que necesitas, avísame.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### API de obligaciones, resumen, línea de tiempo y panel

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: backend Django 5.2 + DRF con SQL explícito. La vista solo maneja HTTP; la lógica va en servicios con transaction.atomic; marcadores %s (nunca :1); errores {"detail": "…"} en español; identificación enmascarada; auditoría con config/bitacora.py; permisos según el rol del RF; paginación {total, resultados} con ?limite y ?desplazamiento; fechas AAAA-MM-DD.

TAREA: API de obligaciones (rol ANALISTA_CARTERA; el Administrador recibe 403 con mensaje en español). Crea: GET /api/obligaciones/, GET /api/obligaciones/resumen/, GET /api/obligaciones/{id}/, GET /api/obligaciones/{id}/linea-tiempo/ y GET /api/panel/resumen/.
Fuente: el estado vigente de cada obligación es su fila de NV_REPORTE_DETALLE en el corte más reciente (unida a NV_OBLIGACION y a SAC.CLIENTES para el nombre y la identificación enmascarada). Filtros: estado (01, 02, 03, 06, 07 o ELIM), q (número o deudor), paginación {total, resultados}.
Campos de la fila: id, numero, deudor, identificacion, estado {codigo, nombre}, cerrada, primer_reporte, en_reclamo, eliminada, caducado_sac, edad_mora {codigo, descripcion}, dias_mora, valor_mora, cuotas_mora, saldo, requiere_revision. Detalle: además concepto, valor_inicial, valor_cuota, fecha_exigibilidad, anios_mora, en_sac, cuotas_vencidas, pagos, cierre, pago_mora, reestructurada y transiciones posibles.
Resumen: {total, por_estado, cuotas_mora: {al_dia, una, dos_a_tres, cuatro_o_mas}, ultimo_corte}. Panel: distribución por estado, último archivo, reclamos en curso, novedades pendientes, obligaciones con 2 o más cuotas en mora y entidad_completa.
Línea de tiempo: un evento por corte (fecha, estado, edad, texto) más reclamos, novedades y eliminaciones. Pruebas con pytest para cada endpoint y para el 403 del Administrador.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Contrato OpenAPI 0.9 de la Iteración 2

```text
Lee CLAUDE.md y docs/contrato/README.md (docs/API.md está en el repo del backend y describe lo que ya funciona). Actualiza docs/contrato/openapi.yaml a la versión 0.9 (Iteración 2). No cambies los endpoints existentes, salvo POST /extracciones/{id}/validar/ y POST /extracciones/{id}/registrar-envio/, que se ajustan como se indica abajo. En el archivo las rutas van sin el prefijo /api, porque ya está en servers (por ejemplo /obligaciones/).
Agrega estos endpoints con esquemas de petición y respuesta, roles (ANALISTA_CARTERA o ADMINISTRADOR), paginación {total, resultados} con ?limite y ?desplazamiento, errores {"detail": "…"} o {"campo": ["…"]}, fechas AAAA-MM-DD, marcas de tiempo ISO con -05:00 e identificación enmascarada (******5678):
- GET /api/obligaciones/  [Analista; RF10–19, 45–49, 50]
- GET /api/obligaciones/resumen/  [Analista; RF19, panel]
- GET /api/obligaciones/{id}/  [Analista; RF10–19, 22, 45–50, 52]
- GET /api/obligaciones/{id}/linea-tiempo/  [Analista; RF10–19, 45–47]
- GET /api/matriz-estados/  [Analista; RF14, 15, 45, 46 (Matriz)]
- GET /api/ciclos/  [Analista; RF10–17, 19, 45–49]
- POST /api/ciclos/  [Analista; RF10–17, 19, 45–49]
- GET /api/ciclos/{corte_id}/  [Analista; RF10–17, 19, 45–49]
- GET /api/refinanciaciones/  [Analista; RF18]
- POST /api/refinanciaciones/  [Analista; RF18]
- GET /api/catalogos/{nombre}/  [Analista; RF18, 23, 24, 47, 50 (modos-extincion, tipos-pago, naturalezas-reestructuracion, motivos-eliminacion, tipologias-reclamo)]
- GET /api/estados/  [Administrador; RF48]
- GET /api/homologacion-estados/  [Administrador; RF48]
- PUT /api/homologacion-estados/{estado_sac}/  [Administrador; RF48]
- GET /api/extracciones/{id}/validaciones/  [Analista; RF19, 21, 22, 49, 53, 57]
- POST /api/extracciones/{id}/validar/ (existente, ajustar)  [Analista; RF53 (409 con la lista si hay correctivas)]
- POST /api/extracciones/{id}/archivo/  [Analista; RF20, 21, 51, 57]
- GET /api/archivos/  [Analista; RF20, 54]
- GET /api/archivos/{id}/descarga/  [Analista; RF20]
- POST /api/extracciones/{id}/registrar-envio/ (existente, ajustar)  [Analista; RF13, 16, 20, 54]
- POST /api/archivos/{id}/resultados/  [Analista; RF54, RF23]
- GET /api/archivos/{id}/resultados/  [Analista; RF54]
- GET /api/reclamos/  [Analista; RF23]
- POST /api/reclamos/  [Analista; RF23]
- POST /api/reclamos/{id}/cerrar/  [Analista; RF23]
- GET /api/reclamos/insumo/?tipo=marcacion|desmarcacion  [Analista; RF23]
- GET /api/novedades/  [Analista; RF24]
- POST /api/novedades/  [Analista; RF24, RF55]
- POST /api/novedades/{id}/gestionar/  [Analista; RF24, RF50]
- POST /api/novedades/{id}/rechazar/  [Analista; RF24]
- GET /api/eliminaciones/  [Analista; RF50]
- POST /api/eliminaciones/{id}/reactivar/  [Analista; RF50]
- GET /api/rectificaciones/  [Analista; RF55]
- POST /api/rectificaciones/  [Analista; RF55]
- POST /api/rectificaciones/{id}/confirmar/  [Analista; RF55]
- GET /api/entidad/  [Analista y Administrador (lectura); RF57]
- PUT /api/entidad/  [Administrador; RF57]
- GET /api/panel/resumen/  [Analista; RF6, 19, 23, 24, 57]

Los campos de cada respuesta salen de NexoVolt_Mockups_Iteracion2_v3.html (S.obls, S.cycles, S.files, S.claims, S.novs, S.elims, S.ent): conserva sus nombres en español. Los ejemplos son las 12 obligaciones del mockup.
No inventes campos que el RF no pida. Entrega el diff y el resumen de cambios para docs/contrato/README.md.
```

### Base compartida del frontend, guardas por rol y panel principal

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: frontend React 19 + Vite. Una carpeta por módulo (features/…, con nombre en inglés como las existentes) con página, servicio, mapper y validaciones; las pantallas no llaman a axios, usan el servicio; formularios con useFormulario y error por campo; textos en español; estados vacío, de carga y de error; datos simulados con MSW mientras no esté el backend; RequireRole según el rol del RF; sigue la pantalla del mockup v3.

TAREA: base compartida de la Iteración 2 y panel principal. Crea las carpetas features/obligations, cycle, refinancing, report, claims, updates, entity y state-mapping (en inglés, como las carpetas que ya existen: extraction, parameters, audit) (servicio, mapper y pruebas base) y los handlers de MSW con las 12 obligaciones del mockup v3 y los ejemplos del contrato 0.9.
Componentes: EstadoBadge (estados 01, 02, 03, 04, 06, 07, 08, 10, 11 y 12 con el color del mockup), EdadMoraBadge, candado de obligación cerrada, etiqueta «por confirmar», NoteBox y formateadores (pesos, fechas, días).
Roles: usa el RequireRole que ya existe (src/features/auth/RequireRole.jsx): <RequireRole roles={[ROLES.ANALISTA]} seccion={…}> en las pantallas 9 a 14 y roles={[ROLES.ADMIN]} en 15 y 16. Si el rol no corresponde, se muestra «Acceso restringido» (el botón «Cambiar de perfil» solo existe en modo demostración). En NAV_ITEMS agrega analystOnly junto al adminOnly que ya existe, para que el menú muestre los ítems bloqueados con la etiqueta ANALISTA o ADMIN.
Panel (pantalla 4, GET /api/panel/resumen/ y GET /api/entidad/): para el Analista, «Estado de la cartera» con barra de distribución, «Último archivo para TransUnion», tarjetas de reclamos, novedades pendientes y obligaciones con 2 o más cuotas en mora, y el aviso de entidad con relleno. El Administrador no ve nada de HU-B ni de HU-C.
Pruebas con vitest para los guardas de rol, los componentes y el panel.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Script 10 · Columnas, catálogos y marcadores de la entidad

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: script 10 (10_iter2_columnas_catalogos.sql). Crea o modifica lo siguiente en el esquema NEXOVOLT:
1. NV_CORTE: Ampliar CK_NV_CORTE_ESTADO: BORRADOR, VALIDADO, ENVIADO, ENVIADO_CON_INCONSISTENCIAS, ANULADO (RF54).
2. NV_REPORTE_DETALLE (columnas nuevas): PRIMER_REPORTE CHAR(1), FECHA_EXIGIBILIDAD DATE, ANIOS_MORA NUMBER(2), CUOTAS_PAGADAS NUMBER(3), ESTADO_CONTRATO VARCHAR2(3), FECHA_PAGO DATE, MODO_EXTINCION VARCHAR2(2), TIPO_PAGO VARCHAR2(2), N_REESTRUCTURACIONES NUMBER(3), NATURALEZA_REESTR VARCHAR2(2), EDAD_ANTERIOR VARCHAR2(2), REQUIERE_REVISION CHAR(1), MOTIVO_REVISION VARCHAR2(200 CHAR). Ya existen OBLIGACION_REFINANCIADA (01 reestructurada, 02 no) y VALOR_REAL_PAGADO.
3. NV_OBLIGACION (columnas nuevas): ELIMINADA CHAR(1) DEFAULT N, CIERRE_DEFINITIVO CHAR(1) DEFAULT N, FECHA_CIERRE DATE. El vínculo de refinanciación usa la columna que ya existe, OBLIGACION_ANTERIOR_ID.
4. Catálogos del Manual: NV_MODO_EXTINCION (Tabla 10), NV_TIPO_PAGO (Tabla 31), NV_NATURALEZA_REESTR (Tabla 11), NV_MOTIVO_ELIMINACION (Tabla 28), NV_TIPOLOGIA_RECLAMO (Ley 1266 y lista de TransUnion). Cada uno: CODIGO, DESCRIPCION, CONFIRMADO. Cargar solo códigos que estén en el Manual v34: lo que no esté confirmado queda con CONFIRMADO = N.
5. NV_PARAMETRO (RF57): TIPO_ENTIDAD = XXX, CODIGO_ENTIDAD = XXX, CODIGO_SUCURSAL = XXXXXX (marcadores del mismo largo del campo), CONFIRMADO = N. Hoy tienen PENDIENTE / PEND.

Entrega: el script, la reversa (ALTER … DROP COLUMN y DROP TABLE de lo nuevo), una consulta de verificación que muestre las columnas y tablas creadas (USER_TAB_COLUMNS y USER_TABLES) y la actualización del script consolidado NexoVolt_BD_completa_autonomous.sql. Aplícalo primero en desarrollo y avisa al equipo.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Script 12 · Matriz de transiciones y homologación de estados

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: script 12 (12_iter2_matriz_homologacion.sql). Crea o modifica lo siguiente en el esquema NEXOVOLT:
1. NV_ESTADO_TU y NV_HOMOLOGA_ESTADO (RF48): NV_ESTADO_TU: ADD USADO CHAR(1) DEFAULT S (08 y 04 en N). NV_HOMOLOGA_ESTADO: ADD ACCION (ESTADO o CIERRE), USUARIO_ID NUMBER(19), FECHA_ACTUALIZACION DATE; el estado F del SAC pasa a ACCION = CIERRE con ESTADO_TU nulo; B y D quedan sin homologar.
2. NV_TRANSICION_ESTADO: Borrar y recargar la matriz completa de servicios (TIPO_CARTERA = 2): 10 estados de origen × 2 (sin mora, con mora) × 10 destinos × 2 = 400 filas, desde la Matriz de la p. 40 del Manual. En el mockup v3 está codificada en la constante MX, que sirve para verificar la transcripción.

Entrega: el script, la reversa (ALTER … DROP COLUMN y DROP TABLE de lo nuevo), una consulta de verificación que muestre las columnas y tablas creadas (USER_TAB_COLUMNS y USER_TABLES) y la actualización del script consolidado NexoVolt_BD_completa_autonomous.sql. Aplícalo primero en desarrollo y avisa al equipo.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Script 11 · Tablas nuevas

```text
Lee CLAUDE.md y docs/contrato/openapi.yaml (en el backend, también docs/API.md). Fuentes de verdad, en docs/iteracion2/: RF_ITERACION2.md (texto del RF), NexoVolt_Mockups_Iteracion2_v3.html (pantallas y reglas de ejemplo), MATRIZ_ESTADOS_SERVICIOS.md (Matriz de la p. 40) y NexoVolt_BD_completa_autonomous.sql con los scripts 08 y 09 (modelo de datos). Lo marcado «por confirmar» o entre [corchetes] depende de CENS o TransUnion: hazlo parametrizable y no inventes valores.
Rol: DBA de NexoVolt (Oracle Autonomous, esquema NEXOVOLT; SAC es de solo lectura y no se modifica). Entrega un script SQL numerado, repetible (CREATE OR REPLACE en las vistas), con la reversa, una consulta de verificación y sin punto y coma dentro de los comentarios. En tablas nuevas, USUARIO_ID es NUMBER(19) sin llave foránea. Las fechas del SAC son números julianos: TO_DATE(TO_CHAR(n), 'J').

TAREA: script 11 (11_iter2_tablas_nuevas.sql). Crea o modifica lo siguiente en el esquema NEXOVOLT:
1. NV_ARCHIVO: ARCHIVO_ID PK, CORTE_ID FK, NOMBRE VARCHAR2(40), FECHA_GENERACION DATE, USUARIO_ID NUMBER(19), TIPO_REPORTE VARCHAR2(2), N_REGISTROS NUMBER(8), N_EXCLUIDAS NUMBER(8), SALDO_TOTAL NUMBER(16), APTO_ENVIO CHAR(1), ENVIADO CHAR(1) DEFAULT N, FECHA_ENVIO DATE, CONTENIDO BLOB.
2. NV_CARGUE_RESULTADO y NV_CARGUE_INCONSISTENCIA: Cargue: CARGUE_ID PK, ARCHIVO_ID FK, CORTE_ID, TIPO_ARCHIVO (ESTADISTICOS, CORRECTIVAS, ALERTAS, ESPECIALES, DETALLE_953, NOREP, RADICACION, CIERRE_RECLAMO), NOMBRE_ARCHIVO, FECHA_CARGA, USUARIO_ID, N_FILAS. Inconsistencia: ID PK, CARGUE_ID FK, CORTE_ID, OBLIGACION_ID (nulo si no se reconoce), NUMERO_OBLIGACION_TU, CODIGO, DESCRIPCION, TIPO (CORRECTIVA, INFORMATIVA, NO_REPORTADA).
3. NV_REFINANCIACION: REFINANCIACION_ID PK, OBLIGACION_ORIGEN_ID FK, OBLIGACION_NUEVA_ID FK, CORTE_ID, FECHA DATE, NATURALEZA FK a NV_NATURALEZA_REESTR, N_CUOTAS NUMBER(3), SALDO_REFINANCIADO NUMBER(14), ORIGEN (SAC o MANUAL), USUARIO_ID.
4. NV_MARCA_CASTIGO: CLIENTE_ID, NUMERO_PROCESO, FECHA_CASTIGO DATE, FUENTE VARCHAR2(30), USUARIO_ID, FECHA_REGISTRO. Provisional hasta que CENS confirme el campo del SAC (P-CENS-05).
5. NV_RECLAMO: RECLAMO_ID PK, OBLIGACION_ID FK, TIPOLOGIA FK, FECHA_RADICACION DATE, OBSERVACION VARCHAR2(500 CHAR), ESTADO (EN_RECLAMO o CERRADO), RESULTADO VARCHAR2(30), FECHA_CIERRE DATE, FECHA_LIMITE_RESPUESTA DATE, MARCACION_GENERADA CHAR(1), DESMARCACION_GENERADA CHAR(1), USUARIO_ID, FECHA_REGISTRO.
6. NV_NOVEDAD: NOVEDAD_ID PK, TIPO (INCLUSION, ACTUALIZACION, CORRECCION, ELIMINACION), SUJETO (OBLIGACION o TITULAR), OBLIGACION_ID (nulo en inclusiones), REFERENCIA VARCHAR2(40), MOTIVO VARCHAR2(500 CHAR), MOTIVO_ELIM FK a NV_MOTIVO_ELIMINACION, VALORES_ENVIADOS VARCHAR2(1000 CHAR), FECHA_DETECCION DATE, ORIGEN (MANUAL o AUTOMATICA), ESTADO (PENDIENTE, GESTIONADA, RECHAZADA), NUMERO_TRANSACCION_TU VARCHAR2(30), FECHA_GESTION DATE, MOTIVO_RECHAZO VARCHAR2(300 CHAR), USUARIO_ID.
7. NV_ELIMINACION: ELIMINACION_ID PK, OBLIGACION_ID FK, NOVEDAD_ID FK, FECHA DATE, MOTIVO FK, NUMERO_TRANSACCION_TU, BLOQUEADA CHAR(1) DEFAULT S, FECHA_ACTIVACION DATE, NUMERO_ACTIVACION_TU.
8. NV_RECTIFICACION: RECTIFICACION_ID PK, NOVEDAD_ID FK (opcional), OBLIGACION_ID FK, CORTE_ID FK (corte afectado), CAMPO VARCHAR2(40), VALOR_ANTERIOR VARCHAR2(100), VALOR_CORREGIDO VARCHAR2(100), JUSTIFICACION VARCHAR2(500 CHAR), MEDIO (ACTUALIZACION_LINEA o PROCESO_ESPECIAL), ESTADO (REGISTRADA o CONFIRMADA), CONFIRMACION_TU, USUARIO_ID, FECHA_REGISTRO. El valor original nunca se borra.

Entrega: el script, la reversa (ALTER … DROP COLUMN y DROP TABLE de lo nuevo), una consulta de verificación que muestre las columnas y tablas creadas (USER_TAB_COLUMNS y USER_TABLES) y la actualización del script consolidado NexoVolt_BD_completa_autonomous.sql. Aplícalo primero en desarrollo y avisa al equipo.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

### Datos de prueba v2 (SAC y NEXOVOLT)

```text
Lee extraccion/sql/03_datos_prueba.sql y 03_limpiar_datos_prueba.sql y el modelo de SAC en NexoVolt_BD_completa_autonomous.sql. Crea 03_datos_prueba_v2.sql y su limpieza para Oracle Autonomous, solo para desarrollo, con datos 100 % ficticios.
Crea clientes desde 900101 con tipo y número de documento. Por cada escenario crea los créditos (SAC.CREDITOS: ESTADO, DEUDA_INICIAL_CAP, DEUDA_ACTUAL_CAP, VALOR_CUOTA, CONTATRASOS, ATRASOS_PERMITIDOS, NUMERO_PROCESO, CODIGO_CONCEPTO, FECHA_ACTIVACION, FECHA_DESACTIVACION, FECHA_ULTIMO_PAGO, VALOR_ULTIMO_PAGO, PROCESO_REFINANCIACION), las facturas vencidas (SAC.CLI_FACTURACION) y los pagos (SAC.CLI_PAGOS). Las fechas del SAC son julianos.
Escenarios y resultado esperado:
- E1 Vigente al día → Estado 01, mora 0, edad 00 (RF10, RF11)
- E2 Vigente con una cuota vencida (23 días) → 01, edad 00 y mora mayor a cero (RF10, RF11, RF19)
- E3 Vigente con dos cuotas vencidas de $70.000 (47 días) → 01, edad 01, 2 cuotas en mora (RF11, RF17, RF19)
- E4 Abono parcial que paga la cuota más antigua → Mora y cuotas recalculadas; la edad solo baja si paga las más antiguas (RF17)
- E5 Pago total estando en 01 → 02 con fecha de pago, modo 01 y tipo 01 (RF12, RF22)
- E6 Crédito caducado (6 atrasos con tope de 4) y con mora → 03 (RF14)
- E7 Marca de castigo con mora → 06 (RF45)
- E8 En 03 que paga todo → 07 con fecha de pago (RF15, RF22)
- E9 En 03 que paga toda la mora y conserva saldo → Vuelve a 01 y reporta el pago de la mora (RF46, RF47)
- E10 Refinanciación (proceso nuevo con PROCESO_REFINANCIACION) → Original en 02 modo 16; nueva en 01 reestructurada (RF18)
- E11 Obligación nueva caducada pero sin mora → Entra en 01 (no en 03, porque no tiene mora) y queda marcada para revisión (RF14) (RF10, RF14)
- E12 Obligación cerrada en un corte anterior con movimiento nuevo → No se reporta; alerta (RF13, RF16)
- E13 Crédito con estado B del SAC (sin homologar) → Bloquea la obligación (RF48, RF53)
- E14 Cliente sin tipo o número de documento → Correctiva (RF53)
- E15 Proceso negativo de migración con cliente de 10 dígitos (número de más de 20 caracteres) → Correctiva de número de obligación (RF53)
- E16 Valores de $9.000 y de $120 millones → Advertencias informativas (RF51, RF53)
- E17 Más de 730 días de mora → Edad 14 y años en mora (RF11, RF49)
- E18 Obligación eliminada ante TransUnion → No se incluye en el corte (RF50, RF21)
Inserta un corte anterior ENVIADO (con NV_OBLIGACION y NV_REPORTE_DETALLE) que deje cada obligación en el estado previo necesario.
Entrega: los dos scripts, un README con el orden de ejecución y una consulta que muestre, por escenario, el estado esperado.
No cambies nada fuera de lo pedido. Ejecuta todas las pruebas y entrégame el conteo y la lista de archivos modificados.
```

---

## Plantilla de descripción del PR

```text
Título: RFxx – descripción corta

Qué cambia: [2 o 3 líneas]
Requerimiento y componente: RFxx · base de datos, backend o frontend
Cómo probarlo: [pasos, datos de prueba v2 y resultado esperado]
Pruebas: [conteo de pytest o vitest y archivos nuevos]
IA: [se usó apoyo de IA para… / no se usó IA]
Contrato y docs: [openapi.yaml y docs/API.md actualizados: sí o no]
Oracle: [script aplicado en desarrollo y consulta de verificación]
Pendientes o supuestos: [lo que se asumió mientras CENS o TransUnion confirman]
```
