from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory

from cartera import servicios
from cartera.serializers import GenerarCorteSerializer, CorteResumenSerializer
from cartera.views import ExtraccionViewSet


# ── Helpers de test ───────────────────────────────────────────────────────────

@contextmanager
def _noop_atomic():
    yield


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


_FECHA_PASADA = date(2026, 9, 30)
_FECHA_FUTURA = date(date.today().year + 1, 1, 1)
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


def _usuario_analista():
    user = MagicMock()
    user.rol = "ANALISTA_CARTERA"
    return user


# ── Serializer GenerarCorteSerializer ─────────────────────────────────────────

def test_serializer_fecha_corte_obligatoria():
    s = GenerarCorteSerializer(data={})
    assert not s.is_valid()
    assert "fecha_corte" in s.errors


def test_serializer_grupo_id_opcional():
    s = GenerarCorteSerializer(data={"fecha_corte": "2026-09-30"})
    assert s.is_valid(), s.errors
    assert "grupo_id" not in s.validated_data


def test_serializer_grupo_id_incluido():
    s = GenerarCorteSerializer(data={"fecha_corte": "2026-09-30", "grupo_id": 3})
    assert s.is_valid(), s.errors
    assert s.validated_data["grupo_id"] == 3


# ── Serializer CorteResumenSerializer ─────────────────────────────────────────

def test_resumen_serializer_sin_grupo():
    data = CorteResumenSerializer(_RESUMEN).data
    assert data["id"] == 1
    assert data["grupo"] is None
    assert data["estado"] == "BORRADOR"
    assert data["ejecutada_por"] is None
    assert data["saldo_consolidado"] == 1000000


def test_resumen_serializer_con_grupo():
    resumen = {**_RESUMEN, "grupo": {"id": 2, "nombre": "Grupo A"}}
    data = CorteResumenSerializer(resumen).data
    assert data["grupo"]["id"] == 2
    assert data["grupo"]["nombre"] == "Grupo A"


# ── Servicios — validaciones ──────────────────────────────────────────────────

def test_fecha_futura_lanza_excepcion():
    with patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.FechaInvalida):
            servicios.generar_corte(fecha_corte=_FECHA_FUTURA)


def test_grupo_inexistente_lanza_grupo_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoNoEncontrado):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=99)


def test_grupo_inactivo_lanza_grupo_inactivo():
    mock_conn, mock_cursor = _mock_conn(fetchone=("Grupo X", "N"))
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoInactivo):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=5)


def test_corte_misma_fecha_estado_fijo_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("Grupo A", "S"),    # _validar_grupo — nombre y activo
        (7, "VALIDADO"),     # _verificar_corte_existente — corte con esa fecha
    ]
    mock_cursor.fetchall.return_value = [(30,)]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.CorteEnEstadoFijo):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=1)


def test_borrador_otra_fecha_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    otra_fecha = date(2026, 8, 31)
    mock_cursor.fetchone.side_effect = [
        None,                        # _verificar_corte_existente — sin corte esa fecha
        (3, otra_fecha),             # _verificar_corte_existente — borrador de otra fecha
    ]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios._todos_los_conceptos_reportables", return_value="30,61"):
        with pytest.raises(servicios.BorradorOtraFecha) as exc_info:
            servicios.generar_corte(fecha_corte=_FECHA_PASADA)
    assert exc_info.value.fecha == otra_fecha


# ── Servicios — orden de operaciones ─────────────────────────────────────────

def test_corte_insertado_antes_de_vistas():
    """INSERT/UPDATE de NV_CORTE ocurre antes que SELECT de V_CALCULO_CORTE."""
    sqls_ejecutados = []

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False

    mock_cursor.fetchone.side_effect = [
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador otra fecha
        (1,),               # _persistir_corte — NEXTVAL (INSERT no llama fetchone)
        (5, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL, FECHA_GENERACION
        (500000,),          # _finalizar_y_resumir — SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,)],     # _todos_los_conceptos_reportables
        [],                 # _insertar_obligaciones_nuevas — sin nuevas
    ]

    def capture_execute(sql, params=None):
        sqls_ejecutados.append(sql)

    mock_cursor.execute.side_effect = capture_execute

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    idx_insert_corte = next(
        i for i, s in enumerate(sqls_ejecutados) if "NV_CORTE" in s and "INSERT" in s
    )
    idx_select_vista = next(
        (i for i, s in enumerate(sqls_ejecutados) if "V_CALCULO_CORTE" in s),
        len(sqls_ejecutados),
    )
    assert idx_insert_corte < idx_select_vista, (
        "El INSERT en NV_CORTE debe ocurrir antes de leer V_CALCULO_CORTE"
    )


# ── Servicios — reemplazo de borrador ────────────────────────────────────────

def test_reemplaza_borrador_misma_fecha():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (3, "BORRADOR"),    # _verificar_corte_existente — borrador existente
        (5, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL, FECHA_GENERACION
        (0,),               # _finalizar_y_resumir — SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,)],            # _todos_los_conceptos_reportables
        [],                 # _insertar_obligaciones_nuevas
    ]

    sqls = []
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append(sql)

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    assert any("DELETE" in s and "NV_REPORTE_DETALLE" in s for s in sqls)
    assert any("DELETE" in s and "NV_INCONSISTENCIA" in s for s in sqls)
    assert any("UPDATE" in s and "NV_CORTE" in s for s in sqls)
    assert not any("SEQ_NV_CORTE" in s for s in sqls)


# ── Servicios — conceptos sin grupo ──────────────────────────────────────────

def test_sin_grupo_conceptos_usados_son_todos_reportables():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # _persistir_corte — NEXTVAL (INSERT no llama fetchone)
        (0, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL
        (0,),               # _finalizar_y_resumir — SUM
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,), (90,)],  # _todos_los_conceptos_reportables
        [],                     # _insertar_obligaciones_nuevas
    ]

    inserts = []
    mock_cursor.execute.side_effect = lambda sql, params=None: inserts.append((sql, params))

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    insert_corte_params = next(
        params for sql, params in inserts
        if params and "INSERT" in sql and "NV_CORTE" in sql
    )
    conceptos_usados = insert_corte_params[4]
    assert conceptos_usados == "30,61,90"
    assert insert_corte_params[2] is None   # grupo_id nulo
    assert insert_corte_params[3] is None   # grupo_nombre nulo


