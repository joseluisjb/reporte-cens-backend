# Requerimientos funcionales corregidos · Iteración 2

> Copia para los repos. La versión maestra la mantiene Johan; si algo cambia, se actualiza allí y se vuelve a copiar aquí.

Versión 1 · 07/11/2026. Reemplazan las fichas RF10 a RF24 de la sección 1.4 del FP-15 (`context/FP-15-Documento_ingenieril (2).docx`) y agregan los RF nuevos de la Iteración 2. Siguen el formato de ficha del FP-15.

- **Corchetes `[ ]`:** dependen de una respuesta de CENS, de TransUnion o del área jurídica. Se completan cuando llegue la respuesta. Mientras tanto, se parametrizan y no se inventan.
- **Nota "Cambios" bajo cada ficha:** dice por qué cambió frente al FP-15. Los códigos C-xx son de la revisión interna del equipo.
- **Referencias:** "Manual" es el Manual Sector Real v34 de TransUnion, con páginas del PDF. "Matriz" es la Tabla de Cambios de Estado 2, Sector Real Servicios (p. 40), transcrita en `MATRIZ_ESTADOS_SERVICIOS.md`. "En mora" significa valor de mora mayor que cero, aunque la edad sea 00 (Manual, p. 38).

## Filas para la tabla 1.3

| Iteración | HU | Requerimientos Funcionales |
|---|---|---|
| 2 | HU-B — Gestión del Ciclo de Vida y Estados de la Obligación | RF10: Primer reporte de una obligación. |
| 2 | HU-B | RF11: Evolución mensual de la edad de mora. |
| 2 | HU-B | RF12: Cierre en estado Saldada. |
| 2 | HU-B | RF13: Saldada como cierre definitivo. |
| 2 | HU-B | RF14: Transición a Dudoso Recaudo. |
| 2 | HU-B | RF15: Cierre en Cartera Recuperada. |
| 2 | HU-B | RF16: Cartera Recuperada como cierre definitivo. |
| 2 | HU-B | RF17: Recálculo por abono parcial. |
| 2 | HU-B | RF18: Refinanciación. |
| 2 | HU-B | RF19: Cuotas en mora y coherencia de la mora. |
| 2 | HU-B | RF45: Transición a Castigada. |
| 2 | HU-B | RF46: Normalización sin pago total. |
| 2 | HU-B | RF47: Reporte del pago de la mora. |
| 2 | HU-B | RF48: Catálogo y homologación de estados. |
| 2 | HU-B | RF49: Fecha de exigibilidad y años en mora. |
| 2 | HU-C — Generación y Transmisión del Reporte | RF20: Generación del archivo plano del reporte total. |
| 2 | HU-C | RF21: Universo del reporte total. |
| 2 | HU-C | RF22: Validación de cierre. |
| 2 | HU-C | RF23: Registro de reclamos de Habeas Data. |
| 2 | HU-C | RF24: Registro de novedades de Actualización en Línea. |
| 2 | HU-C | RF50: Control de eliminaciones. |
| 2 | HU-C | RF51: Expresión de valores en miles de pesos. |
| 2 | HU-C | RF52: Composición de los valores de la obligación. |
| 2 | HU-C | RF53: Validación del corte contra el manual. |
| 2 | HU-C | RF54: Resultados del cargue de TransUnion. |
| 2 | HU-C | RF55: Rectificación de información reportada. |
| 2 | HU-C | RF57: Datos de la entidad y código de sucursal. |

RF56 (oportunidad y caducidad del dato negativo, C-41) va con RF36 en la Iteración 3 y no está en este documento.

## HU-B — Gestión del ciclo de vida y estados de la obligación

### RF10

| REQUERIMIENTO FUNCIONAL RF10 |
| Código: | RF10 | Actores que utilizan el RF10: | Analista de Cartera |
| Nombre RF: | Primer reporte de una obligación |
| Descripción: | El sistema debe reportar por primera vez una obligación a TransUnion con su estado, edad de mora, valor de mora y cuotas en mora reales a la fecha de corte, validando las restricciones de primer reporte del Manual (págs. 38-39). |
| Precondición: | La obligación no figura en ningún corte enviado antes a TransUnion. En el primer corte de NexoVolt esto aplica a toda la cartera. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema identifica que la obligación no tiene un corte enviado anterior.<br>2. El sistema calcula su estado (RF48), su edad de mora (RF7), su valor de mora y sus cuotas en mora a la fecha de corte. Un crédito caducado sin mora no pasa a Dudoso Recaudo (03): entra en Vigente (01) y queda marcado para revisión (RF14).<br>3. El sistema valida la combinación de estado y comportamiento: Vigente (01) se acepta con o sin mora; Dudoso Recaudo (03) solo en mora; Castigada (06) solo con edad de mora mayor a 00 y valor de mora mayor a cero; Cartera Recuperada (07) nunca. [Saldada (02) en primer reporte: confirmar con TransUnion.]<br>4. El sistema incluye la obligación en el corte. |
| Flujo Alterno |
| Actor | Sistema |
| 2. El Analista revisa la obligación en el origen y la corrige o la excluye con justificación. | 1. Si la combinación no está permitida, el sistema no incluye la obligación en el archivo y registra la inconsistencia "Estado y comportamiento no permitido en primer reporte" (equivalente a la 881 de TransUnion).<br>3. Si la obligación está en mora y no cumple la comunicación previa (RF36), el sistema aplica la regla definida por el área jurídica de CENS. [Pendiente (C-42).] |
| Postcondición: | La obligación ingresa a TransUnion con información veraz y en una combinación de estado aceptada. |

> Cambios: ya no se fuerza Vigente sin mora; se aplican las reglas de primer reporte del manual (C-03). El primer corte de NexoVolt será primer reporte para todas las obligaciones (C-52, resuelto).

### RF11

