/* =============================================================================
   Reversa del script 12a (RF48)
   Devuelve F a ESTADO_TU 02 (como en la carga inicial) y quita las columnas que
   agrego el 12a. CONFIRMADO solo se quita si la agrego el 12a: si ya existia en
   la carga inicial, borrar esa linea antes de ejecutar.
   Es repetible: cada DROP revisa antes si la columna existe.
   ============================================================================= */

UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO SET ESTADO_TU = '02' WHERE ESTADO_SAC = 'F' AND ESTADO_TU IS NULL;
COMMIT;

DECLARE
    PROCEDURE quitar(p_tabla VARCHAR2, p_columna VARCHAR2) IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
        WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = p_tabla AND COLUMN_NAME = p_columna;
        IF v_count > 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.' || p_tabla || ' DROP COLUMN ' || p_columna;
        END IF;
    END;
BEGIN
    quitar('NV_HOMOLOGA_ESTADO', 'ACCION');
    quitar('NV_HOMOLOGA_ESTADO', 'USUARIO_ID');
    quitar('NV_HOMOLOGA_ESTADO', 'FECHA_ACTUALIZACION');
    quitar('NV_HOMOLOGA_ESTADO', 'CONFIRMADO');
    quitar('NV_ESTADO_TU', 'USADO');
    quitar('NV_ESTADO_TU', 'CONFIRMADO');
END;
/
