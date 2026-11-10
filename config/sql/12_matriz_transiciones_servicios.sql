/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Script: 12 - Matriz de cambios de estado, Sector Real Servicios (RF10, RF14,
           RF15, RF45, RF46; RNF-06)

   Carga en NV_TRANSICION_ESTADO las 400 casillas de la Tabla de Cambios de
   Estado 2 del Manual Sector Real v34 (p. 40) para TIPO_CARTERA = 2: 10 estados
   de origen con y sin mora por 10 estados de destino con y sin mora.
   119 casillas permitidas (PERMITIDO = 'S') y 281 no permitidas
   ('N', error 713 de TransUnion).

   Fuente: docs/iteracion2/MATRIZ_ESTADOS_SERVICIOS.md (verificada contra la
   p. 40 y la constante MX del mockup v3). tests/test_matriz_estados.py falla si
   este script y la Matriz se separan.

   Columnas reales de la tabla (script base 01, seccion 3.6): TIPO_CARTERA,
   ESTADO_ORIGEN, MORA_ORIGEN, ESTADO_DESTINO, MORA_DESTINO y PERMITIDO. La mora
   va como 'M' (con mora) o 'N' (sin mora). Las llaves foraneas exigen que los 10
   estados existan en NV_ESTADO_TU con TIPO_CARTERA = 2 (los carga el script 01).

   Antes de este script la tabla solo tenia las 40 casillas de 02 y 07 sin mora
   (todas 'N'). Sin la matriz completa el ciclo (POST /api/ciclos/) rechaza con
   713 todo cambio de estado.

   Es seguro repetirlo: MERGE actualiza PERMITIDO si la casilla ya existe y la
   inserta si falta; no duplica.

   Reversa: config/sql/reversa_12_matriz_transiciones_servicios.sql
   Verificacion: config/sql/verificacion_matriz_transiciones.sql (debe dar 400
   casillas, 400 coinciden).
   ============================================================================= */

MERGE INTO NEXOVOLT.NV_TRANSICION_ESTADO t
USING (
    SELECT '01' AS ESTADO_ORIGEN, 'N' AS MORA_ORIGEN, '01' AS ESTADO_DESTINO, 'N' AS MORA_DESTINO, 'S' AS PERMITIDO FROM DUAL
    UNION ALL
    SELECT '01', 'N', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'M', '12', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'M', '12', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'M', '12', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '08', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '10', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '11', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'M', '12', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '01', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '02', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '04', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '08', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '06', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '07', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '03', 'M', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '10', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '11', 'M', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'M', '12', 'M', 'S' FROM DUAL
) s
ON (    t.TIPO_CARTERA   = 2
    AND t.ESTADO_ORIGEN  = s.ESTADO_ORIGEN
    AND t.MORA_ORIGEN    = s.MORA_ORIGEN
    AND t.ESTADO_DESTINO = s.ESTADO_DESTINO
    AND t.MORA_DESTINO   = s.MORA_DESTINO)
WHEN MATCHED THEN UPDATE SET t.PERMITIDO = s.PERMITIDO
WHEN NOT MATCHED THEN INSERT (TIPO_CARTERA, ESTADO_ORIGEN, MORA_ORIGEN, ESTADO_DESTINO, MORA_DESTINO, PERMITIDO)
VALUES (2, s.ESTADO_ORIGEN, s.MORA_ORIGEN, s.ESTADO_DESTINO, s.MORA_DESTINO, s.PERMITIDO);

COMMIT;

-- Comprobacion rapida: debe dar 400 casillas y 119 permitidas.
SELECT COUNT(*) AS CASILLAS,
       SUM(CASE WHEN PERMITIDO = 'S' THEN 1 ELSE 0 END) AS PERMITIDAS
FROM NEXOVOLT.NV_TRANSICION_ESTADO
WHERE TIPO_CARTERA = 2;
