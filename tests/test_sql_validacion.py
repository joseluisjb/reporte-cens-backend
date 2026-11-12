"""DF-02: las vistas SQL calculan la exigibilidad como FECHA_CORTE - DIAS_MORA (texto de los scripts)."""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent / "config" / "sql"


def _leer(nombre):
    return (RAIZ / nombre).read_text(encoding="utf-8")


def _bloque(sql, numero):
    """Texto entre '-- N.' y el siguiente comentario numerado."""
    inicio = sql.index(f"-- {numero}. ")
    fin = re.search(r"^-- \d+\. ", sql[inicio + 4:], re.M)
    return sql[inicio:inicio + 4 + fin.start()] if fin else sql[inicio:]


def test_regla_10_usa_corte_menos_dias_de_mora():
    bloque = _bloque(_leer("17_v_validacion_corte_v2.sql"), 10)
    assert "FECHA_EXIGIBILIDAD_FUTURA" in bloque
    assert "JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = rd.CORTE_ID" in bloque
    assert "TRUNC(c.FECHA_CORTE) - rd.DIAS_MORA > TRUNC(SYSDATE)" in bloque
    assert "rd.VALOR_MORA > 0" in bloque
    assert "rd.EDAD_MORA > '00'" in bloque
    assert "rd.DIAS_MORA IS NOT NULL" in bloque
    assert "FECHA_LIMITE_PAGO" not in bloque


def test_regla_19_depende_de_dias_de_mora():
    bloque = _bloque(_leer("17_v_validacion_corte_v2.sql"), 19)
    assert "EDAD_ALTA_SIN_EXIGIBILIDAD" in bloque
    assert "rd.EDAD_MORA IN ('12', '13', '14')" in bloque
    assert "rd.VALOR_MORA > 0" in bloque
    assert "rd.DIAS_MORA IS NULL" in bloque
    assert "FECHA_LIMITE_PAGO" not in bloque


def test_vista_17_documenta_df02():
    assert "Correcciones (DF-02, 2026-11-11)" in _leer("17_v_validacion_corte_v2.sql")


def test_vista_18_calcula_la_exigibilidad_con_dias_de_mora():
    sql = _leer("18_v_reporte_tu_v2.sql")
    columna = re.search(r"^\s*CASE WHEN[^\n]*\n.*?AS FECHA_EXIGIBILIDAD", sql, re.M | re.S)
    assert columna, "FECHA_EXIGIBILIDAD debe ser una expresión CASE"
    texto = columna.group(0)
    assert "TRUNC(c.FECHA_CORTE) - rd.DIAS_MORA" in texto
    assert "rd.DIAS_MORA IS NOT NULL" in texto
    assert "rd.VALOR_MORA" in texto and "rd.EDAD_MORA > '00'" in texto
    assert not re.search(r"rd\.FECHA_LIMITE_PAGO\s+AS FECHA_EXIGIBILIDAD", sql)
    assert "Correcciones (DF-02, 2026-11-11)" in sql
