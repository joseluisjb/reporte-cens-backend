/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Vista: V_REPORTE_TU (Version 2 - Iteracion 2)
   RF aplicables: RF20 (Generacion de archivo plano), RF51 (Formato de valores)
   Responsable DBA: Angel Jhoan Diaz Vanegas
   Esquema: NEXOVOLT (Oracle Autonomous Database)

   Descripcion funcional:
     Provee las columnas necesarias para armar los registros tipo 2 del archivo plano
     de TransUnion (Manual v34, Tabla 2, paginas 44 a 52).
     Incluye campos de identificacion, obligacion (posiciones 89-108), valores monetarios
     (12 digitos en miles o pesos segun acuerdo), estado de contrato, campos de cierre
     (FECHA_PAGO, MODO_EXTINCION, TIPO_PAGO) y de reestructuracion.
     Devuelve solo las obligaciones aptas para reporte (no eliminadas ni excluidas).

   Correcciones aplicadas respecto al diseno original (Jose Luis, 2026-11-10):
     - rd.CLIENTE_ID no existe en NV_REPORTE_DETALLE: el JOIN a NV_TITULAR
       se hace via o.CLIENTE_ID (NV_OBLIGACION si tiene esa columna).
     - rd.EDAD_MORA_TU -> rd.EDAD_MORA (nombre real de la columna).
     - rd.FECHA_EXIGIBILIDAD -> rd.FECHA_LIMITE_PAGO (nombre real).
     - rd.CUOTAS_TOTALES, rd.CUOTAS_CANCELADAS, rd.CUOTAS_PAGADAS no existen
       en NV_REPORTE_DETALLE: se exponen como NULL hasta que se agreguen.
     - rd.ESTADO_CONTRATO no existe: se expone el valor por defecto '001'.
     - rd.NATURALEZA_REESTR, rd.N_REESTRUCTURACIONES no existen: se exponen
       como ' ' y 0 respectivamente hasta que se agreguen.
     - rd.ANIOS_MORA no existe en la tabla real: se calcula como TRUNC(DIAS_MORA/365).

   Reversa:
     DROP VIEW NEXOVOLT.V_REPORTE_TU;

   Verificacion:
     SELECT * FROM NEXOVOLT.V_REPORTE_TU WHERE ROWNUM <= 10;
   ============================================================================= */

CREATE OR REPLACE VIEW NEXOVOLT.V_REPORTE_TU AS
SELECT
    rd.CORTE_ID,
    c.FECHA_CORTE,
    c.TIPO_REPORTE,
    -- Identificacion del titular (desde NV_TITULAR via NV_OBLIGACION)
    t.TIPO_IDENTIFICACION,
    t.NUMERO_IDENTIFICACION,
    t.PRIMER_APELLIDO,
    t.SEGUNDO_APELLIDO,
    t.NOMBRES,
    t.ESTADO_CIUDADANO,
    -- Identificacion de la obligacion (posiciones 89 a 108: 20 caracteres)
    o.OBLIGACION_ID,
    o.CLIENTE_ID,
    o.NUMERO_PROCESO,
    RPAD(NVL(o.NUMERO_OBLIGACION_TU, ' '), 20, ' ') AS NUMERO_OBLIGACION_TU,
    o.FECHA_INICIO,
    -- Estado y comportamiento
    rd.ESTADO_TU,
    rd.EDAD_MORA                                      AS EDAD_MORA_TU,
    NVL(rd.DIAS_MORA, 0)                              AS DIAS_MORA,
    TRUNC(NVL(rd.DIAS_MORA, 0) / 365)                 AS ANIOS_MORA,
    -- Valores monetarios (en pesos; el generador del archivo aplica la conversion a miles)
    NVL(rd.VALOR_INICIAL, 0)                          AS VALOR_INICIAL,
    NVL(rd.VALOR_SALDO, 0)                            AS VALOR_SALDO,
    NVL(rd.VALOR_MORA, 0)                             AS VALOR_MORA,
    NVL(rd.VALOR_CUOTA, 0)                            AS VALOR_CUOTA,
    NVL(rd.VALOR_REAL_PAGADO, 0)                      AS VALOR_REAL_PAGADO,
    -- Cuotas (CUOTAS_TOTALES, CUOTAS_CANCELADAS y CUOTAS_PAGADAS pendientes de agregar a NV_REPORTE_DETALLE)
    CAST(NULL AS NUMBER(10))                           AS CUOTAS_TOTALES,
    CAST(NULL AS NUMBER(10))                           AS CUOTAS_CANCELADAS,
    NVL(rd.CUOTAS_MORA, 0)                            AS CUOTAS_MORA,
    CAST(NULL AS NUMBER(10))                           AS CUOTAS_PAGADAS,
    -- Fechas relevantes
    rd.FECHA_LIMITE_PAGO                              AS FECHA_EXIGIBILIDAD,
    rd.FECHA_PAGO,
    -- Campos de cierre y extincion
    NVL(rd.MODO_EXTINCION, ' ')                       AS MODO_EXTINCION,
    NVL(rd.TIPO_PAGO, ' ')                            AS TIPO_PAGO,
    '001'                                             AS ESTADO_CONTRATO,
    -- Campos de reestructuracion
    NVL(rd.OBLIGACION_REFINANCIADA, '02')             AS OBLIGACION_REESTRUCTURADA,
    ' '                                               AS NATURALEZA_REESTR,
    0                                                 AS N_REESTRUCTURACIONES,
    -- Parametros de entidad (RF57)
    p_suc.VALOR                                       AS CODIGO_SUCURSAL,
    p_ent.VALOR                                       AS CODIGO_ENTIDAD,
    p_tip.VALOR                                       AS TIPO_ENTIDAD
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_CORTE c         ON c.CORTE_ID    = rd.CORTE_ID
JOIN NEXOVOLT.NV_OBLIGACION o    ON o.OBLIGACION_ID = rd.OBLIGACION_ID
LEFT JOIN NEXOVOLT.NV_TITULAR t  ON t.CLIENTE_ID  = o.CLIENTE_ID
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_suc ON p_suc.CLAVE = 'CODIGO_SUCURSAL'
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_ent ON p_ent.CLAVE = 'CODIGO_ENTIDAD'
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_tip ON p_tip.CLAVE = 'TIPO_ENTIDAD'
WHERE NVL(o.ELIMINADA, 'N') = 'N';
/

COMMENT ON TABLE NEXOVOLT.V_REPORTE_TU IS 'Columnas y estructura del registro tipo 2 para el archivo mensual de TransUnion (RF20, RF51).';
