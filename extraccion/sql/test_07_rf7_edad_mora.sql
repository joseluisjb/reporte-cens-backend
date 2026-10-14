CREATE OR REPLACE PACKAGE test_edad_mora AS
    --%suite(RF7 - Edad de mora Tabla 9)
    --%suitepath(NexoVolt)

    --%test(Valida todos los limites de la Tabla 9)
    PROCEDURE test_limites_tabla_9;

    --%test(Rechaza dias negativos)
    PROCEDURE test_dias_negativos;

    --%test(Rechaza dias nulos)
    PROCEDURE test_dias_nulos;

    --%test(Calcula dias calendario entre vencimiento y corte)
    PROCEDURE test_calculo_dias_mora;

    --%test(Rechaza fechas nulas)
    PROCEDURE test_fechas_nulas;
END test_edad_mora;
/

CREATE OR REPLACE PACKAGE BODY test_edad_mora AS
    PROCEDURE assert_codigo (
        p_dias IN PLS_INTEGER,
        p_codigo_esperado IN VARCHAR2
    )
    IS
    BEGIN
        ut.expect(edad_mora(p_dias)).to_equal(p_codigo_esperado);
    END assert_codigo;

    PROCEDURE test_limites_tabla_9
    IS
    BEGIN
        assert_codigo(0, '00');
        assert_codigo(29, '00');
        assert_codigo(30, '01');
        assert_codigo(59, '01');
        assert_codigo(60, '02');
        assert_codigo(89, '02');
        assert_codigo(90, '03');
        assert_codigo(119, '03');
        assert_codigo(120, '04');
        assert_codigo(149, '04');
        assert_codigo(150, '05');
        assert_codigo(179, '05');
        assert_codigo(180, '06');
        assert_codigo(209, '06');
        assert_codigo(210, '07');
        assert_codigo(239, '07');
        assert_codigo(240, '08');
        assert_codigo(269, '08');
        assert_codigo(270, '09');
        assert_codigo(299, '09');
        assert_codigo(300, '10');
        assert_codigo(329, '10');
        assert_codigo(330, '11');
        assert_codigo(359, '11');
        assert_codigo(360, '12');
        assert_codigo(539, '12');
        assert_codigo(540, '13');
        assert_codigo(729, '13');
        assert_codigo(730, '14');
        assert_codigo(1000, '14');
    END test_limites_tabla_9;

    PROCEDURE test_dias_negativos
    IS
        l_codigo VARCHAR2(2);
        l_error_code PLS_INTEGER := 0;
    BEGIN
        BEGIN
            l_codigo := edad_mora(-1);
        EXCEPTION
            WHEN OTHERS THEN
                l_error_code := SQLCODE;
        END;

        ut.expect(l_error_code).to_equal(-20001);
    END test_dias_negativos;

    PROCEDURE test_dias_nulos
    IS
        l_codigo VARCHAR2(2);
        l_error_code PLS_INTEGER := 0;
    BEGIN
        BEGIN
            l_codigo := edad_mora(NULL);
        EXCEPTION
            WHEN OTHERS THEN
                l_error_code := SQLCODE;
        END;

        ut.expect(l_error_code).to_equal(-20001);
    END test_dias_nulos;

    PROCEDURE test_calculo_dias_mora
    IS
    BEGIN
        ut.expect(
            dias_mora(
                TO_DATE('2026-10-30 23:59', 'YYYY-MM-DD HH24:MI'),
                TO_DATE('2026-09-30 00:01', 'YYYY-MM-DD HH24:MI')
            )
        ).to_equal(30);
        ut.expect(
            dias_mora(
                TO_DATE('2026-09-29', 'YYYY-MM-DD'),
                TO_DATE('2026-09-30', 'YYYY-MM-DD')
            )
        ).to_equal(-1);
    END test_calculo_dias_mora;

    PROCEDURE test_fechas_nulas
    IS
        l_dias PLS_INTEGER;
        l_error_code PLS_INTEGER := 0;
    BEGIN
        BEGIN
            l_dias := dias_mora(NULL, SYSDATE);
        EXCEPTION
            WHEN OTHERS THEN
                l_error_code := SQLCODE;
        END;

        ut.expect(l_error_code).to_equal(-20002);
    END test_fechas_nulas;
END test_edad_mora;
/
