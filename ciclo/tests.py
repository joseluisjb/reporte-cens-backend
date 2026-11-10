from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, call, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol

from ciclo import servicios
from ciclo.serializers import CicloCreateSerializer
from ciclo.views import CicloViewSet, MatrizEstadosView, ObligacionesViewSet


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


# ── Tabla 9 · RF11 · _calcular_edad_mora ─────────────────────────────────────

def test_edad_mora_0_dias():
    assert servicios._calcular_edad_mora(0) == "00"


def test_edad_mora_29_dias():
    assert servicios._calcular_edad_mora(29) == "00"


def test_edad_mora_30_dias():
    assert servicios._calcular_edad_mora(30) == "01"


def test_edad_mora_47_dias():
    assert servicios._calcular_edad_mora(47) == "01"


def test_edad_mora_360_dias():
    assert servicios._calcular_edad_mora(360) == "12"


def test_edad_mora_539_dias():
    assert servicios._calcular_edad_mora(539) == "12"


def test_edad_mora_540_dias():
    assert servicios._calcular_edad_mora(540) == "13"


def test_edad_mora_729_dias():
    assert servicios._calcular_edad_mora(729) == "13"


def test_edad_mora_730_dias():
    assert servicios._calcular_edad_mora(730) == "14"


def test_edad_mora_1000_dias():
    assert servicios._calcular_edad_mora(1000) == "14"


# ── Helpers de prueba para ejecutar_ciclo ─────────────────────────────────────

def _setup_ciclo(
    mock_conn,
    mock_cursor,
    corte_id=1,
    obligaciones=None,
    ultimo_enviado=None,
    es_primer_reporte=True,
    edad_anterior="00",
    estado_anterior=None,
    mora_anterior=0,
    matriz=None,
    marcas_castigo=None,
):
    """
    Monta el mock_cursor con respuestas para ejecutar_ciclo.

    Obligaciones: tuplas de 11 columnas:
      (obligacion_id, estado_tu, valor_mora, edad_mora,
       nombre_titular, numero_obl, dias_mora, fecha_limite_pago, valor_real_pagado,
       valor_saldo, fecha_ultimo_pago)

    marcas_castigo: lista de obligacion_ids con marca de castigo (RF45).
    """
    fecha_corte_bd = date(2026, 10, 31)

    mock_cursor.fetchone.side_effect = [
        (ultimo_enviado,),    # _verificar_fecha_posterior
        (corte_id,),          # _obtener_corte_borrador
        (0,),                 # _guardar_ciclo COUNT(*)
        (fecha_corte_bd,),    # fecha_corte final
    ]

    # Extender las obligaciones a 14 columnas:
    # 0-8 base, 9=valor_saldo, 10=fecha_ultimo_pago (RF12/RF15), 11-13=caducado/atrasos/cuotas (RF14)
    extendidas = []
    defaults_all = (0, None, 'N', 0, 0)
    for obl in (obligaciones or []):
        lst = list(obl)
        for i in range(len(lst), 14):
            lst.append(defaults_all[i - 9])
        extendidas.append(tuple(lst))

    datos_previos = [
        (
            obl[0],
            "S" if es_primer_reporte else "N",
            None if es_primer_reporte else edad_anterior,
            None if es_primer_reporte else estado_anterior,
            0 if es_primer_reporte else mora_anterior,
        )
        for obl in (obligaciones or [])
    ]

    castigo_rows = [(oid,) for oid in (marcas_castigo or [])]

    mock_cursor.fetchall.side_effect = [
        extendidas,           # _cargar_obligaciones_corte
        datos_previos,        # _cargar_datos_previos
        matriz or [],         # _cargar_transiciones_permitidas
        castigo_rows,         # _cargar_marcas_castigo (RF45)
        [],                   # RF13 MOVIMIENTO_POSTERIOR query
    ]


# ── Casos RF10 ────────────────────────────────────────────────────────────────

def test_ciclo_obligacion_nueva_al_dia():
    """Nueva al día (01, sin mora) → Entra en 01, edad 00, primer_reporte=True."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (10, "01", 0, "00", "Cliente A", "2263-9004", 0, None, 0, 0, None),
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
        (11, "01", 85000, "00", "Cliente B", "2263-0001", 23, None, 0, 0, None),
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
        (12, "03", 200000, "02", "Cliente C", "2263-0002", 65, None, 0, 0, None),
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
        (13, "01", 0, "00", "Cliente D", "2263-0003", 0, None, 0, 0, None),
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

    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    rev_update = any("REQUIERE_REVISION" in s and "MOTIVO_REVISION" in s for s in sqls_em)
    assert rev_update, "RF10: debe persistir REQUIERE_REVISION en NV_REPORTE_DETALLE"


def test_ciclo_nueva_estado_07_rechazada():
    """Nueva en estado 07 → Rechazada con error 881."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (14, "07", 0, "00", "Cliente E", "2267-3361", 0, None, 0, 0, None),
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
        (10, "01", 0, "00", "Cliente A", "2263-9004", 0, None, 0, 0, None),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora", lambda a: __import__("contextlib").nullcontext()):
        servicios.ejecutar_ciclo(_FECHA_VALIDA)

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    delete_trans = any("DELETE FROM NEXOVOLT.NV_CICLO_TRANSICION" in s for s in sqls)
    delete_incons = any(
        "DELETE FROM NEXOVOLT.NV_INCONSISTENCIA" in s and "PRIMER_REPORTE_INVALIDO" in s
        for s in sqls
    )
    update_reset = any(
        "UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "PRIMER_REPORTE = 'N'" in s
        for s in sqls
    )
    update_rev_reset = any(
        "UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "REQUIERE_REVISION = 'N'" in s
        for s in sqls
    )
    assert delete_trans, "Debe limpiar NV_CICLO_TRANSICION en cada ejecución"
    assert delete_incons, "Debe limpiar inconsistencias 881 anteriores"
    assert update_reset, "Debe resetear PRIMER_REPORTE a N antes de recalcular"
    assert update_rev_reset, "Debe resetear REQUIERE_REVISION a N antes de recalcular (RF11)"


