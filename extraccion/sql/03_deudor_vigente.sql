/* NexoVolt - 03 Vista V_DEUDOR_VIGENTE (RF1)
   Ejecutar DESPUES de 01_nexovolt_bd_autonomous.sql
   Es seguro repetirlo? SI: usa CREATE OR REPLACE */

/* NOTA: El filtro ESTADO_SAC = 'A' (vigente) es PROVISIONAL,
         pendiente de confirmar la semantica exacta de los estados con CENS */

CREATE OR REPLACE VIEW NEXOVOLT.V_DEUDOR_VIGENTE AS
SELECT o.CLIENTE_ID,
       o.NUMERO_PROCESO,
       o.N_CREDITOS,
       o.ESTADO_SAC,
       o.FECHA_INICIO,
       o.VALOR_INICIAL,
       o.VALOR_SALDO,
       o.CUOTAS_MORA
FROM   NEXOVOLT.V_OBLIGACION_SAC o
WHERE  o.ESTADO_SAC = 'A'
AND    o.VALOR_SALDO > 0;
