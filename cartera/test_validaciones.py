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


def test_estado_sin_homologar_bloquea():
    errores = _errores([("ESTADO_SIN_HOMOLOGAR", "CORRECTIVA", "Estado B no existe", 13, "2259-0013")])
    assert (errores[0]["regla"], errores[0]["campo"]) == ("ESTADO_SIN_HOMOLOGAR", "estado")


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
    conexion, _ = _conexion([(5,), fila, None, None], [])
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


# ── DF-04 · arrastre de abiertas del último corte enviado (RF21, CP-C-08) ──────

_FECHA_GEN = date(2026, 10, 10)
_OMISION_ARRASTRADA = (
    "OMISION_VS_ULTIMO_CORTE", "INFORMATIVA",
    "Obligacion 2241-3302 ya no viene del SAC: se arrastro con los datos del corte enviado del 2026-09-30. "
    "Revise si sigue abierta.",
    9, "2241-3302",
)


def _generar_corte_capturando_sql():
    conexion, cursor = _conexion(
        [(None,), None, None, (1,), (5, _FECHA_GEN), (0,)], []
    )
    llamadas = []
    cursor.execute.side_effect = lambda sql, params=None: llamadas.append((sql, params))
    with patch("cartera.servicios.connection", conexion), \
         patch("cartera.servicios.transaction.atomic", _sin_transaccion), \
         patch("cartera.servicios._todos_los_conceptos_reportables", return_value=[30]):
        servicios.generar_corte(fecha_corte=date(2026, 9, 30))
    return llamadas


