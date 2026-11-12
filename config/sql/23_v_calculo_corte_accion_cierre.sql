/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Script: 23 - V_CALCULO_CORTE lee la accion de homologacion (RF48, OBS-06, MJ-09)

   Problema: el script 12a dejo los estados de cierre del SAC (F, y los que el
   Administrador marque como cierre) con NV_HOMOLOGA_ESTADO.ACCION = 'CIERRE' y
   ESTADO_TU nulo. V_CALCULO_CORTE solo miraba ESTADO_TU: una obligacion cerrada
   en el SAC quedaba con ESTADO_TU nulo, INCLUIR = 'N' y MOTIVO_EXCLUSION =
   'ESTADO_SIN_HOMOLOGAR', asi que su cierre nunca se reportaba a TransUnion.

   Que hace: recrea V_CALCULO_CORTE con un solo cambio en el bloque "res":
     - une NV_HOMOLOGA_ESTADO (alias ha) por tipo de cartera y estado del SAC;
     - si ha.ACCION = 'CIERRE', el estado de TransUnion es el cierre que
       corresponde a lo ultimo reportado (NV_ESTADO_TU.CIERRE_AL_PAGAR del
       ultimo reporte: 01 da 02; 03 y 06 dan 07) y 02 si nunca se reporto.
   El resto de la vista es el texto que tenia Oracle el 12/11/2026 (obtenido
   con DBMS_METADATA.GET_DDL), sin otros cambios. V_CREDITO_REPORTABLE y
   V_OBLIGACION_SAC no se tocan.

   Efecto esperado:
     - Cerrada en el SAC y abierta en TransUnion: entra al corte una vez con
       estado 02 o 07 (INCLUIR = 'S').
     - Cerrada en el SAC y ya cerrada en TransUnion: no entra (YA_CERRADA_EN_TU).
     - Cerrada en el SAC y nunca reportada: no entra (CERRADA_NUNCA_REPORTADA).
     - Estado sin homologar (sin fila o con ACCION nula): sigue con ESTADO_TU
       nulo y MOTIVO_EXCLUSION = 'ESTADO_SIN_HOMOLOGAR'; el backend lo bloquea.

   Requiere: parametros/sql/12a_rf48_homologacion_estados.sql (columna ACCION).
   Es seguro repetirlo: usa CREATE OR REPLACE VIEW.
   NO esta verificado en Oracle: probarlo en desarrollo antes de produccion.

   Verificacion (con un corte en BORRADOR):
     SELECT ESTADO_SAC, ESTADO_TU, INCLUIR, MOTIVO_EXCLUSION, COUNT(*)
     FROM   NEXOVOLT.V_CALCULO_CORTE
     GROUP  BY ESTADO_SAC, ESTADO_TU, INCLUIR, MOTIVO_EXCLUSION
     ORDER  BY ESTADO_SAC;
   Ninguna fila con ESTADO_SAC = 'F' debe tener ESTADO_TU nulo.

   Reversa: en el bloque "res" quitar el LEFT JOIN de NV_HOMOLOGA_ESTADO (ha) y
   la linea "WHEN ha.ACCION = 'CIERRE' THEN NVL(eu.CIERRE_AL_PAGAR, '02')" del
   CASE de ESTADO_TU, y volver a crear la vista.
   ============================================================================= */

