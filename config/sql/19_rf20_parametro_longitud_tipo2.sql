/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Script: 19 - Parametro LONGITUD_REGISTRO_TIPO2 (RF20)

   El Manual v34 (pag. 44) declara 930 caracteres para el registro tipo 2 y sus
   campos (Tabla 2) suman 929. Queda en 930 y CONFIRMADO = 'N' hasta que
   TransUnion confirme. El generador rellena con espacios hasta esta longitud;
   si la clave no existe usa 930.

   Es seguro repetirlo: MERGE no duplica ni pisa un valor ya confirmado.

   Reversa:
     DELETE FROM NEXOVOLT.NV_PARAMETRO WHERE CLAVE = 'LONGITUD_REGISTRO_TIPO2';
     COMMIT;

   Verificacion:
     SELECT CLAVE, VALOR, CONFIRMADO FROM NEXOVOLT.NV_PARAMETRO
     WHERE CLAVE = 'LONGITUD_REGISTRO_TIPO2';
   ============================================================================= */

MERGE INTO NEXOVOLT.NV_PARAMETRO d
USING (SELECT 'LONGITUD_REGISTRO_TIPO2' AS CLAVE FROM DUAL) s
ON (d.CLAVE = s.CLAVE)
WHEN NOT MATCHED THEN INSERT (CLAVE, VALOR, DESCRIPCION, CONFIRMADO)
VALUES (
    'LONGITUD_REGISTRO_TIPO2', '930',
    'Longitud del registro tipo 2 del archivo plano (Manual v34: 930 declarados, 929 por suma). Por confirmar con TransUnion.',
    'N'
);

COMMIT;
