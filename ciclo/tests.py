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
    estado_anterior="01",
    mora_anterior=0,
    matriz=None,
):
    """
    Monta el mock_cursor con respuestas para ejecutar_ciclo.

    Obligaciones: tuplas de 9 a 12 columnas:
      (obligacion_id, estado_tu, valor_mora, edad_mora,
       nombre_titular, numero_obl, dias_mora, fecha_limite_pago, valor_real_pagado
       [, caducado='N', atrasos_permitidos=0, cuotas_mora=0])  -- RF14

    matriz: lista de tuplas (estado_desde, con_mora_desde, estado_hacia, con_mora_hacia)
      que se consideran PERMITIDA='S'. Si es None, se usa una lista vacía.
    """
    fecha_corte_bd = date(2026, 10, 31)

    mock_cursor.fetchone.side_effect = [
        (ultimo_enviado,),    # _verificar_fecha_posterior
        (corte_id,),          # _obtener_corte_borrador
        (0,),                 # _guardar_ciclo COUNT(*)
        (fecha_corte_bd,),    # fecha_corte final
    ]

    # Extender las obligaciones a 12 columnas con valores por defecto para RF14
    extendidas = []
    defaults_rf14 = ('N', 0, 0)  # caducado, atrasos_permitidos, cuotas_mora
    for obl in (obligaciones or []):
        lst = list(obl)
        for i in range(len(lst), 12):
            lst.append(defaults_rf14[i - 9])
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

    mock_cursor.fetchall.side_effect = [
        extendidas,                # _cargar_obligaciones_corte
        datos_previos,             # _cargar_datos_previos
        matriz or [],              # _cargar_transiciones_permitidas
    ]


# ── Casos RF10 ────────────────────────────────────────────────────────────────

def test_ciclo_obligacion_nueva_al_dia():
    """Nueva al día (01, sin mora) → Entra en 01, edad 00, primer_reporte=True."""
    mock_conn, mock_cursor = _mock_conn_multiple()
    obligaciones = [
        (10, "01", 0, "00", "Cliente A", "2263-9004", 0, None, 0),
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
        (11, "01", 85000, "00", "Cliente B", "2263-0001", 23, None, 0),
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
        (12, "03", 200000, "02", "Cliente C", "2263-0002", 65, None, 0),
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
        (13, "01", 0, "00", "Cliente D", "2263-0003", 0, None, 0),
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
        (14, "07", 0, "00", "Cliente E", "2267-3361", 0, None, 0),
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
        (10, "01", 0, "00", "Cliente A", "2263-9004", 0, None, 0),
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
         47, date(2026, 9, 14), 0),
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
         90, date(2026, 7, 14), 0),
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
         0, None, 0),
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
         0, None, 150000),  # valor_real_pagado > 0
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
         730, date(2024, 10, 31), 0),
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
        (       # obtener_obligacion row (20 columns: +CADUCADO, +ATRASOS_PERMITIDOS)
            24, "2263-9004", "Ferretería La Esquina", "1234567890",
            "03", "14", 730, 0,
            500000, 2000000,
            "N", "N", "N", None,
            date(2026, 1, 31), 3000000, 100000, None,
            "N", 0,
        ),
    ]

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
         156, None, 0, 'S', 4, 6),
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
         0, None, 0, 'S', 4, 0),
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
         75, None, 0, 'N', 4, 3),
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
         120, None, 0, 'S', 3, 4),
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
        (       # 20 columnas: 18 base + CADUCADO='S', ATRASOS_PERMITIDOS=4
            30, "2250-0987", "Empresa Caducada", "9876543210",
            "03", "05", 156, 6,
            1620000, 5420000,
            "N", "N", "N", None,
            date(2025, 6, 30), 8000000, 270000, None,
            "S", 4,
        ),
    ]

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
