/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Vista: V_MORA_OBLIGACION y V_MORA_OBLIGACION_RESUMEN
   RF aplicables: RF17 (Recalculo por abono parcial), RF19 (Cuotas en mora),
                  RF49 (Fecha de exigibilidad y anos en mora),
                  RF52 (Composicion de valores de la obligacion)
   Responsable DBA: Angel Jhoan Diaz Vanegas
   Esquema: NEXOVOLT (Oracle Autonomous Database)

   Descripcion funcional:
     Calcula por obligacion y por cuota la imputacion de pagos (de la cuota mas antigua
     a la mas reciente) aplicando funciones analiticas SUM() OVER sobre SAC.CLI_FACTURACION
     y SAC.CLI_PAGOS.
     Expone en columnas separadas:
       - VALOR_INICIAL, VALOR_SALDO, VALOR_MORA, VALOR_CUOTA (RF52)
       - CUOTAS_MORA, CUOTAS_PAGADAS (RF19)
       - FECHA_EXIGIBILIDAD, DIAS_MORA, ANIOS_MORA (RF49)
       - VALOR_PAGADO_PERIODO, ORIGEN_DIAS_MORA (RF17)
       - FECHA_VENCIMIENTO, PENDIENTE, DIAS (para detalle per-cuota requerido por ciclo)

   Limitacion documentada:
     La copia del sistema comercial SAC no desagrega conceptos en facturas de cuotas.
     Si una obligacion no presenta registros en SAC.CLI_FACTURACION, la vista aplica
     el respaldo de calculo estimado basado en CONTATRASOS x VALOR_CUOTA marcando
     ORIGEN_DIAS_MORA = 'ESTIMADO'.

   Reversa:
     DROP VIEW NEXOVOLT.V_MORA_OBLIGACION_RESUMEN;
     DROP VIEW NEXOVOLT.V_MORA_OBLIGACION;

   Verificacion:
     SELECT * FROM NEXOVOLT.V_MORA_OBLIGACION WHERE ROWNUM <= 20;
     SELECT * FROM NEXOVOLT.V_MORA_OBLIGACION_RESUMEN WHERE ROWNUM <= 20;
   ============================================================================= */

