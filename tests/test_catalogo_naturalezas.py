"""Catálogo NV_NATURALEZA_REESTR según el Manual v34, Tabla 11 (RF18, OBS-03).

Lee config/sql/22_rf18_catalogo_naturalezas_manual.sql y comprueba que carga los nueve códigos del
Manual con su descripción y CONFIRMADO = 'S', que no siembra el 99 y que lo borra solo si no está
en uso. La prueba contra Oracle es la consulta de verificación del final del script.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SQL = RAIZ / "config" / "sql" / "22_rf18_catalogo_naturalezas_manual.sql"

# Manual Sector Real v34, «Naturaleza de la reestructuración» (Tabla 11, campo 45), en el estilo
# de los catálogos del script 11 (mayúsculas, sin acentos).
MANUAL = {
    "01": "LEY 550",
    "02": "CONCORDATO",
    "03": "LEY 617",
    "04": "ACUERDO ACREEDORES O PRIVADO",
    "05": "EXTRAORDINARIA",
    "06": "ORDINARIA",
    "07": "OTRA",
    "08": "LEY 1116",
    "09": "LEY 546",
}


def _filas_del_merge():
    texto = SQL.read_text(encoding="utf-8")
    cuerpo = texto.split("MERGE INTO NEXOVOLT.NV_NATURALEZA_REESTR d\nUSING (")[1].split("ON (d.CODIGO")[0]
    return re.findall(r"SELECT '(\d+)'(?: AS CODIGO)?, '([^']+)'(?: AS DESCRIPCION)?, '([SN])'", cuerpo)


def test_el_script_carga_los_nueve_codigos_del_manual():
    filas = _filas_del_merge()
    assert {c: d for c, d, _ in filas} == MANUAL
    assert len(filas) == len(MANUAL)


def test_todos_quedan_confirmados():
    assert {conf for _, _, conf in _filas_del_merge()} == {"S"}


def test_no_siembra_el_99():
    assert "99" not in {c for c, _, _ in _filas_del_merge()}


def test_el_99_solo_se_borra_si_no_esta_en_uso():
    texto = SQL.read_text(encoding="utf-8")
    assert "FROM NEXOVOLT.NV_REFINANCIACION WHERE NATURALEZA = '99'" in texto
    assert "IF v_uso = 0 THEN" in texto
    assert "DBMS_OUTPUT.PUT_LINE" in texto