| REQUERIMIENTO FUNCIONAL RF11 |
| Código: | RF11 | Actores que utilizan el RF11: | Analista de Cartera |
| Nombre RF: | Evolución mensual de la edad de mora |
| Descripción: | En cada corte, el sistema debe recalcular la edad de mora de toda obligación no cerrada (cualquier estado distinto de Saldada y Cartera Recuperada) a partir de los días de mora reales (RF7) y codificarla según la Tabla 9 del Manual. |
| Precondición: | La obligación tiene al menos un corte anterior y no está cerrada. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema calcula los días de mora reales a la fecha de corte (RF7).<br>2. El sistema asigna el código de la Tabla 9 (00 a 14).<br>3. Si la edad de mora es 14, el sistema calcula los años en mora (RF49).<br>4. El sistema compara la edad con la del último corte enviado. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la edad avanza más de un tramo respecto al corte anterior, el sistema marca la obligación para revisión del Analista, sin modificar el valor calculado.<br>2. Si la edad disminuye y no hay un abono registrado en el periodo (RF17), el sistema marca la obligación para revisión. |
| Postcondición: | La edad de mora reportada corresponde a los días de mora reales a la fecha de corte, en todos los estados con saldo. |

> Cambios: aplica a todos los estados, no solo a Vigente; "gradual" pasa de regla a alerta de calidad; se agregan los años en mora (C-04).

### RF12

| REQUERIMIENTO FUNCIONAL RF12 |
| Código: | RF12 | Actores que utilizan el RF12: | Analista de Cartera |
| Nombre RF: | Cierre en estado Saldada |
| Descripción: | El sistema debe reportar una obligación como Saldada (02) cuando se extinga por completo, siempre que en el último corte enviado esté en Vigente (01) o Inactivo (08) y se cumplan las validaciones de cierre (RF22). |
| Precondición: | El saldo de la obligación es cero a la fecha de corte, por pago total o por refinanciación (RF18). |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema verifica que el estado del último corte enviado sea Vigente (01) o Inactivo (08).<br>2. El sistema aplica las validaciones de cierre (RF22).<br>3. El sistema reporta la obligación en Saldada (02), con comportamiento normal, fecha de pago, modo de extinción y tipo de pago. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el estado del último corte es Dudoso Recaudo (03) o Castigada (06), el sistema aplica el cierre en Cartera Recuperada (RF15).<br>2. Si el estado del último corte es Suspendida (04) o un estado de ley (10, 11, 12), el sistema no genera el cierre, porque la Matriz no lo permite, y lo muestra al Analista como inconsistencia "Cambio de estado inválido" (713).<br>3. Si alguna validación de RF22 falla, el sistema no reporta el cierre. |
| Postcondición: | La obligación queda en Saldada (02) con los valores de cierre exigidos por el Manual. |

> Cambios: se restringe el origen según la Matriz y se exigen los campos de cierre (C-05).

### RF13

| REQUERIMIENTO FUNCIONAL RF13 |
| Código: | RF13 | Actores que utilizan el RF13: | Analista de Cartera |
| Nombre RF: | Saldada como cierre definitivo |
| Descripción: | El sistema debe reportar una obligación Saldada (02) una sola vez, en el corte en que se cierra, y excluirla de los cortes siguientes. |
| Precondición: | La obligación fue reportada en Saldada (02) en un corte enviado (RF12). |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema marca la obligación como cierre definitivo.<br>2. En los cortes siguientes, el sistema excluye la obligación del archivo, sin contarla como omitida (RF21).<br>3. El sistema impide reutilizar su número de obligación. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, el sistema no la reporta y la muestra al Analista: solo puede corregirse por rectificación (RF55). |
| Postcondición: | La obligación Saldada no vuelve a reportarse y su número no se reutiliza. |

> Cambios: se define qué pasa después del cierre (C-06).

### RF14

| REQUERIMIENTO FUNCIONAL RF14 |
| Código: | RF14 | Actores que utilizan el RF14: | Analista de Cartera |
| Nombre RF: | Transición a Dudoso Recaudo |
| Descripción: | El sistema debe reportar una obligación como Dudoso Recaudo (03) cuando el crédito esté caducado en el sistema comercial de CENS y su valor de mora sea mayor a cero. [Confirmar con CENS que el crédito caducado se reporta en 03 (C-53).] |
| Precondición: | El crédito tiene estado caducado en el sistema comercial: su número de atrasos alcanzó los atrasos permitidos del crédito (CREDITOS.CONTATRASOS = CREDITOS.ATRASOS_PERMITIDOS). [Confirmar el código de estado con CENS.] |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema obtiene el estado homologado del crédito (RF48).<br>2. El sistema verifica que el valor de mora sea mayor a cero.<br>3. El sistema verifica que la Matriz permita el cambio desde el estado del último corte: Vigente, Inactivo en mora, Suspendida en mora, Dudoso Recaudo en mora o un estado de ley.<br>4. El sistema reporta la obligación en Dudoso Recaudo (03), en mora. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el valor de mora es cero, el sistema no reporta el estado 03 y marca la obligación para revisión.<br>2. Si la Matriz no permite el cambio, el sistema no lo reporta y registra la inconsistencia "Cambio de estado inválido" (713). |
| Postcondición: | La obligación queda en Dudoso Recaudo (03), siempre en mora. |

> Cambios: el umbral no lo define TransUnion sino el sistema comercial de CENS, según el tope de atrasos de cada crédito (C-07, C-53).

### RF15

| REQUERIMIENTO FUNCIONAL RF15 |
| Código: | RF15 | Actores que utilizan el RF15: | Analista de Cartera |
| Nombre RF: | Cierre en Cartera Recuperada |
| Descripción: | El sistema debe reportar una obligación como Cartera Recuperada (07) cuando, estando en Castigada (06) o Dudoso Recaudo (03) en mora en el último corte enviado, reciba el pago total o se cierre por refinanciación (RF18). |
| Precondición: | El último corte enviado tiene la obligación en 03 o 06, en mora, y su saldo es cero a la fecha de corte. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema verifica el estado de origen.<br>2. El sistema aplica las validaciones de cierre (RF22).<br>3. El sistema reporta la obligación en Cartera Recuperada (07), con comportamiento normal, modo de extinción (Tabla 10; 16 "Refinanciación" si el cierre es por refinanciación) y tipo de pago. [Confirmar con TransUnion el cierre por refinanciación desde 03 o 06 (P-TU-06).] |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el pago es parcial, el sistema aplica el recálculo de RF17.<br>2. Si el estado de origen es distinto de 03 o 06 en mora, el sistema no reporta el estado 07 y registra la inconsistencia "Cambio de estado inválido" (713).<br>3. Si alguna validación de RF22 falla, el sistema no reporta el cierre. |
| Postcondición: | La obligación queda en Cartera Recuperada (07) con los valores de cierre exigidos por el Manual. |