CREATE OR REPLACE VIEW NEXOVOLT.V_MORA_OBLIGACION AS
WITH facturas_base AS (
    SELECT
        f.CLIENTE_ID,
        f.NUMERO_PROCESO,
        CASE
            WHEN f.FECHA_VENCIMIENTO > 1000000 THEN TO_DATE(TO_CHAR(f.FECHA_VENCIMIENTO), 'J')
            ELSE TRUNC(SYSDATE)
        END AS FECHA_VENCIMIENTO,
        f.TOTAL_FACTURADO
    FROM SAC.CLI_FACTURACION f
),
pagos_totales AS (
    SELECT
        p.CLIENTE_ID,
        p.NUMERO_PROCESO,
        SUM(p.VALOR_PAGO) AS TOTAL_PAGOS,
        SUM(CASE
            WHEN p.FECHA_PAGO >= TRUNC(SYSDATE, 'MM') THEN p.VALOR_PAGO
            ELSE 0
        END) AS VALOR_PAGADO_PERIODO
    FROM SAC.CLI_PAGOS p
    GROUP BY p.CLIENTE_ID, p.NUMERO_PROCESO
),
cuotas_acumuladas AS (
    SELECT
        fb.CLIENTE_ID,
        fb.NUMERO_PROCESO,
        fb.FECHA_VENCIMIENTO,
        fb.TOTAL_FACTURADO,
        NVL(pt.TOTAL_PAGOS, 0) AS TOTAL_PAGOS,
        NVL(pt.VALOR_PAGADO_PERIODO, 0) AS VALOR_PAGADO_PERIODO,
        SUM(fb.TOTAL_FACTURADO) OVER (
            PARTITION BY fb.CLIENTE_ID, fb.NUMERO_PROCESO
            ORDER BY fb.FECHA_VENCIMIENTO ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS ACUMULADO_FACTURADO,
        NVL(SUM(fb.TOTAL_FACTURADO) OVER (
            PARTITION BY fb.CLIENTE_ID, fb.NUMERO_PROCESO
            ORDER BY fb.FECHA_VENCIMIENTO ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ), 0) AS PREVIO_FACTURADO
    FROM facturas_base fb
    LEFT JOIN pagos_totales pt
      ON pt.CLIENTE_ID = fb.CLIENTE_ID AND pt.NUMERO_PROCESO = fb.NUMERO_PROCESO
),
cuotas_imputadas AS (
    SELECT
        ca.CLIENTE_ID,
        ca.NUMERO_PROCESO,
        ca.FECHA_VENCIMIENTO,
        ca.TOTAL_FACTURADO,
        ca.TOTAL_PAGOS,
        ca.VALOR_PAGADO_PERIODO,
        -- REGLA DE IMPUTACION (CENS C-29): Imputacion de la cuota mas antigua a la mas reciente
        LEAST(ca.TOTAL_FACTURADO, GREATEST(0, ca.ACUMULADO_FACTURADO - ca.TOTAL_PAGOS)) AS PENDIENTE,
        GREATEST(0, TRUNC(SYSDATE) - TRUNC(ca.FECHA_VENCIMIENTO)) AS DIAS
    FROM cuotas_acumuladas ca
),
creditos_sac AS (
    SELECT
        c.CLIENTE_ID,
        c.NUMERO_PROCESO,
        SUM(c.DEUDA_INICIAL_CAP) AS VALOR_INICIAL,
        SUM(c.DEUDA_ACTUAL_CAP) AS VALOR_SALDO,
        MAX(c.VALOR_CUOTA) AS VALOR_CUOTA,
        MAX(c.CONTATRASOS) AS CONTATRASOS
    FROM SAC.CREDITOS c
    GROUP BY c.CLIENTE_ID, c.NUMERO_PROCESO
),
cuotas_con_resumen AS (
    SELECT
        ci.CLIENTE_ID,
        ci.NUMERO_PROCESO,
        ci.FECHA_VENCIMIENTO,
        ci.TOTAL_FACTURADO,
        ci.PENDIENTE,
        ci.DIAS,
        SUM(CASE WHEN ci.PENDIENTE > 0 AND ci.FECHA_VENCIMIENTO <= TRUNC(SYSDATE) THEN ci.PENDIENTE ELSE 0 END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO) AS VALOR_MORA,
        COUNT(CASE WHEN ci.PENDIENTE > 0 AND ci.FECHA_VENCIMIENTO <= TRUNC(SYSDATE) THEN 1 END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO) AS CUOTAS_MORA,
        COUNT(CASE WHEN ci.PENDIENTE = 0 THEN 1 END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO) AS CUOTAS_PAGADAS,
        MIN(CASE WHEN ci.PENDIENTE > 0 AND ci.FECHA_VENCIMIENTO <= TRUNC(SYSDATE) THEN ci.FECHA_VENCIMIENTO END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO) AS FECHA_EXIGIBILIDAD,
        NVL(MAX(CASE WHEN ci.PENDIENTE > 0 AND ci.FECHA_VENCIMIENTO <= TRUNC(SYSDATE) THEN ci.DIAS END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO), 0) AS DIAS_MORA,
        TRUNC(NVL(MAX(CASE WHEN ci.PENDIENTE > 0 AND ci.FECHA_VENCIMIENTO <= TRUNC(SYSDATE) THEN ci.DIAS END)
            OVER (PARTITION BY ci.CLIENTE_ID, ci.NUMERO_PROCESO), 0) / 365) AS ANIOS_MORA,
        ci.VALOR_PAGADO_PERIODO,
        'CALCULADO' AS ORIGEN_DIAS_MORA,
        cs.VALOR_INICIAL,
        cs.VALOR_SALDO,
        cs.VALOR_CUOTA
    FROM cuotas_imputadas ci
    LEFT JOIN creditos_sac cs
      ON cs.CLIENTE_ID = ci.CLIENTE_ID AND cs.NUMERO_PROCESO = ci.NUMERO_PROCESO
),
obligaciones_sin_facturas AS (
    SELECT
        cs.CLIENTE_ID,
        cs.NUMERO_PROCESO,
        CAST(NULL AS DATE) AS FECHA_VENCIMIENTO,
        0 AS TOTAL_FACTURADO,
        0 AS PENDIENTE,
        0 AS DIAS,
        NVL(cs.CONTATRASOS, 0) * NVL(cs.VALOR_CUOTA, 0) AS VALOR_MORA,
        NVL(cs.CONTATRASOS, 0) AS CUOTAS_MORA,
        0 AS CUOTAS_PAGADAS,
        CAST(NULL AS DATE) AS FECHA_EXIGIBILIDAD,
        NVL(cs.CONTATRASOS, 0) * 30 AS DIAS_MORA,
        TRUNC(NVL(cs.CONTATRASOS, 0) * 30 / 365) AS ANIOS_MORA,
        0 AS VALOR_PAGADO_PERIODO,
        'ESTIMADO' AS ORIGEN_DIAS_MORA,
        cs.VALOR_INICIAL,
        cs.VALOR_SALDO,
        cs.VALOR_CUOTA
    FROM creditos_sac cs
    WHERE NOT EXISTS (
        SELECT 1 FROM facturas_base fb
        WHERE fb.CLIENTE_ID = cs.CLIENTE_ID AND fb.NUMERO_PROCESO = cs.NUMERO_PROCESO
    )
)
SELECT * FROM cuotas_con_resumen
UNION ALL
SELECT * FROM obligaciones_sin_facturas;
/

-- Vista agregada consolidada: 1 fila por cada obligacion (CLIENTE_ID + NUMERO_PROCESO)
CREATE OR REPLACE VIEW NEXOVOLT.V_MORA_OBLIGACION_RESUMEN AS
SELECT
    CLIENTE_ID,
    NUMERO_PROCESO,
    MAX(VALOR_INICIAL) AS VALOR_INICIAL,
    MAX(VALOR_SALDO) AS VALOR_SALDO,
    MAX(VALOR_MORA) AS VALOR_MORA,
    MAX(VALOR_CUOTA) AS VALOR_CUOTA,
    MAX(CUOTAS_MORA) AS CUOTAS_MORA,
    MAX(CUOTAS_PAGADAS) AS CUOTAS_PAGADAS,
    MIN(FECHA_EXIGIBILIDAD) AS FECHA_EXIGIBILIDAD,
    MAX(DIAS_MORA) AS DIAS_MORA,
    MAX(ANIOS_MORA) AS ANIOS_MORA,
    MAX(VALOR_PAGADO_PERIODO) AS VALOR_PAGADO_PERIODO,
    MAX(ORIGEN_DIAS_MORA) AS ORIGEN_DIAS_MORA
FROM NEXOVOLT.V_MORA_OBLIGACION
GROUP BY CLIENTE_ID, NUMERO_PROCESO;
/

COMMENT ON TABLE NEXOVOLT.V_MORA_OBLIGACION IS 'Detalle de cuotas e imputacion analitica de pagos de cartera con resumen por obligacion (RF17, RF19, RF49, RF52).';
COMMENT ON TABLE NEXOVOLT.V_MORA_OBLIGACION_RESUMEN IS 'Resumen consolidado por obligacion para calculo de cortes y cruce de datos (RF17, RF19, RF49, RF52).';
