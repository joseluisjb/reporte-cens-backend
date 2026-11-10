"""RF21 (universo), RF22 (cierre), RF52 (valores) y RF53 (reglas del Manual). Datos ficticios."""
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from cartera import servicios
from cartera.views import ExtraccionViewSet
from ciclo import servicios as ciclo_servicios
from tests.ayudas import usuario_con_rol

FECHA_CORTE = date(2026, 10, 31)
RESUMEN = (5, FECHA_CORTE, "VALIDADO", None, 3, None, None, 0, None)
factory = APIRequestFactory()


@contextmanager
def _sin_transaccion():
    yield


def _conexion(fetchone, fetchall):
    conexion, cursor = MagicMock(), MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = fetchone
    cursor.fetchall.return_value = fetchall
    return conexion, cursor


def _validar(filas, tiene_ciclo=True):
    """Corre validar_corte con las filas que devolverían la vista y NV_INCONSISTENCIA."""
    conexion, cursor = _conexion(
        [("BORRADOR",), (1 if tiene_ciclo else 0,), RESUMEN], filas
    )
    with patch("cartera.servicios.connection", conexion), \
         patch("cartera.servicios.transaction.atomic", _sin_transaccion):
        resultado = servicios.validar_corte(5)
    return resultado, cursor


def _errores(filas, tiene_ciclo=True):
    with pytest.raises(servicios.CorteConErroresCorrectivos) as exc:
        _validar(filas, tiene_ciclo)
    return exc.value.errores


def _validaciones(filas, estado="BORRADOR", activas=3):
    conexion, _ = _conexion([(estado, FECHA_CORTE), (1,), (activas,)], filas)
    with patch("cartera.servicios.connection", conexion):
        resultado = servicios.validaciones_corte(5)
    return resultado, {r["regla"]: r for r in resultado["resultados"]}


# ── RF53 · reglas del Manual ──────────────────────────────────────────────────

def test_sin_identificacion_es_correctiva_con_la_obligacion_y_el_campo():
    errores = _errores([("SIN_IDENTIFICACION", "CORRECTIVA", "Titular sin identificación", 7, "2259-1092")])
    assert errores == [{
        "regla": "SIN_IDENTIFICACION", "mensaje": "Titular sin identificación",
        "obligacion_id": 7, "numero_obligacion": "2259-1092", "campo": "numero_identificacion",
    }]


def test_numero_de_obligacion_de_21_caracteres_bloquea():
    errores = _errores([("NUMERO_OBLIGACION_INVALIDO", "CORRECTIVA", "Longitud superior a 20", 8, "X" * 21)])
    assert errores[0]["campo"] == "numero_obligacion"


def test_cambio_de_estado_rechazado_por_la_matriz_bloquea():
    errores = _errores([("CAMBIO_ESTADO_INVALIDO", "CORRECTIVA", "Transición no permitida (713)", 9, "2250-0987")])
    assert errores[0]["regla"] == "CAMBIO_ESTADO_INVALIDO"


def test_sin_actualizacion_mensual_va_primero():
    errores = _errores([("SIN_NOMBRE", "CORRECTIVA", "Sin nombre", 7, "2259-1092")], tiene_ciclo=False)
    assert [e["regla"] for e in errores] == ["ACTUALIZACION_MENSUAL", "SIN_NOMBRE"]


def test_entidad_con_marcadores_solo_advierte():
    resultado, _ = _validar([("ENTIDAD_CON_MARCADOR", "INFORMATIVA", "Marcadores XXX", None, None)])
    assert resultado["advertencias"][0]["regla"] == "ENTIDAD_CON_MARCADOR"
    _, reglas = _validaciones([("ENTIDAD_CON_MARCADOR", "INFORMATIVA", "Marcadores XXX", None, None)])
    assert reglas["ENTIDAD_CON_MARCADOR"]["nivel"] == "advertencia"


def test_corte_sin_correctivas_pasa_a_validado_y_copia_a_nv_inconsistencia():
    filas = [("SALDO_MAYOR_VALOR_INICIAL", "INFORMATIVA", "Saldo mayor", 7, "2259-1092")]
    resultado, cursor = _validar(filas)
    sqls = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("ESTADO = 'VALIDADO'" in s for s in sqls)
    assert any("DELETE FROM NEXOVOLT.NV_INCONSISTENCIA" in s for s in sqls)
    insert_sql, filas_insert = cursor.executemany.call_args.args
    assert "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in insert_sql
    assert filas_insert[0][:4] == (5, 7, "SALDO_MAYOR_VALOR_INICIAL", "Saldo mayor")
    assert resultado["advertencias"][0]["campo"] == "valor_saldo"


def test_la_limpieza_no_borra_las_inconsistencias_del_ciclo():
    _, cursor = _validar([])
    delete = next(c for c in cursor.execute.call_args_list if "DELETE" in c.args[0])
    assert delete.args[1] == [5, "PRIMER_REPORTE_INVALIDO", "CAMBIO_ESTADO_INVALIDO"]


