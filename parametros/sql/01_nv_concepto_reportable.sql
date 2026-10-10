/* =============================================================================
   NexoVolt — Automatización del Reporte de Cartera a Centrales de Riesgo (CENS)
   Módulo: Parametrización de Conceptos de Energía (RF35)
   Responsable DBA: Angel Jhoan Díaz Vanegas (Fila 36 del Project)
   Esquema: NEXOVOLT (Oracle Database)
   ============================================================================= */

-- 1. Creación de la tabla de conceptos de energía
CREATE TABLE NEXOVOLT.NV_CONCEPTO_REPORTABLE (
    CODIGO_CONCEPTO  NUMBER(4)          NOT NULL,
    DESCRIPCION      VARCHAR2(60)       NOT NULL,
    REPORTABLE       CHAR(1)            DEFAULT 'S' NOT NULL,
    OBSERVACION      VARCHAR2(200),
    FECHA_CREACION   TIMESTAMP          DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT PK_NV_CONCEPTO_REPORTABLE PRIMARY KEY (CODIGO_CONCEPTO),
    CONSTRAINT CK_NV_CONCEPTO_REPORTABLE CHECK (REPORTABLE IN ('S', 'N'))
);

-- Comentarios explicativos en el diccionario de datos
COMMENT ON TABLE NEXOVOLT.NV_CONCEPTO_REPORTABLE IS 'Catálogo de conceptos de facturación considerados energía para el reporte a TransUnion (RF35).';
COMMENT ON COLUMN NEXOVOLT.NV_CONCEPTO_REPORTABLE.CODIGO_CONCEPTO IS 'Código interno del concepto de facturación en el sistema comercial SAC.';
COMMENT ON COLUMN NEXOVOLT.NV_CONCEPTO_REPORTABLE.DESCRIPCION IS 'Descripción funcional del concepto de facturación.';
COMMENT ON COLUMN NEXOVOLT.NV_CONCEPTO_REPORTABLE.REPORTABLE IS 'Indicador de inclusión en la extracción: S = Activo/Reportable, N = Inactivo/Excluido.';
COMMENT ON COLUMN NEXOVOLT.NV_CONCEPTO_REPORTABLE.OBSERVACION IS 'Notas adicionales de auditoría o justificación del concepto.';
COMMENT ON COLUMN NEXOVOLT.NV_CONCEPTO_REPORTABLE.FECHA_CREACION IS 'Fecha y hora de registro del concepto en la base de datos (RNF-Auditoría).';

-- 2. En caso de que la tabla ya exista en el entorno Cloud sin la columna FECHA_CREACION (Diferencia B):
-- ALTER TABLE NEXOVOLT.NV_CONCEPTO_REPORTABLE ADD (FECHA_CREACION TIMESTAMP DEFAULT SYSTIMESTAMP);

-- 3. Carga inicial de conceptos identificados en el sistema comercial CENS
MERGE INTO NEXOVOLT.NV_CONCEPTO_REPORTABLE d
USING (
    SELECT 30 AS CODIGO_CONCEPTO, 'CUOTA FINANCIACION ENERGIA' AS DESCRIPCION, 'S' AS REPORTABLE, 'Grupo crédito 6. Más frecuente' AS OBSERVACION FROM DUAL UNION ALL
    SELECT 94, 'INTERES FINANCIACION ENERGIA', 'S', 'Interés asociado a financiación' FROM DUAL UNION ALL
    SELECT 61, 'ENERGIA ACTIVA RECONEXION', 'N', 'Grupo crédito 16' FROM DUAL UNION ALL
    SELECT 241, 'ENERGIA REACTIVA', 'N', 'Grupo crédito 20' FROM DUAL UNION ALL
    SELECT 472, 'CARGO FIJO ENERGIA', 'N', 'Grupo crédito 60' FROM DUAL UNION ALL
    SELECT 508, 'RECARGO POR MORA ENERGIA', 'N', 'Grupo crédito 65' FROM DUAL
) s
ON (d.CODIGO_CONCEPTO = s.CODIGO_CONCEPTO)
WHEN MATCHED THEN
    UPDATE SET d.DESCRIPCION = s.DESCRIPCION, d.REPORTABLE = s.REPORTABLE, d.OBSERVACION = s.OBSERVACION
WHEN NOT MATCHED THEN
    INSERT (CODIGO_CONCEPTO, DESCRIPCION, REPORTABLE, OBSERVACION, FECHA_CREACION)
    VALUES (s.CODIGO_CONCEPTO, s.DESCRIPCION, s.REPORTABLE, s.OBSERVACION, SYSTIMESTAMP);

COMMIT;

-- 4. Verificación de conceptos activos para la extracción (RF1, RF2, RF35)
SELECT CODIGO_CONCEPTO, DESCRIPCION, REPORTABLE, OBSERVACION, FECHA_CREACION
FROM   NEXOVOLT.NV_CONCEPTO_REPORTABLE
ORDER BY CODIGO_CONCEPTO;
