-- Fila 42: guardar en cada corte quién lo generó (ejecutada_por).
-- NV_CORTE.USUARIO_ID apunta a la tabla anterior NV_USUARIO, pero los usuarios de la app están en
-- USUARIOS_USUARIO (Django, RF25). Igual que el script 08 con NV_BITACORA, se quita esa llave para
-- poder guardar el id del usuario de la sesión. El nombre se toma de USUARIOS_USUARIO al leer.
-- Se ejecuta UNA vez en el Oracle que usa Render, ANTES de desplegar el código que lo usa: sin esto,
-- generar un corte con sesión falla (ORA-02291). Busca la llave por su destino, así que no hace falta
-- conocer su nombre; si ya no existe, no hace nada.
BEGIN
    FOR r IN (
        SELECT c.constraint_name
        FROM all_constraints c
        JOIN all_constraints p
          ON p.owner = c.r_owner AND p.constraint_name = c.r_constraint_name
        WHERE c.owner = 'NEXOVOLT'
          AND c.table_name = 'NV_CORTE'
          AND c.constraint_type = 'R'
          AND p.table_name = 'NV_USUARIO'
    ) LOOP
        EXECUTE IMMEDIATE 'ALTER TABLE NEXOVOLT.NV_CORTE DROP CONSTRAINT ' || r.constraint_name;
    END LOOP;
END;
/
