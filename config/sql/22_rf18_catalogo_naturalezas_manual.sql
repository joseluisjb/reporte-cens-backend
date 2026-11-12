/* =============================================================================
   NexoVolt - Automatizacion del Reporte de Cartera a Centrales de Riesgo (CENS)
   Script: 22 - Catalogo NV_NATURALEZA_REESTR segun el Manual v34 (RF18, OBS-03)

   El script 11 sembro el catalogo con 01 REESTRUCTURACION VOLUNTARIA,
   02 LEY 550 O REESTRUCTURACION EMPRESARIAL, 03 LEY 1116 O INSOLVENCIA y
   99 OTRA NATURALEZA DE REESTRUCTURACION, todos con CONFIRMADO = 'N'. Esos
   codigos no salen del Manual Sector Real v34 de TransUnion: la tabla
   «Naturaleza de la reestructuracion» (Tabla No. 11 del layout del registro
   tipo 2, campo 45) trae exactamente nueve:
     01 Ley 550 · 02 Concordato · 03 Ley 617 · 04 Acuerdo acreedores o privado
     05 Extraordinaria · 06 Ordinaria · 07 Otra · 08 Ley 1116 · 09 Ley 546
   La fuente de verdad es el Manual.

   Que hace:
     1. MERGE de los 9 codigos del Manual con su descripcion y CONFIRMADO = 'S'
        (actualiza los que ya existen, inserta los que faltan).
     2. Borra el codigo 99 (no existe en el Manual) solo si ninguna fila de
        NV_REFINANCIACION lo usa (FK_NV_REFIN_NAT). Si esta en uso, no lo borra
        y lo informa con DBMS_OUTPUT.
   Las descripciones van en mayusculas y sin acentos, igual que los demas
   catalogos sembrados en el script 11.

   ADVERTENCIA: las refinanciaciones ya registradas con 01, 02 o 03 cambian de
   significado (antes 01 voluntaria, 02 Ley 550/empresarial, 03 Ley 1116; ahora
   01 Ley 550, 02 Concordato, 03 Ley 617; la Ley 1116 pasa a ser 08). Son datos
   de prueba, pero deben revisarse y corregirse antes de reportar. Esta revision
   no la hace el script.

   Es seguro repetirlo: MERGE no duplica y el borrado del 99 es condicional.
   Requiere SET SERVEROUTPUT ON para ver el aviso del 99.

   Reversa (restaura la siembra original del script 11; los codigos 04 a 09 se
   borran solo si ninguna refinanciacion los usa):
     MERGE INTO NEXOVOLT.NV_NATURALEZA_REESTR d
     USING (
         SELECT '01' AS CODIGO, 'REESTRUCTURACION VOLUNTARIA' AS DESCRIPCION FROM DUAL UNION ALL
         SELECT '02', 'LEY 550 O REESTRUCTURACION EMPRESARIAL' FROM DUAL UNION ALL
         SELECT '03', 'LEY 1116 O INSOLVENCIA' FROM DUAL UNION ALL
         SELECT '99', 'OTRA NATURALEZA DE REESTRUCTURACION' FROM DUAL
     ) s ON (d.CODIGO = s.CODIGO)
     WHEN MATCHED THEN UPDATE SET d.DESCRIPCION = s.DESCRIPCION, d.CONFIRMADO = 'N'
     WHEN NOT MATCHED THEN INSERT (CODIGO, DESCRIPCION, CONFIRMADO)
     VALUES (s.CODIGO, s.DESCRIPCION, 'N');
     DELETE FROM NEXOVOLT.NV_NATURALEZA_REESTR n
     WHERE n.CODIGO IN ('04', '05', '06', '07', '08', '09')
       AND NOT EXISTS (SELECT 1 FROM NEXOVOLT.NV_REFINANCIACION r WHERE r.NATURALEZA = n.CODIGO);
     COMMIT;

   Verificacion: la consulta del final debe devolver 9 filas, todas con
   CONFIRMADO = 'S' (y 99 solo si estaba en uso).

   Estado: escrito, pendiente de aplicar en Oracle (no se ha ejecutado).
   ============================================================================= */

MERGE INTO NEXOVOLT.NV_NATURALEZA_REESTR d
USING (
    SELECT '01' AS CODIGO, 'LEY 550' AS DESCRIPCION, 'S' AS CONFIRMADO FROM DUAL UNION ALL
    SELECT '02', 'CONCORDATO', 'S' FROM DUAL UNION ALL
    SELECT '03', 'LEY 617', 'S' FROM DUAL UNION ALL
    SELECT '04', 'ACUERDO ACREEDORES O PRIVADO', 'S' FROM DUAL UNION ALL
    SELECT '05', 'EXTRAORDINARIA', 'S' FROM DUAL UNION ALL
    SELECT '06', 'ORDINARIA', 'S' FROM DUAL UNION ALL
    SELECT '07', 'OTRA', 'S' FROM DUAL UNION ALL
    SELECT '08', 'LEY 1116', 'S' FROM DUAL UNION ALL
    SELECT '09', 'LEY 546', 'S' FROM DUAL
) s
ON (d.CODIGO = s.CODIGO)
WHEN MATCHED THEN
    UPDATE SET d.DESCRIPCION = s.DESCRIPCION, d.CONFIRMADO = s.CONFIRMADO
WHEN NOT MATCHED THEN
    INSERT (CODIGO, DESCRIPCION, CONFIRMADO)
    VALUES (s.CODIGO, s.DESCRIPCION, s.CONFIRMADO);

SET SERVEROUTPUT ON

DECLARE
    v_uso NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_uso FROM NEXOVOLT.NV_REFINANCIACION WHERE NATURALEZA = '99';
    IF v_uso = 0 THEN
        DELETE FROM NEXOVOLT.NV_NATURALEZA_REESTR WHERE CODIGO = '99';
        DBMS_OUTPUT.PUT_LINE('Codigo 99 eliminado del catalogo (no esta en el Manual).');
    ELSE
        DBMS_OUTPUT.PUT_LINE('Codigo 99 NO eliminado: lo usan ' || v_uso
            || ' refinanciacion(es) en NV_REFINANCIACION. Reasignarlas a un codigo del Manual y repetir el script.');
    END IF;
END;
/

COMMIT;

-- Verificacion
SELECT CODIGO, DESCRIPCION, CONFIRMADO FROM NEXOVOLT.NV_NATURALEZA_REESTR ORDER BY CODIGO;
