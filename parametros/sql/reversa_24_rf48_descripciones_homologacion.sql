/* =============================================================================
   Reversa del script 24 (RF48)
   Devuelve las descripciones de la carga inicial. Solo toca las filas que el
   script 24 dejo (A, C y F con el texto nuevo; B y D sin descripcion).
   Es repetible.
   ============================================================================= */

UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO
SET DESCRIPCION_SAC = CASE ESTADO_SAC
                          WHEN 'A' THEN 'Activo (propuesto)'
                          WHEN 'C' THEN 'Caducado (propuesto)'
                          WHEN 'F' THEN 'Finalizado (propuesto)'
                          ELSE 'Desconocido: preguntar a CENS'
                      END
WHERE (ESTADO_SAC = 'A' AND DESCRIPCION_SAC = 'Activo')
   OR (ESTADO_SAC = 'C' AND DESCRIPCION_SAC = 'Caducado')
   OR (ESTADO_SAC = 'F' AND DESCRIPCION_SAC = 'Finalizado')
   OR (ESTADO_SAC IN ('B', 'D') AND DESCRIPCION_SAC IS NULL);

COMMIT;