> Cambios: se exige origen en mora y campos de cierre; se agrega el cierre por refinanciación (C-10, C-24).

### RF16

| REQUERIMIENTO FUNCIONAL RF16 |
| Código: | RF16 | Actores que utilizan el RF16: | Analista de Cartera |
| Nombre RF: | Cartera Recuperada como cierre definitivo |
| Descripción: | El sistema debe reportar una obligación en Cartera Recuperada (07) una sola vez, en el corte en que se cierra, y excluirla de los cortes siguientes. |
| Precondición: | La obligación fue reportada en Cartera Recuperada (07) en un corte enviado (RF15). |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema marca la obligación como cierre definitivo.<br>2. En los cortes siguientes, el sistema excluye la obligación del archivo, sin contarla como omitida (RF21).<br>3. El sistema impide reutilizar su número de obligación. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el sistema comercial vuelve a mostrar movimiento sobre la obligación cerrada, el sistema no la reporta y la muestra al Analista: solo puede corregirse por rectificación (RF55). |
| Postcondición: | La obligación en Cartera Recuperada no vuelve a reportarse y su número no se reutiliza. |

> Cambios: se define qué pasa después del cierre (C-06).

### RF17

| REQUERIMIENTO FUNCIONAL RF17 |
| Código: | RF17 | Actores que utilizan el RF17: | Analista de Cartera |
| Nombre RF: | Recálculo por abono parcial |
| Descripción: | Cuando un abono no cubra toda la mora, el sistema debe aplicarlo según la regla de imputación de CENS y recalcular a la fecha de corte el valor de mora, la edad de mora, las cuotas en mora, las cuotas pagadas y el saldo. |
| Precondición: | Una obligación en mora recibe un abono que no cubre todo lo vencido. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema identifica el abono (RF3) y lo aplica por concepto y por cuota según la regla de imputación de CENS. [Regla pendiente de CENS (C-29).]<br>2. El sistema recalcula el valor de mora como lo vencido que sigue sin pagar.<br>3. El sistema recalcula la edad de mora desde la cuota vencida más antigua que quede sin pagar completa (RF7). La edad solo baja si el abono paga completas las cuotas más antiguas.<br>4. El sistema actualiza las cuotas en mora (RF19), las cuotas pagadas y el saldo. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el abono cubre toda la mora y la obligación conserva saldo, el sistema aplica el reporte del pago de la mora (RF47).<br>2. Si el abono cubre todo el saldo, no es un abono parcial: el sistema aplica el cierre (RF12 o RF15). |
| Postcondición: | La mora reportada refleja el abono aplicado, sin reducciones proporcionales ni estimadas. |

> Cambios: se elimina "proporcionalmente"; la edad depende de la cuota impaga más antigua; un pago total va al cierre (C-17).

### RF18

| REQUERIMIENTO FUNCIONAL RF18 |
| Código: | RF18 | Actores que utilizan el RF18: | Analista de Cartera |
| Nombre RF: | Refinanciación |
| Descripción: | Cuando CENS refinancie una obligación, el sistema debe cerrar la obligación original y registrar la nueva con número propio, guardando el vínculo entre ambas en la base de datos de NexoVolt. |
| Precondición: | El sistema comercial registra un nuevo proceso de financiación que refinancia uno anterior (CREDITOS.PROCESO_REFINANCIACION). [Confirmar con CENS que este campo se diligencia.] |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema identifica la refinanciación y la obligación original.<br>2. En el mismo corte, el sistema cierra la obligación original con modo de extinción 16 "Refinanciación" (Tabla 10): en Saldada (02) si estaba en 01 u 08 (RF12), o en Cartera Recuperada (07) si estaba en 03 o 06 en mora (RF15).<br>3. El sistema registra la nueva obligación con un número nuevo (RF5), "Obligación reestructurada" = 01, la naturaleza de la reestructuración [código de la Tabla 11 a definir con CENS] y el número de reestructuraciones.<br>4. El sistema guarda el vínculo entre la obligación original y la nueva en la base de datos de NexoVolt. El archivo de TransUnion no tiene un campo para ese vínculo. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la obligación original está en Suspendida (04) o en un estado de ley (10, 11, 12), desde donde la Matriz no permite el cierre, el sistema no genera el cierre y lo muestra al Analista para definir el tratamiento con CENS.<br>2. Una vez reportada la nueva obligación como reestructurada (01), el sistema mantiene ese valor en todos los cortes siguientes (Manual, p. 17). |
| Postcondición: | La obligación original queda cerrada, la nueva queda registrada con número propio y el vínculo entre ambas es trazable en NexoVolt. |

> Cambios: el campo "Naturaleza de la reestructuración" no vincula obligaciones; la original se cierra con modo 16 (C-24).

### RF19

| REQUERIMIENTO FUNCIONAL RF19 |
| Código: | RF19 | Actores que utilizan el RF19: | Analista de Cartera |
| Nombre RF: | Cuotas en mora y coherencia de la mora |
| Descripción: | El sistema debe calcular en cada corte el número de cuotas en mora de cada obligación y garantizar su coherencia con la edad de mora y el valor de mora. |
| Precondición: | Existe un corte en cálculo. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema cuenta las cuotas facturadas, vencidas y no pagadas completas, sin incluir cuotas aún no facturadas.<br>2. El sistema valida que, si la edad de mora es mayor a 00, el valor de mora y las cuotas en mora sean mayores a cero.<br>3. El sistema valida que, si el valor de mora es cero, las cuotas en mora sean cero y la edad sea 00. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la edad de mora es mayor a 00 y el valor de mora es cero, el sistema bloquea la obligación en la validación del corte (correctiva 707, RF53).<br>2. Si las cuotas en mora no son coherentes, el sistema muestra una alerta (informativa, RF53). |
| Postcondición: | Las cuotas en mora, la edad de mora y el valor de mora de cada obligación son coherentes entre sí. |

