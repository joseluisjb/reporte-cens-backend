# Informe de rendimiento RF3-RF8

## Estado de ejecucion

Pendiente de medicion conjunta con Dilan. No se registran tiempos ni planes
inventados: este entorno no tiene una instancia Oracle de prueba con el
conjunto ficticio creciente ni el acceso de solo lectura necesario para
obtener los planes reales.

## Consultas a medir

1. RF3/RF4: agregacion de facturacion y pagos por credito/concepto y saldo
   neto por proceso.
2. RF5: agrupacion por cliente y numero de proceso, junto con deteccion de
   creditos vinculados a mas de un proceso.
3. RF7: calculo de dias de mora y clasificacion por Tabla 9.
4. RF8: consulta del ultimo estado por obligacion y linea temporal.

## Protocolo

- Usar unicamente datos sinteticos. Probar, como minimo, 1.000, 10.000 y
  100.000 filas, con abonos parciales, pagos excedentes, conceptos sin pago,
  obligaciones con varios creditos y claves inconsistentes.
- Ejecutar cada consulta cinco veces por volumen; guardar mediana, minimo y
  maximo, version de Oracle, fecha, cardinalidad y parametros del caso.
- Separar ejecuciones de calentamiento y medicion. No medir sobre datos CENS.
- Capturar el plan real desde el cursor ejecutado con `DBMS_XPLAN.DISPLAY_CURSOR`
  cuando la cuenta de lectura tenga los permisos requeridos. Guardar el SQL_ID,
  el plan y las estadisticas de filas; no crear objetos en Oracle.
- Comparar cardinalidades estimadas/reales, accesos a tablas, joins y sorts.
  Documentar cualquier indice sugerido a CENS; no crear indices en su base.

## Registro

| RF / caso | Filas | Min (ms) | Mediana (ms) | Max (ms) | SQL_ID / plan |
|---|---:|---:|---:|---:|---|
| RF3/RF4 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| RF5 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| RF7 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |
| RF8 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

Este informe se completa al ejecutar el protocolo en el ambiente acordado con
Dilan y guardar los planes y mediciones observados.
