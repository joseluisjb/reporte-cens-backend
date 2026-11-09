/* =============================================================================
   Script 12a · Homologacion de estados (RF48)
   Esquema NEXOVOLT · Oracle Autonomous · solo desarrollo primero

   Que hace (parte de homologacion del script 12, propuesta para revision de Clara):
     1. NV_ESTADO_TU: agrega USADO (S/N) y, si falta, CONFIRMADO. 04 y 08 quedan
        con USADO = N (ficha RF48: 08 no se usa por el Acta 3, 04 propuesta).
     2. NV_HOMOLOGA_ESTADO: agrega ACCION (ESTADO o CIERRE), USUARIO_ID y
        FECHA_ACTUALIZACION, y si falta, CONFIRMADO. Permite ESTADO_TU nulo.
     3. Carga: los estados con ESTADO_TU quedan con ACCION = ESTADO, salvo F,
        que pasa a ACCION = CIERRE con ESTADO_TU nulo (al cerrar, el estado sale de
        NV_ESTADO_TU.CIERRE_AL_PAGAR: 01 da 02, 03 y 06 dan 07). B y D siguen sin
        homologar (ACCION nula).

   No recarga NV_TRANSICION_ESTADO: esa parte del script 12 es aparte. Para
   verificarla esta config/sql/verificacion_matriz_transiciones.sql.

   ANTES DE EJECUTAR
     a. Correr la seccion 0 de verificacion_12a_rf48_homologacion_estados.sql y
        confirmar que la columna del codigo en NV_ESTADO_TU se llama ESTADO_TU y la
        del nombre DESCRIPCION. Si se llaman distinto, cambiarlas aqui y en
        parametros/servicios.py (constantes _COL_ESTADO_TU).
     b. Revisar las vistas que viven solo en Oracle (V_CREDITO_REPORTABLE,
        V_OBLIGACION_SAC, V_CALCULO_CORTE): si alguna toma el estado de F de
        NV_HOMOLOGA_ESTADO.ESTADO_TU = 02, debe pasar a leer ACCION = CIERRE. Si no,
        tras este script los creditos en F quedarian sin estado.

   Es repetible: cada ALTER revisa antes si la columna ya existe.
   Reversa: reversa_12a_rf48_homologacion_estados.sql
   En tablas nuevas o columnas nuevas, USUARIO_ID es NUMBER(19) sin llave foranea.
   ============================================================================= */

-- 1. NV_ESTADO_TU.USADO y NV_ESTADO_TU.CONFIRMADO
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_ESTADO_TU' AND COLUMN_NAME = 'USADO';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_ESTADO_TU ADD (USADO CHAR(1) DEFAULT ''S'' NOT NULL)';
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_ESTADO_TU ADD CONSTRAINT CK_NV_ESTADO_TU_USADO CHECK (USADO IN (''S'', ''N''))';
    END IF;

    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_ESTADO_TU' AND COLUMN_NAME = 'CONFIRMADO';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_ESTADO_TU ADD (CONFIRMADO CHAR(1) DEFAULT ''N'' NOT NULL)';
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_ESTADO_TU ADD CONSTRAINT CK_NV_ESTADO_TU_CONF CHECK (CONFIRMADO IN (''S'', ''N''))';
    END IF;
END;
/

-- Uso en CENS segun la ficha RF48. Confirmados: lo que la ficha no deja entre corchetes.
UPDATE NEXOVOLT.NV_ESTADO_TU
SET USADO = CASE WHEN ESTADO_TU IN ('04', '08') THEN 'N' ELSE 'S' END,
    CONFIRMADO = CASE WHEN ESTADO_TU IN ('01', '02', '06', '07', '08') THEN 'S' ELSE 'N' END
WHERE TIPO_CARTERA = 2;

-- 2. NV_HOMOLOGA_ESTADO: ACCION, USUARIO_ID, FECHA_ACTUALIZACION, CONFIRMADO y ESTADO_TU nulo
DECLARE
    v_count NUMBER;
    v_nulo  VARCHAR2(1);
BEGIN
    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_HOMOLOGA_ESTADO' AND COLUMN_NAME = 'ACCION';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD (ACCION VARCHAR2(10))';
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD CONSTRAINT CK_NV_HOMOLOGA_ACCION CHECK (ACCION IN (''ESTADO'', ''CIERRE''))';
    END IF;

    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_HOMOLOGA_ESTADO' AND COLUMN_NAME = 'USUARIO_ID';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD (USUARIO_ID NUMBER(19))';
    END IF;

    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_HOMOLOGA_ESTADO' AND COLUMN_NAME = 'FECHA_ACTUALIZACION';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD (FECHA_ACTUALIZACION TIMESTAMP)';
    END IF;

    SELECT COUNT(*) INTO v_count FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_HOMOLOGA_ESTADO' AND COLUMN_NAME = 'CONFIRMADO';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD (CONFIRMADO CHAR(1) DEFAULT ''N'' NOT NULL)';
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO ADD CONSTRAINT CK_NV_HOMOLOGA_CONF CHECK (CONFIRMADO IN (''S'', ''N''))';
    END IF;

    SELECT NULLABLE INTO v_nulo FROM ALL_TAB_COLUMNS
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_HOMOLOGA_ESTADO' AND COLUMN_NAME = 'ESTADO_TU';
    IF v_nulo = 'N' THEN
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_HOMOLOGA_ESTADO MODIFY (ESTADO_TU NULL)';
    END IF;
END;
/

-- 3. Carga de la accion. Solo toca las filas que todavia no tienen accion: repetirlo no borra
-- lo que el Administrador haya cambiado por la API.
UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO
SET ACCION = 'CIERRE', ESTADO_TU = NULL
WHERE ESTADO_SAC = 'F' AND ACCION IS NULL;

UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO
SET ACCION = 'ESTADO'
WHERE ESTADO_TU IS NOT NULL AND ACCION IS NULL;

COMMIT;
