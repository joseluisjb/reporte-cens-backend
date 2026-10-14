"""HU-A · CA-A6 — "Se puede agregar, editar y desactivar códigos desde la configuración" (RF35).

El criterio no se agota en que la pantalla responda: lo que el cliente valida es que los códigos
se puedan cambiar **sin modificar la lógica del sistema**, y que la extracción siguiente respete
el cambio. Por eso aquí se comprueba, además del CRUD, quién tiene permiso de tocarlos (RF27).

Casos de la matriz: docs/pruebas/matriz-HU-A.md
"""

from unittest.mock import patch

from django.db import IntegrityError
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol
from tests.aceptacion.ayudas import CONCEPTO_CUOTA, OraculoFalso

from parametros.views import ConceptoViewSet

factory = APIRequestFactory()

CODIGO_FICTICIO = 9100
DESCRIPCION_FICTICIA = "CONCEPTO FICTICIO"


def _fila(codigo, descripcion, reportable):
    """Fila de NV_CONCEPTO_REPORTABLE: código, descripción, reportable, observación."""
    return (codigo, descripcion, reportable, None)


def _pedir(vista, metodo, ruta, datos=None, oraculo=None, rol="ADMINISTRADOR", pk=None):
    request = getattr(factory, metodo)(ruta, datos or {}, format="json")
    force_authenticate(request, user=usuario_con_rol(rol))
    with patch("parametros.servicios.connection", oraculo.conexion):
        return vista(request, pk=pk) if pk is not None else vista(request)


# ── CP-A-31 · agregar ─────────────────────────────────────────────────────────

def test_cp_a_31_el_administrador_agrega_un_concepto_de_energia():
    oraculo = OraculoFalso(
        fetchone=[_fila(CODIGO_FICTICIO, DESCRIPCION_FICTICIA, "S")],
    )

    response = _pedir(
        ConceptoViewSet.as_view({"post": "create"}), "post", "/api/conceptos/",
        {"codigo": CODIGO_FICTICIO, "descripcion": DESCRIPCION_FICTICIA,
         "activo": True},
        oraculo,
    )

    assert response.status_code == 201
    assert response.data["codigo"] == CODIGO_FICTICIO
    assert response.data["activo"] is True


# ── CP-A-32 · editar ──────────────────────────────────────────────────────────

def test_cp_a_32_el_administrador_edita_la_descripcion_de_un_concepto():
    oraculo = OraculoFalso(
        fetchone=[_fila(CODIGO_FICTICIO, "DESCRIPCION CORREGIDA", "S")],
    )

    response = _pedir(
        ConceptoViewSet.as_view({"patch": "partial_update"}), "patch",
        f"/api/conceptos/{CODIGO_FICTICIO}/", {"descripcion": "DESCRIPCION CORREGIDA"},
        oraculo, pk=str(CODIGO_FICTICIO),
    )

    assert response.status_code == 200
    assert response.data["descripcion"] == "DESCRIPCION CORREGIDA"


# ── CP-A-33 · desactivar ──────────────────────────────────────────────────────

def test_cp_a_33_el_administrador_desactiva_un_concepto():
    """Desactivar es marcarlo como no reportable: deja de entrar en la siguiente extracción."""
    oraculo = OraculoFalso(
        fetchone=[_fila(CODIGO_FICTICIO, DESCRIPCION_FICTICIA, "N")],
    )

    response = _pedir(
        ConceptoViewSet.as_view({"patch": "partial_update"}), "patch",
        f"/api/conceptos/{CODIGO_FICTICIO}/", {"activo": False},
        oraculo, pk=str(CODIGO_FICTICIO),
    )

    assert response.status_code == 200
    assert response.data["activo"] is False
    assert "REPORTABLE = %s" in oraculo.sql_completo


# ── CP-A-34 · el listado de la extracción solo trae los activos ───────────────

def test_cp_a_34_solo_los_conceptos_activos_quedan_disponibles_para_el_corte():
    """La consulta que alimenta la extracción filtra por REPORTABLE, no por una lista fija."""
    oraculo = OraculoFalso(
        fetchall=[[_fila(CONCEPTO_CUOTA, "CUOTA FINANCIACION ENERGIA", "S")]],
    )

    response = _pedir(
        ConceptoViewSet.as_view({"get": "list"}), "get", "/api/conceptos/?activo=true",
        None, oraculo, rol="ANALISTA_CARTERA",
    )

    assert response.status_code == 200
    assert [c["codigo"] for c in response.data] == [CONCEPTO_CUOTA]
    assert "REPORTABLE" in oraculo.sql_completo


# ── CP-A-35 · código duplicado ────────────────────────────────────────────────

def test_cp_a_35_un_codigo_de_concepto_duplicado_se_rechaza():
    oraculo = OraculoFalso()
    oraculo.cursor.execute.side_effect = IntegrityError("ORA-00001: unique constraint")

    response = _pedir(
        ConceptoViewSet.as_view({"post": "create"}), "post", "/api/conceptos/",
        {"codigo": CONCEPTO_CUOTA, "descripcion": "DUPLICADO", "activo": True},
        oraculo,
    )

    assert response.status_code == 409
    assert "ya existe" in response.data["detail"].lower()


# ── CP-A-36 · campos obligatorios (RF31) ─────────────────────────────────────

def test_cp_a_36_no_se_crea_un_concepto_sin_descripcion():
    oraculo = OraculoFalso()

    response = _pedir(
        ConceptoViewSet.as_view({"post": "create"}), "post", "/api/conceptos/",
        {"codigo": CODIGO_FICTICIO, "activo": True},
        oraculo,
    )

    assert response.status_code == 400
    assert "descripcion" in response.data


# ── CP-A-37 · la parametrización es solo del Administrador (RF27) ────────────

def test_cp_a_37_un_analista_no_puede_crear_conceptos():
    oraculo = OraculoFalso()

    response = _pedir(
        ConceptoViewSet.as_view({"post": "create"}), "post", "/api/conceptos/",
        {"codigo": CODIGO_FICTICIO, "descripcion": DESCRIPCION_FICTICIA,
         "activo": True},
        oraculo, rol="ANALISTA_CARTERA",
    )

    assert response.status_code == 403


def test_cp_a_37_un_analista_no_puede_desactivar_conceptos():
    oraculo = OraculoFalso()

    response = _pedir(
        ConceptoViewSet.as_view({"patch": "partial_update"}), "patch",
        f"/api/conceptos/{CODIGO_FICTICIO}/", {"activo": False},
        oraculo, rol="ANALISTA_CARTERA", pk=str(CODIGO_FICTICIO),
    )

    assert response.status_code == 403


def test_cp_a_37_un_analista_si_puede_consultar_los_conceptos():
    """Lectura para ambos roles: el Analista necesita verlos para elegir al extraer."""
    oraculo = OraculoFalso(
        fetchall=[[_fila(CONCEPTO_CUOTA, "CUOTA FINANCIACION ENERGIA", "S")]],
    )

    response = _pedir(
        ConceptoViewSet.as_view({"get": "list"}), "get", "/api/conceptos/",
        None, oraculo, rol="ANALISTA_CARTERA",
    )

    assert response.status_code == 200
