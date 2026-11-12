from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from novedades import refinanciaciones
from novedades.refinanciaciones_views import RefinanciacionesViewSet
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


# cols: 0=REFINANCIACION_ID, 1=FECHA, 2=FECHA_REGISTRO, 3=ORIGEN,
#       4=OBLIGACION_ORIGEN_ID, 5=o_orig.NUMERO_OBLIGACION_TU, 6=NOMBRE_TITULAR,
#       7=NVL(rd_orig.ESTADO_TU,'01'), 8=OBLIGACION_NUEVA_ID,
#       9=o_nueva.NUMERO_OBLIGACION_TU, 10=NVL(rd_nueva.ESTADO_TU,'01'),
#       11=NVL(N_REESTRUCTURACIONES,1), 12=SALDO_REFINANCIADO,
#       13=NATURALEZA, 14=nat.DESCRIPCION, 15=nat.CONFIRMADO,
#       16=N_CUOTAS, 17=u.NOMBRE
_FILA_REFINANCIACION = (
    1, date(2026, 9, 28), datetime(2026, 9, 28, 15, 20), "MANUAL",
    11, "2255-7788", "Inversiones Pamplona S.A.S.", "01",
    12, "REFI-1", "01", 1,
    4380000, "01", "REESTRUCTURACION VOLUNTARIA", "N",
    36, "Juan Pérez",
)

_REFINANCIACION = {
    "id": 1,
    "fecha": "2026-09-28",
    "fecha_registro": "2026-09-28T15:20:00-05:00",
    "registrada_por": "Juan Pérez",
    "origen": "MANUAL",
    "obligacion_original": {
        "obligacion_id": 11,
        "numero_obligacion": "2255-7788",
        "nombre_titular": "Inversiones Pamplona S.A.S.",
        "estado_cierre": "02",
        "modo_extincion": {"codigo": "16", "descripcion": "Refinanciación"},
    },
    "obligacion_nueva": {
        "obligacion_id": 12,
        "numero_obligacion": "REFI-1",
        "estado_tu": "01",
        "numero_reestructuraciones": 1,
    },
    "saldo_refinanciado": 4380000,
    "naturaleza": {"codigo": "01", "descripcion": "REESTRUCTURACION VOLUNTARIA", "confirmado": False},
    "numero_cuotas": 36,
}


def test_listar_refinanciaciones_vacio():
    conn, cursor = _mock_conn()
    cursor.fetchall.return_value = []
    with patch("novedades.refinanciaciones.connection", conn):
        resultado = refinanciaciones.listar_refinanciaciones()
    assert resultado == []


def test_crear_refinanciacion_manual_inserta_obligacion_y_refinanciacion():
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        (5001, 99, "2255-7788", "N", "N", date(2026, 1, 1)),  # obligación + FECHA_INICIO
        (None,),                                               # MAX FECHA_CORTE (sin corte enviado)
        ("01", 4380000),                                       # último estado reportado + saldo
        ("REESTRUCTURACION VOLUNTARIA",),                      # naturaleza
        (1,),                                                  # SEQ_NV_REFINANCIACION
        (12,),                                                 # SEQ_NV_OBLIGACION
        _FILA_REFINANCIACION,                                  # obtener_refinanciacion
    ]

    with patch("novedades.refinanciaciones.connection", conn), \
         patch("novedades.refinanciaciones.transaction.atomic", _noop_atomic), \
         patch("novedades.refinanciaciones.registrar_bitacora"), \
         patch("novedades.refinanciaciones.tolerar_fallo_bitacora", _noop_tolerar):
        resultado = refinanciaciones.crear_refinanciacion(
            {
                "obligacion_original_id": 11,
                "naturaleza": "01",
                "numero_cuotas": 36,
                "fecha": date(2026, 9, 28),
            },
            usuario=usuario_con_rol("ANALISTA_CARTERA"),
        )

    assert resultado["origen"] == "MANUAL"
    assert resultado["obligacion_original"]["estado_cierre"] == "02"
    assert resultado["obligacion_nueva"]["numero_obligacion"] == "REFI-1"

    sqls = [str(call.args[0]) for call in cursor.execute.call_args_list if call.args]
    inserts = [s for s in sqls if "INSERT INTO NEXOVOLT" in s]
    updates = [s for s in sqls if "UPDATE NEXOVOLT.NV_OBLIGACION" in s]
    assert any("NV_OBLIGACION" in s for s in inserts)
    assert any("NV_REFINANCIACION" in s and "'MANUAL'" in s and "SALDO_REFINANCIADO" in s for s in inserts)
    assert any("CIERRE_DEFINITIVO" in s for s in updates)


