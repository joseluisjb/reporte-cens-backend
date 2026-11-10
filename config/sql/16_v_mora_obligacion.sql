/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Vista: V_MORA_OBLIGACION y V_MORA_OBLIGACION_RESUMEN
   RF aplicables: RF17 (Recalculo por abono parcial), RF19 (Cuotas en mora),
                  RF49 (Fecha de exigibilidad y anos en mora),
                  RF52 (Composicion de valores de la obligacion)
   Responsable DBA: Angel Jhoan Diaz Vanegas
   Esquema: NEXOVOLT (Oracle Autonomous Database)

   Descripcion funcional:
     Una fila por obligacion (CLIENTE_ID + NUMERO_PROCESO). Los valores de mora,
     saldo, cuota y cuotas en mora vienen de V_OBLIGACION_SAC (que ya los agrega
     desde SAC.CREDITOS). La fecha de exigibilidad se extrae de SAC.CLI_FACTURACION
     por CLIENTE_ID, usando el mismo criterio que V_CALCULO_CORTE: la N-esima factura
     mas reciente vencida (N = CUOTAS_MORA) corresponde a la cuota impaga mas antigua.
     El pago del periodo viene de V_CREDITO_REPORTABLE.

   Nota de diseno:
     SAC.CLI_FACTURACION no tiene NUMERO_PROCESO: el detalle por cuota por obligacion
     no es posible con el esquema actual del SAC. El diseno original que intentaba hacer
     ese JOIN fue corregido para seguir el patron de V_CALCULO_CORTE.

   Reversa:
     DROP VIEW NEXOVOLT.V_MORA_OBLIGACION_RESUMEN;
     DROP VIEW NEXOVOLT.V_MORA_OBLIGACION;

   Verificacion:
     SELECT * FROM NEXOVOLT.V_MORA_OBLIGACION WHERE ROWNUM <= 20;
     SELECT * FROM NEXOVOLT.V_MORA_OBLIGACION_RESUMEN WHERE ROWNUM <= 20;
   ============================================================================= */

CREATE OR REPLACE VIEW NEXOVOLT.V_MORA_OBLIGACION AS
WITH fac_vencida AS (
    -- Facturas vencidas hasta hoy, ordenadas de mas reciente a mas antigua por cliente.
    -- RN = CUOTAS_MORA da la fecha de vencimiento de la cuota impaga mas antigua (RF49).
    SELECT
        f.CLIENTE_ID,
        TO_DATE(TO_CHAR(f.FECHA_VENCIMIENTO), 'J') AS FECHA_VENCIMIENTO,
        ROW_NUMBER() OVER (
            PARTITION BY f.CLIENTE_ID
            ORDER BY f.FECHA_VENCIMIENTO DESC, f.CONSECUTIVO DESC
        ) AS RN
    FROM SAC.CLI_FACTURACION f
    WHERE f.FECHA_VENCIMIENTO > 1000000
      AND f.FECHA_VENCIMIENTO <= TO_NUMBER(TO_CHAR(TRUNC(SYSDATE), 'J'))
),
pago_periodo AS (
    -- Pagos recibidos en el mes en curso, por obligacion (RF17).
    SELECT
        cr.CLIENTE_ID,
        cr.NUMERO_PROCESO,
        ROUND(SUM(cr.VALOR_ULTIMO_PAGO)) AS VALOR_PAGADO_PERIODO
    FROM NEXOVOLT.V_CREDITO_REPORTABLE cr
    WHERE cr.FECHA_ULTIMO_PAGO >= TRUNC(SYSDATE, 'MM')
      AND cr.FECHA_ULTIMO_PAGO <= TRUNC(SYSDATE)
    GROUP BY cr.CLIENTE_ID, cr.NUMERO_PROCESO
)
SELECT
    o.CLIENTE_ID,
    o.NUMERO_PROCESO,
    -- RF52: composicion de valores
    o.VALOR_INICIAL,
    o.VALOR_SALDO,
    o.VALOR_MORA,
    o.VALOR_CUOTA,
    -- RF19: cuotas en mora y pagadas
    o.CUOTAS_MORA,
    GREATEST(o.CUOTAS_PACTADAS - o.CUOTAS_MORA, 0)          AS CUOTAS_PAGADAS,
    -- RF49: fecha de exigibilidad (vencimiento de la cuota impaga mas antigua)
    fv.FECHA_VENCIMIENTO                                      AS FECHA_EXIGIBILIDAD,
    -- RF49: dias y anos en mora
    CASE
        WHEN o.VALOR_MORA = 0            THEN 0
        WHEN fv.FECHA_VENCIMIENTO IS NOT NULL
             THEN GREATEST(TRUNC(SYSDATE) - fv.FECHA_VENCIMIENTO, 0)
        ELSE o.CUOTAS_MORA * 30
    END                                                       AS DIAS_MORA,
    CASE
        WHEN o.VALOR_MORA = 0            THEN 0
        WHEN fv.FECHA_VENCIMIENTO IS NOT NULL
             THEN TRUNC(GREATEST(TRUNC(SYSDATE) - fv.FECHA_VENCIMIENTO, 0) / 365)
        ELSE TRUNC(o.CUOTAS_MORA * 30 / 365)
    END                                                       AS ANIOS_MORA,
    -- RF17: valor pagado en el periodo
    NVL(p.VALOR_PAGADO_PERIODO, 0)                           AS VALOR_PAGADO_PERIODO,
    CASE
        WHEN o.VALOR_MORA = 0                THEN 'SIN_MORA'
        WHEN fv.FECHA_VENCIMIENTO IS NOT NULL THEN 'CALCULADO'
        ELSE 'ESTIMADO'
    END                                                       AS ORIGEN_DIAS_MORA
FROM NEXOVOLT.V_OBLIGACION_SAC o
LEFT JOIN fac_vencida fv
    ON  fv.CLIENTE_ID = o.CLIENTE_ID
    AND fv.RN         = o.CUOTAS_MORA
LEFT JOIN pago_periodo p
    ON  p.CLIENTE_ID    = o.CLIENTE_ID
    AND p.NUMERO_PROCESO = o.NUMERO_PROCESO;
/

-- Vista de resumen: compatible con el nombre original; ahora es un alias directo
-- porque la vista principal ya devuelve una fila por obligacion.
CREATE OR REPLACE VIEW NEXOVOLT.V_MORA_OBLIGACION_RESUMEN AS
SELECT
    CLIENTE_ID,
    NUMERO_PROCESO,
    VALOR_INICIAL,
    VALOR_SALDO,
    VALOR_MORA,
    VALOR_CUOTA,
    CUOTAS_MORA,
    CUOTAS_PAGADAS,
    FECHA_EXIGIBILIDAD,
    DIAS_MORA,
    ANIOS_MORA,
    VALOR_PAGADO_PERIODO,
    ORIGEN_DIAS_MORA
FROM NEXOVOLT.V_MORA_OBLIGACION;
/

COMMENT ON TABLE NEXOVOLT.V_MORA_OBLIGACION IS 'Mora, saldo y fecha de exigibilidad por obligacion para el ciclo mensual (RF17, RF19, RF49, RF52).';
COMMENT ON TABLE NEXOVOLT.V_MORA_OBLIGACION_RESUMEN IS 'Alias de V_MORA_OBLIGACION; una fila por obligacion (RF17, RF19, RF49, RF52).';
