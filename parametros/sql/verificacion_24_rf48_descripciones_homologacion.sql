/* =============================================================================
   Verificacion del script 24 (RF48). Solo lectura.
   ============================================================================= */

-- 1. Descripciones por tipo de cartera: A Activo, C Caducado, F Finalizado, B y D vacias
SELECT TIPO_CARTERA, ESTADO_SAC, DESCRIPCION_SAC, PRIORIDAD, CONFIRMADO
FROM NEXOVOLT.NV_HOMOLOGA_ESTADO
ORDER BY TIPO_CARTERA, PRIORIDAD;

-- 2. Textos de trabajo que quedan: debe dar 0
SELECT COUNT(*) AS QUEDAN
FROM NEXOVOLT.NV_HOMOLOGA_ESTADO
WHERE DESCRIPCION_SAC LIKE '%(propuesto)%' OR DESCRIPCION_SAC LIKE '%preguntar a CENS%';

-- 3. Lo que ve la pantalla: solo el tipo de cartera de CENS, un estado por fila (5 filas)
SELECT h.ESTADO_SAC, h.DESCRIPCION_SAC
FROM NEXOVOLT.NV_HOMOLOGA_ESTADO h
WHERE h.TIPO_CARTERA = (SELECT TO_NUMBER(VALOR) FROM NEXOVOLT.NV_PARAMETRO WHERE CLAVE = 'TIPO_CARTERA')
ORDER BY h.PRIORIDAD;
