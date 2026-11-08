from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol

from ciclo import servicios
from ciclo.serializers import CicloCreateSerializer
from ciclo.views import CicloViewSet, MatrizEstadosView


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def _noop_atomic():
    yield


def _mock_conn_multiple():
    """Cursor con soporte para múltiples llamadas a execute/fetchone/fetchall."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    return mock_conn, mock_cursor


_FECHA_VALIDA = date(2026, 10, 31)
_FECHA_NO_ULTIMO = date(2026, 10, 15)
_FECHA_FEB_NO_ULTIMO = date(2026, 2, 14)


# ── Serializer CicloCreateSerializer ─────────────────────────────────────────

def test_serializer_fecha_obligatoria():
    s = CicloCreateSerializer(data={})
    assert not s.is_valid()
    assert "fecha_corte" in s.errors


def test_serializer_fecha_no_ultimo_dia_mes():
    s = CicloCreateSerializer(data={"fecha_corte": "2026-10-15"})
    assert not s.is_valid()
    assert "fecha_corte" in s.errors
    assert "31/10/2026" in s.errors["fecha_corte"][0]


def test_serializer_fecha_no_ultimo_dia_febrero():
    s = CicloCreateSerializer(data={"fecha_corte": "2026-02-14"})
    assert not s.is_valid()
    assert "fecha_corte" in s.errors
    assert "28/02/2026" in s.errors["fecha_corte"][0]


def test_serializer_fecha_valida():
    s = CicloCreateSerializer(data={"fecha_corte": "2026-10-31"})
    assert s.is_valid(), s.errors
    assert s.validated_data["fecha_corte"] == _FECHA_VALIDA


# ── Validación 881 ────────────────────────────────────────────────────────────

def test_881_vigente_sin_mora():
    assert servicios._valida_881("01", 0, "00") is True


def test_881_vigente_con_mora():
    assert servicios._valida_881("01", 50000, "01") is True


def test_881_dudoso_con_mora():
    assert servicios._valida_881("03", 80000, "01") is True


def test_881_dudoso_sin_mora_rechazado():
    assert servicios._valida_881("03", 0, "00") is False


def test_881_dudoso_mora_none_rechazado():
    assert servicios._valida_881("03", None, None) is False


def test_881_castigada_con_edad_y_mora():
    assert servicios._valida_881("06", 150000, "01") is True


def test_881_castigada_sin_mora_rechazado():
    assert servicios._valida_881("06", 0, "00") is False


def test_881_castigada_mora_sin_edad_rechazado():
    assert servicios._valida_881("06", 150000, "00") is False


def test_881_recuperada_siempre_rechazada():
    assert servicios._valida_881("07", 0, "00") is False
    assert servicios._valida_881("07", 100000, "01") is False


# ── Casos RF10 ────────────────────────────────────────────────────────────────
# Se prueban via ejecutar_ciclo con mocks de BD.

def _mock_sequence(mock_cursor, side_effects):
    """Configura side_effect para múltiples llamadas a fetchone/fetchall."""
    mock_cursor.fetchone.side_effect = side_effects


def _setup_ciclo(
    mock_conn,
    mock_cursor,
    corte_id=1,
    obligaciones=None,
    ultimo_enviado=None,
    es_primer_reporte=True,
):
    """Monta el mock_cursor con respuestas apropiadas para ejecutar_ciclo."""
    fecha_corte_bd = date(2026, 10, 31)

    fetchone_calls = [
        # _verificar_fecha_posterior: MAX(FECHA_CORTE) de ENVIADO
        (ultimo_enviado,),
        # _obtener_corte_borrador: CORTE_ID del BORRADOR
        (corte_id,),
    ]
    # Para cada obligación: _es_primer_reporte → COUNT(*)
    if obligaciones:
        for _ in obligaciones:
            fetchone_calls.append((0 if es_primer_reporte else 1,))
    # _guardar_ciclo: COUNT(*) de NV_CICLO
    fetchone_calls.append((0,))
    # fecha_corte_bd para el retorno
    fetchone_calls.append((fecha_corte_bd,))

    mock_cursor.fetchone.side_effect = fetchone_calls
    mock_cursor.fetchall.return_value = obligaciones or []


def test_ciclo_obligacion_nueva_al_dia():
    """Nueva al día (01, sin mora) → Entra en 01, edad 00, primer_reporte=True."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (10, "01", 0, "00", "Cliente A", "2263-9004"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["primer_reporte"] == 1
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["edad_nueva"] == "00"
    assert t["primer_reporte"] is True
    assert t["estado_anterior"] is None


