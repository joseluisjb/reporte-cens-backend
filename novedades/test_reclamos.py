from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from novedades import reclamos
from novedades.reclamos_views import ReclamosViewSet
from tests.ayudas import usuario_con_rol


@contextmanager
def _noop_atomic():
    yield


@contextmanager
def _noop_tolerar(_accion):
    yield


def _mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cursor


_RECLAMO = {
    "id": 1,
    "obligacion_id": 4,
    "numero_obligacion": "2260-5543",
    "nombre_titular": "Diana Patricia Niño",
    "tipologia": {"codigo": "01", "descripcion": "PAGO NO REFLEJADO", "confirmado": True},
    "fecha_radicacion": "2026-09-22",
    "observacion": "Pago realizado.",
    "estado": "EN_RECLAMO",
    "radicado_en_tu": False,
    "fecha_limite_respuesta": "2026-10-14",
    "vencido": False,
    "resultado": None,
    "fecha_cierre": None,
    "observacion_cierre": None,
    "registrado_por": "Analista",
    "fecha_registro": "2026-09-22T09:15:00-05:00",
}

_FILA_RECLAMO = (
    1, 4, "2260-5543", "Diana Patricia Niño", "01", "PAGO NO REFLEJADO", "S",
    date(2026, 9, 22), "Pago realizado.", "EN_RECLAMO", "N",
    date(2026, 10, 14), None, None, None, "Analista",
    datetime(2026, 9, 22, 9, 15),
)


def test_fecha_limite_cuenta_quince_dias_habiles_y_festivos_colombianos():
    assert reclamos.calcular_fecha_limite_respuesta(date(2026, 9, 22)) == date(2026, 10, 14)


def test_crear_reclamo_guarda_plazo_y_no_excluye_obligacion():
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        ("2260-5543",),  # obligación
        (1,),            # tipología
        None,            # sin reclamo abierto
        (17,),           # secuencia
        _FILA_RECLAMO,   # lectura posterior a la creación
    ]

    with patch("novedades.reclamos.connection", conn), \
         patch("novedades.reclamos.transaction.atomic", _noop_atomic), \
         patch("novedades.reclamos.registrar_bitacora"), \
         patch("novedades.reclamos.tolerar_fallo_bitacora", _noop_tolerar):
        resultado = reclamos.crear_reclamo(
            {
                "obligacion_id": 4,
                "tipologia": "01",
                "fecha_radicacion": date(2026, 9, 22),
                "observacion": "Pago realizado.",
            },
            usuario=usuario_con_rol("ANALISTA_CARTERA"),
        )

    assert resultado["estado"] == "EN_RECLAMO"
    assert resultado["fecha_limite_respuesta"] == "2026-10-14"
    insert = next(
        str(call.args[0])
        for call in cursor.execute.call_args_list
        if call.args and "INSERT INTO NEXOVOLT.NV_RECLAMO" in str(call.args[0])
    )
    assert "INCLUIR" not in insert
    assert "FECHA_LIMITE_RESPUESTA" in insert


def test_crear_reclamo_abierto_en_la_obligacion_lanza_conflicto():
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        ("2260-5543",),
        (1,),
        (3,),
    ]
    with patch("novedades.reclamos.connection", conn), \
         patch("novedades.reclamos.transaction.atomic", _noop_atomic):
        try:
            reclamos.crear_reclamo(
                {
                    "obligacion_id": 4,
                    "tipologia": "01",
                    "fecha_radicacion": date(2026, 9, 22),
                }
            )
        except reclamos.ObligacionConReclamoAbierto:
            pass
        else:
            raise AssertionError("El reclamo duplicado debía rechazarse.")


def test_post_tipologia_invalida_responde_400():
    with patch(
        "novedades.reclamos_views.reclamos.crear_reclamo",
        side_effect=reclamos.TipologiaNoEncontrada,
    ):
        request = APIRequestFactory().post(
            "/api/reclamos/",
            {
                "obligacion_id": 4,
                "tipologia": "XX",
                "fecha_radicacion": "2026-09-22",
            },
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = ReclamosViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400
    assert "tipologia" in response.data


def test_post_reclamo_abierto_responde_409_en_espanol():
    with patch(
        "novedades.reclamos_views.reclamos.crear_reclamo",
        side_effect=reclamos.ObligacionConReclamoAbierto,
    ):
        request = APIRequestFactory().post(
            "/api/reclamos/",
            {
                "obligacion_id": 4,
                "tipologia": "01",
                "fecha_radicacion": "2026-09-22",
            },
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = ReclamosViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 409
    assert response.data["detail"] == "La obligación ya tiene un reclamo abierto."


def test_cierre_anterior_a_radicacion_responde_400_por_campo():
    with patch(
        "novedades.reclamos_views.reclamos.cerrar_reclamo",
        side_effect=ValueError(
            "La fecha de cierre no puede ser anterior a la de radicación."
        ),
    ):
        request = APIRequestFactory().post(
            "/api/reclamos/1/cerrar/",
            {"resultado": "Procedente", "fecha_cierre": "2026-09-17"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = ReclamosViewSet.as_view({"post": "cerrar"})(request, pk="1")

    assert response.status_code == 400
    assert "fecha_cierre" in response.data


def test_insumo_marcacion_solo_incluye_pendientes_y_marca_generados():
    conn, cursor = _mock_conn()
    cursor.fetchall.return_value = [
        ("2260-5543", "01", date(2026, 9, 22), 1),
        ("2259-1092", "02", date(2026, 9, 23), 2),
    ]
    cursor.rowcount = 2
    with patch("novedades.reclamos.connection", conn), \
         patch("novedades.reclamos.transaction.atomic", _noop_atomic), \
         patch("novedades.reclamos.registrar_bitacora"), \
         patch("novedades.reclamos.tolerar_fallo_bitacora", _noop_tolerar):
        contenido = reclamos.generar_insumo("marcacion")

    assert contenido == (
        "2260-5543|01|20260922\r\n"
        "2259-1092|02|20260923\r\n"
    )
    assert any(
        "MARCACION_GENERADA = 'S'" in str(call.args[0])
        for call in cursor.executemany.call_args_list
    )


def test_insumo_reclamos_vacio_queda_vacio():
    conn, cursor = _mock_conn()
    cursor.fetchall.return_value = []
    with patch("novedades.reclamos.connection", conn), \
         patch("novedades.reclamos.transaction.atomic", _noop_atomic):
        contenido = reclamos.generar_insumo("desmarcacion")
    assert contenido == ""
    assert not cursor.executemany.called


def test_listado_alerta_reclamo_vencido():
    conn, cursor = _mock_conn()
    cursor.fetchall.return_value = [
        (*_FILA_RECLAMO[:11], date(2026, 10, 1), *_FILA_RECLAMO[12:])
    ]
    with patch("novedades.reclamos.connection", conn), \
         patch("novedades.reclamos.hoy_bogota", return_value=date(2026, 10, 10)):
        resultado = reclamos.listar_reclamos(estado="EN_RECLAMO")

    assert resultado[0]["vencido"] is True


def test_usuario_administrador_no_puede_acceder_a_reclamos():
    request = APIRequestFactory().get("/api/reclamos/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = ReclamosViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403
