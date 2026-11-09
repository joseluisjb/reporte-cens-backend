from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol
from novedades import servicios
from novedades.views import (
    EliminacionesViewSet,
    NovedadesViewSet,
    RectificacionesViewSet,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def _noop_atomic():
    yield


@contextmanager
def _noop_tolerar(accion):
    yield


def _mock_conn():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    return mock_conn, mock_cursor


_FILA_NOVEDAD = (
    3, "ACTUALIZACION", "OBLIGACION", 6, "2262-3318",
    "Cambio de dirección de contacto del titular",
    None, None, None,          # motivo_eliminacion cols
    None,                      # valores_enviados
    date(2026, 9, 24),         # fecha_deteccion
    "MANUAL",                  # origen
    "PENDIENTE",               # estado
    None,                      # numero_transaccion_tu
    None,                      # fecha_gestion
    None,                      # motivo_rechazo
    "Carlos Sánchez",          # registrada_por
)

_FILA_GESTIONADA = (
    3, "ACTUALIZACION", "OBLIGACION", 6, "2262-3318",
    "Cambio de dirección de contacto del titular",
    None, None, None,
    None,
    date(2026, 9, 24),
    "MANUAL",
    "GESTIONADA",
    "TU-AL-001532",
    date(2026, 9, 24),
    None,
    "Carlos Sánchez",
)

_FILA_RECHAZADA = (
    1, "ACTUALIZACION", "OBLIGACION", 4, "2260-5543",
    "Pago del titular posterior al corte",
    None, None, None,
    None,
    date(2026, 9, 29),
    "AUTOMATICA",
    "RECHAZADA",
    None,
    date(2026, 9, 30),
    "El módulo en línea rechazó la transacción por datos del titular.",
    None,
)


# ── Servicios ─────────────────────────────────────────────────────────────────

def test_rf24_crear_actualizacion_queda_pendiente():
    """Registrar ACTUALIZACION sobre 2262-3318 → PENDIENTE, ORIGEN=MANUAL."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1,),               # COUNT(*) NV_OBLIGACION → existe
        (101,),             # SEQ_NV_NOVEDAD.NEXTVAL
        _FILA_NOVEDAD,      # _fetch_novedad final
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar):
        result = servicios.crear_novedad(
            {
                "tipo": "ACTUALIZACION",
                "sujeto": "OBLIGACION",
                "obligacion_id": 6,
                "referencia": "2262-3318",
                "motivo": "Cambio de dirección de contacto del titular",
            }
        )

    assert result["estado"] == "PENDIENTE"
    assert result["origen"] == "MANUAL"
    assert result["referencia"] == "2262-3318"


def test_rf24_novedad_sobre_obligacion_no_existe_lanza_excepcion():
    """Novedad sobre obligación que no existe → ObligacionNoEncontrada."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (0,)   # COUNT(*) → no existe

    with patch("novedades.servicios.connection", mock_conn):
        with pytest.raises(servicios.ObligacionNoEncontrada):
            servicios.crear_novedad(
                {
                    "tipo": "ACTUALIZACION",
                    "sujeto": "OBLIGACION",
                    "obligacion_id": 999,
                    "referencia": "9999-9999",
                    "motivo": "Obligación inexistente",
                }
            )


def test_rf24_gestionar_novedad_pasa_a_gestionada():
    """Gestionar con número TU-AL-001532 → estado GESTIONADA con fecha."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        _FILA_NOVEDAD,      # _fetch_novedad inicial (PENDIENTE)
        _FILA_GESTIONADA,   # _fetch_novedad final (GESTIONADA)
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar):
        result = servicios.gestionar_novedad(
            3, "TU-AL-001532", date(2026, 9, 24)
        )

    assert result["estado"] == "GESTIONADA"
    assert result["numero_transaccion_tu"] == "TU-AL-001532"
    assert result["fecha_gestion"] == "2026-09-24"


def test_rf24_gestionar_novedad_no_pendiente_lanza_excepcion():
    """Gestionar novedad ya gestionada → NovedadNoPendiente."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = _FILA_GESTIONADA   # ya GESTIONADA

    with patch("novedades.servicios.connection", mock_conn):
        with pytest.raises(servicios.NovedadNoPendiente):
            servicios.gestionar_novedad(3, "TU-AL-999", date(2026, 9, 25))


def test_rf24_rechazar_con_motivo_queda_rechazada():
    """Rechazar con motivo → estado RECHAZADA y motivo registrado."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        _FILA_NOVEDAD,       # _fetch_novedad inicial (PENDIENTE)
        _FILA_RECHAZADA,     # _fetch_novedad final (RECHAZADA)
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar), \
         patch("novedades.servicios.hoy_bogota", return_value=date(2026, 9, 30)):
        result = servicios.rechazar_novedad(
            1,
            "El módulo en línea rechazó la transacción por datos del titular.",
        )

    assert result["estado"] == "RECHAZADA"
    assert result["motivo_rechazo"] is not None


def test_rf24_listar_sin_filtro_devuelve_todas():
    """GET /api/novedades/ sin filtro → lista todas las novedades."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchall.return_value = [_FILA_NOVEDAD]

    with patch("novedades.servicios.connection", mock_conn):
        result = servicios.listar_novedades()

    assert len(result) == 1
    assert result[0]["estado"] == "PENDIENTE"


def test_rf24_listar_filtro_estado_pendiente():
    """GET /api/novedades/?estado=PENDIENTE → solo pendientes."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchall.return_value = [_FILA_NOVEDAD]

    with patch("novedades.servicios.connection", mock_conn):
        result = servicios.listar_novedades(estado="PENDIENTE")

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    assert any("ESTADO" in s for s in sqls), "Debe filtrar por ESTADO en la query"


# ── Vistas ────────────────────────────────────────────────────────────────────

def test_rf24_post_crear_201():
    """POST /api/novedades/ → 201 con la novedad PENDIENTE."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1,),           # COUNT obligacion
        (101,),         # SEQ
        _FILA_NOVEDAD,  # fetch final
    ]

    factory = APIRequestFactory()
    view = NovedadesViewSet.as_view({"post": "create"})
    request = factory.post(
        "/novedades/",
        {
            "tipo": "ACTUALIZACION",
            "sujeto": "OBLIGACION",
            "obligacion_id": 6,
            "referencia": "2262-3318",
            "motivo": "Cambio de dirección de contacto del titular",
        },
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar):
        response = view(request)

    assert response.status_code == 201
    assert response.data["estado"] == "PENDIENTE"


