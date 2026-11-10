/* =============================================================================
   Verificacion de NV_TRANSICION_ESTADO contra la Matriz de cambios de estado
   Sector Real Servicios (Manual Sector Real v34, p. 40)

   Para que sirve: prueba de cobertura del RNF-06 (100 por ciento de las
   transiciones probadas y al menos 98 por ciento de aciertos). Compara las 400
   casillas esperadas (10 estados de origen con y sin mora por 10 estados de
   destino con y sin mora) con lo que tiene la tabla.

   Fuente de las casillas esperadas: docs/iteracion2/MATRIZ_ESTADOS_SERVICIOS.md
   (verificada contra la p. 40 y contra la constante MX del mockup v3). La prueba
   tests/test_matriz_estados.py falla si este archivo y la Matriz se separan.

   CON_MORA_DESDE y CON_MORA_HACIA: S = con mora (m), N = sin mora (n).
   PERMITIDA: S = TransUnion acepta el cambio, N = lo rechaza (error 713).

   Es de solo lectura: no crea ni modifica objetos. Ejecutar en el esquema de
   desarrollo despues del script 12 (carga completa de la matriz).
   ============================================================================= */

-- 1. Resumen: cuantas casillas coinciden, difieren, faltan o sobran
WITH esperada (ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA, PERMITIDA) AS (
    SELECT '01', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'S', 'S' FROM DUAL
),
comparacion AS (
    SELECT
        CASE
            WHEN r.ESTADO_DESDE IS NULL THEN 'FALTA_EN_TABLA'
            WHEN e.ESTADO_DESDE IS NULL THEN 'SOBRA_EN_TABLA'
            WHEN r.PERMITIDA = e.PERMITIDA THEN 'COINCIDE'
            ELSE 'DIFIERE'
        END AS RESULTADO
    FROM esperada e
    FULL OUTER JOIN NEXOVOLT.NV_TRANSICION_ESTADO r
      ON  r.ESTADO_DESDE   = e.ESTADO_DESDE
      AND r.CON_MORA_DESDE = e.CON_MORA_DESDE
      AND r.ESTADO_HACIA   = e.ESTADO_HACIA
      AND r.CON_MORA_HACIA = e.CON_MORA_HACIA
)
SELECT
    COUNT(*)                                                    AS TOTAL_CASILLAS,
    SUM(CASE WHEN RESULTADO = 'COINCIDE' THEN 1 ELSE 0 END)     AS COINCIDEN,
    SUM(CASE WHEN RESULTADO = 'DIFIERE' THEN 1 ELSE 0 END)      AS DIFIEREN,
    SUM(CASE WHEN RESULTADO = 'FALTA_EN_TABLA' THEN 1 ELSE 0 END) AS FALTAN,
    SUM(CASE WHEN RESULTADO = 'SOBRA_EN_TABLA' THEN 1 ELSE 0 END) AS SOBRAN,
    ROUND(100 * SUM(CASE WHEN RESULTADO = 'COINCIDE' THEN 1 ELSE 0 END) / 400, 2) AS PORCENTAJE_ACIERTOS
FROM comparacion;

-- 2. Detalle: cada casilla que no coincide, para reportarla como defecto DF-xx
WITH esperada (ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA, PERMITIDA) AS (
    SELECT '01', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '01', 'N', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '02', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '04', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '08', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '06', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '07', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '07', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '01', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '06', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '03', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '03', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '08', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '10', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '10', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '04', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'S', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '04', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '11', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '11', 'N', '12', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'S', '12', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '01', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '02', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '04', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '08', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '06', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '07', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '03', 'S', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '10', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'N', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '11', 'S', 'N' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'N', 'S' FROM DUAL
    UNION ALL
    SELECT '12', 'N', '12', 'S', 'S' FROM DUAL
)
SELECT
    NVL(e.ESTADO_DESDE, r.ESTADO_DESDE)       AS ESTADO_DESDE,
    NVL(e.CON_MORA_DESDE, r.CON_MORA_DESDE)   AS CON_MORA_DESDE,
    NVL(e.ESTADO_HACIA, r.ESTADO_HACIA)       AS ESTADO_HACIA,
    NVL(e.CON_MORA_HACIA, r.CON_MORA_HACIA)   AS CON_MORA_HACIA,
    e.PERMITIDA                               AS ESPERADA,
    r.PERMITIDA                               AS EN_TABLA
FROM esperada e
FULL OUTER JOIN NEXOVOLT.NV_TRANSICION_ESTADO r
  ON  r.ESTADO_DESDE   = e.ESTADO_DESDE
  AND r.CON_MORA_DESDE = e.CON_MORA_DESDE
  AND r.ESTADO_HACIA   = e.ESTADO_HACIA
  AND r.CON_MORA_HACIA = e.CON_MORA_HACIA
WHERE e.ESTADO_DESDE IS NULL
   OR r.ESTADO_DESDE IS NULL
   OR e.PERMITIDA <> r.PERMITIDA
ORDER BY 1, 2, 3, 4;
