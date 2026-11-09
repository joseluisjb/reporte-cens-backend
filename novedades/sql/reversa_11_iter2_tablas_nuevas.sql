/* =============================================================================
   NexoVolt - Reversa del Script 11: Tablas nuevas de la Iteracion 2
   Responsable DBA: Angel Jhoan Diaz Vanegas
   Esquema: NEXOVOLT (Oracle Autonomous Database)
   ============================================================================= */

-- 1. Eliminacion de tablas en orden inverso de dependencias de llaves foraneas

BEGIN
    FOR r IN (
        SELECT table_name
        FROM all_tables
        WHERE owner = 'NEXOVOLT'
          AND table_name IN (
              'NV_RECTIFICACION', 'NV_ELIMINACION', 'NV_NOVEDAD',
              'NV_MOTIVO_ELIMINACION', 'NV_RECLAMO', 'NV_TIPOLOGIA_RECLAMO',
              'NV_MARCA_CASTIGO', 'NV_REFINANCIACION', 'NV_NATURALEZA_REESTR',
              'NV_CARGUE_INCONSISTENCIA', 'NV_CARGUE_RESULTADO', 'NV_ARCHIVO'
          )
    ) LOOP
        EXECUTE IMMEDIATE 'DROP TABLE NEXOVOLT.' || r.table_name || ' CASCADE CONSTRAINTS';
    END LOOP;
END;
/

-- 2. Eliminacion de secuencias asociadas

BEGIN
    FOR s IN (
        SELECT sequence_name
        FROM all_sequences
        WHERE sequence_owner = 'NEXOVOLT'
          AND sequence_name IN (
              'SEQ_NV_ARCHIVO', 'SEQ_NV_CARGUE_RESULTADO', 'SEQ_NV_CARGUE_INCONSISTENCIA',
              'SEQ_NV_REFINANCIACION', 'SEQ_NV_TIPOLOGIA_RECLAMO', 'SEQ_NV_RECLAMO',
              'SEQ_NV_MOTIVO_ELIMINACION', 'SEQ_NV_NOVEDAD', 'SEQ_NV_ELIMINACION',
              'SEQ_NV_RECTIFICACION'
          )
    ) LOOP
        EXECUTE IMMEDIATE 'DROP SEQUENCE NEXOVOLT.' || s.sequence_name;
    END LOOP;
END;
/

-- 3. Reversar columna agregada en NV_OBLIGACION (si aplica)

DECLARE
    v_col NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_col
    FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_OBLIGACION' AND COLUMN_NAME = 'ELIMINADA';
    IF v_col > 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_OBLIGACION DROP COLUMN ELIMINADA';
    END IF;
END;
/

-- 4. Reversar constraint de estado en NV_CORTE

BEGIN
    FOR r IN (
        SELECT constraint_name
        FROM all_constraints
        WHERE owner = 'NEXOVOLT'
          AND table_name = 'NV_CORTE'
          AND constraint_name = 'CK_NV_CORTE_ESTADO'
    ) LOOP
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_CORTE DROP CONSTRAINT ' || r.constraint_name;
    END LOOP;
END;
/

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_CORTE ADD CONSTRAINT CK_NV_CORTE_ESTADO CHECK (ESTADO IN (''BORRADOR'', ''VALIDADO'', ''ENVIADO'', ''RECHAZADO'', ''ANULADO''))';
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
/
