/* NexoVolt - 10 Tabla NV_TITULAR (RF2)
   Crea NV_TITULAR: datos de identificacion del titular de cada obligacion,
   poblada por la extraccion desde SAC.CLIENTES.
   Es seguro repetirlo: usa CREATE TABLE via bloque PL/SQL si no existe.

   Reversa:
     DROP TABLE NEXOVOLT.NV_TITULAR;

   Verificacion:
     SELECT TABLE_NAME FROM ALL_TABLES
     WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_TITULAR';
*/

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM ALL_TABLES
    WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_TITULAR';

    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE NEXOVOLT.NV_TITULAR (
                TITULAR_ID            NUMBER(19)      NOT NULL,
                CLIENTE_ID            NUMBER(19)      NOT NULL,
                TIPO_IDENTIFICACION   VARCHAR2(2)     NOT NULL,
                NUMERO_IDENTIFICACION VARCHAR2(20)    NOT NULL,
                PRIMER_APELLIDO       VARCHAR2(40)    NOT NULL,
                SEGUNDO_APELLIDO      VARCHAR2(40),
                NOMBRES               VARCHAR2(60)    NOT NULL,
                ESTADO_CIUDADANO      VARCHAR2(2),
                FECHA_EXPEDICION      DATE,
                LUGAR_EXPEDICION      VARCHAR2(6),
                CONSTRAINT PK_NV_TITULAR PRIMARY KEY (TITULAR_ID),
                CONSTRAINT UK_NV_TITULAR_CLIENTE UNIQUE (CLIENTE_ID)
            )';
    END IF;
END;
/

SELECT TABLE_NAME FROM ALL_TABLES
WHERE OWNER = 'NEXOVOLT' AND TABLE_NAME = 'NV_TITULAR';
