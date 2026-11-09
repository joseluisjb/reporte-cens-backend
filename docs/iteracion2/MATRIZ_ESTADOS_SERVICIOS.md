# Matriz de cambios de estado — Sector Real Servicios

Transcripción de la *Tabla de Cambios de Estado 2 Sector Real Servicios* del Manual Sector Real v34 de TransUnion (p. 40 del PDF), con las reglas de primer reporte y de cierre que la acompañan (p. 38-39). La necesita el generador de la Iteración 2: TransUnion rechaza con el error **713** (cambio de estado inválido) o el **881** (estado no permitido en primer reporte) lo que no cumpla esta tabla.

> **Cómo se obtuvo.** La matriz no es una imagen: es texto con las letras en posiciones sueltas. Se reconstruyó leyendo la posición de cada letra en el PDF (06/11/2026). **Verificada el 07/11/2026** contra la página 40 renderizada en imagen, casilla por casilla: coinciden las 400. Las dos casillas que habían quedado en duda (Suspendida con mora hacia Inactivo y hacia Cartera recuperada) se resolvieron con los rectángulos del PDF. En esa fila, las celdas de Inactivo y de Cartera recuperada son un solo rectángulo que cubre los renglones n y m, con la letra arriba, así que la letra vale para los dos. La de Comercio (p. 37) no se transcribió: solo aplicaría si CENS reportara como Comercio, y CENS confirmó Servicios.

## Cómo leerla

- **Fila** = estado que la obligación tiene en la base de TransUnion (el del corte anterior). Si es su primera vez, aplica la sección *Primer reporte*.
- **Columna** = estado que se reporta en el corte nuevo.
- Cada estado se divide en **n** (sin mora: valor en mora 0 y edad de mora 00) y **m** (con mora: valor en mora mayor que 0).
- **S** = TransUnion acepta el cambio. **N** = lo rechaza como inconsistencia.

## Matriz

| Desde \ hacia | Vigente n | Vigente m | Saldada n | Saldada m | Suspendida n | Suspendida m | Inactivo n | Inactivo m | Castigada n | Castigada m | Recuperada n | Recuperada m | Dudoso n | Dudoso m | Ley 550 n | Ley 550 m | Ley 1116 n | Ley 1116 m | Ley 1564 n | Ley 1564 m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Vigente n** | S | S | S | N | N | N | S | S | N | S | N | N | N | S | S | S | S | S | S | S |
| **Vigente m** | S | S | S | N | N | S | S | S | N | S | N | N | N | S | S | S | S | S | S | S |
| **Saldada n** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Saldada m** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Suspendida n** | N | N | N | N | S | S | S | S | N | N | N | N | N | N | N | N | N | N | N | N |
| **Suspendida m** | N | N | N | N | S | S | S | S | N | S | N | N | N | S | N | N | N | N | N | N |
| **Inactivo n** | S | S | S | N | N | N | S | S | N | S | N | N | N | N | N | N | N | N | N | N |
| **Inactivo m** | S | S | S | N | N | N | S | S | N | S | N | N | N | S | N | N | N | N | N | N |
| **Castigada n** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Castigada m** | S | S | N | N | N | N | N | N | N | S | S | N | N | N | S | S | S | S | S | S |
| **Recuperada n** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Recuperada m** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Dudoso recaudo n** | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N | N |
| **Dudoso recaudo m** | S | S | N | N | N | N | N | N | N | S | S | N | N | S | S | S | S | S | S | S |
| **Ley 550 n** | S | S | N | N | N | N | N | N | N | S | N | N | N | S | S | S | N | N | N | N |
| **Ley 550 m** | S | S | N | N | N | N | N | N | N | S | N | N | N | S | S | S | N | N | N | N |
| **Ley 1116 n** | S | S | N | N | N | N | S | S | N | S | N | N | N | S | N | N | S | S | N | N |
| **Ley 1116 m** | S | S | N | N | S | S | S | S | N | S | N | N | N | S | N | N | S | S | N | N |
| **Ley 1564 n** | S | S | N | N | N | S | S | S | N | S | N | N | N | S | N | N | N | N | S | S |
| **Ley 1564 m** | S | S | N | N | N | S | S | S | N | S | N | N | N | S | N | N | N | N | S | S |

Códigos de la Tabla 4b: 01 Vigente, 02 Saldada, 03 Dudoso recaudo, 04 Suspendida por la entidad, 06 Castigada, 07 Cartera recuperada, 08 Inactivo, 10 Ley 550, 11 Ley 1116, 12 Ley 1564. En Servicios **no existen** *cancelada por mora*, *cancelada por extravío o robo*, *refinanciada*, *jurídico* ni *prejurídico*: son de Comercio (Tabla 4a).

## Primer reporte (p. 38-39)

Cuando la obligación se reporta por primera vez:

| Estado | ¿Se acepta? |
|---|---|
| Cartera recuperada | Nunca. |
| Dudoso recaudo | Solo con mora (valor en mora mayor que 0). |
| Castigada | Solo con mora de 30 días o más (edad de mora mayor que 00) y valor en mora mayor que 0. |
| Cualquier estado con comportamiento no permitido | Error **881**, correctivo: la obligación no se carga. |

La ficha corregida de **RF10** (`RF_ITERACION2.md`) ya aplica estas reglas. En el primer corte de NexoVolt, toda la cartera es primer reporte.

## Cierres

- **Saldada** y **cartera recuperada** son finales: sus filas son todas N. Después no aceptan ningún otro estado ni comportamiento (p. 38-39).
- **Saldada** exige saldo 0, valor en mora 0, edad 00, cuota 0 y cuotas en mora 0. Si hubo mora, también fecha de pago, modo de extinción y tipo de pago.
- **Cartera recuperada** solo se usa cuando una castigada o en dudoso recaudo **recibe el pago total**. Exige los mismos datos que la saldada.
- Desde **dudoso recaudo** no se puede pasar a saldada. Solo se puede ir a recuperada, y sin mora.

## Lo que implica para CENS

CENS usa vigente (al día y en mora), saldada y "caducado" (cada crédito caduca al llegar a sus atrasos permitidos). No usa inactivo y casi nunca castiga. Para que cada paso de su ciclo dé S en la matriz, falta confirmar:

1. A qué estado va un crédito caducado: 03 dudoso recaudo o 06 castigada (RF14, C-53).
2. En qué estado queda el crédito viejo cuando el cliente refinancia sin pagar todo. La matriz no permite cerrarlo como saldado, y recuperado exige pago total (RF15, RF18, P-TU-06).

