from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol
from novedades import servicios
from novedades.views import EliminacionesViewSet, NovedadesViewSet


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