def test_rf24_post_gestionar_sin_numero_400():
    """POST /api/novedades/{id}/gestionar/ sin numero_transaccion_tu → 400."""
    factory = APIRequestFactory()
    view = NovedadesViewSet.as_view({"post": "gestionar"})
    request = factory.post(
        "/novedades/3/gestionar/",
        {"fecha_gestion": "2026-09-24"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = view(request, pk="3")
    assert response.status_code == 400
    assert "numero_transaccion_tu" in response.data


def test_rf24_post_novedad_obligacion_no_existe_404():
    """POST /api/novedades/ con obligación inexistente → 404."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (0,)   # obligacion no existe

    factory = APIRequestFactory()
    view = NovedadesViewSet.as_view({"post": "create"})
    request = factory.post(
        "/novedades/",
        {
            "tipo": "ACTUALIZACION",
            "sujeto": "OBLIGACION",
            "obligacion_id": 999,
            "referencia": "9999-9999",
            "motivo": "Obligación inexistente",
        },
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn):
        response = view(request)

    assert response.status_code == 404
    assert "Obligación no encontrada" in response.data["detail"]


# ── RF50: Eliminaciones ───────────────────────────────────────────────────────

# ELIMINACION_ID, OBLIGACION_ID, NUMERO_OBLIGACION_TU, FECHA,
# CODIGO, DESCRIPCION, CONFIRMADO,
# NUMERO_TRANSACCION_TU, BLOQUEADA, FECHA_ACTIVACION, NUMERO_ACTIVACION_TU
_FILA_ELIMINACION_BLOQUEADA = (
    1, 42, "2249-1180", date(2026, 9, 15),
    "01", "Reportada por error", "N",
    "TU-AL-001198", "S", None, None,
)

_FILA_ELIMINACION_REACTIVADA = (
    1, 42, "2249-1180", date(2026, 9, 15),
    "01", "Reportada por error", "N",
    "TU-AL-001198", "N", date(2026, 10, 20), "TU-AC-000045",
)

# Fila de NV_NOVEDAD para novedad de tipo ELIMINACION (con obligacion_id)
_FILA_NOVEDAD_ELIM = (
    10, "ELIMINACION", "OBLIGACION", 42, "2249-1180",
    "Obligación errada",
    "01", "Reportada por error", "N",  # motivo_eliminacion
    None,                               # valores_enviados
    date(2026, 9, 10),                  # fecha_deteccion
    "MANUAL",                           # origen
    "PENDIENTE",                        # estado
    None,                               # numero_transaccion_tu
    None,                               # fecha_gestion
    None,                               # motivo_rechazo
    "Carlos Sánchez",                   # registrada_por
)

_FILA_NOVEDAD_ELIM_GESTIONADA = (
    10, "ELIMINACION", "OBLIGACION", 42, "2249-1180",
    "Obligación errada",
    "01", "Reportada por error", "N",
    None,
    date(2026, 9, 10),
    "MANUAL",
    "GESTIONADA",
    "TU-AL-001198",
    date(2026, 9, 15),
    None,
    "Carlos Sánchez",
)


def test_rf50_gestionar_eliminacion_crea_registro():
    """Gestionar novedad ELIMINACION → NV_ELIMINACION creado, NV_OBLIGACION.ELIMINADA='S'."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        _FILA_NOVEDAD_ELIM,              # _fetch_novedad inicial
        (7,),                            # MOTIVO_ID desde NV_MOTIVO_ELIMINACION
        (501,),                          # SEQ_NV_ELIMINACION.NEXTVAL
        _FILA_NOVEDAD_ELIM_GESTIONADA,  # _fetch_novedad final
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar):
        result = servicios.gestionar_novedad(
            10, "TU-AL-001198", date(2026, 9, 15)
        )

    assert result["estado"] == "GESTIONADA"
    assert result["numero_transaccion_tu"] == "TU-AL-001198"
    # Verificar que se ejecutaron INSERT en NV_ELIMINACION y UPDATE en NV_OBLIGACION
    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    assert any("NV_ELIMINACION" in s and "INSERT" in s for s in sqls), \
        "Debe insertar en NV_ELIMINACION"
    assert any("NV_OBLIGACION" in s and "ELIMINADA" in s for s in sqls), \
        "Debe marcar ELIMINADA='S' en NV_OBLIGACION"


def test_rf50_listar_eliminaciones_paginado():
    """GET /api/eliminaciones/ → {total, resultados} con paginación."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1,)
    mock_cursor.fetchall.return_value = [_FILA_ELIMINACION_BLOQUEADA]

    with patch("novedades.servicios.connection", mock_conn):
        result = servicios.listar_eliminaciones(20, 0)

    assert result["total"] == 1
    assert len(result["resultados"]) == 1
    elim = result["resultados"][0]
    assert elim["id"] == 1
    assert elim["numero_obligacion"] == "2249-1180"
    assert elim["bloqueada"] is True
    assert elim["fecha_activacion"] is None


def test_rf50_reactivar_sin_numero_400():
    """POST /api/eliminaciones/{id}/reactivar/ sin numero_activacion_tu → 400."""
    factory = APIRequestFactory()
    view = EliminacionesViewSet.as_view({"post": "reactivar"})
    request = factory.post(
        "/eliminaciones/1/reactivar/",
        {"fecha_activacion": "2026-10-20"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = view(request, pk="1")
    assert response.status_code == 400
    assert "numero_activacion_tu" in response.data


def test_rf50_reactivar_exitoso_desbloquea():
    """POST /api/eliminaciones/{id}/reactivar/ → BLOQUEADA='N', ELIMINADA='N'."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        _FILA_ELIMINACION_BLOQUEADA,    # fetch inicial (BLOQUEADA='S')
        _FILA_ELIMINACION_REACTIVADA,   # fetch final después del UPDATE
    ]

    factory = APIRequestFactory()
    view = EliminacionesViewSet.as_view({"post": "reactivar"})
    request = factory.post(
        "/eliminaciones/1/reactivar/",
        {"numero_activacion_tu": "TU-AC-000045", "fecha_activacion": "2026-10-20"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar):
        response = view(request, pk="1")

    assert response.status_code == 200
    assert response.data["bloqueada"] is False
    assert response.data["numero_activacion_tu"] == "TU-AC-000045"
    assert response.data["fecha_activacion"] == "2026-10-20"


def test_rf50_reactivar_no_existe_404():
    """POST /api/eliminaciones/{id}/reactivar/ con id inexistente → 404."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None

    factory = APIRequestFactory()
    view = EliminacionesViewSet.as_view({"post": "reactivar"})
    request = factory.post(
        "/eliminaciones/999/reactivar/",
        {"numero_activacion_tu": "TU-AC-000045", "fecha_activacion": "2026-10-20"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn):
        response = view(request, pk="999")

    assert response.status_code == 404
    assert "Eliminación no encontrada" in response.data["detail"]


def test_rf50_reactivar_ya_reactivada_409():
    """POST /api/eliminaciones/{id}/reactivar/ con eliminación ya reactivada → 409."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = _FILA_ELIMINACION_REACTIVADA  # BLOQUEADA='N'

    factory = APIRequestFactory()
    view = EliminacionesViewSet.as_view({"post": "reactivar"})
    request = factory.post(
        "/eliminaciones/1/reactivar/",
        {"numero_activacion_tu": "TU-AC-000099", "fecha_activacion": "2026-11-01"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn):
        response = view(request, pk="1")

    assert response.status_code == 409
    assert "reactivada" in response.data["detail"]


# ── RF55: Rectificaciones ────────────────────────────────────────────────────

_FILA_RECTIFICACION = (
    201, 101, 42, "2249-1180", 5, date(2026, 9, 30),
    "valor_mora", "12000", "15000", "Corrección validada",
    "ACTUALIZACION_LINEA", "REGISTRADA", None, 2, None,
)


def test_rf55_crear_rectificacion_conserva_anterior_y_actualiza_corte():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("ENVIADO", date(2026, 9, 30), "2249-1180", 12000),
        (101,),  # SEQ_NV_NOVEDAD
        (201,),  # SEQ_NV_RECTIFICACION
        _FILA_RECTIFICACION,
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar), \
         patch("novedades.servicios._nombres_usuarios", return_value={}):
        result = servicios.crear_rectificacion({
            "obligacion_id": 42,
            "corte_id": 5,
            "campo": "valor_mora",
            "valor_corregido": "15000",
            "justificacion": "Corrección validada",
            "medio": "ACTUALIZACION_LINEA",
        })

    assert result["valor_anterior"] == "12000"
    assert result["valor_corregido"] == "15000"
    calls = [
        (call.args[0], call.args[1] if len(call.args) > 1 else [])
        for call in mock_cursor.execute.call_args_list
    ]
    insert = next(params for sql, params in calls if "INSERT INTO NEXOVOLT.NV_RECTIFICACION" in sql)
    update = next(params for sql, params in calls if "UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in sql)
    assert insert[5:7] == ["12000", "15000"]
    assert update == [Decimal("15000"), 5, 42]


def test_rf55_crear_rectificacion_enlaza_novedad_correccion_existente():
    novedad_id = 321
    fila_rectificacion = (
        201, novedad_id, 42, "2249-1180", 5, date(2026, 9, 30),
        "valor_mora", "12000", "15000", "Corrección validada",
        "ACTUALIZACION_LINEA", "REGISTRADA", None, 2, None,
    )
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("ENVIADO", date(2026, 9, 30), "2249-1180", 12000),
        (1,),  # Existe una novedad CORRECCION
        (201,),  # SEQ_NV_RECTIFICACION
        fila_rectificacion,
    ]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar), \
         patch("novedades.servicios._nombres_usuarios", return_value={}):
        result = servicios.crear_rectificacion({
            "novedad_id": novedad_id,
            "obligacion_id": 42,
            "corte_id": 5,
            "campo": "valor_mora",
            "valor_corregido": "15000",
            "justificacion": "Corrección validada",
            "medio": "ACTUALIZACION_LINEA",
        })

    sqls = [call.args[0] for call in mock_cursor.execute.call_args_list]
    insert = next(
        call.args[1] for call in mock_cursor.execute.call_args_list
        if "INSERT INTO NEXOVOLT.NV_RECTIFICACION" in call.args[0]
    )
    assert result["novedad_id"] == novedad_id
    assert insert[1] == novedad_id
    assert not any("SEQ_NV_NOVEDAD.NEXTVAL" in sql for sql in sqls)
    assert not any("INSERT INTO NEXOVOLT.NV_NOVEDAD" in sql for sql in sqls)


