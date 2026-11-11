/* =============================================================================
   Verificacion del script 12a (RF48). Solo lectura.
   ============================================================================= */

-- 0. Columnas de las dos tablas (correr ANTES del 12a para confirmar los nombres)
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, NULLABLE
FROM ALL_TAB_COLUMNS
WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME IN ('NV_ESTADO_TU', 'NV_HOMOLOGA_ESTADO')
ORDER BY TABLE_NAME, COLUMN_ID;

-- 1. Estados de servicios con su uso: 04 y 08 en USADO = N, los otros 8 en S
SELECT CODIGO_ESTADO, NOMBRE, ES_CIERRE, USADO, CONFIRMADO
FROM NEXOVOLT.NV_ESTADO_TU
WHERE TIPO_CARTERA = 2
ORDER BY CODIGO_ESTADO;

-- 2. Homologacion: A y C con ESTADO, F con CIERRE y estado nulo, B y D sin accion
SELECT ESTADO_SAC, PRIORIDAD, DESCRIPCION_SAC, ACCION, ESTADO_TU, CONFIRMADO, USUARIO_ID, FECHA_ACTUALIZACION
FROM NEXOVOLT.NV_HOMOLOGA_ESTADO
ORDER BY PRIORIDAD;

-- 3. Ninguna fila incoherente: CIERRE con estado, ESTADO sin estado, o ESTADO hacia 02 o 07
SELECT ESTADO_SAC, ACCION, ESTADO_TU
FROM NEXOVOLT.NV_HOMOLOGA_ESTADO
WHERE (ACCION = 'CIERRE' AND ESTADO_TU IS NOT NULL)
   OR (ACCION = 'ESTADO' AND (ESTADO_TU IS NULL OR ESTADO_TU IN ('02', '07')));
