from contextlib import contextmanager
from datetime import date, datetime
from io import StringIO
from unittest.mock import call, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol, _mock_conn

from historial import servicios
from historial.serializers import ReporteEnviadoSerializer, DeudorSerializer
from historial.views import ReporteViewSet, DeudorViewSet


# ── Helpers ───────────────────────────────────────────────────────────────────


@contextmanager
def _noop_atomic():
    yield


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

_RESULTADO_MOCK = {
    "id": 7,
    "fecha_corte": _FECHA_CORTE,
    "estado": "BORRADOR",
    "obligaciones": 150,
    "saldo_consolidado": 45000000,
    "grupo": None,
}


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
    assert "FECHA_ENVIO >= %s" in sql
    assert "FECHA_ENVIO <= %s" in sql
    assert params == [desde, hasta]


def test_listar_reportes_solo_filtro_desde():
    mock_conn, mock_cursor = _mock_conn(fetchall=[])
    desde = date(2026, 9, 1)
    with patch("historial.servicios.connection", mock_conn):
        servicios.listar_reportes_enviados(desde=desde)
    sql = mock_cursor.execute.call_args[0][0]
    assert "FECHA_ENVIO >= %s" in sql
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
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila], fetchone=(1,))
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(cliente_id=900001)
    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "CLIENTE_ID = %s" in sql
    assert params == [900001, 0, 20]
    assert result["total"] == 1
    assert len(result["resultados"]) == 1


def test_buscar_deudores_por_numero_obligacion():
    fila = (10, "OBL001", 900001, 1001, _FECHA_CORTE, "01", 500000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila], fetchone=(1,))
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(numero_obligacion="OBL001")
    sql = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "NUMERO_OBLIGACION_TU = %s" in sql
    assert params == ["OBL001", 0, 20]
    assert result["resultados"][0]["numero_obligacion"] == "OBL001"


def test_buscar_deudores_sin_ultimo_estado():
    fila = (10, "OBL001", 900001, 1001, None, None, None)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila], fetchone=(0,))
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.buscar_deudores(cliente_id=900001)
    assert result["resultados"][0]["ultimo_estado_tu"] is None
    assert result["resultados"][0]["ultimo_valor_saldo"] is None


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
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("historial.views.servicios.listar_reportes_enviados", return_value=[_REPORTE]):
        response = ReporteViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data) == 1


