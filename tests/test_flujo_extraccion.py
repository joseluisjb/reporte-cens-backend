from datetime import date, datetime
from unittest.mock import patch

from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol

from cartera.views import ExtraccionViewSet


_FECHA_PASADA = date(2026, 9, 30)
_FECHA_GEN = datetime(2026, 10, 10, 12, 0, 0)
_RESUMEN = {
    "id": 1,
    "fecha_corte": _FECHA_PASADA,
    "fecha_ejecucion": _FECHA_GEN,
    "grupo": None,
    "obligaciones": 5,
    "saldo_consolidado": 1000000,
    "estado": "BORRADOR",
    "ejecutada_por": None,
}
_OBLIGACION = {
    "numero_obligacion": "OBL001",
    "nombre_titular": "Juan Pérez",
    "numero_identificacion": "12345678",
    "estado_tu": "01",
    "edad_mora": "00",
    "dias_mora": 0,
    "cuotas_mora": 0,
    "valor_mora": 0,
    "valor_saldo": 500000,
    "n_creditos": 1,
}


factory = APIRequestFactory()


def test_flujo_extraccion_sin_grupo():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte", return_value=_RESUMEN):
        r1 = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert r1.status_code == 201
    assert r1.data["estado"] == "BORRADOR"
    corte_id = r1.data["id"]

    request2 = factory.get(f"/api/extracciones/{corte_id}/")
    force_authenticate(request2, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_corte", return_value=_RESUMEN):
        r2 = ExtraccionViewSet.as_view({"get": "retrieve"})(request2, pk=str(corte_id))
    assert r2.status_code == 200
    assert r2.data["id"] == corte_id

    request3 = factory.get("/api/extracciones/ultima/")
    force_authenticate(request3, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_ultimo_corte", return_value=_RESUMEN):
        r3 = ExtraccionViewSet.as_view({"get": "ultima"})(request3)
    assert r3.status_code == 200
    assert r3.data["id"] == corte_id

    payload_obs = {"total": 1, "resultados": [_OBLIGACION]}
    request4 = factory.get(f"/api/extracciones/{corte_id}/obligaciones/")
    force_authenticate(request4, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.listar_obligaciones", return_value=payload_obs):
        r4 = ExtraccionViewSet.as_view({"get": "obligaciones"})(request4, pk=str(corte_id))
    assert r4.status_code == 200
    assert r4.data["total"] == 1
    assert r4.data["resultados"][0]["numero_obligacion"] == "OBL001"


def test_flujo_extraccion_con_grupo():
    resumen_con_grupo = {**_RESUMEN, "grupo": {"id": 1, "nombre": "Grupo A"}}
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30", "grupo_id": 1},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte", return_value=resumen_con_grupo):
        r = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert r.status_code == 201
    assert r.data["grupo"]["id"] == 1
    assert r.data["grupo"]["nombre"] == "Grupo A"