# ── Casos RF11 ────────────────────────────────────────────────────────────────

@contextmanager
def _patch_ciclo(mock_conn):
    with patch("ciclo.servicios.connection", mock_conn), \
         patch("ciclo.servicios.transaction.atomic", _noop_atomic), \
         patch("ciclo.servicios.registrar_bitacora"), \
         patch("ciclo.servicios.tolerar_fallo_bitacora",
               lambda a: __import__("contextlib").nullcontext()):
        yield


def test_rf11_ciclo_47_dias_edad_01():
    """47 días de mora → Edad 01, RF11, primer_reporte=False."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (20, "01", 100000, "01", "Hotel Mirador", "2258-7731",
         47, date(2026, 9, 14), 0, 0, None),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones,
                 es_primer_reporte=False, edad_anterior="00")

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "01"
    assert t["edad_anterior"] == "00"
    assert t["primer_reporte"] is False
    assert t["requiere_revision"] is False
    assert t["reglas"][0]["rf"] == "RF11"
    assert "47" in t["reglas"][0]["texto"]
    assert "00" in t["reglas"][0]["texto"]
    assert "01" in t["reglas"][0]["texto"]


def test_rf11_ciclo_salto_mayor_tramo_requiere_revision():
    """Edad pasa de 00 a 03 en un corte → requiere_revision=True, edad calculada no cambia."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (21, "01", 300000, "03", "Comercial Los Pinos", "2250-0987",
         90, date(2026, 7, 14), 0, 0, None),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones,
                 es_primer_reporte=False, edad_anterior="00")

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "03"
    assert t["edad_anterior"] == "00"
    assert t["requiere_revision"] is True

    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    rev_update = any("REQUIERE_REVISION" in s and "MOTIVO_REVISION" in s for s in sqls_em)
    assert rev_update, "Debe actualizar REQUIERE_REVISION y MOTIVO_REVISION en BD"


def test_rf11_ciclo_baja_sin_abono_requiere_revision():
    """Edad baja de 02 a 00 sin abono → requiere_revision=True."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (22, "01", 0, "00", "Panadería La Espiga", "2265-2208",
         0, None, 0, 0, None),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones,
                 es_primer_reporte=False, edad_anterior="02")

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "00"
    assert t["edad_anterior"] == "02"
    assert t["requiere_revision"] is True


def test_rf11_ciclo_baja_con_abono_sin_revision():
    """Edad baja con abono que cubre las cuotas más antiguas → sin marca de revisión."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (23, "01", 0, "00", "Colegio San Rafael", "2266-7745",
         0, None, 150000, 0, None),  # valor_real_pagado > 0
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones,
                 es_primer_reporte=False, edad_anterior="02")

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "00"
    assert t["edad_anterior"] == "02"
    assert t["requiere_revision"] is False


