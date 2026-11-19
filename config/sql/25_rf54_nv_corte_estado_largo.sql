/* =============================================================================
   Script 25 · NV_CORTE.ESTADO con espacio para ENVIADO_CON_INCONSISTENCIAS (RF54)
   Esquema NEXOVOLT · Oracle Autonomous

   El script 11 amplio CK_NV_CORTE_ESTADO con ENVIADO_CON_INCONSISTENCIAS, pero
   la columna ESTADO quedo en VARCHAR2(10 CHAR) en Oracle (el DDL de referencia
   de docs/iteracion2 la tiene en 30). Ese valor tiene 27 caracteres: al cargar
   un archivo de correctivas de TransUnion, cargar_resultados falla con
   ORA-12899 y no se guarda nada. Hallazgo de la prueba del proceso completo
   contra Oracle del 18/11/2026.

   Que hace: amplia ESTADO a VARCHAR2(30 CHAR), como el DDL de referencia.
   Solo amplia: ningun valor guardado cambia. Es repetible: si la columna ya
   tiene 30 o mas, no hace nada.

   Reversa: reversa_25_rf54_nv_corte_estado_largo.sql
   Verificacion: verificacion_25_rf54_nv_corte_estado_largo.sql
   ============================================================================= */

DECLARE
    v_largo NUMBER;
BEGIN
    SELECT CHAR_LENGTH INTO v_largo
    FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_CORTE' AND COLUMN_NAME = 'ESTADO';

    IF v_largo < 30 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_CORTE MODIFY (ESTADO VARCHAR2(30 CHAR))';
    END IF;
END;
/