> Cambios: se agrega la regla de coherencia del Manual (págs. 16-17) (C-18).

### RF45 (nuevo)

| REQUERIMIENTO FUNCIONAL RF45 |
| Código: | RF45 | Actores que utilizan el RF45: | Analista de Cartera |
| Nombre RF: | Transición a Castigada |
| Descripción: | El sistema debe reportar una obligación como Castigada (06) cuando CENS la haya castigado contablemente en sus estados financieros, según la marca de castigo del sistema comercial, y siempre con valor de mora mayor a cero. [Campo o tabla de la marca de castigo: confirmar con CENS (P-CENS-05).] |
| Precondición: | El castigo está registrado en el sistema comercial. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema identifica la marca de castigo.<br>2. El sistema verifica que el valor de mora sea mayor a cero y, si es el primer reporte, que la edad de mora sea mayor a 00 (RF10).<br>3. El sistema verifica que la Matriz permita el cambio desde el estado del último corte: Vigente, Inactivo, Suspendida en mora, Dudoso Recaudo en mora, Castigada en mora o un estado de ley.<br>4. El sistema reporta la obligación en Castigada (06), en mora. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el valor de mora es cero, el sistema no reporta el estado 06 y marca la obligación para revisión.<br>2. Si la Matriz no permite el cambio, el sistema no lo reporta y registra la inconsistencia "Cambio de estado inválido" (713). |
| Postcondición: | La obligación queda en Castigada (06), siempre en mora. |

> Cambios: no existía un RF para entrar a Castigada (C-08). El castigo es una decisión contable (Manual, p. 11), no un conteo de días.

### RF46 (nuevo)

| REQUERIMIENTO FUNCIONAL RF46 |
| Código: | RF46 | Actores que utilizan el RF46: | Analista de Cartera |
| Nombre RF: | Normalización sin pago total |
| Descripción: | Si una obligación en Dudoso Recaudo (03) o Castigada (06) en mora paga lo vencido pero conserva saldo, o si una obligación en estado de ley (10, 11, 12) retoma su curso normal, el sistema debe reportarla en Vigente (01) con los datos del pago de la mora (RF47). [Confirmar con CENS si este caso ocurre o si toda normalización se hace como refinanciación (RF18).] |
| Precondición: | La obligación está en 03 o 06 en mora, o en un estado de ley, en el último corte enviado. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema detecta que el valor de mora quedó en cero y el saldo es mayor a cero.<br>2. El sistema reporta la obligación en Vigente (01), cambio permitido por la Matriz.<br>3. El sistema aplica el reporte del pago de la mora (RF47). |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la obligación conserva valor de mora, el sistema mantiene su estado. |
| Postcondición: | La obligación que se puso al día vuelve a Vigente sin reportarse como cerrada. |

> Cambios: la Matriz permite volver a Vigente desde 03, 06 y los estados de ley, y los requerimientos no lo contemplaban (C-09).

### RF47 (nuevo)

| REQUERIMIENTO FUNCIONAL RF47 |
| Código: | RF47 | Actores que utilizan el RF47: | Analista de Cartera |
| Nombre RF: | Reporte del pago de la mora |
| Descripción: | Cuando una obligación que en el último corte enviado tenía valor de mora mayor a cero quede al día sin cerrarse (valor de mora 0, edad 00 y cuotas en mora 0), el sistema debe reportar la fecha de pago, el modo de extinción y el tipo de pago. |
| Precondición: | La obligación tenía mora en el último corte enviado y sigue con saldo. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema detecta que la obligación quedó al día.<br>2. El sistema registra como fecha de pago la fecha en que quedó al día, menor o igual a la fecha de corte.<br>3. El sistema registra el modo de extinción (Tabla 10) y el tipo de pago (Tabla 31): Voluntario (01) en ambos, salvo que medie un proceso judicial. [Confirmar con CENS.]<br>4. El sistema registra el valor real pagado en el corte. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si no hay fecha de pago disponible, el sistema marca la obligación para revisión: TransUnion tomaría la fecha de corte como fecha de pago y alteraría la permanencia del dato negativo (Manual, p. 26). |
| Postcondición: | El pago de la mora queda reportado con su fecha real. |

> Cambios: requerimiento nuevo (C-13). Manual, págs. 26 y 30.

### RF48 (nuevo)

| REQUERIMIENTO FUNCIONAL RF48 |
| Código: | RF48 | Actores que utilizan el RF48: | Administrador |
| Nombre RF: | Catálogo y homologación de estados |
| Descripción: | El sistema debe soportar los 10 estados de la Tabla 4b del Manual y homologar cada estado del sistema comercial de CENS a uno de ellos según la tabla aprobada por CENS. |
| Precondición: | CENS aprobó el catálogo de estados y la tabla de homologación. [Pendiente de CENS (C-11, C-54).] |
| Flujo Normal |
| Actor | Sistema |
| 1. El Administrador registra o actualiza la homologación de estados. | 2. El sistema aplica el catálogo aprobado: 01 Vigente, 02 Saldada, 03 Dudoso Recaudo (RF14), 06 Castigada (RF45) y 07 Cartera Recuperada se usan; 08 Inactivo no se usa (Acta 3); 04 Suspendida [propuesta: no se usa, porque desde 04 no se puede volver a Vigente ni cerrar]; 10, 11 y 12 [se usan cuando el cliente esté admitido en el proceso de ley; fuente del dato a confirmar].<br>3. El sistema homologa los estados del sistema comercial: A → 01, C → 03, F → cierre (RF12 o RF15). [B y D: pendientes de CENS.]<br>4. En cada corte, el sistema asigna el estado homologado a cada obligación. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si un crédito tiene un estado del sistema comercial sin homologar, el sistema bloquea la obligación en la validación del corte (RF53). |
| Postcondición: | Cada obligación tiene un estado válido de la Tabla 4b. |

