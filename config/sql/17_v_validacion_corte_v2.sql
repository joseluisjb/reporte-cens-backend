/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Vista: V_VALIDACION_CORTE (Version 2 - Iteracion 2)
   RF aplicables: RF19, RF22 (Validacion de cierre), RF49, RF52,
                  RF53 (Validacion del corte contra el Manual v34)
   Responsable DBA: Angel Jhoan Diaz Vanegas
   Esquema: NEXOVOLT (Oracle Autonomous Database)

   Salida de la vista:
     CORTE_ID       NUMBER(19)
     OBLIGACION_ID  NUMBER(19)
     REGLA          VARCHAR2(50)
     SEVERIDAD      VARCHAR2(20)  ('CORRECTIVA' o 'INFORMATIVA')
     MENSAJE        VARCHAR2(500 CHAR)

   Es seguro repetirlo: usa CREATE OR REPLACE VIEW.

   Correcciones aplicadas respecto al diseno original (Jose Luis, 2026-11-10):
     - NV_REPORTE_DETALLE no tiene CLIENTE_ID: los datos del titular ya estan
       desnormalizados en TIPO_ID_TU, NUMERO_IDENTIFICACION y NOMBRE_TITULAR.
       Se elimino el JOIN a NV_TITULAR.
     - EDAD_MORA_TU -> EDAD_MORA (nombre real de la columna).
     - FECHA_EXIGIBILIDAD -> FECHA_LIMITE_PAGO (nombre real de la columna).
     - PRIMER_REPORTE no existe: se calcula como obligacion sin corte enviado previo.
     - Regex de NUMERO_OBLIGACION_INVALIDO: '\-.' dentro de [] era un rango invalido
       (ORA-12728 al consultar) y '¯·' eran caracteres danados. El guion va al final.
       (Dilan, 2026-11-10; desbloquea RF21, RF22 y RF53.)
     - CUOTAS_PAGADAS no existe: condicion eliminada de CIERRE_INCOMPLETO.
       Cuando se agregue la columna, restaurar la condicion de RF22.

   Reversa:
     DROP VIEW NEXOVOLT.V_VALIDACION_CORTE;

   Verificacion:
     SELECT CORTE_ID, REGLA, SEVERIDAD, COUNT(*)
     FROM NEXOVOLT.V_VALIDACION_CORTE
     GROUP BY CORTE_ID, REGLA, SEVERIDAD;
   ============================================================================= */