CREATE OR REPLACE VIEW NEXOVOLT.V_CALCULO_CORTE AS
WITH k AS (
  SELECT c.CORTE_ID,
         TRUNC(c.FECHA_CORTE)                      AS FECHA_CORTE,
         TRUNC(c.FECHA_CORTE, 'MM')                AS INICIO_MES,
         TO_NUMBER(TO_CHAR(c.FECHA_CORTE, 'J'))    AS CORTE_J
  FROM   NEXOVOLT.NV_CORTE c
  WHERE  c.ESTADO = 'BORRADOR'
),
fac_emitida AS (
  SELECT f.CLIENTE_ID, f.FECHA_VENCIMIENTO,
         ROW_NUMBER() OVER (PARTITION BY f.CLIENTE_ID
                            ORDER BY f.FECHA_FACTURACION DESC, f.CONSECUTIVO DESC) AS RN
  FROM   SAC.CLI_FACTURACION f
  CROSS JOIN k
  WHERE  f.FECHA_FACTURACION <= k.CORTE_J
  AND    f.FECHA_VENCIMIENTO > 0
),
fac_vencida AS (
  SELECT f.CLIENTE_ID, f.FECHA_VENCIMIENTO,
         ROW_NUMBER() OVER (PARTITION BY f.CLIENTE_ID
                            ORDER BY f.FECHA_VENCIMIENTO DESC, f.CONSECUTIVO DESC) AS RN
  FROM   SAC.CLI_FACTURACION f
  CROSS JOIN k
  WHERE  f.FECHA_VENCIMIENTO <= k.CORTE_J
  AND    f.FECHA_VENCIMIENTO > 0
),
pago_mes AS (
  SELECT cr.CLIENTE_ID, cr.NUMERO_PROCESO, ROUND(SUM(cr.VALOR_ULTIMO_PAGO)) AS VALOR_REAL_PAGADO
  FROM   NEXOVOLT.V_CREDITO_REPORTABLE cr
  CROSS JOIN k
  WHERE  cr.FECHA_ULTIMO_PAGO >= k.INICIO_MES
  AND    cr.FECHA_ULTIMO_PAGO <= k.FECHA_CORTE
  GROUP  BY cr.CLIENTE_ID, cr.NUMERO_PROCESO
),
calc AS (
  SELECT k.CORTE_ID, k.FECHA_CORTE,
         o.CLIENTE_ID, o.NUMERO_PROCESO, o.N_CREDITOS, o.ESTADO_SAC, o.ESTADO_TU,
         o.FECHA_INICIO, o.CUOTAS_PACTADAS, o.CUOTAS_MORA,
         o.VALOR_INICIAL, o.VALOR_SALDO, o.VALOR_CUOTA, o.VALOR_MORA, o.FECHA_ULTIMO_PAGO,
         COUNT(*) OVER (PARTITION BY o.NUMERO_PROCESO)  AS CLIENTES_DEL_PROCESO,
         CASE WHEN fe.FECHA_VENCIMIENTO IS NOT NULL
              THEN TO_DATE(TO_CHAR(fe.FECHA_VENCIMIENTO), 'J') END AS FECHA_LIMITE_PAGO,
         NVL(p.VALOR_REAL_PAGADO, 0)                    AS VALOR_REAL_PAGADO,
         CASE WHEN o.VALOR_MORA = 0 THEN 0
              WHEN o.FECHA_DESACTIVACION IS NOT NULL
                   THEN GREATEST(k.CORTE_J - TO_NUMBER(TO_CHAR(ADD_MONTHS(o.FECHA_DESACTIVACION, -o.CUOTAS_MORA), 'J')), 0)
              WHEN fv.FECHA_VENCIMIENTO IS NOT NULL
                   THEN k.CORTE_J - fv.FECHA_VENCIMIENTO
              ELSE o.CUOTAS_MORA * 30 END               AS DIAS_MORA,
         CASE WHEN o.VALOR_MORA = 0 THEN 'SIN_MORA'
              WHEN o.FECHA_DESACTIVACION IS NOT NULL THEN 'DESACTIVACION'
              WHEN fv.FECHA_VENCIMIENTO IS NOT NULL THEN 'FACTURA'
              ELSE 'ESTIMADO' END                       AS ORIGEN_DIAS_MORA,
         sac.ATRASOS_PERMITIDOS,
         CASE WHEN sac.CONTATRASOS >= sac.ATRASOS_PERMITIDOS THEN 'S' ELSE 'N' END AS CADUCADO
  FROM   k
  CROSS JOIN NEXOVOLT.V_OBLIGACION_SAC o
  LEFT JOIN fac_emitida fe  ON fe.CLIENTE_ID    = o.CLIENTE_ID AND fe.RN = 1
  LEFT JOIN fac_vencida fv  ON fv.CLIENTE_ID    = o.CLIENTE_ID AND fv.RN = o.CUOTAS_MORA
  LEFT JOIN pago_mes p      ON p.CLIENTE_ID     = o.CLIENTE_ID AND p.NUMERO_PROCESO = o.NUMERO_PROCESO
  LEFT JOIN SAC.CREDITOS sac ON sac.CLIENTE_ID  = o.CLIENTE_ID AND sac.NUMERO_PROCESO = o.NUMERO_PROCESO
),
res AS (
  SELECT x.CORTE_ID, x.FECHA_CORTE, x.CLIENTE_ID, x.NUMERO_PROCESO, x.N_CREDITOS, x.ESTADO_SAC,
         x.FECHA_INICIO, x.CUOTAS_MORA, x.VALOR_INICIAL, x.VALOR_SALDO, x.VALOR_CUOTA,
         x.VALOR_MORA, x.FECHA_ULTIMO_PAGO, x.CLIENTES_DEL_PROCESO, x.FECHA_LIMITE_PAGO,
         x.VALOR_REAL_PAGADO, x.DIAS_MORA, x.ORIGEN_DIAS_MORA,
         x.ATRASOS_PERMITIDOS, x.CADUCADO,
         g.TIPO_CARTERA, g.CODIGO_SUCURSAL, g.CALIDAD, g.PERIODICIDAD, g.LINEA_CREDITO,
         g.OBLIGACION_REFINANCIADA,
         ob.OBLIGACION_ID,
         ur.OBLIGACION_ID                                AS REPORTADA_ANTES,
         eu.ES_CIERRE                                    AS CIERRE_ANTERIOR,
         -- RF48 / OBS-06: un estado del SAC homologado como CIERRE no trae ESTADO_TU;
         -- el estado sale del cierre que corresponde a lo ultimo reportado.
         CASE WHEN ha.ACCION = 'CIERRE' THEN NVL(eu.CIERRE_AL_PAGAR, '02')
              WHEN x.ESTADO_TU IS NULL THEN NULL
              WHEN x.VALOR_SALDO = 0 AND es.ES_CIERRE = 'N' THEN NVL(eu.CIERRE_AL_PAGAR, '02')
              ELSE x.ESTADO_TU END                       AS ESTADO_TU
  FROM   calc x
  CROSS JOIN NEXOVOLT.V_CONFIG g
  LEFT JOIN NEXOVOLT.NV_HOMOLOGA_ESTADO ha
         ON ha.TIPO_CARTERA = g.TIPO_CARTERA AND ha.ESTADO_SAC = x.ESTADO_SAC
  LEFT JOIN NEXOVOLT.NV_ESTADO_TU es
         ON es.TIPO_CARTERA = g.TIPO_CARTERA AND es.CODIGO_ESTADO = x.ESTADO_TU
  LEFT JOIN NEXOVOLT.NV_OBLIGACION ob
         ON ob.CLIENTE_ID = x.CLIENTE_ID AND ob.NUMERO_PROCESO = x.NUMERO_PROCESO
  LEFT JOIN NEXOVOLT.V_ULTIMO_REPORTE ur
         ON ur.OBLIGACION_ID = ob.OBLIGACION_ID
  LEFT JOIN NEXOVOLT.NV_ESTADO_TU eu
         ON eu.TIPO_CARTERA = ur.TIPO_CARTERA AND eu.CODIGO_ESTADO = ur.ESTADO_TU
)
SELECT r.CORTE_ID,
       r.FECHA_CORTE,
       r.OBLIGACION_ID,
       r.CLIENTE_ID,
       r.NUMERO_PROCESO,
       CASE WHEN r.NUMERO_PROCESO > 0 AND r.CLIENTES_DEL_PROCESO = 1 THEN TO_CHAR(r.NUMERO_PROCESO)
            WHEN r.NUMERO_PROCESO > 0 THEN TO_CHAR(r.NUMERO_PROCESO) || '-' || TO_CHAR(r.CLIENTE_ID)
            ELSE 'M' || TO_CHAR(r.CLIENTE_ID) || '-' || TO_CHAR(ABS(r.NUMERO_PROCESO)) END AS NUMERO_OBLIGACION_PROPUESTO,
       td.TIPO_ID_TU,
       cl.NUMERO_DOCUMENTO                              AS NUMERO_IDENTIFICACION,
       cl.NOMBRE                                        AS NOMBRE_TITULAR,
       r.FECHA_LIMITE_PAGO,
       r.CODIGO_SUCURSAL,
       r.CALIDAD,
       r.TIPO_CARTERA,
       r.ESTADO_TU,
       em.CODIGO                                        AS EDAD_MORA,
       r.FECHA_INICIO,
       r.PERIODICIDAD,
       r.CUOTAS_MORA,
       r.VALOR_INICIAL,
       r.VALOR_MORA,
       r.VALOR_SALDO,
       r.VALOR_CUOTA,
       r.LINEA_CREDITO,
       r.OBLIGACION_REFINANCIADA,
       cl.CORREO,
       TO_CHAR(cl.TELEFONO_CELULAR)                     AS CELULAR,
       r.VALOR_REAL_PAGADO,
       r.ESTADO_SAC,
       r.N_CREDITOS,
       r.DIAS_MORA,
       r.ORIGEN_DIAS_MORA,
       r.FECHA_ULTIMO_PAGO,
       r.CADUCADO,
       r.ATRASOS_PERMITIDOS,
       cl.AUTORIZA_DATOS,
       CASE WHEN r.ESTADO_TU IS NULL                      THEN 'N'
            WHEN cl.CLIENTE_ID IS NULL                    THEN 'N'
            WHEN ef.ES_CIERRE = 'N'                       THEN 'S'
            WHEN r.REPORTADA_ANTES IS NOT NULL
                 AND r.CIERRE_ANTERIOR = 'N'              THEN 'S'
            ELSE 'N' END                                AS INCLUIR,
       CASE WHEN r.ESTADO_TU IS NULL                      THEN 'ESTADO_SIN_HOMOLOGAR'
            WHEN cl.CLIENTE_ID IS NULL                    THEN 'CLIENTE_NO_EXISTE'
            WHEN ef.ES_CIERRE = 'N'                       THEN NULL
            WHEN r.REPORTADA_ANTES IS NOT NULL
                 AND r.CIERRE_ANTERIOR = 'N'              THEN NULL
            WHEN r.REPORTADA_ANTES IS NOT NULL            THEN 'YA_CERRADA_EN_TU'
            ELSE 'CERRADA_NUNCA_REPORTADA' END          AS MOTIVO_EXCLUSION
FROM   res r
LEFT JOIN SAC.CLIENTES cl
       ON cl.CLIENTE_ID = r.CLIENTE_ID
LEFT JOIN NEXOVOLT.NV_HOMOLOGA_TIPO_DOC td
       ON td.DOCUMENTO_TIPO_SAC = cl.DOCUMENTO_TIPO
LEFT JOIN NEXOVOLT.NV_EDAD_MORA em
       ON r.DIAS_MORA BETWEEN em.DIAS_DESDE AND em.DIAS_HASTA
LEFT JOIN NEXOVOLT.NV_ESTADO_TU ef
       ON ef.TIPO_CARTERA = r.TIPO_CARTERA AND ef.CODIGO_ESTADO = r.ESTADO_TU;

COMMENT ON TABLE NEXOVOLT.V_CALCULO_CORTE IS
  'Calculo del corte en BORRADOR: una fila por obligacion. Lee la accion de homologacion (RF48): CIERRE toma el cierre del ultimo estado reportado.';