> Cambios: requerimiento nuevo; los requerimientos solo modelaban 5 de los 10 estados (C-11, C-54).

### RF49 (nuevo)

| REQUERIMIENTO FUNCIONAL RF49 |
| Código: | RF49 | Actores que utilizan el RF49: | Analista de Cartera |
| Nombre RF: | Fecha de exigibilidad y años en mora |
| Descripción: | Para toda obligación con valor de mora mayor a cero, el sistema debe reportar la fecha de exigibilidad y, cuando la edad de mora sea 14, los años en mora. |
| Precondición: | La obligación tiene valor de mora mayor a cero. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema toma como fecha de exigibilidad la fecha límite de pago de la cuota impaga más antigua (RF7), en formato AAAAMMDD.<br>2. Si la edad de mora es 14, el sistema calcula y reporta los años en mora.<br>3. Cuando la obligación queda al día, el sistema envía la fecha de exigibilidad vacía. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la fecha de exigibilidad es mayor a la fecha del sistema, el sistema bloquea la obligación en la validación del corte (correctiva, RF53). |
| Postcondición: | Las obligaciones en mora tienen la fecha base para el cálculo de permanencia de TransUnion. |

> Cambios: requerimiento nuevo (C-19). Manual, págs. 13, 20 y 59; Ley 2157 de 2021 (caducidad a los 8 años).

## HU-C — Generación y transmisión del reporte

### RF20

| REQUERIMIENTO FUNCIONAL RF20 |
| Código: | RF20 | Actores que utilizan el RF20: | Analista de Cartera |
| Nombre RF: | Generación del archivo plano del reporte total |
| Descripción: | El sistema debe generar mensualmente el archivo del reporte total con la estructura completa del Manual (págs. 44-52): registro tipo 1, registros tipo 2 y registro tipo 9, en texto plano de longitud fija y codificación ANSI (Windows-1252). |
| Precondición: | El corte está validado sin inconsistencias correctivas (RF53). El tipo de entidad, el código de entidad y el código de sucursal están parametrizados con los valores de TransUnion o con su marcador mientras TransUnion no los asigne (RF57). |
| Flujo Normal |
| Actor | Sistema |
| 6. El Analista descarga el archivo, lo verifica y lo carga en STRANSFER de TransUnion. | 1. El sistema genera el registro tipo 1 (29 caracteres): tipo de registro "1", código de paquete 11 (Sector Real Servicios), tipo de entidad, código de entidad, 10 espacios reservados, tipo de reporte 01 (total) y fecha de corte AAAAMMDD.<br>2. El sistema genera un registro tipo 2 por obligación y titular, con cada campo en su posición y longitud (Tabla 2 del Manual, columna Real Servicios). Los campos que no aplican van en espacios, incluida la línea de crédito, y la categoría de servicios es 04. [Longitud: el Manual declara 930 caracteres y sus campos suman 929; confirmar con TransUnion.]<br>3. El sistema genera el registro tipo 9 (33 caracteres): total de registros (incluye el 1 y el 9), número de registros tipo 2, tipo 3 y tipo 4.<br>4. El sistema aplica las reglas de formato:<br>- Números sin decimales, a la derecha y con ceros a la izquierda.<br>- Alfanuméricos de tabla en mayúsculas, a la izquierda y con espacios a la derecha.<br>- Número de obligación a la derecha, con espacios a la izquierda.<br>- Número de identificación con ceros a la izquierda.<br>- Fechas en AAAAMMDD.<br>- Campo vacío en espacios, que no es lo mismo que cero.<br>5. El sistema nombra el archivo: SSR + tipo de entidad (3) + código de entidad (3) + fecha de corte (AAAAMMDD). |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si un campo excede su longitud o no corresponde a su tipo de dato, el sistema no genera el archivo e indica la obligación y el campo.<br>2. Si los conteos del registro tipo 9 no coinciden con los registros generados, el sistema no genera el archivo. |
| Postcondición: | El archivo del reporte total queda generado conforme al Manual. Si usa los datos reales de la entidad, está listo para cargarse en STRANSFER; si usa marcadores (RF57), queda identificado como no apto para envío. |

> Cambios: se especifican los registros 1 y 9, el nombre del archivo, el relleno, el paquete 11, la sucursal y el medio de envío (C-01, C-02, C-30, C-48, C-51).

### RF21

| REQUERIMIENTO FUNCIONAL RF21 |
| Código: | RF21 | Actores que utilizan el RF21: | Analista de Cartera |
| Nombre RF: | Universo del reporte total |
| Descripción: | El archivo mensual debe incluir todas las obligaciones de financiación de energía vigentes a la fecha de corte, más todas las obligaciones reportadas antes a TransUnion que no estén cerradas ni eliminadas, aunque ya no aparezcan como vigentes en el sistema comercial. |
| Precondición: | Existe un corte mensual en cálculo, con fecha de corte el último día del mes. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema incluye las obligaciones vigentes en el sistema comercial.<br>2. El sistema incluye las obligaciones del último corte enviado que no estén cerradas (estado distinto de 02 y 07) ni eliminadas (RF50): las que se pagaron en el periodo, con su estado de cierre (RF12, RF15), y las que están en 03, 04, 06 o en estados de ley.<br>3. El sistema excluye las obligaciones cerradas en cortes anteriores (RF13, RF16) y las eliminadas (RF50).<br>4. Antes de validar el corte, el sistema compara el corte contra el último corte enviado. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si una obligación activa en el último corte enviado no tiene registro en el nuevo corte, el sistema bloquea la validación del corte y la muestra al Analista. Si se enviara así, TransUnion la marcaría como no reportada (R). |
| Postcondición: | El archivo refleja toda la base de obligaciones de CENS en TransUnion, sin omisiones. |

