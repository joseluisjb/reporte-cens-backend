"""RF20 (archivo plano del reporte total) y RF51 (valores en miles). Datos ficticios."""
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from cartera import servicios
from cartera.archivo_plano import (
    REGISTRO_1, REGISTRO_2, REGISTRO_9, a_miles, armar_archivo, fuera_de_rango, longitud_layout,
)
from cartera.views import ArchivoViewSet, ExtraccionViewSet
from tests.ayudas import usuario_con_rol

FECHA_CORTE = date(2026, 9, 30)
CABECERA = {
    "codigo_paquete": "11", "tipo_reporte": "01", "categoria_servicios": "04",
    "tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "000001",
    "fecha_corte": FECHA_CORTE,
}
factory = APIRequestFactory()


def _obligacion(n=1, **cambios):
    return {
        "OBLIGACION_ID": n, "NUMERO_OBLIGACION_TU": f"2259-{1000 + n}", "TIPO_ID_TU": "1",
        "NUMERO_IDENTIFICACION": "12345678", "NOMBRE_TITULAR": "Juan Perez",
        "FECHA_LIMITE_PAGO": date(2026, 10, 15), "CALIDAD": "P", "ESTADO_TU": "01",
        "EDAD_MORA": "01", "ANIOS_MORA": 0, "FECHA_INICIO": date(2020, 1, 1), "FECHA_PAGO": None,
        "MODO_EXTINCION": None, "TIPO_PAGO": None, "PERIODICIDAD": "05", "CUOTAS_MORA": 1,
        "VALOR_INICIAL": 1_500_000, "VALOR_MORA": 400, "VALOR_SALDO": 1_276_016,
        "VALOR_CUOTA": 85_000, "OBLIGACION_REFINANCIADA": "02", "CORREO": "titular@ejemplo.com",
        "CELULAR": "3000000000", "VALOR_REAL_PAGADO": 0, "ELIMINADA": "N", **cambios,
    }


def _campo(linea, nombre):
    _, _, inicio, longitud, _, _ = next(c for c in REGISTRO_2 if c[1] == nombre)
    return linea[inicio - 1:inicio - 1 + longitud]


def _lineas(contenido):
    return contenido.decode("cp1252").split("\r\n")[:-1]


# ── RF51 · a_miles ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pesos, miles", [
    (400, 1),            # mora de $400 → 1, nunca 0 (P-TU-02)
    (1_276_016, 1276),   # saldo de $1.276.016
    (1_500, 2),          # mitad hacia arriba
    (1_499, 1),
    (0, 0),
    (None, None),
])
def test_a_miles(pesos, miles):
    assert a_miles(pesos, 1000) == miles


def test_a_miles_devuelve_enteros_sin_decimales():
    assert isinstance(a_miles(1_276_016.75, 1000), int)


@pytest.mark.parametrize("pesos, alerta", [
    (9_000, True), (120_000_000, True), (50_000, False), (0, False),
])
def test_alerta_informativa_fuera_de_rango(pesos, alerta):
    assert fuera_de_rango(pesos) is alerta


# ── RF20 · layout del Manual ──────────────────────────────────────────────────

@pytest.mark.parametrize("layout, largo, campos", [
    (REGISTRO_1, 29, 7), (REGISTRO_2, 929, 85), (REGISTRO_9, 33, 5),
])
def test_layout_contiguo_y_con_el_largo_del_manual(layout, largo, campos):
    posicion = 1
    for _, campo, inicio, longitud, _, _ in layout:
        assert inicio == posicion, campo
        posicion += longitud
    assert longitud_layout(layout) == largo
    assert len(layout) == campos


def test_corte_con_9_obligaciones_da_11_registros_del_mismo_largo():
    contenido, errores = armar_archivo(CABECERA, [_obligacion(n) for n in range(1, 10)], 1000, 930)
    assert errores == []
    assert contenido.endswith(b"\r\n")
    lineas = _lineas(contenido)
    assert len(lineas) == 11
    assert lineas[0] == "111001123          0120260930"
    assert {len(l) for l in lineas[1:-1]} == {930}
    assert all(l.startswith("2") for l in lineas[1:-1])
    assert lineas[-1] == "9" + "00000011" + "00000009" + "0" * 16