# ── Servicios — resumen ───────────────────────────────────────────────────────

def test_resumen_estructura_correcta():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        None, None,         # _verificar_corte_existente
        (1,),               # NEXTVAL (INSERT no llama fetchone)
        (3, _FECHA_GEN),    # TOTAL + FECHA_GEN
        (750000,),          # SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [[(30,)], []]

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    assert set(resumen.keys()) == {
        "id", "fecha_corte", "fecha_ejecucion", "grupo",
        "obligaciones", "saldo_consolidado", "estado", "ejecutada_por",
    }
    assert resumen["estado"] == "BORRADOR"
    assert resumen["ejecutada_por"] is None
    assert resumen["grupo"] is None
    assert resumen["saldo_consolidado"] == 750000


def test_resumen_grupo_presente_cuando_se_usa_grupo():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("Grupo A", "S"),   # _validar_grupo — nombre, activo
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # NEXTVAL (INSERT no llama fetchone)
        (2, _FECHA_GEN),    # TOTAL + FECHA_GEN
        (200000,),          # SUM
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,)],     # _validar_grupo — conceptos
        [],                 # _insertar_obligaciones_nuevas
    ]

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=2)

    assert resumen["grupo"] == {"id": 2, "nombre": "Grupo A"}


# ── Vistas ────────────────────────────────────────────────────────────────────

factory = APIRequestFactory()


def test_post_201_genera_corte():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 201
    assert response.data["estado"] == "BORRADOR"


def test_post_400_fecha_futura():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": str(_FECHA_FUTURA)},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.FechaInvalida("La fecha de corte no puede ser futura.")):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert "futura" in response.data["detail"]


def test_post_404_grupo_inexistente():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30", "grupo_id": 99},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.GrupoNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 404


def test_post_409_grupo_inactivo():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30", "grupo_id": 5},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.GrupoInactivo):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_post_409_borrador_otra_fecha():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.BorradorOtraFecha(date(2026, 8, 31))):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409
    assert "BORRADOR" in response.data["detail"]


def test_post_409_estado_fijo():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.CorteEnEstadoFijo):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_get_list_200():
    request = factory.get("/api/extracciones/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.listar_cortes", return_value=[_RESUMEN]):
        response = ExtraccionViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data) == 1


def test_get_ultima_200():
    request = factory.get("/api/extracciones/ultima/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.obtener_ultimo_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"get": "ultima"})(request)
    assert response.status_code == 200
    assert response.data["id"] == 1


def test_get_ultima_204_sin_cortes():
    request = factory.get("/api/extracciones/ultima/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.obtener_ultimo_corte", return_value=None):
        response = ExtraccionViewSet.as_view({"get": "ultima"})(request)
    assert response.status_code == 204


def test_get_id_200():
    request = factory.get("/api/extracciones/1/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.obtener_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"get": "retrieve"})(request, pk="1")
    assert response.status_code == 200


def test_get_id_404():
    request = factory.get("/api/extracciones/999/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.obtener_corte", return_value=None):
        response = ExtraccionViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404


def test_get_obligaciones_200():
    request = factory.get(
        "/api/extracciones/1/obligaciones/",
        {"limite": "10", "desplazamiento": "0"},
    )
    request.user = _usuario_analista()
    payload = {
        "total": 2,
        "resultados": [
            {
                "numero_obligacion": "OBL001",
                "nombre_titular": "Juan",
                "numero_identificacion": "12345",
                "estado_tu": "01",
                "edad_mora": "00",
                "dias_mora": 0,
                "cuotas_mora": 0,
                "valor_mora": 0,
                "valor_saldo": 500000,
                "n_creditos": 1,
            }
        ],
    }
    with patch("cartera.views.servicios.listar_obligaciones", return_value=payload):
        response = ExtraccionViewSet.as_view({"get": "obligaciones"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["total"] == 2


def test_get_obligaciones_404():
    request = factory.get("/api/extracciones/999/obligaciones/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.listar_obligaciones",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"get": "obligaciones"})(request, pk="999")
    assert response.status_code == 404