def test_ciclo_nueva_con_cuota_vencida_23_dias():
    """Nueva con una cuota vencida de 23 días → Entra en 01, edad 00, mora > 0."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (11, "01", 85000, "00", "Cliente B", "2263-0001"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["primer_reporte"] == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["edad_nueva"] == "00"
    assert t["primer_reporte"] is True


def test_ciclo_nueva_caducada_con_mora():
    """Nueva con crédito caducado y mora → Entra en 03 (válido)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (12, "03", 200000, "02", "Cliente C", "2263-0002"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["primer_reporte"] == 1
    assert resultado["rechazados"] == 0
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "03"
    assert t["primer_reporte"] is True


def test_ciclo_nueva_caducada_sin_mora_requiere_revision():
    """Nueva caducada sin mora → 01, primer_reporte=True, requiere_revision=True (RF14)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (13, "01", 0, "00", "Cliente D", "2263-0003"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["primer_reporte"] == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["requiere_revision"] is True


def test_ciclo_nueva_estado_07_rechazada():
    """Nueva en estado 07 → Rechazada con error 881."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (14, "07", 0, "00", "Cliente E", "2267-3361"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["primer_reporte"] == 0
    assert resultado["rechazados"] == 1
    assert len(resultado["transiciones"]) == 0
    r = resultado["rechazos"][0]
    assert r["codigo"] == "881"
    assert r["estado_calculado"] == "07"
    assert r["estado_anterior"] is None


def test_ciclo_no_duplica_en_segunda_ejecucion():
    """Segunda ejecución llama a limpiar_ciclo_anterior (delete NV_CICLO_TRANSICION)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (10, "01", 0, "00", "Cliente A", "2263-9004"),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        servicios.ejecutar_ciclo(_FECHA_VALIDA)

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    delete_trans = any("DELETE FROM NEXOVOLT.NV_CICLO_TRANSICION" in s for s in sqls)
    delete_incons = any("DELETE FROM NEXOVOLT.NV_INCONSISTENCIA" in s and "PRIMER_REPORTE_INVALIDO" in s for s in sqls)
    update_reset = any("UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "PRIMER_REPORTE = 'N'" in s for s in sqls)
    assert delete_trans, "Debe limpiar NV_CICLO_TRANSICION en cada ejecución"
    assert delete_incons, "Debe limpiar inconsistencias 881 anteriores"
    assert update_reset, "Debe resetear PRIMER_REPORTE a N antes de recalcular"


# ── Permisos ──────────────────────────────────────────────────────────────────

def test_ciclo_analista_puede_post():
    factory = APIRequestFactory()
    view = CicloViewSet.as_view({"post": "create"})
    request = factory.post("/ciclos/", {"fecha_corte": "2026-10-31"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("ciclo.views.servicios.ejecutar_ciclo") as mock_exec:
        mock_exec.return_value = {
            "corte_id": 1, "fecha_corte": date(2026, 10, 31),
            "fecha_ejecucion": None, "ejecutada_por": None,
            "primer_reporte": 0, "cambios_estado": 0, "cierres": 0, "rechazados": 0,
            "con_pagos": 0, "a_dudoso": 0, "a_castigada": 0, "normalizadas": 0,
            "transiciones": [], "rechazos": [],
        }
        response = view(request)

    assert response.status_code != 403


def test_ciclo_administrador_no_puede_post():
    factory = APIRequestFactory()
    view = CicloViewSet.as_view({"post": "create"})
    request = factory.post("/ciclos/", {"fecha_corte": "2026-10-31"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = view(request)
    assert response.status_code == 403


def test_matriz_analista_puede_get():
    factory = APIRequestFactory()
    view = MatrizEstadosView.as_view()
    request = factory.get("/matriz-estados/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("ciclo.views.servicios.obtener_matriz") as mock_m:
        mock_m.return_value = {"tipo_cartera": 2, "estados": [], "transiciones": []}
        response = view(request)

    assert response.status_code == 200


def test_matriz_administrador_no_puede_get():
    factory = APIRequestFactory()
    view = MatrizEstadosView.as_view()
    request = factory.get("/matriz-estados/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = view(request)
    assert response.status_code == 403