def test_crear_obligacion_no_encontrada_lanza_excepcion():
    conn, cursor = _mock_conn()
    cursor.fetchone.return_value = None
    with patch("novedades.refinanciaciones.connection", conn), \
         patch("novedades.refinanciaciones.transaction.atomic", _noop_atomic):
        try:
            refinanciaciones.crear_refinanciacion(
                {"obligacion_original_id": 999, "naturaleza": "01",
                 "numero_cuotas": 12, "fecha": date(2026, 9, 28)}
            )
        except refinanciaciones.ObligacionNoEncontrada:
            pass
        else:
            raise AssertionError("Debía lanzarse ObligacionNoEncontrada.")


def test_post_obligacion_no_encontrada_responde_404():
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=refinanciaciones.ObligacionNoEncontrada,
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 999, "naturaleza": "01",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 404


def test_post_obligacion_eliminada_responde_409():
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=refinanciaciones.ObligacionEliminada("2255-7788"),
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 11, "naturaleza": "01",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 409
    assert response.data["code"] == "obligacion_eliminada"
    assert "2255-7788" in response.data["detail"]


def test_post_obligacion_cerrada_responde_409():
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=refinanciaciones.ObligacionCerrada("2255-7788"),
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 11, "naturaleza": "01",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 409
    assert response.data["code"] == "obligacion_cerrada"
    assert "2255-7788" in response.data["detail"]


def test_post_transicion_no_permitida_responde_409_con_mensaje_713():
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=refinanciaciones.TransicionNoPermitida("04"),
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 11, "naturaleza": "01",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 409
    assert response.data["code"] == "transicion_no_permitida"
    assert "04" in response.data["detail"]
    assert "713" in response.data["detail"]


def test_post_naturaleza_invalida_responde_400():
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=refinanciaciones.NaturalezaNoEncontrada,
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 11, "naturaleza": "ZZ",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400
    assert "naturaleza" in response.data


def test_post_cuotas_fuera_de_rango_responde_400():
    request = APIRequestFactory().post(
        "/api/refinanciaciones/",
        {"obligacion_original_id": 11, "naturaleza": "01",
         "numero_cuotas": 200, "fecha": "2026-09-28"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400
    assert "numero_cuotas" in response.data


def test_fecha_anterior_al_ingreso_lanza_error():
    """fecha antes de FECHA_INICIO → ValueError con texto que menciona ingreso."""
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        (5001, 99, "2255-7788", "N", "N", date(2026, 10, 1)),  # ingresó el 01/10/2026
        (None,),                                                 # sin corte enviado
    ]
    with patch("novedades.refinanciaciones.connection", conn), \
         patch("novedades.refinanciaciones.transaction.atomic", _noop_atomic):
        try:
            refinanciaciones.crear_refinanciacion(
                {"obligacion_original_id": 11, "naturaleza": "01",
                 "numero_cuotas": 12, "fecha": date(2026, 9, 28)},
            )
        except ValueError as exc:
            assert "ingreso" in str(exc).lower()
        else:
            raise AssertionError("Debía lanzarse ValueError.")


def test_fecha_anterior_a_corte_enviado_lanza_error():
    """fecha antes del último corte enviado → ValueError con texto que menciona corte enviado."""
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        (5001, 99, "2255-7788", "N", "N", date(2026, 1, 1)),  # ingresó en enero
        (date(2026, 10, 31),),                                  # último corte enviado: 31/10/2026
    ]
    with patch("novedades.refinanciaciones.connection", conn), \
         patch("novedades.refinanciaciones.transaction.atomic", _noop_atomic):
        try:
            refinanciaciones.crear_refinanciacion(
                {"obligacion_original_id": 11, "naturaleza": "01",
                 "numero_cuotas": 12, "fecha": date(2026, 9, 28)},
            )
        except ValueError as exc:
            assert "corte enviado" in str(exc).lower()
        else:
            raise AssertionError("Debía lanzarse ValueError.")


def test_post_fecha_invalida_responde_400_por_campo():
    """ValueError en crear_refinanciacion → 400 con key 'fecha'."""
    with patch(
        "novedades.refinanciaciones_views.refinanciaciones.crear_refinanciacion",
        side_effect=ValueError(
            "La fecha no puede ser anterior al ingreso de la obligación (2026-10-01)."
        ),
    ):
        request = APIRequestFactory().post(
            "/api/refinanciaciones/",
            {"obligacion_original_id": 11, "naturaleza": "01",
             "numero_cuotas": 12, "fecha": "2026-09-28"},
            format="json",
        )
        force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
        response = RefinanciacionesViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400
    assert "fecha" in response.data


def test_administrador_no_puede_acceder_a_refinanciaciones():
    request = APIRequestFactory().get("/api/refinanciaciones/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = RefinanciacionesViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403
