/* NexoVolt - 13 Tablas del ciclo mensual (RF10)
   Crea NV_CICLO y NV_CICLO_TRANSICION.
   Es seguro repetirlo? SÍ: usa CREATE TABLE ... IF NOT EXISTS vía bloque PL/SQL.

   Reversa:
     DROP TABLE NEXOVOLT.NV_CICLO_TRANSICION;
     DROP TABLE NEXOVOLT.NV_CICLO;

   Verificación:
     SELECT TABLE_NAME FROM ALL_TABLES
     WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME IN ('NV_CICLO', 'NV_CICLO_TRANSICION')
     ORDER BY TABLE_NAME;
*/

-- ── NV_CICLO ─────────────────────────────────────────────────────────────────
-- Un registro por corte que fue procesado por el ciclo mensual.

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM ALL_TABLES
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_CICLO';

    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE NEXOVOLT.NV_CICLO (
                CORTE_ID        NUMBER(19)                    NOT NULL,
                FECHA_EJEC      TIMESTAMP WITH TIME ZONE      NOT NULL,
                USUARIO_ID      NUMBER(19),
                PRIMER_REPORTE  NUMBER(10)  DEFAULT 0         NOT NULL,
                CAMBIOS_ESTADO  NUMBER(10)  DEFAULT 0         NOT NULL,
                CIERRES         NUMBER(10)  DEFAULT 0         NOT NULL,
                RECHAZADOS      NUMBER(10)  DEFAULT 0         NOT NULL,
                CON_PAGOS       NUMBER(10)  DEFAULT 0         NOT NULL,
                A_DUDOSO        NUMBER(10)  DEFAULT 0         NOT NULL,
                A_CASTIGADA     NUMBER(10)  DEFAULT 0         NOT NULL,
                NORMALIZADAS    NUMBER(10)  DEFAULT 0         NOT NULL,
                CONSTRAINT PK_NV_CICLO PRIMARY KEY (CORTE_ID)
            )';
    END IF;
END;
/

-- ── NV_CICLO_TRANSICION ───────────────────────────────────────────────────────
-- Una fila por obligación procesada en cada ciclo. Registra qué pasó.

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM ALL_TABLES
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_CICLO_TRANSICION';

    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE NEXOVOLT.NV_CICLO_TRANSICION (
                TRANSICION_ID       NUMBER(19)      GENERATED ALWAYS AS IDENTITY,
                CORTE_ID            NUMBER(19)      NOT NULL,
                OBLIGACION_ID       NUMBER(19)      NOT NULL,
                ESTADO_ANTERIOR     VARCHAR2(2),
                ESTADO_NUEVO        VARCHAR2(2)     NOT NULL,
                EDAD_ANTERIOR       VARCHAR2(2),
                EDAD_NUEVA          VARCHAR2(2)     NOT NULL,
                PRIMER_REPORTE      CHAR(1)         DEFAULT ''N'' NOT NULL,
                REQUIERE_REVISION   CHAR(1)         DEFAULT ''N'' NOT NULL,
                REGLA_RF            VARCHAR2(10),
                REGLA_TEXTO         VARCHAR2(500),
                REGLA_POR_CONFIRMAR CHAR(1)         DEFAULT ''N'',
                CONSTRAINT PK_NV_CICLO_TRANS    PRIMARY KEY (TRANSICION_ID),
                CONSTRAINT CK_CICLO_TRANS_PR    CHECK (PRIMER_REPORTE IN (''S'', ''N'')),
                CONSTRAINT CK_CICLO_TRANS_RR    CHECK (REQUIERE_REVISION IN (''S'', ''N''))
            )';
    END IF;
END;
/

-- ── Verificación ─────────────────────────────────────────────────────────────
SELECT TABLE_NAME
FROM ALL_TABLES
WHERE OWNER = 'NEXOVOLT'
  AND TABLE_NAME IN ('NV_CICLO', 'NV_CICLO_TRANSICION')
ORDER BY TABLE_NAME;