def test_rf55_novedad_rectificacion_inexistente_devuelve_error_por_campo():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("ENVIADO", date(2026, 9, 30), "2249-1180", 12000),
        (0,),
    ]
    factory = APIRequestFactory()
    view = RectificacionesViewSet.as_view({"post": "create"})
    request = factory.post(
        "/rectificaciones/",
        {
            "novedad_id": 999,
            "obligacion_id": 42,
            "corte_id": 5,
            "campo": "valor_mora",
            "valor_corregido": "15000",
            "justificacion": "Corrección validada",
            "medio": "ACTUALIZACION_LINEA",
        },
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic):
        response = view(request)

    assert response.status_code == 400
    assert response.data == {
        "novedad_id": ["La novedad no existe o no es de tipo CORRECCION."]
    }


def test_rf55_no_rectifica_corte_no_enviado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (
        "BORRADOR", date(2026, 9, 30), "2249-1180", 12000
    )

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.CorteNoEnviado):
            servicios.crear_rectificacion({
                "obligacion_id": 42,
                "corte_id": 5,
                "campo": "valor_mora",
                "valor_corregido": "15000",
                "justificacion": "Corrección validada",
                "medio": "ACTUALIZACION_LINEA",
            })

    assert mock_cursor.execute.call_count == 1


