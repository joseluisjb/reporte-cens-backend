/* =============================================================================
   Script 21 · NV_REFINANCIACION: columna FECHA_REGISTRO

   Que hace:
     Agrega FECHA_REGISTRO TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL a
     NV_REFINANCIACION, alineando con las demás tablas de la iteración 2
     (NV_RECLAMO, NV_NOVEDAD, NV_ELIMINACION, NV_RECTIFICACION, NV_MARCA_CASTIGO).

   Es repetible: el ALTER verifica antes si la columna ya existe.
   Reversa: ALTER TABLE NEXOVOLT.NV_REFINANCIACION DROP COLUMN FECHA_REGISTRO;
   ============================================================================= */

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT'
      AND TABLE_NAME = 'NV_REFINANCIACION'
      AND COLUMN_NAME = 'FECHA_REGISTRO';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE
            'ALTER TABLE NEXOVOLT.NV_REFINANCIACION '
            'ADD (FECHA_REGISTRO TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL)';
    END IF;
END;
/

-- Verificación
SELECT COLUMN_NAME, DATA_TYPE, NULLABLE
FROM ALL_TAB_COLUMNS
WHERE OWNER = 'NEXOVOLT'
  AND TABLE_NAME = 'NV_REFINANCIACION'
  AND COLUMN_NAME = 'FECHA_REGISTRO';