> Cambios: el universo no es solo "lo vigente", y la omisión se previene antes de enviar en lugar de alertarse después (C-22, C-23).

### RF22

| REQUERIMIENTO FUNCIONAL RF22 |
| Código: | RF22 | Actores que utilizan el RF22: | Analista de Cartera |
| Nombre RF: | Validación de cierre |
| Descripción: | Antes de reportar una obligación como Saldada (02) o Cartera Recuperada (07), el sistema debe validar todos los campos de cierre exigidos por el Manual (págs. 18 y 25-27), sin corregir ningún dato automáticamente. |
| Precondición: | Una obligación va a cerrarse por pago total o por refinanciación (RF12, RF15, RF18). |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema valida que el saldo, el valor de mora, las cuotas en mora y el valor de la cuota sean cero, y que la edad de mora sea 00.<br>2. El sistema valida que el número de cuotas pagadas sea mayor a cero.<br>3. El sistema valida que el estado del contrato sea 002 (No vigente).<br>4. El sistema valida que la fecha de pago sea menor o igual a la fecha de corte y mayor o igual a la fecha de inicio.<br>5. El sistema valida que el modo de extinción (Tabla 10) y el tipo de pago (Tabla 31) estén diligenciados; si el tipo de pago es Voluntario (01), el modo de extinción debe ser Voluntario (01), salvo en refinanciación (16). |
| Flujo Alterno |
| Actor | Sistema |
| 2. El Analista revisa y corrige el dato en el origen. | 1. Si alguna validación falla, el sistema no reporta el cierre, no modifica ningún valor y registra la inconsistencia. |
| Postcondición: | Una obligación Saldada o en Cartera Recuperada se reporta con todos los valores de cierre exigidos por el Manual. |

> Cambios: se agregan cuotas pagadas, estado del contrato, fecha de pago, modo de extinción y tipo de pago; se elimina "forzar la cuota a cero" (C-12).

### RF23

| REQUERIMIENTO FUNCIONAL RF23 |
| Código: | RF23 | Actores que utilizan el RF23: | Analista de Cartera |
| Nombre RF: | Registro de reclamos de Habeas Data |
| Descripción: | El sistema debe permitir registrar los reclamos de los titulares y preparar el insumo para marcar y desmarcar las obligaciones en el proceso "Marcación de obligaciones (Reclamos Batch)" de TransUnion. La obligación en reclamo se sigue reportando en el archivo total. |
| Precondición: | Un titular presentó un reclamo según las tipologías de la Ley 1266 de 2008. |
| Flujo Normal |
| Actor | Sistema |
| 1. El Analista registra el reclamo: tipología, fecha de radicación y obligación.<br>4. El Analista registra la respuesta y el cierre del reclamo. | 2. El sistema genera el insumo para la marcación batch de TransUnion.<br>3. El sistema mantiene la obligación en el reporte total.<br>5. El sistema genera el insumo para la desmarcación batch.<br>6. El sistema carga los archivos de radicación, cierre e inconsistencias que devuelve TransUnion (RF54). |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el reclamo no corresponde a una tipología válida, el sistema no permite registrarlo.<br>2. Si el reclamo supera el plazo legal de respuesta (15 días hábiles, prorrogables 8), el sistema alerta al Analista. |
| Postcondición: | El reclamo queda registrado y la obligación sigue reportándose; la marcación la hace TransUnion. |

> Cambios: la obligación no se "aísla" (quedaría como no reportada), y los archivos de radicación y cierre los genera TransUnion, no NexoVolt (C-43). El proceso de TransUnion sirve para marcar y desmarcar, y exige un perfil de marcación (Manual, p. 57).

### RF24

| REQUERIMIENTO FUNCIONAL RF24 |
| Código: | RF24 | Actores que utilizan el RF24: | Analista de Cartera |
| Nombre RF: | Registro de novedades de Actualización en Línea |
| Descripción: | El sistema debe registrar toda transacción hecha en el módulo de Actualización en Línea de TransUnion y tenerla en cuenta en el siguiente reporte total. |
| Precondición: | Existe una novedad puntual (inclusión, actualización, corrección o eliminación) que no puede esperar al corte mensual. |
| Flujo Normal |
| Actor | Sistema |
| 1. El Analista realiza la transacción en el módulo de Actualización en Línea.<br>2. El Analista la registra en NexoVolt. | 3. El sistema guarda el tipo de transacción, el número de obligación, el número de transacción de TransUnion, la fecha, el usuario, el motivo (si es eliminación, con el catálogo homologado al de la Tabla 28) y los valores enviados.<br>4. En el siguiente corte, el sistema aplica la novedad: una obligación saldada o recuperada en línea no recibe más comportamientos, y una eliminada no se vuelve a reportar (RF50). |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el módulo de Actualización en Línea rechaza la transacción, el Analista registra el rechazo y lo gestiona con TransUnion. |
| Postcondición: | NexoVolt conoce todas las novedades enviadas en línea y el siguiente corte es coherente con ellas. |

> Cambios: el módulo en línea lo opera una persona en la web de TransUnion; NexoVolt registra lo hecho y lo tiene en cuenta (C-36, C-37). No debe usarse para pruebas, porque escribe en la base real.

### RF50 (nuevo)

| REQUERIMIENTO FUNCIONAL RF50 |
| Código: | RF50 | Actores que utilizan el RF50: | Analista de Cartera |
| Nombre RF: | Control de eliminaciones |
| Descripción: | El sistema debe registrar toda obligación o titular eliminado ante TransUnion y excluirlo de los cortes siguientes. |
| Precondición: | Se eliminó una obligación o un titular por Actualización en Línea (RF24) o por registro tipo 4. |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema registra la eliminación con fecha, motivo (Tabla 28) y número de transacción.<br>2. El sistema excluye ese número de obligación de los cortes siguientes. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si se requiere volver a reportar una obligación eliminada, el sistema la mantiene bloqueada hasta que se registre el proceso de activación hecho con TransUnion. |
| Postcondición: | Ninguna obligación eliminada se vuelve a enviar por error. |

