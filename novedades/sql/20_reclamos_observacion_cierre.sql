/* =============================================================================
   Script 20 · NV_RECLAMO: columna OBSERVACION_CIERRE

   Que hace:
     Agrega OBSERVACION_CIERRE VARCHAR2(500) a NV_RECLAMO para guardar la
     observación de cierre del reclamo (antes era CAST(NULL ...) en la consulta).

   Es repetible: el ALTER revisa antes si la columna ya existe.
   Reversa: reversa_20_reclamos_observacion_cierre.sql
   ============================================================================= */

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT'
      AND TABLE_NAME = 'NV_RECLAMO'
      AND COLUMN_NAME = 'OBSERVACION_CIERRE';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE
            'ALTER TABLE NEXOVOLT.NV_RECLAMO ADD (OBSERVACION_CIERRE VARCHAR2(500))';
    END IF;
END;
/

-- Verificación
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
FROM ALL_TAB_COLUMNS
WHERE OWNER = 'NEXOVOLT'
  AND TABLE_NAME = 'NV_RECLAMO'
  AND COLUMN_NAME = 'OBSERVACION_CIERRE';