def test_cp_c_08_generar_corte_arrastra_las_abiertas_del_ultimo_enviado():
    """CP-C-08 / DF-04: la abierta que ya no viene del SAC entra al corte con los datos del enviado."""
    llamadas = _generar_corte_capturando_sql()
    sqls = [s for s, _ in llamadas]
    i_vista = next(i for i, s in enumerate(sqls) if "FROM NEXOVOLT.V_CALCULO_CORTE WHERE INCLUIR" in s)
    i_aviso = next(i for i, s in enumerate(sqls) if "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in s)
    i_arrastre = next(
        i for i, s in enumerate(sqls) if "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE" in s and "ant." in s
    )
    i_total = next(i for i, s in enumerate(sqls) if "SET TOTAL_REGISTROS" in s)
    assert i_vista < i_aviso < i_arrastre < i_total

    sql, params = llamadas[i_arrastre]
    assert "ant.ESTADO_TU" in sql and "ant.EDAD_MORA" in sql
    assert "ESTADO IN ('ENVIADO', 'ENVIADO_CON_INCONSISTENCIAS')" in sql
    assert "FETCH FIRST 1 ROW ONLY" in sql
    assert "ant.ESTADO_TU NOT IN ('02', '07')" in sql
    assert "NVL(o.ELIMINADA, 'N') = 'N'" in sql
    assert "NOT EXISTS (SELECT 1 FROM NEXOVOLT.V_CALCULO_CORTE v" in sql
    assert "NOT EXISTS (SELECT 1 FROM NEXOVOLT.NV_REPORTE_DETALLE rd" in sql
    assert params == [1, 1, 1]


def test_cp_c_08_la_advertencia_va_primero_y_es_informativa():
    """DF-04: el aviso INFORMATIVA de OMISION_VS_ULTIMO_CORTE se registra antes de las filas."""
    llamadas = _generar_corte_capturando_sql()
    sql, params = next((s, p) for s, p in llamadas if "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in s)
    assert "'OMISION_VS_ULTIMO_CORTE', 'INFORMATIVA'" in sql
    assert "ENVIADO_CON_INCONSISTENCIAS" in sql
    assert params[0] == 1 and params[2:] == [1, 1]


def test_cp_c_08_el_arrastre_copia_las_mismas_columnas_que_las_originales_refinanciadas():
    """DF-04: la lista de columnas es la de DF-03 (ciclo), sin duplicarla."""
    llamadas = _generar_corte_capturando_sql()
    sql = next(s for s, _ in llamadas if "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE" in s and "ant." in s)
    columnas = ciclo_servicios._COLUMNAS_COPIADAS_ORIGINAL + ", " + ciclo_servicios._COLUMNAS_COPIADAS_ORIGINAL_2
    for columna in (c.strip() for c in columnas.split(",")):
        assert columna in sql
        assert f"ant.{columna}" in sql


def test_cp_c_08_omision_informativa_sola_no_bloquea_y_se_informa():
    """DF-04: una arrastrada sola da nivel informativa y deja generar si el corte esta VALIDADO."""
    resultado, reglas = _validaciones([_OMISION_ARRASTRADA], estado="VALIDADO")
    regla = reglas["OMISION_VS_ULTIMO_CORTE"]
    assert regla["nivel"] == "informativa"
    assert resultado["puede_generar"] is True
    assert regla["detalle"] == (
        "3 de 3 obligaciones activas del último corte incluidas. "
        "1 arrastrada(s) con los datos del último corte enviado porque ya no vienen del SAC; revíselas."
    )
    assert regla["obligaciones"][0]["obligacion_id"] == 9
    assert regla["obligaciones"][0]["mensaje"] == _OMISION_ARRASTRADA[2]


def test_cp_c_08_omision_correctiva_despues_de_una_informativa_sigue_bloqueando():
    """DF-04 / CP-C-10: si hay una omision CORRECTIVA mezclada, el nivel es correctiva."""
    filas = [
        _OMISION_ARRASTRADA,
        ("OMISION_VS_ULTIMO_CORTE", "CORRECTIVA", "Omitida", 10, "2250-0987"),
    ]
    resultado, reglas = _validaciones(filas, estado="VALIDADO")
    regla = reglas["OMISION_VS_ULTIMO_CORTE"]
    assert regla["nivel"] == "correctiva"
    assert resultado["puede_generar"] is False
    assert regla["detalle"].startswith("2 de 3 obligaciones activas")


def test_cp_c_08_validar_con_solo_la_arrastrada_pasa_a_validado_con_advertencia():
    """DF-04: la arrastrada no bloquea la validacion y queda como advertencia."""
    resultado, cursor = _validar([_OMISION_ARRASTRADA])
    sqls = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("ESTADO = 'VALIDADO'" in s for s in sqls)
    assert resultado["advertencias"][0]["regla"] == "OMISION_VS_ULTIMO_CORTE"
    assert resultado["advertencias"][0]["numero_obligacion"] == "2241-3302"
    assert cursor.executemany.call_args.args[1][0][:3] == (5, 9, "OMISION_VS_ULTIMO_CORTE")


def test_cp_c_08_una_omision_correctiva_de_la_vista_sigue_bloqueando():
    errores = _errores([("OMISION_VS_ULTIMO_CORTE", "CORRECTIVA", "Omitida", 9, "2241-3302")])
    assert errores[0]["regla"] == "OMISION_VS_ULTIMO_CORTE"


def test_cp_c_08_evaluar_reglas_lee_las_omisiones_informativas_de_nv_inconsistencia():
    _, cursor = _validar([])
    sql = next(
        c.args[0] for c in cursor.execute.call_args_list if "NEXOVOLT.NV_INCONSISTENCIA i" in c.args[0]
    )
    assert "i.REGLA = 'CAMBIO_ESTADO_INVALIDO'" in sql
    assert "i.REGLA = 'OMISION_VS_ULTIMO_CORTE' AND i.SEVERIDAD = 'INFORMATIVA'" in sql


# ── DF-05 · estados del SAC sin homologar (RF48, CP-B-55) ──────────────────────

def _fila_sin_homologar(obligacion_id=None, numero=None):
    return (
        "ESTADO_SIN_HOMOLOGAR", "CORRECTIVA",
        "Obligacion 2260-0001: el estado B del SAC no esta homologado y la obligacion no entra al corte. "
        "Homologuelo (RF48) y vuelva a generar el corte.",
        obligacion_id, numero,
    )


def test_cp_b_55_generar_corte_registra_los_estados_sin_homologar():
    """CP-B-55 / DF-05: una inconsistencia CORRECTIVA por obligacion con estado sin homologar."""
    llamadas = _generar_corte_capturando_sql()
    sqls = [s for s, _ in llamadas]
    i_arrastre = next(
        i for i, s in enumerate(sqls) if "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE" in s and "ant." in s
    )
    i_sin = next(i for i, s in enumerate(sqls) if "'ESTADO_SIN_HOMOLOGAR'" in s)
    i_total = next(i for i, s in enumerate(sqls) if "SET TOTAL_REGISTROS" in s)
    assert i_arrastre < i_sin < i_total

    sql, params = llamadas[i_sin]
    assert "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA" in sql
    assert "'ESTADO_SIN_HOMOLOGAR', 'CORRECTIVA'" in sql
    assert "FROM NEXOVOLT.V_CALCULO_CORTE v" in sql
    assert "NEXOVOLT.NV_HOMOLOGA_ESTADO h" in sql
    assert "h.ACCION IS NOT NULL" in sql
    assert "NVL(o.ELIMINADA, 'N') = 'N'" in sql
    assert params[0] == 1 and params[2] == 1


def test_cp_b_55_no_marca_por_estado_tu_nulo_ni_motivo_de_exclusion():
    """DF-05 / OBS-06: F con ACCION = CIERRE (ESTADO_TU nulo) esta homologado y no se marca."""
    llamadas = _generar_corte_capturando_sql()
    sql = next(s for s, _ in llamadas if "'ESTADO_SIN_HOMOLOGAR'" in s)
    assert "ESTADO_TU IS NULL" not in sql
    assert "MOTIVO_EXCLUSION" not in sql


def test_cp_b_55_obligacion_nueva_sin_homologar_bloquea_la_validacion():
    """DF-05: la obligacion nunca registrada (sin id ni numero) igual bloquea."""
    errores = _errores([_fila_sin_homologar()])
    assert errores == [{
        "regla": "ESTADO_SIN_HOMOLOGAR", "mensaje": _fila_sin_homologar()[2],
        "obligacion_id": None, "numero_obligacion": None, "campo": "estado",
    }]


def test_cp_b_55_validaciones_cuenta_las_obligaciones_sin_homologar():
    """DF-05: nivel correctiva, no deja generar y el detalle cuenta las obligaciones."""
    resultado, reglas = _validaciones([_fila_sin_homologar(), _fila_sin_homologar(4, "2260-0002")],
                                      estado="VALIDADO")
    regla = reglas["ESTADO_SIN_HOMOLOGAR"]
    assert regla["nivel"] == "correctiva"
    assert resultado["puede_generar"] is False
    assert regla["detalle"] == (
        "2 obligación(es) con un estado sin homologar: "
        "homologue el estado del SAC (RF48) y vuelva a generar el corte."
    )


def test_cp_b_55_evaluar_reglas_lee_los_estados_sin_homologar_de_nv_inconsistencia():
    """DF-05: la lectura de NV_INCONSISTENCIA incluye ESTADO_SIN_HOMOLOGAR CORRECTIVA y conserva DF-04."""
    _, cursor = _validar([])
    sql = next(
        c.args[0] for c in cursor.execute.call_args_list if "NEXOVOLT.NV_INCONSISTENCIA i" in c.args[0]
    )
    assert "i.REGLA = 'ESTADO_SIN_HOMOLOGAR' AND i.SEVERIDAD = 'CORRECTIVA'" in sql
    assert "i.REGLA = 'OMISION_VS_ULTIMO_CORTE' AND i.SEVERIDAD = 'INFORMATIVA'" in sql


def test_rf18_la_obligacion_nueva_no_entra_a_un_corte_anterior_a_su_refinanciacion():
    """RF18: REFI-n comparte cliente y proceso con la original; antes de su fecha saldria duplicada."""
    llamadas = _generar_corte_capturando_sql()
    sql = next(
        s for s, _ in llamadas
        if "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE" in s and "V_CALCULO_CORTE v" in s
    )
    assert "WHERE v.INCLUIR = 'S'" in sql
    assert "NOT EXISTS (SELECT 1 FROM NEXOVOLT.NV_REFINANCIACION r" in sql
    assert "r.OBLIGACION_NUEVA_ID = v.OBLIGACION_ID AND r.FECHA > v.FECHA_CORTE" in sql
    assert ":1" not in sql
