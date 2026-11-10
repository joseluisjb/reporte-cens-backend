from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from rest_framework.test import APIRequestFactory, force_authenticate

from novedades import rectificaciones
from novedades.rectificaciones_views import RectificacionesViewSet
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


_FILA_RECTIFICACION = (
    31, 20, 2, "2258-7731", 1, date(2026, 8, 31), "valor_mora",
    "140000", "70000", "El corte reportó un valor errado.",
    "ACTUALIZACION_LINEA", "REGISTRADA", None, "Analista",
    datetime(2026, 9, 30, 11, 0),
)

_FILA_CONFIRMADA = (
    31, 20, 2, "2258-7731", 1, date(2026, 8, 31), "valor_mora",
    "140000", "70000", "El corte reportó un valor errado.",
    "ACTUALIZACION_LINEA", "CONFIRMADA", "TU-AL-001610", "Analista",
    datetime(2026, 9, 30, 11, 0),
)


def test_crear_rectificacion_conserva_original_actualiza_historico_y_devuelve_insumo():
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        ("ENVIADO",),                # corte
        ("2258-7731",),              # obligación
        (140000,),                   # valor reportado
        (20,),                       # secuencia de novedad asociada
        (31,),                       # secuencia de rectificación
        _FILA_RECTIFICACION,         # respuesta
    ]

    with patch("novedades.rectificaciones.connection", conn), \
         patch("novedades.rectificaciones.transaction.atomic", _noop_atomic), \
         patch("novedades.rectificaciones.registrar_bitacora"), \
         patch("novedades.rectificaciones.tolerar_fallo_bitacora", _noop_tolerar):
        resultado = rectificaciones.crear_rectificacion(
            {
                "obligacion_id": 2,
                "corte_id": 1,
                "campo": "valor_mora",
                "valor_corregido": "70000",
                "justificacion": "El corte reportó un valor errado.",
                "medio": "ACTUALIZACION_LINEA",
            },
            usuario=usuario_con_rol("ANALISTA_CARTERA"),
        )

    assert resultado["valor_anterior"] == "140000"
    assert resultado["valor_corregido"] == "70000"
    assert resultado["insumo"] == "2258-7731|valor_mora|70000\r\n"

    sqls = [
        str(call.args[0])
        for call in cursor.execute.call_args_list
        if call.args
    ]
    assert any("INSERT INTO NEXOVOLT.NV_RECTIFICACION" in sql for sql in sqls)
    assert any(
        "UPDATE NEXOVOLT.NV_REPORTE_DETALLE SET VALOR_MORA = %s" in sql
        for sql in sqls
    )
    insert = next(sql for sql in sqls if "INSERT INTO NEXOVOLT.NV_RECTIFICACION" in sql)
    assert "VALOR_ANTERIOR" in insert
    assert any("INSERT INTO NEXOVOLT.NV_NOVEDAD" in sql for sql in sqls)


def test_corte_no_enviado_rechaza_rectificacion():
    conn, cursor = _mock_conn()
    cursor.fetchone.return_value = ("BORRADOR",)
    with patch("novedades.rectificaciones.connection", conn), \
         patch("novedades.rectificaciones.transaction.atomic", _noop_atomic):
        try:
            rectificaciones.crear_rectificacion(
                {
                    "obligacion_id": 2,
                    "corte_id": 1,
                    "campo": "valor_mora",
                    "valor_corregido": "70000",
                    "justificacion": "Corrección.",
                    "medio": "ACTUALIZACION_LINEA",
                }
            )
        except rectificaciones.CorteNoEnviado:
            pass
        else:
            raise AssertionError("El corte no enviado debía rechazarse.")
    assert cursor.execute.call_count == 1


def test_campo_no_permitido_no_se_inserta_en_sql():
    try:
        rectificaciones._validar_valor_corregido("obligacion_id", "55")
    except rectificaciones.RectificacionDatoInvalido as exc:
        assert exc.campo == "campo"
    else:
        raise AssertionError("No se debe poder rectificar la llave de obligación.")


def test_confirmar_rectificacion_actualiza_estado_y_confirma_transunion():
    conn, cursor = _mock_conn()
    cursor.fetchone.side_effect = [
        ("REGISTRADA",),
        _FILA_CONFIRMADA,
    ]
    with patch("novedades.rectificaciones.connection", conn), \
         patch("novedades.rectificaciones.transaction.atomic", _noop_atomic), \
         patch("novedades.rectificaciones.registrar_bitacora"), \
         patch("novedades.rectificaciones.tolerar_fallo_bitacora", _noop_tolerar):
        resultado = rectificaciones.confirmar_rectificacion(
            31,
            "TU-AL-001610",
            usuario=usuario_con_rol("ANALISTA_CARTERA"),
        )

    assert resultado["estado"] == "CONFIRMADA"
    assert resultado["confirmacion_tu"] == "TU-AL-001610"
    assert any(
        "SET ESTADO = 'CONFIRMADA', CONFIRMACION_TU = %s" in str(call.args[0])
        for call in cursor.execute.call_args_list
        if call.args
    )


def test_confirmar_sin_numero_transunion_responde_400():
    request = APIRequestFactory().post(
        "/api/rectificaciones/31/confirmar/",
        {"confirmacion_tu": "   "},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = RectificacionesViewSet.as_view({"post": "confirmar"})(
        request, pk="31"
    )

    assert response.status_code == 400
    assert "confirmacion_tu" in response.data


def test_rectificacion_rechaza_admin():
    request = APIRequestFactory().get("/api/rectificaciones/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = RectificacionesViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403
