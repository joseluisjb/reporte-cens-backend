/* =============================================================================
   Reversa del script 12 - Matriz de cambios de estado, Sector Real Servicios

   Deja NV_TRANSICION_ESTADO (TIPO_CARTERA = 2) como la dejo el script base 01:
   solo las 40 casillas de 02 y 07 sin mora, todas no permitidas.
   ============================================================================= */

DELETE FROM NEXOVOLT.NV_TRANSICION_ESTADO
WHERE TIPO_CARTERA = 2
AND NOT (ESTADO_ORIGEN IN ('02', '07') AND MORA_ORIGEN = 'N');

UPDATE NEXOVOLT.NV_TRANSICION_ESTADO
SET PERMITIDO = 'N'
WHERE TIPO_CARTERA = 2;

COMMIT;

SELECT COUNT(*) AS CASILLAS FROM NEXOVOLT.NV_TRANSICION_ESTADO WHERE TIPO_CARTERA = 2;
