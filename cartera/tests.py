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


# ── Servicios — validar_corte ─────────────────────────────────────────────────

def test_validar_corte_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.validar_corte(99)


def test_validar_corte_no_es_borrador():
    mock_conn, mock_cursor = _mock_conn(fetchone=("VALIDADO",))
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEsBorrador):
            servicios.validar_corte(1)


def test_validar_corte_con_correctivas_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("BORRADOR",)
    mock_cursor.fetchall.return_value = [
        ("SIN_IDENTIFICACION", "CORRECTIVA", "Falta el tipo o el número de identificación"),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteConErroresCorrectivos) as exc_info:
            servicios.validar_corte(1)
    assert len(exc_info.value.errores) == 1
    assert exc_info.value.errores[0]["regla"] == "SIN_IDENTIFICACION"


def test_validar_corte_sin_errores_actualiza_estado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),   # SELECT ESTADO
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0),  # obtener_corte
    ]
    mock_cursor.fetchall.return_value = []   # V_VALIDACION_CORTE → sin errores
    with patch("cartera.servicios.connection", mock_conn):
        servicios.validar_corte(1)
    sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
    assert any("ESTADO = 'VALIDADO'" in s for s in sqls)


def test_validar_corte_devuelve_advertencias():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0),
    ]
    mock_cursor.fetchall.return_value = [
        ("SIN_FECHA_LIMITE_PAGO", "INFORMATIVA", "No se encontró una factura"),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        resultado = servicios.validar_corte(1)
    assert len(resultado["advertencias"]) == 1
    assert resultado["advertencias"][0]["regla"] == "SIN_FECHA_LIMITE_PAGO"


# ── Servicios — registrar_envio ───────────────────────────────────────────────

def test_registrar_envio_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.registrar_envio(99)


def test_registrar_envio_no_es_validado():
    mock_conn, mock_cursor = _mock_conn(fetchone=("BORRADOR",))
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEsValidado):
            servicios.registrar_envio(1)


def test_registrar_envio_fecha_futura():
    from datetime import timedelta
    mock_conn, mock_cursor = _mock_conn()
    fecha_futura = date.today() + timedelta(days=1)
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.FechaInvalida):
            servicios.registrar_envio(1, fecha_envio=fecha_futura)


def test_registrar_envio_usa_hoy_sin_fecha():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("VALIDADO",),
        (1, "2026-09-30", "ENVIADO", None, 5, None, None, 0),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        servicios.registrar_envio(1)
    sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
    assert any("ESTADO = 'ENVIADO'" in s for s in sqls)


# ── Vistas — ciclo mínimo ─────────────────────────────────────────────────────

def test_post_validar_200_sin_errores():
    request = factory.post("/api/extracciones/1/validar/")
    request.user = _usuario_analista()
    corte_mock = {**_RESUMEN, "estado": "VALIDADO"}
    resultado = {"corte": corte_mock, "advertencias": []}
    with patch("cartera.views.servicios.validar_corte", return_value=resultado):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["estado"] == "VALIDADO"
    assert response.data["advertencias"] == []


def test_post_validar_409_correctivas():
    request = factory.post("/api/extracciones/1/validar/")
    request.user = _usuario_analista()
    errores = [{"regla": "SIN_IDENTIFICACION", "mensaje": "Falta identificación"}]
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteConErroresCorrectivos(errores)):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 409
    assert "errores" in response.data


def test_post_validar_404():
    request = factory.post("/api/extracciones/999/validar/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="999")
    assert response.status_code == 404


def test_post_validar_409_no_borrador():
    request = factory.post("/api/extracciones/1/validar/")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteNoEsBorrador):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 409


def test_post_registrar_envio_200():
    request = factory.post("/api/extracciones/1/registrar-envio/", {}, format="json")
    request.user = _usuario_analista()
    corte_mock = {**_RESUMEN, "estado": "ENVIADO"}
    with patch("cartera.views.servicios.registrar_envio", return_value=corte_mock):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["estado"] == "ENVIADO"


def test_post_registrar_envio_404():
    request = factory.post("/api/extracciones/999/registrar-envio/", {}, format="json")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="999")
    assert response.status_code == 404


def test_post_registrar_envio_409_no_validado():
    request = factory.post("/api/extracciones/1/registrar-envio/", {}, format="json")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.CorteNoEsValidado):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 409


def test_post_registrar_envio_400_fecha_futura():
    request = factory.post("/api/extracciones/1/registrar-envio/",
                           {"fecha_envio": "2099-01-01"}, format="json")
    request.user = _usuario_analista()
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.FechaInvalida("fecha futura")):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 400