> Cambios: requerimiento nuevo (C-25). TransUnion rechaza las obligaciones eliminadas con la correctiva 117 (Manual, págs. 19, 24 y 57).

### RF51 (nuevo)

| REQUERIMIENTO FUNCIONAL RF51 |
| Código: | RF51 | Actores que utilizan el RF51: | Analista de Cartera |
| Nombre RF: | Expresión de valores en miles de pesos |
| Descripción: | El sistema debe reportar en miles de pesos, como enteros sin decimales, el valor inicial, el valor de mora, el valor del saldo, el valor de la cuota, el valor de cargo fijo y el valor real pagado. |
| Precondición: | Los valores de la obligación están calculados en pesos (RF52). |
| Flujo Normal |
| Actor | Sistema |
|  | 1. El sistema convierte cada valor a miles de pesos con la regla de redondeo aprobada. [Regla a confirmar con TransUnion; propuesta: redondeo al millar más cercano y, si un valor mayor a cero redondea a cero, reportar 1 (P-TU-02).]<br>2. El sistema conserva los valores en pesos en NexoVolt para consulta y auditoría. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si un valor es menor a $10.000 o mayor a $99 millones, el sistema muestra una alerta (informativa en TransUnion, Manual p. 19). |
| Postcondición: | Ningún valor en mora se reporta como cero por efecto del redondeo. |

> Cambios: requerimiento nuevo (C-26). Manual, págs. 8, 9 y 44.

### RF52 (nuevo)

| REQUERIMIENTO FUNCIONAL RF52 |
| Código: | RF52 | Actores que utilizan el RF52: | Analista de Cartera |
| Nombre RF: | Composición de los valores de la obligación |
| Descripción: | Para cada obligación, el sistema debe calcular el valor inicial, el saldo, el valor de mora y el valor de la cuota según los conceptos aprobados por CENS, parametrizables en RF35. |
| Precondición: | CENS aprobó la relación de conceptos de cada valor. [Pendiente de CENS (P-CENS-03, pregunta 10).] |
| Flujo Normal |
| Actor | Sistema |
|  | 1. Valor inicial: el monto total financiado (CREDITOS.DEUDA_INICIAL_CAP). [Confirmar si suma intereses.]<br>2. Saldo: el capital pendiente a la fecha de corte (CREDITOS.DEUDA_ACTUAL_CAP). [Confirmar si incluye intereses (DEUDA_ACTUAL_INT).]<br>3. Valor de mora: lo facturado, vencido y no pagado a la fecha de corte.<br>4. Valor de la cuota: la cuota periódica de la financiación. [Confirmar conceptos: 30 y, si aplica, 241.]<br>5. Intereses de mora (concepto 472): [se incluyen / no se incluyen]. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el saldo es mayor al valor inicial, el sistema muestra una alerta (informativa en TransUnion, Manual p. 18). |
| Postcondición: | Saldo, mora y cuota son tres valores distintos, calculados con una regla aprobada por CENS. |

> Cambios: requerimiento nuevo; precisa RF4 (C-27, C-55).

### RF53 (nuevo)

| REQUERIMIENTO FUNCIONAL RF53 |
| Código: | RF53 | Actores que utilizan el RF53: | Analista de Cartera |
| Nombre RF: | Validación del corte contra el manual |
| Descripción: | Antes de pasar un corte a VALIDADO, el sistema debe aplicar las reglas del Manual. Toda regla que en TransUnion es correctiva bloquea la validación; toda regla informativa se muestra como advertencia. |
| Precondición: | Existe un corte en BORRADOR. |
| Flujo Normal |
| Actor | Sistema |
| 3. El Analista revisa las advertencias y valida el corte. | 1. El sistema aplica, como mínimo, estas reglas correctivas (bloquean):<br>- Campos obligatorios de Servicios: tipo y número de identificación, nombre, número de obligación, sucursal, calidad, estado, edad de mora, fecha de corte y valor de mora.<br>- Fecha límite de pago, salvo castigadas.<br>- Edad de mora mayor a 00 sin valor de mora.<br>- Primer reporte inválido (RF10).<br>- Cambio de estado no permitido por la Matriz.<br>- Cierre incompleto (RF22).<br>- Número de obligación de más de 20 caracteres o con caracteres no permitidos.<br>- Fecha de corte no posterior a la del último corte enviado.<br>- Fecha de exigibilidad futura.<br>- Estado sin homologar (RF48).<br>- Omisiones frente al último corte (RF21).<br>2. El sistema aplica, como mínimo, estas reglas informativas (advierten):<br>- Cuotas en mora incoherentes.<br>- Saldo mayor al valor inicial.<br>- Valores fuera de $10.000 a $99 millones.<br>- Pago de mora sin fecha de pago.<br>- Edad 12 a 14 sin fecha de exigibilidad.<br>- Valor real pagado no reportado.<br>- Tipo de entidad, código de entidad o sucursal con marcador (RF57): el archivo se genera, pero queda marcado como no apto para envío. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si existe al menos una regla correctiva incumplida, el sistema no permite validar el corte y muestra la lista por obligación. |
| Postcondición: | Solo se generan archivos de cortes que cumplen las reglas correctivas del Manual. |

> Cambios: requerimiento nuevo; hace verificable la vista V_VALIDACION_CORTE (C-31). Correctiva frente a informativa: Manual, p. 42.

### RF54 (nuevo)

| REQUERIMIENTO FUNCIONAL RF54 |
| Código: | RF54 | Actores que utilizan el RF54: | Analista de Cartera |
| Nombre RF: | Resultados del cargue de TransUnion |
| Descripción: | El sistema debe permitir cargar los archivos que devuelve TransUnion después de cada cargue y asociar cada inconsistencia y cada obligación no reportada al corte correspondiente. |
| Precondición: | El corte fue enviado y TransUnion entregó los archivos de resultado. |
| Flujo Normal |
| Actor | Sistema |
| 1. El Analista carga los archivos de resultado, delimitados por pipes:<br>- estadísticos y detalle de correctivas y de alertas;<br>- Especiales y 953_Detalle;<br>- no reportados (norep). | 2. El sistema asocia cada inconsistencia (código, descripción y tipo) a la obligación del corte.<br>3. El sistema marca el corte como ENVIADO o, si hay correctivas, como ENVIADO_CON_INCONSISTENCIAS.<br>4. El sistema muestra al Analista las obligaciones con inconsistencias y las no reportadas, para corregirlas en el siguiente corte. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si el archivo no corresponde al corte o no tiene la estructura esperada, el sistema lo rechaza e indica el motivo. |
| Postcondición: | El resultado de cada cargue queda registrado y trazable por obligación. |

