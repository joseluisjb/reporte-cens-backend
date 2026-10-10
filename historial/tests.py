from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory

from historial import servicios
from historial.serializers import ReporteEnviadoSerializer, DeudorSerializer
from historial.views import ReporteViewSet, DeudorViewSet


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_conn(fetchall=None, fetchone=None):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    if fetchall is not None:
        mock_cursor.fetchall.return_value = fetchall
    if fetchone is not None:
        mock_cursor.fetchone.return_value = fetchone
    return mock_conn, mock_cursor


_FECHA_CORTE = date(2026, 9, 30)
_FECHA_ENVIO = date(2026, 10, 1)
_FECHA_GEN = datetime(2026, 10, 1, 10, 0, 0)

_REPORTE = {
    "id": 1,
    "fecha_corte": _FECHA_CORTE,
    "fecha_envio": _FECHA_ENVIO,
    "total_registros": 5,
    "saldo_consolidado": 1000000,
    "grupo": None,
    "observacion": None,
}

_DEUDOR = {
    "obligacion_id": 10,
    "numero_obligacion": "OBL001",
    "cliente_id": 900001,
    "numero_proceso": 1001,
    "fecha_inicio": _FECHA_CORTE,
    "ultimo_estado_tu": "01",
    "ultimo_valor_saldo": 500000,
}


def _usuario_analista():
    user = MagicMock()
    user.rol = "ANALISTA_CARTERA"
    return user


factory = APIRequestFactory()


# ── Serializers ───────────────────────────────────────────────────────────────

def test_reporte_serializer_representacion():
    data = ReporteEnviadoSerializer(_REPORTE).data
    assert data["id"] == 1
    assert data["fecha_corte"] == "2026-09-30"
    assert data["fecha_envio"] == "2026-10-01"
    assert data["grupo"] is None
    assert data["saldo_consolidado"] == 1000000


def test_reporte_serializer_con_grupo():
    reporte = {**_REPORTE, "grupo": "Grupo A"}
    data = ReporteEnviadoSerializer(reporte).data
    assert data["grupo"] == "Grupo A"


def test_deudor_serializer_representacion():
    data = DeudorSerializer(_DEUDOR).data
    assert data["obligacion_id"] == 10
    assert data["numero_obligacion"] == "OBL001"
    assert data["ultimo_estado_tu"] == "01"


# ── Servicios — listar_reportes_enviados ──────────────────────────────────────

def test_listar_reportes_sin_filtro():
    fila = (1, _FECHA_CORTE, _FECHA_ENVIO, 5, None, None, 1000000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila])
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.listar_reportes_enviados()
    assert len(result) == 1
    assert result[0]["id"] == 1
    sql_ejecutado = mock_cursor.execute.call_args[0][0]
    assert "ESTADO = 'ENVIADO'" in sql_ejecutado
    params = mock_cursor.execute.call_args[0][1]
    assert params == []


def test_listar_reportes_filtro_desde_hasta():
    mock_conn, mock_cursor = _mock_conn(fetchall=[])
    desde = date(2026, 9, 1)
    hasta = date(2026, 9, 30)
    with patch("historial.servicios.connection", mock_conn):
        servicios.listar_reportes_enviados(desde=desde, hasta=hasta)
    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "FECHA_ENVIO >= :1" in sql
    assert "FECHA_ENVIO <= :2" in sql
    assert params == [desde, hasta]


def test_listar_reportes_solo_filtro_desde():
    mock_conn, mock_cursor = _mock_conn(fetchall=[])
    desde = date(2026, 9, 1)
    with patch("historial.servicios.connection", mock_conn):
        servicios.listar_reportes_enviados(desde=desde)
    sql = mock_cursor.execute.call_args[0][0]
    assert "FECHA_ENVIO >= :1" in sql
    assert "FECHA_ENVIO <=" not in sql


# ── Servicios — listar_detalle_reporte ────────────────────────────────────────

def test_detalle_reporte_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (0,)
    with patch("historial.servicios.connection", mock_conn):
        with pytest.raises(servicios.ReporteNoEncontrado):
            servicios.listar_detalle_reporte(99)


def test_detalle_reporte_paginado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1,),    # COUNT CORTE EXISTS
        (3,),    # COUNT TOTAL
    ]
    fila = ("OBL001", "Juan", "12345", "CC", 2, "01", "00",
            _FECHA_CORTE, 0, 100000, 0, 500000, 50000, 0, "SIN_MORA", 1, None)
    mock_cursor.fetchall.return_value = [fila]
    with patch("historial.servicios.connection", mock_conn):
        resultado = servicios.listar_detalle_reporte(1, limite=10, desplazamiento=0)
    assert resultado["total"] == 3
    assert len(resultado["resultados"]) == 1
    assert resultado["resultados"][0]["numero_obligacion"] == "OBL001"


# ── Servicios — buscar_deudores ───────────────────────────────────────────────