# ── RF22 · cierre ─────────────────────────────────────────────────────────────

def test_cierre_completo_pasa():
    resultado, _ = _validar([])
    assert resultado["advertencias"] == []


@pytest.mark.parametrize("motivo, campo", [
    ("Fecha de pago no registrada", "fecha_pago"),
    ("Valor de cuota mayor a cero", "valor_cuota"),
    ("Incoherencia entre tipo y modo de pago", "modo_extincion"),
])
def test_cierre_incompleto_es_correctiva_y_no_cambia_valores(motivo, campo):
    mensaje = f"Obligacion 2259-1092 en cierre (02) presenta datos inconsistentes: {motivo}"
    conexion, cursor = _conexion([("BORRADOR",), (1,)], [("CIERRE_INCOMPLETO", "CORRECTIVA", mensaje, 3, "2259-1092")])
    with patch("cartera.servicios.connection", conexion), \
         pytest.raises(servicios.CorteConErroresCorrectivos) as exc:
        servicios.validar_corte(5)
    assert exc.value.errores[0]["campo"] == campo
    assert not any("UPDATE" in c.args[0] for c in cursor.execute.call_args_list)


# ── GET validaciones (RF21, RF51, RF53) ───────────────────────────────────────

def test_validaciones_agrupa_por_regla_sin_cambiar_el_corte():
    filas = [
        ("SIN_CALIDAD", "CORRECTIVA", "Sin calidad", 7, "2259-1092"),
        ("SIN_CALIDAD", "CORRECTIVA", "Sin calidad", 8, "2250-0987"),
        ("OMISION_VS_ULTIMO_CORTE", "CORRECTIVA", "Omitida", 9, "2241-3302"),
    ]
    resultado, reglas = _validaciones(filas)
    assert resultado["puede_generar"] is False
    assert reglas["SIN_CALIDAD"]["nivel"] == "correctiva"
    assert [o["obligacion_id"] for o in reglas["SIN_CALIDAD"]["obligaciones"]] == [7, 8]
    assert reglas["SIN_CALIDAD"]["obligaciones"][0]["campo"] == "calidad"
    assert reglas["OMISION_VS_ULTIMO_CORTE"]["detalle"] == (
        "2 de 3 obligaciones activas del último corte incluidas."
    )
    assert reglas["CIERRE_INCOMPLETO"]["nivel"] == "ok"
    assert reglas["VALORES_EN_MILES"]["por_confirmar"] is True


def test_validaciones_de_corte_validado_sin_correctivas_puede_generar():
    resultado, reglas = _validaciones([], estado="VALIDADO")
    assert resultado["puede_generar"] is True
    assert reglas["OMISION_VS_ULTIMO_CORTE"]["detalle"] == (
        "3 de 3 obligaciones activas del último corte incluidas."
    )


def test_validaciones_corte_inexistente():
    conexion, _ = _conexion([None], [])
    with patch("cartera.servicios.connection", conexion), pytest.raises(servicios.CorteNoEncontrado):
        servicios.validaciones_corte(99)


def _get_validaciones(**kwargs):
    request = factory.get("/api/extracciones/5/validaciones/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("cartera.views.servicios.validaciones_corte", **kwargs):
        return ExtraccionViewSet.as_view({"get": "validaciones"})(request, pk="5")


def test_get_validaciones_200():
    assert _get_validaciones(return_value={"corte_id": 5}).status_code == 200


def test_get_validaciones_404():
    response = _get_validaciones(side_effect=servicios.CorteNoEncontrado())
    assert response.status_code == 404
    assert response.data == {"detail": "Corte no encontrado."}


# ── RF52 · valores de la obligación ───────────────────────────────────────────

def _detalle_obligacion(valor_inicial, saldo, mora):
    fila = (
        24, "2263-9004", "Titular de prueba", "1234567890",
        "01", "01", 47, 2,
        mora, saldo,
        "N", "N", "N", None,
        date(2026, 1, 31), valor_inicial, 70_000, None,
        None, None, None, "N", FECHA_CORTE,
        "N", 4, 0, "N", "N",
    )
    conexion, _ = _conexion([(5,), fila], [])
    with patch("ciclo.servicios.connection", conexion):
        return ciclo_servicios.obtener_obligacion(24)


def test_valor_inicial_saldo_mora_y_cuota_por_separado():
    detalle = _detalle_obligacion(1_500_000, 1_276_016, 140_000)
    assert (detalle["valor_inicial"], detalle["valor_saldo"], detalle["valor_mora"], detalle["valor_cuota"]) == (
        1_500_000, 1_276_016, 140_000, 70_000,
    )
    assert detalle["advertencias"] == []


def test_saldo_mayor_al_valor_inicial_es_advertencia():
    detalle = _detalle_obligacion(1_000_000, 1_276_016, 0)
    assert detalle["advertencias"][0]["regla"] == "SALDO_MAYOR_VALOR_INICIAL"
