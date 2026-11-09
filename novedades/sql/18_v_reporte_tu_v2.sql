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
    -- Identificacion del titular
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
    rd.EDAD_MORA_TU,
    NVL(rd.DIAS_MORA, 0) AS DIAS_MORA,
    NVL(rd.ANIOS_MORA, 0) AS ANIOS_MORA,
    -- Valores monetarios (expuestos en pesos; backend o vista aplica formateo de 12 digitos)
    NVL(rd.VALOR_INICIAL, 0) AS VALOR_INICIAL,
    NVL(rd.VALOR_SALDO, 0) AS VALOR_SALDO,
    NVL(rd.VALOR_MORA, 0) AS VALOR_MORA,
    NVL(rd.VALOR_CUOTA, 0) AS VALOR_CUOTA,
    NVL(rd.VALOR_REAL_PAGADO, 0) AS VALOR_REAL_PAGADO,
    -- Cuotas
    NVL(rd.CUOTAS_TOTALES, 0) AS CUOTAS_TOTALES,
    NVL(rd.CUOTAS_CANCELADAS, 0) AS CUOTAS_CANCELADAS,
    NVL(rd.CUOTAS_MORA, 0) AS CUOTAS_MORA,
    NVL(rd.CUOTAS_PAGADAS, 0) AS CUOTAS_PAGADAS,
    -- Fechas relevantes
    rd.FECHA_EXIGIBILIDAD,
    rd.FECHA_PAGO,
    -- Campos de cierre y extincion
    NVL(rd.MODO_EXTINCION, ' ') AS MODO_EXTINCION,
    NVL(rd.TIPO_PAGO, ' ') AS TIPO_PAGO,
    NVL(rd.ESTADO_CONTRATO, '001') AS ESTADO_CONTRATO,
    -- Campos de reestructuracion
    NVL(rd.OBLIGACION_REFINANCIADA, '02') AS OBLIGACION_REESTRUCTURADA,
    NVL(rd.NATURALEZA_REESTR, ' ') AS NATURALEZA_REESTR,
    NVL(rd.N_REESTRUCTURACIONES, 0) AS N_REESTRUCTURACIONES,
    -- Parametros de entidad
    p_suc.VALOR AS CODIGO_SUCURSAL,
    p_ent.VALOR AS CODIGO_ENTIDAD,
    p_tip.VALOR AS TIPO_ENTIDAD
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = rd.CORTE_ID
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
LEFT JOIN NEXOVOLT.NV_TITULAR t ON t.CLIENTE_ID = rd.CLIENTE_ID
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_suc ON p_suc.CLAVE = 'CODIGO_SUCURSAL'
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_ent ON p_ent.CLAVE = 'CODIGO_ENTIDAD'
LEFT JOIN NEXOVOLT.NV_PARAMETRO p_tip ON p_tip.CLAVE = 'TIPO_ENTIDAD'
WHERE NVL(o.ELIMINADA, 'N') = 'N';
/

COMMENT ON TABLE NEXOVOLT.V_REPORTE_TU IS 'Columnas y estructura del registro tipo 2 para el archivo mensual de TransUnion (RF20, RF51).';
