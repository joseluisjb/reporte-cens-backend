"""HU-A · CA-A1 — "Se extraen solo deudores con financiación vigente, aislando exclusivamente
conceptos de energía" (RF1, RF2).

Casos de la matriz: docs/pruebas/matriz-HU-A.md
"""

from datetime import date
from unittest.mock import patch

from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol
from tests.aceptacion.ayudas import (
    CONCEPTO_CUOTA,
    CONCEPTO_INTERES,
    FECHA_CORTE,
    FECHA_CORTE_ANTERIOR,
    OraculoFalso,
    oraculo_corte_exitoso,
    sin_transaccion,
)

from cartera.views import ExtraccionViewSet

factory = APIRequestFactory()


def _extraer(datos, oraculo):
    """Ejecuta POST /api/extracciones/ como Analista de Cartera contra un Oracle simulado."""
    request = factory.post("/api/extracciones/", datos, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.servicios.connection", oraculo.conexion), \
         patch("cartera.servicios.transaction.atomic", sin_transaccion), \
         patch("cartera.servicios.registrar_bitacora"):
        return ExtraccionViewSet.as_view({"post": "create"})(request)


# ── CP-A-01 ───────────────────────────────────────────────────────────────────

def test_cp_a_01_extraccion_de_un_corte_vigente_queda_en_borrador():
    """El Analista inicia la extracción del corte y obtiene un corte en BORRADOR."""
    oraculo = oraculo_corte_exitoso(total_obligaciones=5, saldo=45_000_000)

    response = _extraer({"fecha_corte": str(FECHA_CORTE)}, oraculo)

    assert response.status_code == 201
    assert response.data["estado"] == "BORRADOR"
    assert response.data["obligaciones"] == 5
    assert response.data["saldo_consolidado"] == 45_000_000


# ── CP-A-03 ───────────────────────────────────────────────────────────────────

def test_cp_a_03_el_corte_se_restringe_a_los_conceptos_de_energia():
    """Postcondición de RF2: el corte solo considera los conceptos de energía activos."""
    oraculo = oraculo_corte_exitoso(conceptos=(CONCEPTO_CUOTA, CONCEPTO_INTERES))

    response = _extraer({"fecha_corte": str(FECHA_CORTE)}, oraculo)

    assert response.status_code == 201
    # El corte queda sellado con los conceptos reportables que estaban activos, leídos de la
    # tabla de parámetros y no de una lista escrita en el código: por eso cambiar la
    # parametrización cambia el resultado de la siguiente extracción (RF35).
    assert oraculo.conceptos_sellados_en_el_corte == f"{CONCEPTO_CUOTA},{CONCEPTO_INTERES}"
    assert "NV_CONCEPTO_REPORTABLE" in oraculo.sql_completo
    assert "REPORTABLE = 'S'" in oraculo.sql_completo


# ── CP-A-06 ───────────────────────────────────────────────────────────────────

def test_cp_a_06_un_corte_sin_deudores_vigentes_no_es_un_error():
    """Flujo alterno de RF1: universo vacío que se notifica, no una falla."""
    oraculo = oraculo_corte_exitoso(total_obligaciones=0, saldo=0)

    response = _extraer({"fecha_corte": str(FECHA_CORTE)}, oraculo)

    assert response.status_code == 201
    assert response.data["obligaciones"] == 0
    assert response.data["saldo_consolidado"] == 0


# ── CP-A-07 ───────────────────────────────────────────────────────────────────

def test_cp_a_07_una_fecha_de_corte_futura_se_rechaza_en_espanol():
    fecha_futura = date(date.today().year + 1, 1, 31)
    oraculo = oraculo_corte_exitoso()

    response = _extraer({"fecha_corte": str(fecha_futura)}, oraculo)

    assert response.status_code == 400
    assert "futura" in response.data["detail"].lower()


def test_cp_a_07_la_fecha_de_corte_es_obligatoria():
    """RF31 aplicado a la extracción: sin fecha de corte no se ejecuta el proceso."""
    oraculo = oraculo_corte_exitoso()

    response = _extraer({}, oraculo)

    assert response.status_code == 400
    assert "fecha_corte" in response.data


# ── CP-A-08 ───────────────────────────────────────────────────────────────────

def test_cp_a_08_un_grupo_inexistente_se_rechaza():
    oraculo = OraculoFalso(fetchone=[(None,), None])  # sin enviados; el grupo no existe

    response = _extraer({"fecha_corte": str(FECHA_CORTE), "grupo_id": 999}, oraculo)

    assert response.status_code == 404


def test_cp_a_08_un_grupo_inactivo_se_rechaza_distinguiendolo_del_inexistente():
    oraculo = OraculoFalso(
        fetchone=[(None,), ("Grupo de prueba inactivo", "N")],
        fetchall=[[(CONCEPTO_CUOTA,)]],
    )

    response = _extraer({"fecha_corte": str(FECHA_CORTE), "grupo_id": 3}, oraculo)

    assert response.status_code == 409
    assert "inactivo" in response.data["detail"].lower()


# ── CP-A-24 (CA-A4, se verifica aquí porque ocurre al extraer) ────────────────

def test_cp_a_24_no_se_extrae_un_corte_anterior_al_ultimo_enviado():
    """El corte debe ser posterior al último enviado a TransUnion."""
    oraculo = oraculo_corte_exitoso(ultimo_enviado=FECHA_CORTE)

    response = _extraer({"fecha_corte": str(FECHA_CORTE_ANTERIOR)}, oraculo)

    assert response.status_code == 409
    assert "posterior" in response.data["detail"].lower()