def test_reportes_list_filtro_fecha_invalida():
    request = factory.get("/api/historial/reportes/", {"desde": "no-es-fecha"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ReporteViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_reportes_detalle_200():
    request = factory.get("/api/historial/reportes/1/detalle/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    payload = {"total": 3, "resultados": []}
    with patch("historial.views.servicios.listar_detalle_reporte", return_value=payload):
        response = ReporteViewSet.as_view({"get": "detalle"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["total"] == 3


def test_reportes_detalle_404():
    request = factory.get("/api/historial/reportes/999/detalle/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("historial.views.servicios.listar_detalle_reporte",
               side_effect=servicios.ReporteNoEncontrado):
        response = ReporteViewSet.as_view({"get": "detalle"})(request, pk="999")
    assert response.status_code == 404


# ── Vistas — DeudorViewSet ─────────────────────────────────────────────────────

def test_deudores_list_sin_params_400():
    request = factory.get("/api/historial/deudores/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_deudores_list_200():
    request = factory.get("/api/historial/deudores/", {"cliente_id": "900001"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("historial.views.servicios.buscar_deudores",
               return_value={"total": 1, "resultados": [_DEUDOR]}):
        response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data["total"] == 1
    assert len(response.data["resultados"]) == 1


def test_deudores_list_cliente_id_no_entero_400():
    request = factory.get("/api/historial/deudores/", {"cliente_id": "abc"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = DeudorViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400


def test_deudores_retrieve_200():
    request = factory.get("/api/historial/deudores/10/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
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
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("historial.views.servicios.linea_tiempo_deudor",
               side_effect=servicios.ObligacionNoEncontrada):
        response = DeudorViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404


def test_historial_sin_permiso_403():
    request = factory.get("/api/historial/reportes/")
    force_authenticate(request, user=usuario_con_rol("OTRO_ROL"))
    response = ReporteViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403


# ── Comando actualizar_estados_mensual ────────────────────────────────────────

_CMD = "historial.management.commands.actualizar_estados_mensual"


def test_comando_sin_argumentos():
    with patch(f"{_CMD}.generar_corte", return_value=_RESULTADO_MOCK) as mock_gc, \
         patch(f"{_CMD}.registrar_bitacora"), \
         patch(f"{_CMD}.transaction.atomic", _noop_atomic):
        out = StringIO()
        call_command("actualizar_estados_mensual", stdout=out)
    salida = out.getvalue()
    # Fecha esperada: último día del mes anterior a 2026-10-10 → 2026-09-30
    assert "2026-09-30" in salida
    assert "150" in salida
    assert "45000000" in salida
    assert "Corte 7 generado correctamente." in salida
    kwargs = mock_gc.call_args.kwargs
    assert kwargs["fecha_corte"] == date(2026, 9, 30)
    assert kwargs["grupo_id"] is None


def test_comando_con_fecha_y_grupo():
    resultado = {**_RESULTADO_MOCK, "grupo": {"id": 1, "nombre": "Grupo A"}}
    with patch(f"{_CMD}.generar_corte", return_value=resultado) as mock_gc, \
         patch(f"{_CMD}.registrar_bitacora"), \
         patch(f"{_CMD}.transaction.atomic", _noop_atomic):
        out = StringIO()
        call_command("actualizar_estados_mensual",
                     fecha_corte="2026-09-30", grupo_id=1, stdout=out)
    kwargs = mock_gc.call_args.kwargs
    assert kwargs["fecha_corte"] == date(2026, 9, 30)
    assert kwargs["grupo_id"] == 1


def test_comando_simular():
    with patch(f"{_CMD}.generar_corte", return_value=_RESULTADO_MOCK), \
         patch(f"{_CMD}.registrar_bitacora") as mock_reg, \
         patch(f"{_CMD}.transaction.atomic", _noop_atomic), \
         patch(f"{_CMD}.transaction.set_rollback") as mock_rollback:
        out = StringIO()
        call_command("actualizar_estados_mensual", simular=True, stdout=out)
    salida = out.getvalue()
    assert "SIMULACIÓN" in salida
    mock_rollback.assert_called_once_with(True)
    # La bitácora no debe haberse insertada en simulación
    mock_reg.assert_not_called()


def test_comando_fecha_invalida_formato():
    with patch(f"{_CMD}.generar_corte") as mock_gc:
        with pytest.raises(CommandError):
            call_command("actualizar_estados_mensual", fecha_corte="no-es-fecha")
    mock_gc.assert_not_called()


def test_comando_error_grupo_no_encontrado():
    from cartera.servicios import GrupoNoEncontrado
    with patch(f"{_CMD}.generar_corte", side_effect=GrupoNoEncontrado), \
         patch(f"{_CMD}.registrar_bitacora"), \
         patch(f"{_CMD}.transaction.atomic", _noop_atomic):
        with pytest.raises(CommandError):
            call_command("actualizar_estados_mensual", grupo_id=99)


# ── Corrección 1 — pk no numérico → 404 ──────────────────────────────────────

def test_detalle_pk_no_numerico_404():
    request = factory.get("/api/historial/reportes/abc/detalle/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ReporteViewSet.as_view({"get": "detalle"})(request, pk="abc")
    assert response.status_code == 404


def test_linea_tiempo_pk_no_numerico_404():
    request = factory.get("/api/historial/deudores/abc/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = DeudorViewSet.as_view({"get": "retrieve"})(request, pk="abc")
    assert response.status_code == 404


# ── Corrección 2 — NULL safety en valor_mora / valor_saldo ───────────────────

def test_listar_detalle_reporte_valor_none():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [(1,), (1,)]
    fila = ("OBL001", "Juan", "12345", "01", 2, "01", "00",
            _FECHA_CORTE, 0, 100000, None, None, 50000, 0, "SIN_MORA", 1, None)
    mock_cursor.fetchall.return_value = [fila]
    with patch("historial.servicios.connection", mock_conn):
        resultado = servicios.listar_detalle_reporte(1)
    fila_res = resultado["resultados"][0]
    assert fila_res["valor_mora"] is None
    assert fila_res["valor_saldo"] is None


def test_linea_tiempo_valor_none():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1,)
    fila = (_FECHA_CORTE, "01", "00", 0, 0, None, None, "ENVIADO")
    mock_cursor.fetchall.return_value = [fila]
    with patch("historial.servicios.connection", mock_conn):
        result = servicios.linea_tiempo_deudor(10)
    assert result[0]["valor_mora"] is None
    assert result[0]["valor_saldo"] is None


# ── Corrección 4 — buscar_deudores paginado ───────────────────────────────────

def test_buscar_deudores_filtra_estado_anulado():
    fila = (10, "OBL001", 900001, 1001, _FECHA_CORTE, "01", 500000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila], fetchone=(1,))
    with patch("historial.servicios.connection", mock_conn):
        servicios.buscar_deudores(cliente_id=900001)
    calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
    assert any("ESTADO != 'ANULADO'" in sql for sql in calls)


def test_buscar_deudores_tiene_order_by():
    fila = (10, "OBL001", 900001, 1001, _FECHA_CORTE, "01", 500000)
    mock_conn, mock_cursor = _mock_conn(fetchall=[fila], fetchone=(1,))
    with patch("historial.servicios.connection", mock_conn):
        servicios.buscar_deudores(cliente_id=900001)
    select_sql = mock_cursor.execute.call_args[0][0]
    assert "ORDER BY o.OBLIGACION_ID" in select_sql


# ── C2 — Enmascaramiento de numero_identificacion ────────────────────────────

def test_listar_detalle_reporte_enmascara_identificacion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [(1,), (1,)]
    fila = ("OBL001", "Juan", "12345678", "01", 2, "01", "00",
            _FECHA_CORTE, 0, 100000, 0, 500000, 50000, 0, "SIN_MORA", 1, None)
    mock_cursor.fetchall.return_value = [fila]
    with patch("historial.servicios.connection", mock_conn):
        resultado = servicios.listar_detalle_reporte(1)
    assert resultado["resultados"][0]["numero_identificacion"] == "******5678"
