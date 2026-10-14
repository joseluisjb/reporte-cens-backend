/*
  Consulta de referencia RF3-RF5 para las tablas ficticias:
    facturacion(id_proceso, id_credito, concepto, valor)
    pagos(id_credito, concepto, valor)

  Regla acordada para esta consulta: un pago solo amortiza el mismo credito y
  concepto. Se agrega cada fuente por separado antes del JOIN para evitar
  multiplicar importes cuando existen varias filas de facturacion o pagos.
  Importes negativos y creditos ligados a varios procesos quedan en revision;
  no se les asigna saldo reportable.

  El resultado es una fila por id_proceso (obligacion del proceso), no una
  identificacion completa del deudor: la tabla ficticia no proporciona
  cliente_id. En produccion, la clave segura de obligacion debe incorporar
  CLIENTE_ID y NUMERO_PROCESO de la extraccion existente. No se deben unir
  procesos entre deudores por similitud.
*/

WITH facturacion_consolidada AS (
    SELECT id_proceso,
           id_credito,
           concepto,
           SUM(valor) AS valor_facturado
    FROM facturacion
    GROUP BY id_proceso, id_credito, concepto
),
pagos_consolidados AS (
    SELECT id_credito,
           concepto,
           SUM(valor) AS valor_pagado
    FROM pagos
    GROUP BY id_credito, concepto
),
creditos_proceso AS (
    SELECT id_credito,
           COUNT(DISTINCT id_proceso) AS cantidad_procesos
    FROM facturacion
    GROUP BY id_credito
),
aplicacion AS (
    SELECT f.id_proceso,
           f.id_credito,
           f.concepto,
           f.valor_facturado,
           NVL(p.valor_pagado, 0) AS valor_pagado,
           NVL(cp.cantidad_procesos, 0) AS cantidad_procesos,
           CASE
               WHEN f.valor_facturado < 0 OR NVL(p.valor_pagado, 0) < 0 THEN 'S'
               ELSE 'N'
           END AS datos_invalidos,
           LEAST(
               GREATEST(f.valor_facturado, 0),
               GREATEST(NVL(p.valor_pagado, 0), 0)
           ) AS valor_pago_aplicado
    FROM facturacion_consolidada f
    JOIN creditos_proceso cp
      ON cp.id_credito = f.id_credito
    LEFT JOIN pagos_consolidados p
      ON p.id_credito = f.id_credito
     AND p.concepto = f.concepto
),
resumen_proceso AS (
    SELECT id_proceso,
           SUM(valor_facturado) AS valor_facturado,
           SUM(
               CASE
                   WHEN cantidad_procesos = 1 AND datos_invalidos = 'N'
                       THEN valor_pago_aplicado
                   ELSE 0
               END
           ) AS valor_pago_aplicado,
           SUM(
               CASE
                   WHEN cantidad_procesos > 1 OR datos_invalidos = 'S' THEN 1
                   ELSE 0
               END
           ) AS creditos_inconsistentes,
           SUM(
               CASE
                   WHEN cantidad_procesos = 1 AND datos_invalidos = 'N'
                       THEN GREATEST(valor_facturado - valor_pago_aplicado, 0)
                   ELSE 0
               END
           ) AS saldo_neto_calculado
    FROM aplicacion
    GROUP BY id_proceso
)
SELECT id_proceso,
       valor_facturado,
       CASE
           WHEN creditos_inconsistentes > 0 THEN NULL
           ELSE valor_pago_aplicado
       END AS valor_pago_aplicado,
       CASE
           WHEN creditos_inconsistentes > 0 THEN NULL
           ELSE saldo_neto_calculado
       END AS saldo_neto,
       CASE
           WHEN creditos_inconsistentes > 0 THEN 'REVISAR'
           ELSE 'OK'
       END AS estado_consolidacion
FROM resumen_proceso
ORDER BY id_proceso;

/*
  Diagnostico RF5: un mismo id_credito asociado a mas de un proceso no se
  consolida automaticamente; requiere revision antes de asignar obligacion.
*/
SELECT id_credito,
       COUNT(DISTINCT id_proceso) AS cantidad_procesos
FROM facturacion
GROUP BY id_credito
HAVING COUNT(DISTINCT id_proceso) > 1;

/*
  Pagos sin concepto/credito facturado, o excedentes por encima del valor
  facturado, no se trasladan a otro concepto. Reportarlos para conciliacion:
*/
WITH facturacion_consolidada AS (
    SELECT id_credito, concepto, SUM(valor) AS valor_facturado
    FROM facturacion
    GROUP BY id_credito, concepto
),
pagos_consolidados AS (
    SELECT id_credito, concepto, SUM(valor) AS valor_pagado
    FROM pagos
    GROUP BY id_credito, concepto
)
SELECT p.id_credito,
       p.concepto,
       p.valor_pagado,
       NVL(f.valor_facturado, 0) AS valor_facturado,
       GREATEST(p.valor_pagado - NVL(f.valor_facturado, 0), 0) AS valor_no_aplicado
FROM pagos_consolidados p
LEFT JOIN facturacion_consolidada f
  ON f.id_credito = p.id_credito
 AND f.concepto = p.concepto
WHERE f.id_credito IS NULL
   OR p.valor_pagado > NVL(f.valor_facturado, 0);