def test_buscar_deudores_por_cliente_id():
    fila = (10, "OBL001", 900001, 1001, _FECHA_CORTE, "01", 500000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila])
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(cliente_id=900001)
    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "CLIENTE_ID = :1" in sql
    assert params == [900001]
    assert len(result) == 1


def test_buscar_deudores_por_numero_obligacion():
    fila = (10, "OBL001", 900001, 1001, _FECHA_CORTE, "01", 500000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila])
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(numero_obligacion="OBL001")
    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "NUMERO_OBLIGACION_TU = :1" in sql
    assert params == ["OBL001"]
    assert result[0]["numero_obligacion"] == "OBL001"


def test_buscar_deudores_sin_ultimo_estado():
    fila = (10, "OBL001", 900001, 1001, None, None, None)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila])
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(cliente_id=900001)
    assert result[0]["ultimo_estado_tu"] is None
    assert result[0]["ultimo_valor_saldo"] is None


# ── Servicios — linea_tiempo_deudor ──────────────────────────────────────────

def test_linea_tiempo_no_encontrada():
    mock_conn, mock_cursor = _mock_conn(fetchone=(0,))
    with patch("historial.servicios.connection", mock_conn):
        with pytest.raises(servicios.ObligacionNoEncontrada):
            servicios.linea_tiempo_deudor(99)


def test_linea_tiempo_devuelve_lista():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1,)   # COUNT
    fila1 = (_FECHA_CORTE, "01", "00", 0, 0, 0, 500000, "ENVIADO")
    fila2 = (date(2026, 10, 31), "06", "03", 30, 1, 50000, 450000, "ENVIADO")
    mock_cursor.fetchall.return_value = [fila1, fila2]
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.linea_tiempo_deudor(10)
    assert len(result) == 2
    assert result[0]["fecha_corte"] == _FECHA_CORTE
    assert result[1]["estado_tu"] == "06"
    sql = mock_cursor.execute.call_args[0][0]
    assert "ORDER BY c.FECHA_CORTE" in sql
    assert "ESTADO != 'ANULADO'" in sql


# ── Vistas — ReporteViewSet ────────────────────────────────────────────────────

def test_reportes_list_200():
    request = factory.get("/api/historial/reportes/")
    request.user = _usuario_analista()
    with patch("historial.views.servicios.listar_reportes_enviados", return_value=[_REPORTE]):
        response = ReporteViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data) == 1


def test_reportes_list_filtro_fecha_invalida():
    request = factory.get("/api/historial/reportes/", {"desde": "no-es-fecha"})
    request.user = _usuario_analista()
    response = ReporteViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_reportes_detalle_200():
    request = factory.get("/api/historial/reportes/1/detalle/")
    request.user = _usuario_analista()
    payload = {"total": 3, "resultados": []}
    with patch("historial.views.servicios.listar_detalle_reporte", return_value=payload):
        response = ReporteViewSet.as_view({"get": "detalle"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["total"] == 3


def test_reportes_detalle_404():
    request = factory.get("/api/historial/reportes/999/detalle/")
    request.user = _usuario_analista()
    with patch("historial.views.servicios.listar_detalle_reporte",
               side_effect=servicios.ReporteNoEncontrado):
        response = ReporteViewSet.as_view({"get": "detalle"})(request, pk="999")
    assert response.status_code == 404


# ── Vistas — DeudorViewSet ─────────────────────────────────────────────────────

def test_deudores_list_sin_params_400():
    request = factory.get("/api/historial/deudores/")
    request.user = _usuario_analista()
    response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_deudores_list_200():
    request = factory.get("/api/historial/deudores/", {"cliente_id": "900001"})
    request.user = _usuario_analista()
    with patch("historial.views.servicios.buscar_deudores", return_value=[_DEUDOR]):
        response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data) == 1


def test_deudores_list_cliente_id_no_entero_400():
    request = factory.get("/api/historial/deudores/", {"cliente_id": "abc"})
    request.user = _usuario_analista()
    response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_deudores_retrieve_200():
    request = factory.get("/api/historial/deudores/10/")
    request.user = _usuario_analista()
    linea = [
        {"fecha_corte": _FECHA_CORTE, "estado_tu": "01", "edad_mora": "00",
         "dias_mora": 0, "cuotas_mora": 0, "valor_mora": 0, "valor_saldo": 500000,
         "estado_corte": "ENVIADO"},
    ]
    with patch("historial.views.servicios.linea_tiempo_deudor", return_value=linea):
        response = DeudorViewSet.as_view({"get": "retrieve"})(request, pk="10")
    assert response.status_code == 200
    assert len(response.data) == 1


def test_deudores_retrieve_404():
    request = factory.get("/api/historial/deudores/999/")
    request.user = _usuario_analista()
    with patch("historial.views.servicios.linea_tiempo_deudor",
               side_effect=servicios.ObligacionNoEncontrada):
        response = DeudorViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404
