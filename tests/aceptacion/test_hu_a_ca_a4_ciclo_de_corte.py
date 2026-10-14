"""HU-A · CA-A4 — "Se mantiene historial de reportes y de deudores, actualizado mensualmente"
(RF6, RF8, RF9).

Recorre el ciclo del corte tal como lo hace el Analista: validar el BORRADOR, registrar el envío
a TransUnion y comprobar que el estado queda guardado. Incluye la actualización mensual (RF9).

Casos de la matriz: docs/pruebas/matriz-HU-A.md
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol
from tests.aceptacion.ayudas import (
    CORTE_ID,
    FECHA_CORTE,
    FECHA_EJECUCION,
    OraculoFalso,
    sin_transaccion,
)

from cartera.views import ExtraccionViewSet

factory = APIRequestFactory()

_COMANDO = "historial.management.commands.actualizar_estados_mensual"


def _fila_resumen(estado):
    """Fila de NV_CORTE tal como la devuelve la consulta de resumen."""
    return (CORTE_ID, FECHA_CORTE, estado, FECHA_EJECUCION, 5, None, None, 45_000_000, None)


def _llamar(vista, metodo, ruta, datos=None, oraculo=None):
    request = getattr(factory, metodo)(ruta, datos or {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.servicios.connection", oraculo.conexion), \
         patch("cartera.servicios.transaction.atomic", sin_transaccion), \
         patch("cartera.servicios.registrar_bitacora"):
        return vista(request, pk=str(CORTE_ID))


# ── CP-A-18 · validar y registrar el envío ───────────────────────────────────

def test_cp_a_18_un_borrador_sin_errores_correctivos_queda_validado():
    oraculo = OraculoFalso(
        fetchone=[
            ("BORRADOR",),              # estado actual del corte
            _fila_resumen("VALIDADO"),  # resumen después de validar
        ],
        fetchall=[
            [],                         # la vista de validación no reporta ninguna regla
        ],
    )

    response = _llamar(
        ExtraccionViewSet.as_view({"post": "validar"}),
        "post", f"/api/extracciones/{CORTE_ID}/validar/", oraculo=oraculo,
    )

    assert response.status_code == 200
    assert response.data["estado"] == "VALIDADO"
    assert response.data["advertencias"] == []


def test_cp_a_18_un_corte_con_errores_correctivos_no_se_valida():
    """Flujo alterno: los errores correctivos se devuelven para que el Analista los resuelva."""
    oraculo = OraculoFalso(
        fetchone=[("BORRADOR",)],
        fetchall=[[
            ("SIN_IDENTIFICACION", "CORRECTIVA", "Falta el tipo o el número de identificación"),
        ]],
    )

    response = _llamar(
        ExtraccionViewSet.as_view({"post": "validar"}),
        "post", f"/api/extracciones/{CORTE_ID}/validar/", oraculo=oraculo,
    )

    assert response.status_code == 409
    assert response.data["errores"][0]["regla"] == "SIN_IDENTIFICACION"


def test_cp_a_18_un_corte_validado_queda_enviado_con_su_fecha():
    """Postcondición de RF6: el envío mensual queda registrado con su fecha."""
    fecha_envio = date(2026, 10, 3)
    oraculo = OraculoFalso(
        fetchone=[
            ("VALIDADO", FECHA_CORTE),  # estado y fecha del corte
            _fila_resumen("ENVIADO"),   # resumen después de registrar el envío
        ],
    )

    response = _llamar(
        ExtraccionViewSet.as_view({"post": "registrar_envio"}),
        "post", f"/api/extracciones/{CORTE_ID}/registrar-envio/",
        {"fecha_envio": str(fecha_envio)}, oraculo,
    )

    assert response.status_code == 200
    assert response.data["estado"] == "ENVIADO"
    assert fecha_envio in oraculo.parametros  # la fecha de envío se guarda en el corte


def test_cp_a_18_no_se_registra_el_envio_de_un_corte_sin_validar():
    oraculo = OraculoFalso(fetchone=[("BORRADOR", FECHA_CORTE)])

    response = _llamar(
        ExtraccionViewSet.as_view({"post": "registrar_envio"}),
        "post", f"/api/extracciones/{CORTE_ID}/registrar-envio/",
        {"fecha_envio": "2026-10-03"}, oraculo,
    )

    assert response.status_code == 409
    assert "VALIDADO" in response.data["detail"]


def test_cp_a_18_la_fecha_de_envio_no_puede_ser_anterior_al_corte():
    oraculo = OraculoFalso(fetchone=[("VALIDADO", FECHA_CORTE)])

    response = _llamar(
        ExtraccionViewSet.as_view({"post": "registrar_envio"}),
        "post", f"/api/extracciones/{CORTE_ID}/registrar-envio/",
        {"fecha_envio": "2026-09-01"}, oraculo,
    )

    assert response.status_code == 400
    assert "anterior" in response.data["detail"].lower()


# ── CP-A-22 y CP-A-23 · actualización mensual (RF9) ──────────────────────────

_RESULTADO_MENSUAL = {
    "id": 7,
    "obligaciones": 150,
    "saldo_consolidado": 45_000_000,
    "estado": "BORRADOR",
    "grupo": None,
}


def test_cp_a_22_la_actualizacion_mensual_genera_el_corte_y_deja_bitacora():
    with patch(f"{_COMANDO}.generar_corte", return_value=_RESULTADO_MENSUAL) as generar, \
         patch(f"{_COMANDO}.registrar_bitacora") as bitacora, \
         patch(f"{_COMANDO}.transaction.atomic", sin_transaccion):
        salida = StringIO()
        call_command("actualizar_estados_mensual",
                     fecha_corte=str(FECHA_CORTE), stdout=salida)

    assert generar.call_args.kwargs["fecha_corte"] == FECHA_CORTE
    bitacora.assert_called_once()
    assert "ACTUALIZACION_MENSUAL" in bitacora.call_args.args
    assert "Corte 7 generado correctamente." in salida.getvalue()


def test_cp_a_23_la_simulacion_no_guarda_nada():
    """`--simular` muestra el resultado y revierte: no toca el historial."""
    with patch(f"{_COMANDO}.generar_corte", return_value=_RESULTADO_MENSUAL), \
         patch(f"{_COMANDO}.registrar_bitacora") as bitacora, \
         patch(f"{_COMANDO}.transaction.atomic", sin_transaccion), \
         patch(f"{_COMANDO}.transaction.set_rollback") as revertir:
        salida = StringIO()
        call_command("actualizar_estados_mensual", simular=True, stdout=salida)

    revertir.assert_called_once_with(True)
    bitacora.assert_not_called()
    assert "SIMULACIÓN" in salida.getvalue()


def test_cp_a_22_una_fecha_de_corte_invalida_detiene_la_actualizacion():
    with patch(f"{_COMANDO}.generar_corte") as generar:
        with pytest.raises(CommandError):
            call_command("actualizar_estados_mensual", fecha_corte="30-09-2026")
    generar.assert_not_called()