> Cambios: requerimiento nuevo (C-35). Estructura y nombres de los archivos: Manual, págs. 42-43 y 52-54. Con 6 meses seguidos de X o R, TransUnion inactiva el registro.

### RF55 (nuevo)

| REQUERIMIENTO FUNCIONAL RF55 |
| Código: | RF55 | Actores que utilizan el RF55: | Analista de Cartera |
| Nombre RF: | Rectificación de información reportada |
| Descripción: | Cuando se detecte que un corte ya enviado contenía información errada, el sistema debe permitir registrar la corrección y preparar el insumo para hacerla en TransUnion por Actualización en Línea (Corrección) o por proceso especial masivo. |
| Precondición: | Existe un corte enviado con información errada. |
| Flujo Normal |
| Actor | Sistema |
| 1. El Analista registra la corrección: obligación, fecha de corte afectada, campo, valor anterior, valor corregido y justificación. | 2. El sistema guarda la corrección sin borrar el valor original.<br>3. El sistema genera el insumo para la corrección en TransUnion.<br>4. El sistema registra la confirmación de TransUnion cuando el Analista la carga. |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si la obligación está cerrada (Saldada, Recuperada), prescrita o insoluta, el sistema solo admite su modificación por esta vía. |
| Postcondición: | Toda corrección queda trazable y el histórico de NexoVolt refleja el valor corregido. |

> Cambios: requerimiento nuevo (C-38). Manual, p. 25.

### RF57 (nuevo)

| REQUERIMIENTO FUNCIONAL RF57 |
| Código: | RF57 | Actores que utilizan el RF57: | Administrador |
| Nombre RF: | Datos de la entidad y código de sucursal |
| Descripción: | El sistema debe permitir al Administrador parametrizar el tipo de entidad, el código de entidad y el código de sucursal de CENS ante TransUnion, y usarlos en el registro tipo 1, en el nombre del archivo y en cada registro tipo 2. Mientras TransUnion no los asigne, los tres datos llevan un marcador que se reemplaza cuando lleguen. |
| Precondición: | Ninguna. Por defecto los parámetros tienen el marcador: tipo de entidad `XXX`, código de entidad `XXX` y código de sucursal `XXXXXX`. |
| Flujo Normal |
| Actor | Sistema |
| 1. Cuando TransUnion asigne los códigos, el Administrador reemplaza los marcadores por el tipo de entidad (3 dígitos), el código de entidad (3 dígitos) y el código de sucursal (hasta 6 caracteres) asignados. | 2. El sistema usa los valores vigentes en el registro tipo 1, en el nombre del archivo (SSR + tipo + código + fecha de corte) y en el campo "Código sucursal" de cada registro tipo 2.<br>3. Si TransUnion asigna varias sucursales, el sistema asigna a cada obligación la que corresponda según la regla que defina CENS. [Regla a definir cuando TransUnion asigne las sucursales.] |
| Flujo Alterno |
| Actor | Sistema |
|  | 1. Si algún parámetro conserva el marcador, el sistema genera el archivo y lo marca como "no apto para envío", y avisa en la validación del corte (RF53). Los marcadores tienen la misma longitud del campo, para que el archivo conserve su estructura y pueda corregirse con buscar y reemplazar.<br>2. Si el Administrador ingresa un valor que no cumple la longitud o el tipo del campo, el sistema no lo guarda. |
| Postcondición: | El archivo queda listo para identificar a CENS ante TransUnion apenas se conozcan los códigos asignados. |

> Cambios: requerimiento nuevo. La sucursal es obligatoria y debe existir en TransUnion, o la inconsistencia es correctiva (Manual, págs. 19 y 46) (C-51). Marcadores a pedido de CENS (07/11/2026), mientras TransUnion no asigne los códigos. Si el marcador debe ser numérico en el registro tipo 1, usar `000`, como el ejemplo del convertidor.

## Anexo: RF de la Iteración 1 que la Iteración 2 necesita corregidos

Están en la Iteración 1, pero el archivo de la Iteración 2 depende de ellos. Hay que reemplazar su descripción y ajustar sus flujos:

- **RF4 (C-20, C-29):** "El sistema debe consolidar, para cada obligación (proceso de financiación de energía), los saldos de sus conceptos y los pagos aplicados, obteniendo un único saldo, valor de mora y valor de cuota por obligación. Un deudor puede tener varias obligaciones, cada una reportada por separado." El flujo alterno lleva la regla de imputación de CENS [pendiente].
- **RF5 (C-21):** "El sistema debe asignar a cada obligación (proceso de financiación) un número de obligación único y permanente, de máximo 20 caracteres, con solo los caracteres especiales permitidos por TransUnion: ( ) * , - . / \ _ ¯ ·. El número no cambia nunca; si llegara a cambiar, se envía primero un registro tipo 3 de renumeración. El número de una obligación cerrada o eliminada no se reutiliza." Se quitan "mora, reconexión, aseo".
- **RF7 (C-15, C-16):** "El sistema debe calcular los días de mora como la diferencia en días calendario entre la fecha de corte y la fecha límite de pago de la cuota vencida más antigua que no haya sido pagada en su totalidad, y codificarlos con la Tabla 9. Una obligación con valor de mora mayor a cero y menos de 30 días de atraso se reporta con edad 00, pero se considera en mora."
- **RF6, RF8, RF9 (C-20):** cambiar "deudor" por "obligación" donde se refiere al historial y al estado.