def test_rf11_ciclo_edad_14_en_transicion():
    """730 días o más → edad_nueva='14' en la transición del ciclo."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (24, "03", 500000, "14", "Ferretería La Esquina", "2263-9004",
         730, date(2024, 10, 31), 0, 0, None),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones,
                 es_primer_reporte=False, edad_anterior="13")

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "14"
    assert t["primer_reporte"] is False


def test_rf11_obtener_obligacion_edad_14_anios_mora():
    """730 días de mora y edad '14' → anios_mora = 2 (730 // 365)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),   # _obtener_ultimo_corte_ciclo
        (       # obtener_obligacion row (28 columns: 0-26 existing + 27=EN_RECLAMO)
            24, "2263-9004", "Ferretería La Esquina", "1234567890",
            "03", "14", 730, 0,
            500000, 2000000,
            "N", "N", "N", None,
            date(2026, 1, 31), 3000000, 100000, None,
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []  # cuotas_vencidas: none pending

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(24)

    assert result["edad_mora"] == "14"
    assert result["dias_mora"] == 730
    assert result["anios_mora"] == 2


def test_rf11_obtener_obligacion_no_encontrada():
    """Sin ciclo ejecutado → ObligacionNoEncontrada."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.return_value = None  # _obtener_ultimo_corte_ciclo returns None

    with patch("ciclo.servicios.connection", mock_conn):
        with pytest.raises(servicios.ObligacionNoEncontrada):
            servicios.obtener_obligacion(99)


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


def test_obligaciones_analista_puede_get():
    factory = APIRequestFactory()
    view = ObligacionesViewSet.as_view({"get": "list"})
    request = factory.get("/obligaciones/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("ciclo.views.servicios.listar_obligaciones") as mock_lst:
        mock_lst.return_value = {"total": 0, "resultados": []}
        response = view(request)

    assert response.status_code == 200


def test_obligaciones_administrador_no_puede_get():
    factory = APIRequestFactory()
    view = ObligacionesViewSet.as_view({"get": "list"})
    request = factory.get("/obligaciones/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = view(request)
    assert response.status_code == 403


def test_obligaciones_estado_invalido_devuelve_400():
    factory = APIRequestFactory()
    view = ObligacionesViewSet.as_view({"get": "list"})
    request = factory.get("/obligaciones/", {"estado_tu": "99"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = view(request)
    assert response.status_code == 400
    assert "estado_tu" in response.data


def test_obligaciones_q_max_60_caracteres_devuelve_400():
    factory = APIRequestFactory()
    view = ObligacionesViewSet.as_view({"get": "list"})
    q_larga = "A" * 61
    request = factory.get("/obligaciones/", {"q": q_larga})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = view(request)
    assert response.status_code == 400
    assert "q" in response.data


# ── Casos RF14 ────────────────────────────────────────────────────────────────

# Matriz mínima para RF14: transiciones válidas hacia 03 con mora
_MATRIZ_RF14 = [
    # (desde, con_mora_desde, hacia, con_mora_hacia) donde PERMITIDA='S'
    ('01', 'N', '03', 'S'),
    ('01', 'S', '03', 'S'),
    ('03', 'S', '03', 'S'),
    ('08', 'S', '03', 'S'),
    ('04', 'S', '03', 'S'),
    ('10', 'N', '03', 'S'),
    ('10', 'S', '03', 'S'),
    ('11', 'N', '03', 'S'),
    ('11', 'S', '03', 'S'),
    ('12', 'N', '03', 'S'),
    ('12', 'S', '03', 'S'),
]


def test_rf14_caducado_con_mora_pasa_a_03():
    """2250-0987: 6 cuotas atrasadas (tope 4) con mora → estado 03, a_dudoso=1.

    La extracción (DBA) ya pone ESTADO_TU='03'; el ciclo valida la Matriz y
    registra la transición RF14 sin necesidad de un UPDATE adicional.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    # Tupla: 9 base + caducado='S', atrasos_permitidos=4, cuotas_mora=6
    # ESTADO_TU='03' porque el DBA lo calculó durante la extracción
    obligaciones = [
        (30, "03", 1620000, "05", "Empresa Caducada", "2250-0987",
         156, None, 0, 0, None, 'S', 4, 6),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="04",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF14,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_dudoso"] == 1
    assert resultado["cambios_estado"] == 1
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "03"
    assert t["estado_anterior"] == "01"
    assert t["primer_reporte"] is False
    assert t["reglas"][0]["rf"] == "RF14"
    assert "6" in t["reglas"][0]["texto"]
    assert t["reglas"][0]["por_confirmar"] is True

    # Verificar que se insertó la transición en NV_CICLO_TRANSICION
    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    inserta_trans = any("INSERT INTO NEXOVOLT.NV_CICLO_TRANSICION" in s for s in sqls_em)
    assert inserta_trans, "RF14: debe insertar la transición en NV_CICLO_TRANSICION"


def test_rf14_caducado_sin_mora_no_pasa_a_03_requiere_revision():
    """Crédito caducado pero con mora cero → no reporta 03; marcado para revisión."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (31, "01", 0, "00", "Cliente Sin Mora", "2250-1111",
         0, None, 0, 0, None, 'S', 4, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF14,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_dudoso"] == 0
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["requiere_revision"] is True
    assert t["reglas"][0]["rf"] == "RF14"
    assert "sin mora" in t["reglas"][0]["texto"].lower()

    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    rev_update = any("REQUIERE_REVISION" in s and "MOTIVO_REVISION" in s for s in sqls_em)
    assert rev_update, "RF14: debe persistir REQUIERE_REVISION en NV_REPORTE_DETALLE"


def test_rf14_no_caducado_sigue_en_01():
    """3 de 4 atrasos permitidos (no caducado) → sigue en 01; RF11 rige el cambio de edad."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (32, "01", 90000, "02", "Cliente Vigente", "2250-2222",
         75, None, 0, 0, None, 'N', 4, 3),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF14,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_dudoso"] == 0
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["reglas"][0]["rf"] == "RF11"


def test_rf14_estado_anterior_02_caducado_713():
    """Estado anterior Saldada (02) + crédito caducado → Matriz rechaza; inconsistencia 713."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    # El DBA ya calculó ESTADO_TU='03' por ser caducado con mora
    obligaciones = [
        (33, "03", 500000, "04", "Obligación Saldada Caduca", "2250-3333",
         120, None, 0, 0, None, 'S', 3, 4),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="02",  # Saldada: ninguna transición permitida
        mora_anterior=0,
        matriz=_MATRIZ_RF14,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_dudoso"] == 0
    assert resultado["rechazados"] == 1
    assert len(resultado["transiciones"]) == 0
    r = resultado["rechazos"][0]
    assert r["codigo"] == "713"
    assert r["estado_anterior"] == "02"
    assert r["estado_calculado"] == "03"

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    incons_713 = any(
        "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in s and "CAMBIO_ESTADO_INVALIDO" in s
        for s in sqls
    )
    assert incons_713, "RF14: debe insertar inconsistencia CAMBIO_ESTADO_INVALIDO"

    revert = any("UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "ESTADO_TU" in s for s in sqls)
    assert revert, "RF14: debe revertir ESTADO_TU al estado anterior cuando hay 713"


def test_rf14_obtener_obligacion_caducado():
    """obtener_obligacion devuelve caducado=True y atrasos_permitidos reales."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),   # _obtener_ultimo_corte_ciclo
        (       # 28 columnas: 0-26 existentes + col 27=EN_RECLAMO
            30, "2250-0987", "Empresa Caducada", "9876543210",
            "03", "05", 156, 6,
            1620000, 5420000,
            "N", "N", "N", None,
            date(2025, 6, 30), 8000000, 270000, None,
            None, None, None, "N", None,
            "S", 4, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []  # cuotas_vencidas: none pending

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(30)

    assert result["caducado"] is True
    assert result["atrasos_permitidos"] == 4
    assert result["cuotas_atrasadas"] == 6  # usa cuotas_mora (col 7)


def test_rf14_limpiar_ciclo_borra_713():
    """Segunda ejecución limpia también las inconsistencias CAMBIO_ESTADO_INVALIDO."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (10, "01", 0, "00", "Cliente A", "2263-9004", 0, None, 0),
    ]
    _setup_ciclo(mock_conn, mock_cursor, obligaciones=obligaciones)

    with _patch_ciclo(mock_conn):
        servicios.ejecutar_ciclo(_FECHA_VALIDA)

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    limpia_713 = any(
        "DELETE FROM NEXOVOLT.NV_INCONSISTENCIA" in s and "CAMBIO_ESTADO_INVALIDO" in s
        for s in sqls
    )
    assert limpia_713, "Debe limpiar inconsistencias 713 en cada ejecución"


# ── Casos RF45 ────────────────────────────────────────────────────────────────

_MATRIZ_RF45 = [
    # (desde, con_mora_desde, hacia, con_mora_hacia) donde PERMITIDA='S'
    ('01', 'N', '06', 'S'),
    ('01', 'S', '06', 'S'),
    ('03', 'S', '06', 'S'),
    ('04', 'S', '06', 'S'),
    ('06', 'S', '06', 'S'),
    ('08', 'S', '06', 'S'),
    ('10', 'S', '06', 'S'),
    ('11', 'S', '06', 'S'),
    ('12', 'S', '06', 'S'),
]


def test_rf45_castigo_con_mora_pasa_a_06():
    """2244-6410: con marca de castigo y mora → estado 06, a_castigada=1."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (40, "06", 850000, "04", "Empresa Castigada", "2244-6410",
         130, None, 0, 0, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="03",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF45,
        marcas_castigo=[40],
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_castigada"] == 1
    assert resultado["cambios_estado"] == 1
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "06"
    assert t["estado_anterior"] == "01"
    assert t["primer_reporte"] is False
    assert t["reglas"][0]["rf"] == "RF45"
    assert "Castigada" in t["reglas"][0]["texto"]
    assert t["reglas"][0]["por_confirmar"] is False

    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    inserta_trans = any("INSERT INTO NEXOVOLT.NV_CICLO_TRANSICION" in s for s in sqls_em)
    assert inserta_trans, "RF45: debe insertar la transición en NV_CICLO_TRANSICION"


def test_rf45_castigo_sin_mora_requiere_revision():
    """Marca de castigo con mora cero → no reporta 06; marcado para revisión."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (41, "01", 0, "00", "Cliente Sin Mora", "2244-7001",
         0, None, 0, 0, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF45,
        marcas_castigo=[41],
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_castigada"] == 0
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["requiere_revision"] is True
    assert t["reglas"][0]["rf"] == "RF45"
    assert "sin mora" in t["reglas"][0]["texto"].lower()

    sqls_em = [str(c.args[0]) for c in mock_cursor.executemany.call_args_list if c.args]
    rev_update = any("REQUIERE_REVISION" in s and "MOTIVO_REVISION" in s for s in sqls_em)
    assert rev_update, "RF45: debe persistir REQUIERE_REVISION en NV_REPORTE_DETALLE"


def test_rf45_primer_reporte_castigo_edad_00_rechazado_881():
    """Primer reporte en estado 06 con edad 00 → rechazado (881); _valida_881 lo descarta."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (42, "06", 500000, "00", "Nueva Castigada", "2244-7002",
         0, None, 0, 0, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=True,
        matriz=_MATRIZ_RF45,
        marcas_castigo=[42],
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["rechazados"] == 1
    assert resultado["a_castigada"] == 0
    r = resultado["rechazos"][0]
    assert r["codigo"] == "881"
    assert r["estado_calculado"] == "06"


def test_rf45_estado_anterior_02_castigo_713():
    """Estado anterior Saldada (02) + castigo → Matriz rechaza; inconsistencia 713."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (43, "06", 400000, "03", "Obligación Saldada Castigada", "2244-7003",
         95, None, 0, 0, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="02",
        mora_anterior=0,
        matriz=_MATRIZ_RF45,
        marcas_castigo=[43],
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_castigada"] == 0
    assert resultado["rechazados"] == 1
    assert len(resultado["transiciones"]) == 0
    r = resultado["rechazos"][0]
    assert r["codigo"] == "713"
    assert r["estado_anterior"] == "02"
    assert r["estado_calculado"] == "06"

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    incons_713 = any(
        "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in s and "CAMBIO_ESTADO_INVALIDO" in s
        for s in sqls
    )
    assert incons_713, "RF45: debe insertar inconsistencia CAMBIO_ESTADO_INVALIDO"

    revert = any("UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "ESTADO_TU" in s for s in sqls)
    assert revert, "RF45: debe revertir ESTADO_TU al estado anterior cuando hay 713"


def test_rf45_sin_castigo_no_pasa_a_06():
    """Sin marca de castigo: RF45 no actúa; la obligación sigue el flujo normal (RF11)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (44, "01", 90000, "02", "Cliente Normal", "2244-7004",
         75, None, 0, 0, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=0,
        matriz=_MATRIZ_RF45,
        marcas_castigo=[],
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["a_castigada"] == 0
    assert resultado["rechazados"] == 0
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["reglas"][0]["rf"] == "RF11"


# ── Casos RF17 ────────────────────────────────────────────────────────────────

def test_rf17_ciclo_abono_parcial_paga_cuota_antigua():
    """2258-7731: 2 cuotas de $70.000; abono de $70.000 → paga la más antigua.
    Mora restante $70.000; 1 cuota en mora; con_pagos = 1; regla RF17 en la transición.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    # 9 base cols + 2 (RF12/15: saldo, fecha_pago) + 3 (RF14: caducado, atrasos, cuotas)
    # valor_mora=70000 (resta), edad_mora='01', valor_real_pagado=70000, valor_saldo>0
    obligaciones = [
        (20, "01", 70000, "01", "Hotel Mirador", "2258-7731",
         47, date(2026, 9, 14), 70000, 70000, None, 'N', 0, 1),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=70000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["con_pagos"] == 1
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF17" in rfs, "RF17 debe aparecer en las reglas de la transición"
    rf17 = next(r for r in t["reglas"] if r["rf"] == "RF17")
    assert "70" in rf17["texto"], "El texto debe mencionar el valor del abono"
    assert rf17["por_confirmar"] is True


def test_rf17_ciclo_abono_menor_cuota_edad_no_baja():
    """Abono de $30.000 (menor a la cuota de $70.000) → la cuota sigue vencida.
    La edad de mora no baja; RF17 aparece en la transición; con_pagos = 1.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    # mora sigue = 70000; edad sigue = 01; valor pagado = 30000 (parcial)
    obligaciones = [
        (21, "01", 70000, "01", "Hotel Mirador", "2258-7731",
         47, date(2026, 9, 14), 30000, 100000, None, 'N', 0, 1),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=70000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["con_pagos"] == 1
    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "01"
    assert t["requiere_revision"] is False
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF17" in rfs


def test_rf17_ciclo_cubre_mora_queda_saldo():
    """Abono que cubre toda la mora pero la obligación conserva saldo.
    La edad baja a 00 con abono → no marca revisión; RF17 aparece; con_pagos = 1.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    # mora=0 ahora (pagó la mora), saldo>0, valor_real_pagado>0, edad='00'
    # fecha_ultimo_pago presente → RF47 dispara sin revisión (mora_anterior > 0)
    obligaciones = [
        (22, "01", 0, "00", "Panadería La Espiga", "2265-2208",
         0, None, 140000, 50000, date(2026, 10, 10), 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=140000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["con_pagos"] == 1
    t = resultado["transiciones"][0]
    assert t["edad_nueva"] == "00"
    assert t["requiere_revision"] is False, "Edad bajó CON abono: no debe marcarse para revisión"
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF17" in rfs


def test_rf17_ciclo_cubre_saldo_cierra_rf12():
    """Abono que cubre todo el saldo desde estado Vigente → cierre en Saldada (RF12).
    Con_pagos = 0: el cierre es RF12, no RF17.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    # saldo=0, fecha_ultimo_pago presente → rama RF12
    obligaciones = [
        (23, "01", 0, "00", "Colegio San Rafael", "2266-7745",
         0, None, 140000, 0, date(2026, 10, 15), 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=140000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["cierres"] == 1
    assert resultado["con_pagos"] == 0, "RF12 cierre no cuenta como con_pagos"
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "02"
    assert t["reglas"][0]["rf"] == "RF12"


def test_rf17_obtener_obligacion_cuotas_vencidas_y_pagos():
    """obtener_obligacion devuelve cuotas_vencidas y pagos desde V_MORA_OBLIGACION."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),   # _obtener_ultimo_corte_ciclo
        (       # 28 columnas; col 25=VALOR_REAL_PAGADO=70000, col 26=ELIMINADA, col 27=EN_RECLAMO
            20, "2258-7731", "Hotel Mirador", "2258773100",
            "01", "01", 47, 1,
            70000, 70000,
            "N", "N", "N", None,
            date(2026, 1, 31), 500000, 70000, date(2026, 9, 14),
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 70000, "N", "N",
        ),
    ]
    # cuotas_vencidas desde V_MORA_OBLIGACION: 1 cuota pendiente
    mock_cursor.fetchall.return_value = [
        (date(2026, 9, 14), 70000, 47),
    ]

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(20)

    assert len(result["cuotas_vencidas"]) == 1
    cv = result["cuotas_vencidas"][0]
    assert cv["fecha_vencimiento"] == "2026-09-14"
    assert cv["valor_pendiente"] == 70000
    assert cv["dias"] == 47

    assert len(result["pagos"]) == 1
    pago = result["pagos"][0]
    assert pago["valor"] == 70000
    assert pago["fecha_corte"] == "2026-10-31"
    assert "2026-09-14" in pago["aplicado_a"]


def test_rf17_obtener_obligacion_sin_pagos_sin_cuotas():
    """Obligación al día y sin pagos en el periodo → cuotas_vencidas=[] y pagos=[]."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            25, "2263-9004", "Cliente al Día", "1111111111",
            "01", "00", 0, 0,
            0, 100000,
            "N", "N", "N", None,
            date(2026, 1, 31), 200000, 50000, None,
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(25)

    assert result["cuotas_vencidas"] == []
    assert result["pagos"] == []


# ── Casos RF19 ────────────────────────────────────────────────────────────────

def test_rf19_resumen_cuota_no_facturada_no_cuenta():
    """Cuota aún no facturada no incrementa cuotas_mora (RF19).

    V_MORA_OBLIGACION / NV_REPORTE_DETALLE.CUOTAS_MORA ya excluye cuotas no facturadas (DBA).
    El backend lee el valor sin modificarlo: CUOTAS_MORA=0 → la obligación cae en al_dia.
    """
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (5,),                   # _obtener_ultimo_corte_ciclo
        (date(2026, 10, 31),),  # FECHA_CORTE del corte
        (1, 0, 0, 0),           # cuotas_mora aggregate: al_dia=1 (cuota no facturada excluida)
        (0,),                   # COUNT eliminadas
    ]
    # 1 obligación abierta (01); CUOTAS_MORA=0 porque la cuota aún no está facturada
    mock_cursor.fetchall.side_effect = [
        [("01", 1)],    # GROUP BY ESTADO_TU
        [],             # financiaciones_nuevas
    ]

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_resumen_obligaciones()

    assert result["abiertas"] == 1
    assert result["por_cuotas_mora"]["al_dia"] == 1, "Cuota no facturada no cuenta → al_dia"
    assert result["por_cuotas_mora"]["una"] == 0


def test_rf19_resumen_12_obligaciones_grupos_suman_abiertas():
    """Resumen con 12 obligaciones: los 4 grupos de cuotas_mora suman las abiertas (RF19)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (3,),                           # _obtener_ultimo_corte_ciclo
        (date(2026, 10, 31),),          # FECHA_CORTE del corte
        (2, 2, 2, 3),                   # al_dia=2, una=2, dos_a_tres=2, cuatro_o_mas=3
        (0,),                           # COUNT eliminadas
    ]
    # por_estado: 9 abiertas (01) + 3 cerradas (02); total 12
    mock_cursor.fetchall.side_effect = [
        [("01", 9), ("02", 3)],
        [],     # financiaciones_nuevas
    ]

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_resumen_obligaciones()

    assert result["total"] == 12
    assert result["abiertas"] == 9
    pcm = result["por_cuotas_mora"]
    grupos = pcm["al_dia"] + pcm["una"] + pcm["dos_a_tres"] + pcm["cuatro_o_mas"]
    assert grupos == result["abiertas"], "Los 4 grupos deben sumar las obligaciones abiertas"


def test_rf19_resumen_sin_ciclo_devuelve_vacios():
    """Sin ningún ciclo ejecutado, el resumen devuelve totales en cero."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.return_value = None   # _obtener_ultimo_corte_ciclo → sin ciclos

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_resumen_obligaciones()

    assert result["fecha_ultimo_ciclo"] is None
    assert result["total"] == 0
    assert result["abiertas"] == 0
    assert result["por_estado"] == []
    assert result["financiaciones_nuevas"] == []


def test_rf19_resumen_view_200():
    """GET /api/obligaciones/resumen/ devuelve 200 con la estructura del contrato."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (3,),
        (date(2026, 10, 31),),
        (2, 2, 2, 3),
        (0,),                   # COUNT eliminadas
    ]
    mock_cursor.fetchall.side_effect = [
        [("01", 9), ("02", 3)],
        [],
    ]

    factory = APIRequestFactory()
    view = ObligacionesViewSet.as_view({"get": "resumen"})
    request = factory.get("/obligaciones/resumen/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))

    with patch("ciclo.servicios.connection", mock_conn):
        response = view(request)

    assert response.status_code == 200
    data = response.data
    assert "fecha_ultimo_ciclo" in data
    assert "total" in data
    assert "abiertas" in data
    assert "por_estado" in data
    assert "eliminadas" in data
    assert "por_cuotas_mora" in data
    assert "financiaciones_nuevas" in data
    pcm = data["por_cuotas_mora"]
    assert all(k in pcm for k in ("al_dia", "una", "dos_a_tres", "cuatro_o_mas"))


# ── Casos RF46 ────────────────────────────────────────────────────────────────

def test_rf46_en03_paga_mora_vuelve_01():
    """Obligación en Dudoso (03) paga la mora pero conserva saldo → vuelve a 01 (RF46)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (40, "03", 0, "00", "Comercial Éxito", "2270-4001",
         0, None, 500000, 300000, date(2026, 10, 15), 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="03",
        estado_anterior="03",
        mora_anterior=500000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["normalizadas"] == 1
    assert resultado["cambios_estado"] == 1
    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    assert t["requiere_revision"] is False
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF46" in rfs
    assert "RF47" in rfs


def test_rf46_en06_mora_pendiente_mantiene_06():
    """Obligación en Castigada (06) con mora aún positiva → no normaliza, sigue en 06."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (41, "06", 200000, "02", "Ferretería Norte", "2270-4002",
         75, date(2026, 9, 1), 100000, 400000, None, 'N', 0, 2),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="02",
        estado_anterior="06",
        mora_anterior=300000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["normalizadas"] == 0
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "06"
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF46" not in rfs


def test_rf46_estado_ley_vuelve_01():
    """Obligación en estado de ley (10) paga la mora y conserva saldo → vuelve a 01."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (42, "10", 0, "00", "Cooperativa Ley", "2270-4003",
         0, None, 400000, 600000, date(2026, 10, 20), 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="04",
        estado_anterior="10",
        mora_anterior=400000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["normalizadas"] == 1
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "01"
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF46" in rfs
    assert "RF47" in rfs


def test_rf46_sin_mora_previa_no_normaliza():
    """Estado 03 pero sin mora previa (mora_anterior=0) → no es RF46."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (43, "03", 0, "00", "Sin mora previa", "2270-4004",
         0, None, 0, 100000, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="03",
        mora_anterior=0,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert resultado["normalizadas"] == 0
    t = resultado["transiciones"][0]
    assert t["estado_nuevo"] == "03"


# ── Casos RF47 ────────────────────────────────────────────────────────────────

def test_rf47_ciclo_queda_al_dia_reporta_pago():
    """Obligación en 01 con mora previa que queda al día con fecha_pago → RF47 sin revisión."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (50, "01", 0, "00", "Almacén Sol", "2271-5001",
         0, None, 300000, 200000, date(2026, 10, 12), 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="02",
        estado_anterior="01",
        mora_anterior=300000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    assert len(resultado["transiciones"]) == 1
    t = resultado["transiciones"][0]
    assert t["requiere_revision"] is False
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF47" in rfs
    rf47 = next(r for r in t["reglas"] if r["rf"] == "RF47")
    assert "fecha de pago" in rf47["texto"]

    sqls = [str(c.args[0]) for c in mock_cursor.execute.call_args_list if c.args]
    pago_mora_sql = any(
        "UPDATE NEXOVOLT.NV_REPORTE_DETALLE" in s and "FECHA_PAGO" in s and "MODO_EXTINCION" in s
        for s in sqls
    )
    assert pago_mora_sql, "RF47: debe actualizar FECHA_PAGO, MODO_EXTINCION y TIPO_PAGO"


def test_rf47_ciclo_sin_fecha_pago_requiere_revision():
    """Mora liquidada sin fecha_pago registrada → RF47 marca para revisión."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (51, "01", 0, "00", "Panadería Tres", "2271-5002",
         0, None, 0, 150000, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="01",
        estado_anterior="01",
        mora_anterior=200000,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    assert t["requiere_revision"] is True
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF47" in rfs


def test_rf47_ciclo_sin_mora_previa_no_aplica():
    """Obligación sin mora previa (mora_anterior=0) → RF47 no dispara aunque mora actual sea 0."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (52, "01", 0, "00", "Librería Paz", "2271-5003",
         0, None, 0, 80000, None, 'N', 0, 0),
    ]
    _setup_ciclo(
        mock_conn, mock_cursor,
        obligaciones=obligaciones,
        es_primer_reporte=False,
        edad_anterior="00",
        estado_anterior="01",
        mora_anterior=0,
    )

    with _patch_ciclo(mock_conn):
        resultado = servicios.ejecutar_ciclo(_FECHA_VALIDA)

    t = resultado["transiciones"][0]
    rfs = [r["rf"] for r in t["reglas"]]
    assert "RF47" not in rfs
    assert t["requiere_revision"] is False


def test_rf47_obtener_obligacion_expone_pago_mora():
    """obtener_obligacion devuelve pago_mora cuando MODO_EXTINCION está registrado y estado != 02/07."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),   # _obtener_ultimo_corte_ciclo
        (       # 28 columnas: col 26=ELIMINADA, col 27=EN_RECLAMO
            50, "2271-5001", "Almacén Sol", "1234567890",
            "01", "00", 0, 0,
            0, 200000,
            "N", "N", "N", None,
            date(2026, 1, 31), 500000, 70000, None,
            date(2026, 10, 12), "01", "01", "N", date(2026, 10, 31),
            "N", 0, 300000, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(50)

    assert result["cierre"] is None
    pm = result["pago_mora"]
    assert pm is not None
    assert pm["fecha_pago"] == "2026-10-12"
    assert pm["modo_extincion"]["codigo"] == "01"
    assert pm["tipo_pago"]["codigo"] == "01"
    assert pm["valor_real_pagado"] == 300000


def test_rf47_obtener_obligacion_pago_mora_sin_fecha():
    """pago_mora se expone aunque fecha_pago sea NULL (obligación marcada para revisión)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            51, "2271-5002", "Panadería Tres", "0987654321",
            "01", "00", 0, 0,
            0, 150000,
            "N", "N", "S", "RF47 · Quedó al día sin fecha de pago registrada; requiere revisión para completar el reporte",
            date(2026, 1, 31), 300000, 70000, None,
            None, "01", "01", "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(51)

    pm = result["pago_mora"]
    assert pm is not None
    assert pm["fecha_pago"] is None
    assert pm["modo_extincion"]["codigo"] == "01"


def test_rf47_obtener_obligacion_sin_pago_mora_es_none():
    """Obligación vigente sin pago de mora registrado → pago_mora es None."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            52, "2271-5003", "Librería Paz", "1122334455",
            "01", "00", 0, 0,
            0, 80000,
            "N", "N", "N", None,
            date(2026, 1, 31), 200000, 50000, None,
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(52)

    assert result["pago_mora"] is None


# ── Casos RF49 ────────────────────────────────────────────────────────────────

def test_rf49_fecha_exigibilidad_cuota_antigua():
    """Dos cuotas sin pagar; la más antigua del 14/08 → fecha_exigibilidad = '2026-08-14'."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            60, "2272-6001", "Empresa Solar", "5566778899",
            "03", "02", 75, 2,
            140000, 500000,
            "N", "N", "N", None,
            date(2026, 1, 31), 800000, 70000, date(2026, 8, 14),
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    # Dos cuotas vencidas; la primera (más antigua) vence el 14/08
    mock_cursor.fetchall.return_value = [
        (date(2026, 8, 14), 70000, 47),
        (date(2026, 9, 14), 70000, 17),
    ]

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(60)

    assert result["fecha_exigibilidad"] == "2026-08-14"
    assert result["valor_mora"] == 140000


def test_rf49_anios_mora_edad_14_800_dias():
    """800 días de mora con edad '14' → anios_mora = 2 (800 // 365)."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            61, "2272-6002", "Cooperativa Sur", "9988776655",
            "03", "14", 800, 0,
            500000, 2000000,
            "N", "N", "N", None,
            date(2024, 10, 31), 3000000, 100000, date(2024, 10, 31),
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(61)

    assert result["edad_mora"] == "14"
    assert result["dias_mora"] == 800
    assert result["anios_mora"] == 2


def test_rf49_al_dia_exigibilidad_nula():
    """Obligación sin mora (valor_mora = 0) → fecha_exigibilidad es null."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    mock_cursor.fetchone.side_effect = [
        (1,),
        (
            62, "2272-6003", "Hotel del Norte", "1122334466",
            "01", "00", 0, 0,
            0, 300000,
            "N", "N", "N", None,
            date(2026, 1, 31), 500000, 70000, date(2026, 9, 14),
            None, None, None, "N", date(2026, 10, 31),
            "N", 0, 0, "N", "N",
        ),
    ]
    mock_cursor.fetchall.return_value = []

    with patch("ciclo.servicios.connection", mock_conn):
        result = servicios.obtener_obligacion(62)

    assert result["fecha_exigibilidad"] is None
    assert result["anios_mora"] is None