def test_formato_de_los_campos_del_registro_tipo_2():
    linea = _lineas(armar_archivo(CABECERA, [_obligacion()], 1000, 930)[0])[1]
    assert _campo(linea, "tipo_identificacion") == "01"
    assert _campo(linea, "numero_identificacion") == "000000012345678"
    assert _campo(linea, "nombre_titular") == "JUAN PEREZ".ljust(60)
    assert _campo(linea, "numero_obligacion") == "2259-1001".rjust(20)
    assert _campo(linea, "codigo_sucursal") == "000001"
    assert _campo(linea, "fecha_corte") == "20260930"
    assert _campo(linea, "fecha_pago") == " " * 8           # vacío en espacios, no en ceros
    assert _campo(linea, "valor_mora") == "000000000001"
    assert _campo(linea, "valor_saldo") == "000000001276"
    assert _campo(linea, "linea_credito") == "   "            # N/A en Real servicios
    assert _campo(linea, "categoria_servicios") == "04"
    assert _campo(linea, "correo_electronico") == "titular@ejemplo.com".ljust(60)


# ── RF49 · fecha de exigibilidad y años en mora ───────────────────────────────

def _linea(**cambios):
    contenido, errores = armar_archivo(CABECERA, [_obligacion(**cambios)], 1000, 930)
    assert errores == []
    return _lineas(contenido)[1]


def test_en_mora_reporta_la_fecha_de_exigibilidad():
    # 49 días de mora al corte 30/09 -> la cuota impaga más antigua venció el 12/08.
    linea = _linea(VALOR_MORA=170_000, EDAD_MORA="02", DIAS_MORA=49)
    assert _campo(linea, "fecha_exigibilidad") == "20260812"


def test_cp_b_57_exigibilidad_es_la_cuota_impaga_mas_antigua_no_la_ultima_factura():
    """Dos cuotas sin pagar (14/08 y 14/09), corte 30/09: campo 18 = 20260814, campo 6 intacto."""
    linea = _linea(
        VALOR_MORA=140_000, EDAD_MORA="01", DIAS_MORA=47, CUOTAS_MORA=2,
        FECHA_LIMITE_PAGO=date(2026, 10, 14),
    )
    assert linea[149:157] == "20260814"
    assert _campo(linea, "fecha_exigibilidad") == "20260814"
    assert _campo(linea, "fecha_limite_pago") == "20261014"


def test_sin_dias_de_mora_la_fecha_de_exigibilidad_va_vacia():
    linea = _linea(VALOR_MORA=170_000, EDAD_MORA="02", DIAS_MORA=None)
    assert _campo(linea, "fecha_exigibilidad") == " " * 8


@pytest.mark.parametrize("cambios", [
    {"VALOR_MORA": 0, "EDAD_MORA": "00"},      # al día
    {"VALOR_MORA": 0, "EDAD_MORA": "02"},      # pagó la mora
    {"VALOR_MORA": 5_000, "EDAD_MORA": "00"},  # edad normal: TransUnion no la tendría en cuenta
])
def test_sin_mora_la_fecha_de_exigibilidad_va_vacia(cambios):
    # Con DIAS_MORA informado: lo que apaga el campo es la mora o la edad 00, no la falta de días.
    assert _campo(_linea(DIAS_MORA=20, **cambios), "fecha_exigibilidad") == " " * 8


def test_anios_en_mora_solo_con_edad_14():
    assert _campo(_linea(VALOR_MORA=900_000, EDAD_MORA="14", ANIOS_MORA=2), "anios_mora") == "02"
    assert _campo(_linea(VALOR_MORA=900_000, EDAD_MORA="12", ANIOS_MORA=1), "anios_mora") == "  "


# ── RF18 · obligación reestructurada (campos 44, 45 y 46) ─────────────────────

def test_reestructurada_reporta_01_naturaleza_y_numero():
    linea = _linea(OBLIGACION_REFINANCIADA="01", NATURALEZA_REESTR="07", N_REESTRUCTURACIONES=1)
    assert linea[289:291] == "01"      # campo 44, posición 290
    assert linea[291:293] == "07"      # campo 45, posición 292
    assert linea[293:296] == "001"     # campo 46, posición 294


def test_no_reestructurada_deja_45_y_46_en_espacios():
    linea = _linea(OBLIGACION_REFINANCIADA="02", NATURALEZA_REESTR="07", N_REESTRUCTURACIONES=0)
    assert linea[289:291] == "02"
    assert linea[291:293] == "  "
    assert linea[293:296] == "   "


def test_reestructurada_sin_numero_deja_45_y_46_en_espacios():
    linea = _linea(OBLIGACION_REFINANCIADA="01", NATURALEZA_REESTR="07", N_REESTRUCTURACIONES=0)
    assert linea[289:291] == "01"
    assert linea[291:296] == "     "


def test_reestructuraciones_cadena_de_una():
    assert servicios._reestructuraciones([(1, 2, "07")]) == {2: ("07", 1)}


def test_reestructuraciones_cadena_de_dos():
    filas = [(1, 2, "07"), (2, 3, "08")]
    assert servicios._reestructuraciones(filas) == {2: ("07", 1), 3: ("08", 2)}