CREATE OR REPLACE VIEW NEXOVOLT.V_VALIDACION_CORTE AS
-- 1. SIN_IDENTIFICACION (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_IDENTIFICACION' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Titular sin numero o tipo de identificacion valido' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.NUMERO_IDENTIFICACION IS NULL OR rd.TIPO_ID_TU IS NULL

UNION ALL

-- 2. SIN_NOMBRE (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_NOMBRE' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Titular sin nombre registrado' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.NOMBRE_TITULAR IS NULL

UNION ALL

-- 3. SIN_NUMERO_OBLIGACION (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_NUMERO_OBLIGACION' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ID ' || rd.OBLIGACION_ID || ' sin numero de obligacion TransUnion asignado' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
LEFT JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE o.NUMERO_OBLIGACION_TU IS NULL

UNION ALL

-- 4. NUMERO_OBLIGACION_INVALIDO (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'NUMERO_OBLIGACION_INVALIDO' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Longitud superior a 20 caracteres o caracteres no permitidos' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE LENGTH(o.NUMERO_OBLIGACION_TU) > 20
   OR REGEXP_LIKE(o.NUMERO_OBLIGACION_TU, '[^A-Za-z0-9()*,./\_-]')

UNION ALL

-- 5. SIN_SUCURSAL (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_SUCURSAL' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Sin codigo de sucursal configurado' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE NOT EXISTS (
    SELECT 1 FROM NEXOVOLT.NV_PARAMETRO p
    WHERE p.CLAVE = 'CODIGO_SUCURSAL' AND p.VALOR IS NOT NULL
)

UNION ALL

-- 6. SIN_CALIDAD (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_CALIDAD' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Calidad del deudor no definida' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.CALIDAD IS NULL

UNION ALL

-- 7. SIN_ESTADO (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_ESTADO' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Estado TransUnion no asignado' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.ESTADO_TU IS NULL

UNION ALL

-- 8. SIN_EDAD (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_EDAD' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Edad de mora TransUnion no asignada' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.EDAD_MORA IS NULL

UNION ALL

-- 9. FECHA_CORTE_NO_POSTERIOR (CORRECTIVA)
SELECT
    c.CORTE_ID,
    CAST(NULL AS NUMBER(19)) AS OBLIGACION_ID,
    'FECHA_CORTE_NO_POSTERIOR' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'La fecha de corte (' || TO_CHAR(c.FECHA_CORTE, 'YYYY-MM-DD') || ') debe ser posterior al ultimo corte enviado' AS MENSAJE
FROM NEXOVOLT.NV_CORTE c
WHERE EXISTS (
    SELECT 1 FROM NEXOVOLT.NV_CORTE ant
    WHERE ant.ESTADO IN ('ENVIADO', 'ENVIADO_CON_INCONSISTENCIAS')
      AND c.FECHA_CORTE <= ant.FECHA_CORTE
      AND c.CORTE_ID != ant.CORTE_ID
)

UNION ALL

-- 10. FECHA_EXIGIBILIDAD_FUTURA (CORRECTIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'FECHA_EXIGIBILIDAD_FUTURA' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Fecha limite de pago (' || TO_CHAR(rd.FECHA_LIMITE_PAGO, 'YYYY-MM-DD') || ') no puede ser mayor a la fecha del sistema' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.FECHA_LIMITE_PAGO > TRUNC(SYSDATE)

UNION ALL

-- 11. EDAD_SIN_VALOR_MORA (CORRECTIVA, Regla 707)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'EDAD_SIN_VALOR_MORA' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ' tiene edad ' || rd.EDAD_MORA || ' con valor de mora 0 (regla 707)' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.EDAD_MORA > '00'
  AND (rd.VALOR_MORA IS NULL OR rd.VALOR_MORA = 0)

UNION ALL

-- 12. SIN_FECHA_LIMITE_PAGO (CORRECTIVA, salvo estado 06 Castigada)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SIN_FECHA_LIMITE_PAGO' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Sin fecha limite de pago asignada' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.ESTADO_TU != '06'
  AND rd.FECHA_LIMITE_PAGO IS NULL
  AND rd.VALOR_MORA > 0

UNION ALL

-- 13. PRIMER_REPORTE_INVALIDO (CORRECTIVA, RF10)
-- Primer reporte: obligacion que no aparece en ningun corte enviado previo.
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'PRIMER_REPORTE_INVALIDO' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Estado ' || rd.ESTADO_TU || ' y comportamiento no permitido en primer reporte' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE NOT EXISTS (
    SELECT 1 FROM NEXOVOLT.NV_REPORTE_DETALLE rd2
    WHERE rd2.OBLIGACION_ID = rd.OBLIGACION_ID
      AND rd2.CORTE_ID IN (
          SELECT CORTE_ID FROM NEXOVOLT.NV_CORTE
          WHERE ESTADO IN ('ENVIADO', 'ENVIADO_CON_INCONSISTENCIAS')
      )
)
AND (
    rd.ESTADO_TU NOT IN ('01', '03', '06')
    OR (rd.ESTADO_TU = '03' AND rd.VALOR_MORA = 0)
    OR (rd.ESTADO_TU = '06' AND (rd.EDAD_MORA = '00' OR rd.VALOR_MORA = 0))
)

UNION ALL

-- 14. CIERRE_INCOMPLETO (CORRECTIVA, RF22)
-- Nota: falta la condicion de CUOTAS_PAGADAS (columna pendiente de agregar a NV_REPORTE_DETALLE).
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'CIERRE_INCOMPLETO' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ' en cierre (' || rd.ESTADO_TU || ') presenta datos inconsistentes: ' ||
    CASE
        WHEN rd.VALOR_SALDO > 0                                        THEN 'Saldo mayor a cero'
        WHEN rd.VALOR_MORA > 0                                         THEN 'Valor de mora mayor a cero'
        WHEN rd.CUOTAS_MORA > 0                                        THEN 'Cuotas en mora mayor a cero'
        WHEN rd.VALOR_CUOTA > 0                                        THEN 'Valor de cuota mayor a cero'
        WHEN rd.EDAD_MORA != '00'                                      THEN 'Edad de mora distinta de 00'
        WHEN rd.FECHA_PAGO IS NULL                                     THEN 'Fecha de pago no registrada'
        WHEN rd.FECHA_PAGO > c.FECHA_CORTE                             THEN 'Fecha de pago posterior al corte'
        WHEN rd.FECHA_PAGO < o.FECHA_INICIO                            THEN 'Fecha de pago anterior al inicio'
        WHEN rd.MODO_EXTINCION IS NULL OR rd.TIPO_PAGO IS NULL         THEN 'Modo o tipo de extincion no diligenciados'
        WHEN rd.TIPO_PAGO = '01' AND rd.MODO_EXTINCION NOT IN ('01', '16') THEN 'Incoherencia entre tipo y modo de pago'
        ELSE 'Inconsistencia en cierre'
    END AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = rd.CORTE_ID
WHERE rd.ESTADO_TU IN ('02', '07')
  AND (
      rd.VALOR_SALDO > 0
      OR rd.VALOR_MORA > 0
      OR rd.CUOTAS_MORA > 0
      OR rd.VALOR_CUOTA > 0
      OR rd.EDAD_MORA != '00'
      OR rd.FECHA_PAGO IS NULL
      OR rd.FECHA_PAGO > c.FECHA_CORTE
      OR rd.FECHA_PAGO < o.FECHA_INICIO
      OR rd.MODO_EXTINCION IS NULL
      OR rd.TIPO_PAGO IS NULL
      OR (rd.TIPO_PAGO = '01' AND rd.MODO_EXTINCION NOT IN ('01', '16'))
  )

UNION ALL

-- 15. OMISION_VS_ULTIMO_CORTE (CORRECTIVA, RF21)
SELECT
    c.CORTE_ID,
    ant_rd.OBLIGACION_ID,
    'OMISION_VS_ULTIMO_CORTE' AS REGLA,
    'CORRECTIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ' activa en corte anterior fue omitida en el corte actual sin registro de cierre ni eliminacion' AS MENSAJE
FROM NEXOVOLT.NV_CORTE c
CROSS JOIN (
    SELECT MAX(CORTE_ID) AS ULT_CORTE_ID
    FROM NEXOVOLT.NV_CORTE
    WHERE ESTADO IN ('ENVIADO', 'ENVIADO_CON_INCONSISTENCIAS')
) ult
JOIN NEXOVOLT.NV_REPORTE_DETALLE ant_rd ON ant_rd.CORTE_ID = ult.ULT_CORTE_ID
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = ant_rd.OBLIGACION_ID
WHERE ant_rd.ESTADO_TU NOT IN ('02', '07')
  AND NVL(o.ELIMINADA, 'N') = 'N'
  AND NOT EXISTS (
      SELECT 1 FROM NEXOVOLT.NV_REPORTE_DETALLE curr_rd
      WHERE curr_rd.CORTE_ID = c.CORTE_ID
        AND curr_rd.OBLIGACION_ID = ant_rd.OBLIGACION_ID
  )

-- =============================================================================
-- REGLAS INFORMATIVAS (ADVERTENCIAS)
-- =============================================================================

UNION ALL

-- 16. CUOTAS_MORA_INCOHERENTE (INFORMATIVA, RF19)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'CUOTAS_MORA_INCOHERENTE' AS REGLA,
    'INFORMATIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ' tiene cuotas_mora=' || rd.CUOTAS_MORA || ' con valor de mora 0' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.CUOTAS_MORA > 0
  AND (rd.VALOR_MORA IS NULL OR rd.VALOR_MORA = 0)

UNION ALL

-- 17. SALDO_MAYOR_VALOR_INICIAL (INFORMATIVA, RF52)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'SALDO_MAYOR_VALOR_INICIAL' AS REGLA,
    'INFORMATIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Saldo pendiente (' || rd.VALOR_SALDO || ') superior al valor inicial (' || rd.VALOR_INICIAL || ')' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.VALOR_SALDO > rd.VALOR_INICIAL

UNION ALL

-- 18. VALOR_FUERA_DE_RANGO (INFORMATIVA)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'VALOR_FUERA_DE_RANGO' AS REGLA,
    'INFORMATIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Valor de saldo (' || rd.VALOR_SALDO || ') fuera del rango habitual ($10.000 a $99.000.000)' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.VALOR_SALDO > 99000000
   OR (rd.VALOR_SALDO > 0 AND rd.VALOR_SALDO < 10000)

UNION ALL

-- 19. EDAD_ALTA_SIN_EXIGIBILIDAD (INFORMATIVA, RF49)
SELECT
    rd.CORTE_ID,
    rd.OBLIGACION_ID,
    'EDAD_ALTA_SIN_EXIGIBILIDAD' AS REGLA,
    'INFORMATIVA' AS SEVERIDAD,
    'Obligacion ' || o.NUMERO_OBLIGACION_TU || ': Edad ' || rd.EDAD_MORA || ' sin fecha limite de pago reportada' AS MENSAJE
FROM NEXOVOLT.NV_REPORTE_DETALLE rd
JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID
WHERE rd.EDAD_MORA IN ('12', '13', '14')
  AND rd.FECHA_LIMITE_PAGO IS NULL

UNION ALL

-- 20. ENTIDAD_CON_MARCADOR (INFORMATIVA, RF57)
SELECT
    c.CORTE_ID,
    CAST(NULL AS NUMBER(19)) AS OBLIGACION_ID,
    'ENTIDAD_CON_MARCADOR' AS REGLA,
    'INFORMATIVA' AS SEVERIDAD,
    'Parametros de la entidad o sucursal contienen marcadores provisionales (inician por X). El archivo se generara como NO APTO para envio.' AS MENSAJE
FROM NEXOVOLT.NV_CORTE c
WHERE EXISTS (
    SELECT 1 FROM NEXOVOLT.NV_PARAMETRO p
    WHERE p.CLAVE IN ('TIPO_ENTIDAD', 'CODIGO_ENTIDAD', 'CODIGO_SUCURSAL')
      AND p.VALOR LIKE 'X%'
);
/

COMMENT ON TABLE NEXOVOLT.V_VALIDACION_CORTE IS 'Reglas de validacion correctivas e informativas del corte contra el Manual v34 de TransUnion (RF22, RF53).';
