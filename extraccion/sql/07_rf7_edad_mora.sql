CREATE OR REPLACE FUNCTION dias_mora (
    p_fecha_corte IN DATE,
    p_fecha_limite_pago IN DATE
) RETURN PLS_INTEGER
IS
BEGIN
    IF p_fecha_corte IS NULL OR p_fecha_limite_pago IS NULL THEN
        RAISE_APPLICATION_ERROR(-20002, 'La fecha de corte y la fecha limite de pago son obligatorias.');
    END IF;

    RETURN TRUNC(p_fecha_corte) - TRUNC(p_fecha_limite_pago);
END dias_mora;
/

CREATE OR REPLACE FUNCTION edad_mora (
    p_dias_mora IN PLS_INTEGER
) RETURN VARCHAR2
IS
BEGIN
    IF p_dias_mora IS NULL OR p_dias_mora < 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Los dias de mora deben ser un entero no negativo.');
    ELSIF p_dias_mora < 30 THEN
        RETURN '00';
    ELSIF p_dias_mora < 60 THEN
        RETURN '01';
    ELSIF p_dias_mora < 90 THEN
        RETURN '02';
    ELSIF p_dias_mora < 120 THEN
        RETURN '03';
    ELSIF p_dias_mora < 150 THEN
        RETURN '04';
    ELSIF p_dias_mora < 180 THEN
        RETURN '05';
    ELSIF p_dias_mora < 210 THEN
        RETURN '06';
    ELSIF p_dias_mora < 240 THEN
        RETURN '07';
    ELSIF p_dias_mora < 270 THEN
        RETURN '08';
    ELSIF p_dias_mora < 300 THEN
        RETURN '09';
    ELSIF p_dias_mora < 330 THEN
        RETURN '10';
    ELSIF p_dias_mora < 360 THEN
        RETURN '11';
    ELSIF p_dias_mora < 540 THEN
        RETURN '12';
    ELSIF p_dias_mora < 730 THEN
        RETURN '13';
    ELSE
        RETURN '14';
    END IF;
END edad_mora;
/
