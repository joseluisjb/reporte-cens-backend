/* =============================================================================
   Reversa del script 25 (RF54)
   Devuelve NV_CORTE.ESTADO a VARCHAR2(10 CHAR). Se detiene si algun corte ya
   quedo en ENVIADO_CON_INCONSISTENCIAS (no cabria): hay que decidir antes que
   hacer con esos cortes. Igual que el script 25, quita y recrea el indice
   UK_NV_CORTE_UN_BORRADOR alrededor del cambio.
   ============================================================================= */

DECLARE
    v_largos NUMBER;

    PROCEDURE crear_indice IS
    BEGIN
        EXECUTE IMMEDIATE 'CREATE UNIQUE INDEX NEXOVOLT.UK_NV_CORTE_UN_BORRADOR ON NEXOVOLT.NV_CORTE '
                       || '(CASE ESTADO WHEN ''BORRADOR'' THEN 1 END)';
    END;
BEGIN
    SELECT COUNT(*) INTO v_largos FROM NEXOVOLT.NV_CORTE WHERE LENGTH(ESTADO) > 10;
    IF v_largos > 0 THEN
        RAISE_APPLICATION_ERROR(-20025,
            'Hay ' || v_largos || ' corte(s) con un estado de mas de 10 caracteres: no se reduce la columna.');
    END IF;
    EXECUTE IMMEDIATE 'DROP INDEX NEXOVOLT.UK_NV_CORTE_UN_BORRADOR';
    BEGIN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_CORTE MODIFY (ESTADO VARCHAR2(10 CHAR))';
    EXCEPTION
        WHEN OTHERS THEN
            crear_indice;
            RAISE;
    END;
    crear_indice;
END;
/
