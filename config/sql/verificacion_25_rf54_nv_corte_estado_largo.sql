/* =============================================================================
   Verificacion del script 25 (RF54)
   Esperado: CHAR_LENGTH = 30 y la restriccion CK_NV_CORTE_ESTADO con
   ENVIADO_CON_INCONSISTENCIAS.
   ============================================================================= */

SELECT COLUMN_NAME, DATA_TYPE, CHAR_LENGTH
FROM ALL_TAB_COLUMNS
WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_CORTE' AND COLUMN_NAME = 'ESTADO';

SELECT CONSTRAINT_NAME, SEARCH_CONDITION_VC
FROM ALL_CONSTRAINTS
WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_CORTE' AND CONSTRAINT_NAME = 'CK_NV_CORTE_ESTADO';
