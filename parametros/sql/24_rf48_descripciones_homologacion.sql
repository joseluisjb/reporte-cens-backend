/* =============================================================================
   Script 24 · Descripciones de la homologacion de estados sin notas internas (RF48)
   Esquema NEXOVOLT · Oracle Autonomous

   La carga inicial dejo en NV_HOMOLOGA_ESTADO.DESCRIPCION_SAC textos de trabajo
   del equipo que la pantalla «Homologacion de Estados» muestra tal cual:
   «Activo (propuesto)», «Caducado (propuesto)», «Finalizado (propuesto)» y
   «Desconocido: preguntar a CENS» (B y D). Hallazgo del recorrido en Render del
   18/11/2026.

   Que hace:
     - A, C y F quedan como «Activo», «Caducado» y «Finalizado». Que sean
       propuestas ya lo dice la columna CONFIRMADO (N), que la pantalla muestra.
     - B y D quedan sin descripcion (NULL): la pantalla dice «Sin descripcion»
       hasta que CENS diga que significan. No se inventa un texto.
   Solo cambia las filas que todavia tienen el texto de la carga inicial, en los
   dos tipos de cartera. Es repetible: una segunda ejecucion no cambia nada.

   Reversa: reversa_24_rf48_descripciones_homologacion.sql
   Verificacion: verificacion_24_rf48_descripciones_homologacion.sql
   ============================================================================= */

UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO
SET DESCRIPCION_SAC = CASE ESTADO_SAC
                          WHEN 'A' THEN 'Activo'
                          WHEN 'C' THEN 'Caducado'
                          WHEN 'F' THEN 'Finalizado'
                          ELSE NULL
                      END
WHERE DESCRIPCION_SAC IN ('Activo (propuesto)', 'Caducado (propuesto)',
                          'Finalizado (propuesto)', 'Desconocido: preguntar a CENS');

COMMIT;