def test_rf55_confirmar_actualiza_rectificacion_y_novedad():
    fila_confirmada = (*_FILA_RECTIFICACION[:11], "CONFIRMADA", "TU-AL-001532", 2, None)
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [("REGISTRADA", 101), fila_confirmada]

    with patch("novedades.servicios.connection", mock_conn), \
         patch("novedades.servicios.transaction.atomic", _noop_atomic), \
         patch("novedades.servicios.registrar_bitacora"), \
         patch("novedades.servicios.tolerar_fallo_bitacora", _noop_tolerar), \
         patch("novedades.servicios._nombres_usuarios", return_value={}):
        result = servicios.confirmar_rectificacion(201, "TU-AL-001532")

    assert result["estado"] == "CONFIRMADA"
    assert result["confirmacion_tu"] == "TU-AL-001532"
    sqls = [call.args[0] for call in mock_cursor.execute.call_args_list]
    assert any("UPDATE NEXOVOLT.NV_NOVEDAD" in sql for sql in sqls)


def test_rf55_rechaza_campo_no_acordado():
    factory = APIRequestFactory()
    view = RectificacionesViewSet.as_view({"post": "create"})
    request = factory.post(
        "/rectificaciones/",
        {
            "obligacion_id": 42,
            "corte_id": 5,
            "campo": "valor_saldo",
            "valor_corregido": "15000",
            "justificacion": "Corrección validada",
            "medio": "ACTUALIZACION_LINEA",
        },
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    response = view(request)

    assert response.status_code == 400
    assert "campo" in response.data


def test_rf55_solo_analista_puede_listar_rectificaciones():
    factory = APIRequestFactory()
    view = RectificacionesViewSet.as_view({"get": "list"})
    request = factory.get("/rectificaciones/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))

    response = view(request)

    assert response.status_code == 403


def test_rf55_no_confirma_con_numero_transunion_vacio():
    factory = APIRequestFactory()
    view = RectificacionesViewSet.as_view({"post": "confirmar"})
    request = factory.post(
        "/rectificaciones/201/confirmar/",
        {"confirmacion_tu": "   "},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("novedades.servicios.confirmar_rectificacion") as confirmar:
        response = view(request, pk="201")

    assert response.status_code == 400
    assert "confirmacion_tu" in response.data
    confirmar.assert_not_called()