def test_reestructuraciones_sin_vinculo_no_aparece():
    assert servicios._reestructuraciones([]) == {}
    assert 9 not in servicios._reestructuraciones([(1, 2, "07")])


def test_reestructuraciones_protege_contra_ciclos():
    resultado = servicios._reestructuraciones([(1, 2, "07"), (2, 1, "07")])
    assert resultado[1][1] == 2 and resultado[2][1] == 2


def test_generar_archivo_completa_45_y_46_desde_nv_refinanciacion():
    conexion, cursor = MagicMock(), MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [("VALIDADO", FECHA_CORTE), (5,)]
    cursor.fetchall.return_value = [(1, 2, "07")]
    parametros = {"CODIGO_PAQUETE": "11", "TIPO_REPORTE": "01",
                  "CATEGORIA_SERVICIO": "04", "DIVISOR_VALORES": "1000"}
    obligaciones = [_obligacion(1), _obligacion(2, OBLIGACION_REFINANCIADA="01")]
    with patch("cartera.servicios.connection", conexion), \
         patch("cartera.servicios.transaction.atomic", _sin_transaccion), \
         patch("cartera.servicios._parametros", return_value=parametros), \
         patch("cartera.servicios._leer_obligaciones_archivo", return_value=obligaciones), \
         patch("parametros.servicios.datos_entidad", return_value=_entidad("001", "123")), \
         patch("cartera.servicios.listar_archivos", return_value=[{"id": 5}]):
        servicios.generar_archivo(2)
    consulta = next(
        c for c in cursor.execute.call_args_list if "NV_REFINANCIACION" in c.args[0]
    )
    assert "OBLIGACION_NUEVA_ID" in consulta.args[0]
    assert obligaciones[0]["N_REESTRUCTURACIONES"] == 0
    assert obligaciones[1]["NATURALEZA_REESTR"] == "07"
    assert obligaciones[1]["N_REESTRUCTURACIONES"] == 1
    insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0])
    lineas = insert.args[1][10].datos.decode("cp1252").split("\r\n")
    assert lineas[1][291:296] == "     "      # la 1 no es nueva de nada
    assert lineas[2][289:296] == "0107001"    # campos 44, 45 y 46 de la 2


def test_nombre_con_tildes_se_codifica_en_cp1252_sin_romper_el_largo():
    contenido, errores = armar_archivo(
        CABECERA, [_obligacion(NOMBRE_TITULAR="Ana Peña Álvarez")], 1000, 930
    )
    assert errores == []
    tipo2 = contenido.split(b"\r\n")[1]
    assert len(tipo2) == 930
    assert "PEÑA ÁLVAREZ".encode("cp1252") in tipo2


def test_campo_mas_largo_que_su_posicion_no_genera_el_archivo():
    contenido, errores = armar_archivo(
        CABECERA, [_obligacion(6, NOMBRE_TITULAR="X" * 61)], 1000, 930
    )
    assert contenido is None
    assert errores == [{
        "regla": "CAMPO_EXCEDE_LONGITUD",
        "mensaje": "El campo nombre_titular tiene 61 caracteres y admite 60.",
        "obligacion_id": 6, "numero_obligacion": "2259-1006", "campo": "nombre_titular",
    }]


def test_campo_numerico_con_letras_no_genera_el_archivo():
    _, errores = armar_archivo(CABECERA, [_obligacion(ESTADO_TU="A1")], 1000, 930)
    assert errores[0]["regla"] == "CAMPO_TIPO_INVALIDO"
    assert errores[0]["campo"] == "estado"


def test_longitud_menor_que_la_suma_de_campos_es_error_de_configuracion():
    with pytest.raises(ValueError):
        armar_archivo(CABECERA, [], 1000, 928)


# ── RF20 · servicio generar_archivo ───────────────────────────────────────────

@contextmanager
def _sin_transaccion():
    yield


def _entidad(tipo, codigo):
    return {
        "tipo_entidad": tipo, "codigo_entidad": codigo, "codigo_sucursal": "000001",
        "con_marcador": "X" in tipo + codigo, "prefijo_archivo": f"SSR{tipo}{codigo}",
    }


