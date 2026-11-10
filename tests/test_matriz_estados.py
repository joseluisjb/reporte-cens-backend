"""Cobertura de la Matriz de cambios de estado, Sector Real Servicios (RNF-06, RF14, RF15, RF45, RF46).

Compara las 400 casillas de la transcripción del Manual (p. 40) con la constante MX del mockup v3,
comprueba que el ciclo lee bien cada casilla y que el SQL de verificación contra Oracle no se separa
de la Matriz. La prueba contra NV_TRANSICION_ESTADO real es
config/sql/verificacion_matriz_transiciones.sql (se corre en el esquema de desarrollo).
"""
import re
from pathlib import Path

import pytest

from ciclo.servicios import _transicion_permitida

RAIZ = Path(__file__).resolve().parent.parent
MATRIZ_MD = RAIZ / "docs" / "iteracion2" / "MATRIZ_ESTADOS_SERVICIOS.md"
MOCKUP = RAIZ / "docs" / "iteracion2" / "NexoVolt_Mockups_Iteracion2_v3.html"
SQL_VERIFICACION = RAIZ / "config" / "sql" / "verificacion_matriz_transiciones.sql"
SQL_CARGA = RAIZ / "config" / "sql" / "12_matriz_transiciones_servicios.sql"

# Orden de las columnas en la p. 40 (y en MX_ORDER del mockup).
ORDEN = ["01", "02", "04", "08", "06", "07", "03", "10", "11", "12"]
NOMBRES = {
    "Vigente": "01", "Saldada": "02", "Suspendida": "04", "Inactivo": "08", "Castigada": "06",
    "Recuperada": "07", "Dudoso recaudo": "03", "Ley 550": "10", "Ley 1116": "11", "Ley 1564": "12",
}


def _celdas(filas):
    """{(desde, desde_con_mora, hacia, hacia_con_mora): 'S'|'N'} a partir de {'01n': 'SSN…'}."""
    celdas = {}
    for clave, valores in filas.items():
        desde, mora_desde = clave[:2], clave[2] == "m"
        for i, valor in enumerate(valores):
            celdas[(desde, mora_desde, ORDEN[i // 2], i % 2 == 1)] = valor
    return celdas


def _matriz_del_manual():
    filas = {}
    for linea in MATRIZ_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| \*\*(.+) ([nm])\*\* \|(.*)\|$", linea)
        if m:
            filas[NOMBRES[m.group(1)] + m.group(2)] = "".join(
                c.strip() for c in m.group(3).split("|")
            )
    return filas


def _matriz_del_mockup():
    html = MOCKUP.read_text(encoding="utf-8")
    orden = re.search(r"const MX_ORDER\s*=\s*\[([^\]]*)\]", html).group(1)
    assert re.findall(r"'(\d\d)'", orden) == ORDEN, "MX_ORDER cambió de orden"
    return dict(re.findall(r"'(\d\d[nm])':'([SN]{20})'", html))


def _matriz_del_sql():
    texto = SQL_VERIFICACION.read_text(encoding="utf-8")
    primera = texto.split("-- 2.")[0]
    filas = re.findall(r"SELECT '(\d\d)', '([SN])', '(\d\d)', '([SN])', '([SN])' FROM DUAL", primera)
    return {(d, dm == "S", h, hm == "S"): p for d, dm, h, hm, p in filas}


def _matriz_del_script_12():
    # La carga usa las columnas reales: la mora va como 'M' (con mora) o 'N' (sin mora).
    texto = SQL_CARGA.read_text(encoding="utf-8")
    filas = re.findall(r"SELECT '(\d\d)'(?: AS \w+)?, '([MN])'(?: AS \w+)?, '(\d\d)'(?: AS \w+)?, '([MN])'(?: AS \w+)?, '([SN])'", texto)
    return {(d, dm == "M", h, hm == "M"): p for d, dm, h, hm, p in filas}


MANUAL = _celdas(_matriz_del_manual())


def test_la_transcripcion_tiene_las_400_casillas():
    assert len(MANUAL) == 400
    assert set(MANUAL.values()) <= {"S", "N"}


def test_el_mockup_coincide_con_el_manual_casilla_por_casilla():
    mockup = _celdas(_matriz_del_mockup())
    distintas = sorted(k for k in MANUAL if mockup.get(k) != MANUAL[k])
    assert len(mockup) == 400
    assert distintas == []


def test_el_sql_de_verificacion_coincide_con_el_manual():
    sql = _matriz_del_sql()
    assert len(sql) == 400
    assert sql == MANUAL


def test_el_script_12_carga_las_400_casillas_del_manual():
    carga = _matriz_del_script_12()
    assert len(carga) == 400
    assert carga == MANUAL


@pytest.mark.parametrize("estado", ["02", "07"])
def test_saldada_y_recuperada_no_tienen_salidas(estado):
    salidas = [v for (d, _, _, _), v in MANUAL.items() if d == estado]
    assert len(salidas) == 40
    assert set(salidas) == {"N"}


@pytest.mark.parametrize("desde, mora_desde, hacia, mora_hacia, esperado", [
    ("01", False, "02", False, "S"),   # RF12: pago total desde Vigente
    ("03", True, "02", False, "N"),    # desde Dudoso recaudo no se salda
    ("03", True, "07", False, "S"),    # RF15: Dudoso recaudo en mora → Castigada recuperada
    ("06", True, "07", False, "S"),    # RF15: Castigada en mora → Castigada recuperada
    ("03", False, "07", False, "N"),   # RF15: el origen debe estar en mora
    ("04", True, "02", False, "N"),    # RF12: desde Suspendida no se cierra (713)
    ("06", True, "01", False, "S"),    # RF46: Castigada que paga la mora vuelve a Vigente
    ("10", False, "01", False, "S"),   # RF46: estado de ley que retoma su curso
    ("01", True, "03", True, "S"),     # RF14: Vigente en mora → Dudoso recaudo
    ("01", False, "06", True, "S"),    # RF45: Vigente → Castigada
])
def test_casillas_de_las_fichas(desde, mora_desde, hacia, mora_hacia, esperado):
    assert MANUAL[(desde, mora_desde, hacia, mora_hacia)] == esperado


def test_el_ciclo_lee_bien_las_400_casillas():
    # El ciclo carga solo las filas PERMITIDA = 'S', con CON_MORA en 'S'/'N' (ciclo.servicios).
    permitidas = {
        (d, "S" if dm else "N", h, "S" if hm else "N")
        for (d, dm, h, hm), v in MANUAL.items() if v == "S"
    }
    errores = [
        clave for clave, valor in MANUAL.items()
        if _transicion_permitida(permitidas, *clave) != (valor == "S")
    ]
    assert errores == []


def test_la_consulta_usa_las_columnas_reales_de_nv_transicion_estado():
    """Las pruebas simulan la base: esto fija los nombres del script base 01 (sección 3.6).

    Con ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA y PERMITIDA, Oracle respondía
    ORA-00904 y GET /matriz-estados/ y POST /ciclos/ daban 500 en Render.
    """
    from ciclo.servicios import _SQL_MATRIZ

    for columna in ("TIPO_CARTERA", "ESTADO_ORIGEN", "MORA_ORIGEN", "ESTADO_DESTINO", "MORA_DESTINO", "PERMITIDO"):
        assert columna in _SQL_MATRIZ
    for columna in ("ESTADO_DESDE", "CON_MORA_DESDE", "ESTADO_HACIA", "CON_MORA_HACIA", "PERMITIDA"):
        assert columna not in _SQL_MATRIZ
    assert "WHEN 'M' THEN 'S'" in _SQL_MATRIZ
