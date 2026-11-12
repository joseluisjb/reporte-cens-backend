"""RF48 / OBS-06: V_CALCULO_CORTE lee la accion de homologacion (texto del script 23)."""
from pathlib import Path

SQL = (
    Path(__file__).resolve().parent.parent / "config" / "sql" / "23_v_calculo_corte_accion_cierre.sql"
).read_text(encoding="utf-8")
VISTA = SQL[SQL.index("CREATE OR REPLACE VIEW NEXOVOLT.V_CALCULO_CORTE AS"):]


def test_une_la_homologacion_por_tipo_de_cartera_y_estado_del_sac():
    assert "LEFT JOIN NEXOVOLT.NV_HOMOLOGA_ESTADO ha" in VISTA
    assert "ha.TIPO_CARTERA = g.TIPO_CARTERA AND ha.ESTADO_SAC = x.ESTADO_SAC" in VISTA


def test_el_cierre_se_evalua_antes_que_el_estado_nulo():
    cierre = VISTA.index("WHEN ha.ACCION = 'CIERRE' THEN NVL(eu.CIERRE_AL_PAGAR, '02')")
    nulo = VISTA.index("WHEN x.ESTADO_TU IS NULL THEN NULL")
    assert cierre < nulo


def test_un_estado_sin_homologar_sigue_excluido_con_su_motivo():
    assert "WHEN r.ESTADO_TU IS NULL                      THEN 'ESTADO_SIN_HOMOLOGAR'" in VISTA


def test_conserva_las_columnas_que_lee_el_backend():
    for columna in (
        "NUMERO_OBLIGACION_PROPUESTO", "AS EDAD_MORA", "r.DIAS_MORA", "r.ORIGEN_DIAS_MORA",
        "r.CADUCADO", "r.ATRASOS_PERMITIDOS", "AS INCLUIR", "AS MOTIVO_EXCLUSION",
    ):
        assert columna in VISTA


def test_el_script_no_trae_sentencias_destructivas():
    for palabra in ("DROP ", "DELETE ", "TRUNCATE ", "ALTER TABLE"):
        assert palabra not in VISTA