def _generar(estado="VALIDADO", entidad=None, obligaciones=None):
    conexion, cursor = MagicMock(), MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [(estado, FECHA_CORTE), (5,)]
    cursor.fetchall.return_value = []  # NV_REFINANCIACION (RF18): sin vínculos
    parametros = {"CODIGO_PAQUETE": "11", "TIPO_REPORTE": "01",
                  "CATEGORIA_SERVICIO": "04", "DIVISOR_VALORES": "1000"}
    with patch("cartera.servicios.connection", conexion), \
         patch("cartera.servicios.transaction.atomic", _sin_transaccion), \
         patch("cartera.servicios._parametros", return_value=parametros), \
         patch("cartera.servicios._leer_obligaciones_archivo",
               return_value=obligaciones or [_obligacion(n) for n in range(1, 10)]), \
         patch("parametros.servicios.datos_entidad", return_value=entidad or _entidad("XXX", "XXX")), \
         patch("cartera.servicios.listar_archivos", return_value=[{"id": 5}]):
        servicios.generar_archivo(2)
    insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO" in c.args[0])
    return insert.args[1]


def test_entidad_con_marcadores_genera_ssrxxxxxx_no_apto():
    params = _generar(entidad=_entidad("XXX", "XXX"))
    assert params[2] == "SSRXXXXXX20260930"
    assert params[9] == "N"


def test_entidad_de_prueba_001_123_genera_ssr001123_apto():
    params = _generar(entidad=_entidad("001", "123"))
    assert params[2] == "SSR00112320260930"
    assert params[9] == "S"


def test_eliminadas_no_van_en_el_archivo_y_cuentan_como_excluidas():
    obligaciones = [_obligacion(1), _obligacion(2, ELIMINADA="S")]
    params = _generar(obligaciones=obligaciones)
    assert params[6:9] == [1, 1, 1_276_016]  # N_REGISTROS, N_EXCLUIDAS, SALDO_TOTAL en pesos
    assert params[10].datos.count(b"\r\n") == 3


def test_corte_en_borrador_no_genera_archivo():
    with pytest.raises(servicios.CorteNoEsValidado):
        _generar(estado="BORRADOR")


def test_campo_largo_lanza_campos_invalidos():
    with pytest.raises(servicios.CamposInvalidos) as exc:
        _generar(obligaciones=[_obligacion(NOMBRE_TITULAR="X" * 61)])
    assert exc.value.errores[0]["campo"] == "nombre_titular"


# ── RF20 · vistas ─────────────────────────────────────────────────────────────

def _post_archivo(**kwargs):
    request = factory.post("/api/extracciones/2/archivo/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_archivo", **kwargs):
        return ExtraccionViewSet.as_view({"post": "archivo"})(request, pk="2")


def test_post_archivo_201():
    assert _post_archivo(return_value={"id": 2}).status_code == 201


def test_post_archivo_409_corte_sin_validar():
    response = _post_archivo(side_effect=servicios.CorteNoEsValidado())
    assert response.status_code == 409
    assert response.data == {"detail": "Valida el corte antes de generar el archivo."}


def test_post_archivo_409_campo_largo_con_errores():
    errores = [{"regla": "CAMPO_EXCEDE_LONGITUD", "campo": "nombre_titular"}]
    response = _post_archivo(side_effect=servicios.CamposInvalidos(errores))
    assert response.status_code == 409
    assert response.data["errores"] == errores


def test_post_archivo_404():
    assert _post_archivo(side_effect=servicios.CorteNoEncontrado()).status_code == 404


def test_descarga_con_accept_text_plain():
    request = factory.get("/api/archivos/2/descarga/", HTTP_ACCEPT="text/plain")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("cartera.views.servicios.contenido_archivo",
               return_value=("SSRXXXXXX20260930", b"1\r\n")):
        response = resolve("/api/archivos/2/descarga/").func(request, pk="2")
    assert response.status_code == 200
    assert response.content == b"1\r\n"
    assert response["Content-Disposition"] == 'attachment; filename="SSRXXXXXX20260930.txt"'


def test_descarga_404():
    request = factory.get("/api/archivos/9/descarga/", HTTP_ACCEPT="text/plain")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.contenido_archivo",
               side_effect=servicios.ArchivoNoEncontrado()):
        response = resolve("/api/archivos/9/descarga/").func(request, pk="9")
    assert response.status_code == 404


def test_listar_archivos_filtro_invalido_400():
    request = factory.get("/api/archivos/", {"corte_id": "abc"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ArchivoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 400
    assert response.data == {"corte_id": ["Indica el id numérico del corte."]}


# ── registrar-envio exige archivo apto (0.9) ──────────────────────────────────

@pytest.mark.parametrize("archivo, excepcion", [
    (None, servicios.SinArchivo), ((3, "N"), servicios.ArchivoNoApto),
])
def test_registrar_envio_exige_archivo_apto(archivo, excepcion):
    conexion, cursor = MagicMock(), MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.side_effect = [("VALIDADO", FECHA_CORTE), archivo]
    with patch("cartera.servicios.connection", conexion), pytest.raises(excepcion):
        servicios.registrar_envio(2, fecha_envio=date(2026, 10, 1))
