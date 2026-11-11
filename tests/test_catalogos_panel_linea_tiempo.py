"""GET /catalogos/{nombre}/, /panel/resumen/ y /obligaciones/{id}/linea-tiempo/ (contrato 0.9). Datos ficticios."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from ciclo.views import ObligacionesViewSet, PanelView
from parametros import servicios
from parametros.views import CatalogoView
from tests.ayudas import usuario_con_rol

factory = APIRequestFactory()


def _get(vista, ruta, rol, **kwargs):
    request = factory.get(ruta)
    force_authenticate(request, user=usuario_con_rol(rol))
    return vista(request, **kwargs)


# ── Catálogos ────────────────────────────────────────────────────────────────

def test_modos_de_extincion_son_los_13_de_la_tabla_10_del_manual():
    modos = servicios.listar_catalogo("modos-extincion")
    assert [m["codigo"] for m in modos] == [
        "01", "02", "03", "04", "05", "07", "11", "12", "13", "14", "15", "16", "17",
    ]
    assert {"codigo": "16", "descripcion": "Refinanciación", "confirmado": True} in modos
    assert all(m["confirmado"] for m in modos)


def test_tipos_de_pago_son_los_de_la_tabla_15_del_manual():
    assert servicios.listar_catalogo("tipos-pago") == [
        {"codigo": "01", "descripcion": "Voluntario", "confirmado": True},
        {"codigo": "02", "descripcion": "No voluntario", "confirmado": True},
    ]


def test_catalogo_de_la_base_traduce_confirmado():
    cursor = MagicMock()
    cursor.fetchall.return_value = [("01", "Ley 550", "S"), ("05", "Extraordinaria", "N")]
    conexion = MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    with patch("parametros.servicios.connection", conexion):
        items = servicios.listar_catalogo("naturalezas-reestructuracion")
    assert items == [
        {"codigo": "01", "descripcion": "Ley 550", "confirmado": True},
        {"codigo": "05", "descripcion": "Extraordinaria", "confirmado": False},
    ]
    assert "NV_NATURALEZA_REESTR" in cursor.execute.call_args[0][0]


@pytest.mark.parametrize("rol", ["ANALISTA_CARTERA", "ADMINISTRADOR"])
def test_catalogo_para_los_dos_roles(rol):
    respuesta = _get(CatalogoView.as_view(), "/api/catalogos/tipos-pago/", rol, nombre="tipos-pago")
    assert respuesta.status_code == 200
    assert len(respuesta.data) == 2


def test_catalogo_desconocido_404():
    respuesta = _get(CatalogoView.as_view(), "/api/catalogos/x/", "ANALISTA_CARTERA", nombre="x")
    assert respuesta.status_code == 404
    assert respuesta.data == {"detail": "Catálogo no encontrado."}


# ── Panel ────────────────────────────────────────────────────────────────────

def test_panel_solo_analista():
    resumen = {
        "fecha_ultimo_ciclo": "2026-10-31", "total_obligaciones": 3,
        "distribucion": [{"estado_tu": "01", "cantidad": 3}], "ultimo_archivo": None,
        "en_reclamo": 0, "novedades_pendientes": 1, "con_dos_o_mas_cuotas": 1,
        "entidad_con_marcador": True,
    }
    with patch("ciclo.views.servicios.obtener_panel_resumen", return_value=resumen):
        assert _get(PanelView.as_view(), "/api/panel/resumen/", "ANALISTA_CARTERA").data == resumen
        assert _get(PanelView.as_view(), "/api/panel/resumen/", "ADMINISTRADOR").status_code == 403


# ── Línea de tiempo ──────────────────────────────────────────────────────────

_ESTADOS = [
    {"codigo": "01", "nombre": "Vigente"},
    {"codigo": "04", "nombre": "Suspendida por la entidad"},
    {"codigo": "12", "nombre": "Ley 1564 de 2012 insolvencia PNNC"},
]


def test_linea_tiempo_usa_los_nombres_de_la_tabla_4b():
    eventos = [
        {"fecha_corte": date(2026, 8, 31), "estado_tu": "01", "edad_mora": None, "dias_mora": 0, "cuotas_mora": 0},
        {"fecha_corte": date(2026, 9, 30), "estado_tu": "04", "edad_mora": "02", "dias_mora": 47, "cuotas_mora": 2},
        {"fecha_corte": date(2026, 10, 31), "estado_tu": "12", "edad_mora": "02", "dias_mora": 0, "cuotas_mora": 0},
    ]
    with patch("historial.servicios.linea_tiempo_deudor", return_value=eventos), \
         patch("parametros.servicios.listar_estados_tu", return_value=_ESTADOS):
        vista = ObligacionesViewSet.as_view({"get": "linea_tiempo"})
        respuesta = _get(vista, "/api/obligaciones/5/linea-tiempo/", "ANALISTA_CARTERA", pk="5")
    assert respuesta.status_code == 200
    assert respuesta.data == [
        {"fecha": "2026-08-31", "estado_tu": "01", "edad_mora": "00", "descripcion": "Vigente"},
        {"fecha": "2026-09-30", "estado_tu": "04", "edad_mora": "02",
         "descripcion": "Suspendida por la entidad · 47 días en mora, 2 cuotas"},
        {"fecha": "2026-10-31", "estado_tu": "12", "edad_mora": "02",
         "descripcion": "Ley 1564 de 2012 insolvencia PNNC"},
    ]


def test_linea_tiempo_solo_analista():
    vista = ObligacionesViewSet.as_view({"get": "linea_tiempo"})
    assert _get(vista, "/api/obligaciones/5/linea-tiempo/", "ADMINISTRADOR", pk="5").status_code == 403
