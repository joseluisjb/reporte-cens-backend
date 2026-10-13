from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from config.bitacora import (
    EVENTOS,
    MODULOS,
    TIPOS_ACCION,
    consultar_bitacora,
    registrar_bitacora,
    usuario_actual,
)
from usuarios.models import Rol, Usuario

CLAVE = "ClaveSegura1"
CLAVE_NUEVA = "OtraClave2026"
CORREO_ADMIN = "rmartinez@example.com"
CORREO_ANALISTA = "jperez@example.com"
CONCEPTO = {
    "codigo_concepto": 30,
    "descripcion": "Cuota",
    "reportable": "S",
    "observacion": None,
}
FILA = (
    7,
    datetime(2026, 10, 12, 8, 30, 0),
    3,
    "Rosa Martínez",
    "ADMINISTRADOR",
    "CONCEPTO_CREADO",
    "creacion",
    "Parametrización",
    "Campos: descripcion",
)


@pytest.fixture(autouse=True)
def limpiar_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def administrador(db):
    return Usuario.objects.create_superuser(CORREO_ADMIN, CLAVE, nombre="Rosa Martínez")


@pytest.fixture
def analista(db):
    return Usuario.objects.create_user(
        CORREO_ANALISTA, CLAVE, nombre="Juan Pérez", must_change_password=False
    )


def cliente_de(usuario):
    cliente = APIClient()
    cliente.force_login(usuario)
    return cliente


def conexion_simulada(total=0, filas=()):
    conexion = MagicMock()
    cursor = MagicMock()
    conexion.cursor.return_value.__enter__.return_value = cursor
    conexion.cursor.return_value.__exit__.return_value = False
    cursor.fetchone.return_value = (total,)
    cursor.fetchall.return_value = list(filas)
    return conexion, cursor


def parametros_insertados(**kwargs):
    conexion, cursor = conexion_simulada()
    with patch("config.bitacora.connection", conexion):
        registrar_bitacora(**kwargs)
    sql, params = cursor.execute.call_args.args
    return sql, params


def usuario_sin_guardar(pk=3):
    usuario = Usuario(
        email=CORREO_ADMIN, nombre="Rosa Martínez", rol=Rol.ADMINISTRADOR, is_active=True
    )
    usuario.pk = pk
    return usuario


def test_catalogo_usa_solo_tipos_y_modulos_del_contrato():
    for texto, tipo_accion, modulo in EVENTOS.values():
        assert texto
        assert tipo_accion in TIPOS_ACCION
        assert modulo in MODULOS


def test_registrar_guarda_quien_lo_hizo():
    sql, params = parametros_insertados(
        accion="CONCEPTO_CREADO",
        entidad="NV_CONCEPTO_REPORTABLE",
        entidad_id=30,
        detalle="",
        usuario=usuario_sin_guardar(),
    )
    assert "USUARIO_NOMBRE, USUARIO_ROL, TIPO_ACCION, MODULO" in sql
    assert sql.count("%s") == len(params) == 10
    assert ":1" not in sql
    assert params[1] == 3
    assert params[2:6] == ["CONCEPTO_CREADO", "NV_CONCEPTO_REPORTABLE", "30", ""]
    assert params[6:] == ["Rosa Martínez", "ADMINISTRADOR", "creacion", "Parametrización"]


def test_registrar_toma_el_usuario_de_la_peticion_en_curso():
    marca = usuario_actual.set(usuario_sin_guardar(pk=8))
    try:
        _, params = parametros_insertados(
            accion="ELIMINACION_BORRADOR", entidad="NV_CORTE", entidad_id=5, detalle="Corte 5"
        )
    finally:
        usuario_actual.reset(marca)
    assert params[1] == 8
    assert params[6:] == ["Rosa Martínez", "ADMINISTRADOR", "eliminacion", "Extracción"]


def test_registrar_con_id_de_la_misma_persona_guarda_nombre_y_rol():
    marca = usuario_actual.set(usuario_sin_guardar(pk=8))
    try:
        _, params = parametros_insertados(
            accion="CREAR", entidad="USUARIO", entidad_id=10, detalle="x", usuario_id=8
        )
    finally:
        usuario_actual.reset(marca)
    assert params[1] == 8
    assert params[6:] == ["Rosa Martínez", "ADMINISTRADOR", "creacion", "Usuarios"]


def test_registrar_con_id_de_otra_persona_no_le_atribuye_el_nombre():
    marca = usuario_actual.set(usuario_sin_guardar(pk=8))
    try:
        _, params = parametros_insertados(
            accion="CREAR", entidad="USUARIO", entidad_id=10, detalle="x", usuario_id=42
        )
    finally:
        usuario_actual.reset(marca)
    assert params[1] == 42
    assert params[6:8] == [None, None]


def test_registrar_sin_usuario_queda_como_accion_del_sistema():
    _, params = parametros_insertados(
        accion="ACTUALIZACION_MENSUAL", entidad="NV_CORTE", entidad_id=7, detalle="Corte 7"
    )
    assert params[1] is None
    assert params[6:] == [None, None, "calculo", "Extracción"]


def test_registrar_accion_fuera_del_catalogo_no_falla():
    _, params = parametros_insertados(
        accion="ACCION_NUEVA", entidad="ENTIDAD", entidad_id=1, detalle="x"
    )
    assert params[2] == "ACCION_NUEVA"
    assert params[8:] == [None, None]


def test_registrar_recorta_los_textos_al_tamano_de_la_columna():
    _, params = parametros_insertados(
        accion="A" * 300, entidad="E" * 300, entidad_id="I" * 300, detalle="D" * 5000
    )
    assert [len(params[i]) for i in (2, 3, 4, 5)] == [40, 30, 40, 1000]


def test_codigos_del_catalogo_caben_en_la_columna_accion():
    assert max(len(codigo) for codigo in EVENTOS) <= 40


def test_consultar_sin_filtros_ordena_por_fecha_descendente_y_pagina():
    conexion, cursor = conexion_simulada(total=1, filas=[FILA])
    with patch("config.bitacora.connection", conexion):
        total, resultados = consultar_bitacora({}, 20, 40)
    sql_total, params_total = cursor.execute.call_args_list[0].args
    sql_filas, params_filas = cursor.execute.call_args_list[1].args
    assert "WHERE" not in sql_total
    assert params_total == []
    assert "ORDER BY FECHA DESC, BITACORA_ID DESC" in sql_filas
    assert "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY" in sql_filas
    assert params_filas == [40, 20]
    assert total == 1
    assert resultados == [
        {
            "id": 7,
            "fecha_hora": "2026-10-12T08:30:00-05:00",
            "usuario_id": 3,
            "usuario": "Rosa Martínez",
            "rol": "ADMINISTRADOR",
            "accion": "Concepto creado",
            "tipo_accion": "creacion",
            "modulo": "Parametrización",
            "detalle": "Campos: descripcion",
        }
    ]


def test_consultar_con_todos_los_filtros_usa_parametros_enlazados():
    conexion, cursor = conexion_simulada()
    filtros = {
        "desde": date(2026, 10, 1),
        "hasta": date(2026, 10, 12),
        "usuario": 3,
        "tipo_accion": "creacion",
        "modulo": "Usuarios",
    }
    with patch("config.bitacora.connection", conexion):
        consultar_bitacora(filtros, 20, 0)
    sql_total, params_total = cursor.execute.call_args_list[0].args
    sql_filas, params_filas = cursor.execute.call_args_list[1].args
    condicion = (
        "WHERE FECHA >= %s AND FECHA < %s AND USUARIO_ID = %s "
        "AND TIPO_ACCION = %s AND MODULO = %s"
    )
    assert condicion in sql_total
    assert condicion in sql_filas
    assert sql_total.count("%s") == len(params_total)
    assert sql_filas.count("%s") == len(params_filas)
    assert params_total == [
        datetime(2026, 10, 1),
        datetime(2026, 10, 13),
        3,
        "creacion",
        "Usuarios",
    ]
    assert params_filas == params_total + [0, 20]
    assert "creacion" not in sql_filas
    assert "Usuarios" not in sql_filas


def test_consultar_fila_del_sistema_y_accion_fuera_del_catalogo():
    fila = (1, datetime(2026, 10, 1, 2, 0, 0), None, None, None, "ACCION_VIEJA", None, None, None)
    conexion, _ = conexion_simulada(total=1, filas=[fila])
    with patch("config.bitacora.connection", conexion):
        _, resultados = consultar_bitacora({}, 20, 0)
    assert resultados[0]["usuario"] == "Sistema"
    assert resultados[0]["usuario_id"] is None
    assert resultados[0]["rol"] is None
    assert resultados[0]["accion"] == "ACCION_VIEJA"
    assert resultados[0]["detalle"] == ""


def test_auditoria_sin_sesion_responde_401(db):
    respuesta = APIClient().get("/api/auditoria/")
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "not_authenticated"


def test_auditoria_para_analista_responde_403(analista):
    with patch("config.auditoria.consultar_bitacora") as consultar:
        respuesta = cliente_de(analista).get("/api/auditoria/")
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "permission_denied"
    consultar.assert_not_called()


def test_auditoria_para_administrador_devuelve_total_y_resultados(administrador):
    registro = {"id": 7, "accion": "Concepto creado"}
    with patch("config.auditoria.consultar_bitacora", return_value=(1, [registro])) as consultar:
        respuesta = cliente_de(administrador).get("/api/auditoria/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"total": 1, "resultados": [registro]}
    consultar.assert_called_once_with({}, 20, 0)


def test_auditoria_pasa_filtros_y_paginacion(administrador):
    with patch("config.auditoria.consultar_bitacora", return_value=(0, [])) as consultar:
        respuesta = cliente_de(administrador).get(
            "/api/auditoria/",
            {
                "desde": "2026-10-01",
                "hasta": "2026-10-12",
                "usuario": "3",
                "tipo_accion": "creacion",
                "modulo": "Parametrización",
                "limite": "500",
                "desplazamiento": "40",
            },
        )
    assert respuesta.status_code == 200
    filtros, limite, desplazamiento = consultar.call_args.args
    assert dict(filtros) == {
        "desde": date(2026, 10, 1),
        "hasta": date(2026, 10, 12),
        "usuario": 3,
        "tipo_accion": "creacion",
        "modulo": "Parametrización",
    }
    assert (limite, desplazamiento) == (100, 40)


def test_auditoria_ignora_filtros_vacios(administrador):
    with patch("config.auditoria.consultar_bitacora", return_value=(0, [])) as consultar:
        respuesta = cliente_de(administrador).get(
            "/api/auditoria/", {"desde": "", "hasta": "", "usuario": "", "tipo_accion": "", "modulo": ""}
        )
    assert respuesta.status_code == 200
    assert dict(consultar.call_args.args[0]) == {}


def test_auditoria_acepta_el_mismo_dia_en_desde_y_hasta(administrador):
    with patch("config.auditoria.consultar_bitacora", return_value=(0, [])):
        respuesta = cliente_de(administrador).get(
            "/api/auditoria/", {"desde": "2026-10-12", "hasta": "2026-10-12"}
        )
    assert respuesta.status_code == 200


@pytest.mark.parametrize(
    "parametros, campo, mensaje",
    [
        ({"desde": "12/10/2026"}, "desde", "Usa una fecha válida (AAAA-MM-DD)."),
        ({"hasta": "2026-13-40"}, "hasta", "Usa una fecha válida (AAAA-MM-DD)."),
        (
            {"desde": "2026-10-12", "hasta": "2026-10-01"},
            "hasta",
            "La fecha final no puede ser anterior a la inicial.",
        ),
        ({"usuario": "abc"}, "usuario", "Indica el id numérico del usuario."),
        ({"usuario": "0"}, "usuario", "Indica el id numérico del usuario."),
        ({"usuario": "9" * 40}, "usuario", "Indica el id numérico del usuario."),
        ({"tipo_accion": "borrar_todo"}, "tipo_accion", "Tipo de acción no válido."),
        ({"modulo": "Otro"}, "modulo", "Módulo no válido."),
        ({"modulo": "' OR 1=1 --"}, "modulo", "Módulo no válido."),
    ],
)
def test_auditoria_filtro_invalido_responde_400(administrador, parametros, campo, mensaje):
    with patch("config.auditoria.consultar_bitacora") as consultar:
        respuesta = cliente_de(administrador).get("/api/auditoria/", parametros)
    assert respuesta.status_code == 400
    assert respuesta.json() == {campo: [mensaje]}
    consultar.assert_not_called()


@pytest.mark.parametrize("parametros", [{"limite": "abc"}, {"limite": "0"}, {"desplazamiento": "-1"}])
def test_auditoria_paginacion_invalida_responde_400(administrador, parametros):
    with patch("config.auditoria.consultar_bitacora") as consultar:
        respuesta = cliente_de(administrador).get("/api/auditoria/", parametros)
    assert respuesta.status_code == 400
    assert "detail" in respuesta.json()
    consultar.assert_not_called()


def test_consultar_la_auditoria_no_genera_registros(administrador, bitacora):
    with patch("config.auditoria.consultar_bitacora", return_value=(0, [])):
        cliente_de(administrador).get("/api/auditoria/")
    bitacora.assert_not_called()


def test_inicio_de_sesion_queda_registrado(analista, bitacora):
    respuesta = APIClient().post(
        "/api/auth/login/", {"email": CORREO_ANALISTA, "password": CLAVE}, format="json"
    )
    assert respuesta.status_code == 200
    bitacora.assert_called_once_with(
        "INICIO_SESION", "USUARIO", analista.pk, "Acceso correcto", usuario=analista
    )


def test_inicio_de_sesion_fallido_no_se_registra(analista, bitacora):
    respuesta = APIClient().post(
        "/api/auth/login/", {"email": CORREO_ANALISTA, "password": "ClaveMala1"}, format="json"
    )
    assert respuesta.status_code == 401
    bitacora.assert_not_called()


def test_cierre_de_sesion_queda_registrado_con_el_usuario(analista, bitacora):
    respuesta = cliente_de(analista).post("/api/auth/logout/")
    assert respuesta.status_code == 204
    bitacora.assert_called_once_with(
        "CIERRE_SESION", "USUARIO", analista.pk, "Cierre manual", usuario=analista
    )


def test_cambio_de_contrasena_queda_registrado_sin_la_contrasena(analista, bitacora):
    respuesta = cliente_de(analista).post(
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 204
    bitacora.assert_called_once_with(
        "CONTRASENA_CAMBIADA", "USUARIO", analista.pk, "", usuario=analista
    )
    assert CLAVE not in repr(bitacora.call_args)
    assert CLAVE_NUEVA not in repr(bitacora.call_args)


def test_restablecer_contrasena_queda_registrado_a_nombre_del_usuario(analista, bitacora):
    uid = urlsafe_base64_encode(force_bytes(analista.pk))
    token = f"{uid}.{default_token_generator.make_token(analista)}"
    respuesta = APIClient().post(
        "/api/auth/password-reset/confirm/",
        {"token": token, "new_password": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 204
    bitacora.assert_called_once_with(
        "CONTRASENA_RESTABLECIDA",
        "USUARIO",
        analista.pk,
        "Restablecimiento con enlace del correo",
        usuario=analista,
    )
    assert CLAVE_NUEVA not in repr(bitacora.call_args)
    assert token not in repr(bitacora.call_args)


def test_restablecer_con_token_invalido_no_se_registra(analista, bitacora):
    respuesta = APIClient().post(
        "/api/auth/password-reset/confirm/",
        {"token": "abc.def", "new_password": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 400
    bitacora.assert_not_called()


def test_crear_concepto_queda_registrado(administrador, bitacora):
    with patch("parametros.views.servicios.crear_concepto", return_value=CONCEPTO):
        respuesta = cliente_de(administrador).post(
            "/api/conceptos/", {"codigo": 30, "descripcion": "Cuota"}, format="json"
        )
    assert respuesta.status_code == 201
    bitacora.assert_called_once_with(
        "CONCEPTO_CREADO", "NV_CONCEPTO_REPORTABLE", 30, "", usuario=administrador
    )


def test_editar_concepto_registra_solo_nombres_de_campos_conocidos(administrador, bitacora):
    with patch("parametros.views.servicios.actualizar_concepto", return_value=CONCEPTO):
        respuesta = cliente_de(administrador).patch(
            "/api/conceptos/30/",
            {"descripcion": "Cuota de energía", "<script>": "x", "password": "Secreto123"},
            format="json",
        )
    assert respuesta.status_code == 200
    bitacora.assert_called_once_with(
        "CONCEPTO_EDITADO",
        "NV_CONCEPTO_REPORTABLE",
        "30",
        "Campos: descripcion",
        usuario=administrador,
    )
    assert "Secreto123" not in repr(bitacora.call_args)


def test_desactivar_concepto_se_registra_como_desactivacion(administrador, bitacora):
    inactivo = {**CONCEPTO, "reportable": "N"}
    with patch("parametros.views.servicios.actualizar_concepto", return_value=inactivo):
        respuesta = cliente_de(administrador).patch(
            "/api/conceptos/30/", {"activo": False}, format="json"
        )
    assert respuesta.status_code == 200
    bitacora.assert_called_once_with(
        "CONCEPTO_DESACTIVADO",
        "NV_CONCEPTO_REPORTABLE",
        "30",
        "Campos: activo",
        usuario=administrador,
    )


def test_eliminar_grupo_queda_registrado(administrador, bitacora):
    with patch("parametros.views.servicios.eliminar_grupo"):
        respuesta = cliente_de(administrador).delete("/api/grupos-conceptos/4/")
    assert respuesta.status_code == 204
    bitacora.assert_called_once_with(
        "GRUPO_ELIMINADO", "NV_GRUPO_CONCEPTO", "4", "", usuario=administrador
    )


def test_accion_rechazada_por_permisos_no_se_registra(analista, bitacora):
    with patch("parametros.views.servicios.crear_concepto") as crear:
        respuesta = cliente_de(analista).post(
            "/api/conceptos/", {"codigo": 30, "descripcion": "Cuota"}, format="json"
        )
    assert respuesta.status_code == 403
    crear.assert_not_called()
    bitacora.assert_not_called()


def test_listar_conceptos_no_se_registra(analista, bitacora):
    with patch("parametros.views.servicios.listar_conceptos", return_value=[CONCEPTO]):
        respuesta = cliente_de(analista).get("/api/conceptos/")
    assert respuesta.status_code == 200
    bitacora.assert_not_called()


def test_consulta_de_obligaciones_queda_registrada(analista, bitacora):
    with patch(
        "cartera.views.servicios.listar_obligaciones",
        return_value={"total": 0, "resultados": []},
    ):
        respuesta = cliente_de(analista).get("/api/extracciones/5/obligaciones/")
    assert respuesta.status_code == 200
    bitacora.assert_called_once_with(
        "CONSULTA_OBLIGACIONES", "NV_CORTE", "5", "", usuario=analista
    )


def test_eliminar_borrador_no_se_duplica_en_el_middleware(analista, bitacora):
    with patch("cartera.views.servicios.eliminar_borrador"):
        respuesta = cliente_de(analista).delete("/api/extracciones/5/")
    assert respuesta.status_code == 204
    bitacora.assert_not_called()


def test_un_fallo_de_la_bitacora_no_rompe_la_peticion(analista, bitacora):
    bitacora.side_effect = RuntimeError("bitácora caída")
    respuesta = APIClient().post(
        "/api/auth/login/", {"email": CORREO_ANALISTA, "password": CLAVE}, format="json"
    )
    assert respuesta.status_code == 200
    bitacora.assert_called_once()


def test_el_usuario_de_la_peticion_esta_disponible_solo_durante_ella(analista):
    vistos = []

    def capturar(**kwargs):
        vistos.append(usuario_actual.get())
        return [CONCEPTO]

    with patch("parametros.views.servicios.listar_conceptos", side_effect=capturar):
        cliente_de(analista).get("/api/conceptos/")
    assert vistos == [analista]
    assert usuario_actual.get() is None


@pytest.mark.parametrize(
    "cambio, accion",
    [
        ({"is_active": False}, "DESACTIVAR"),
        ({"is_active": True}, "ACTIVAR"),
        ({"nombre": "Juan Pablo Pérez"}, "EDITAR"),
    ],
)
def test_cambios_de_usuario_se_registran_con_su_accion(administrador, analista, cambio, accion):
    with patch("usuarios.views.registrar_auditoria") as registrar:
        respuesta = cliente_de(administrador).patch(
            f"/api/users/{analista.pk}/", cambio, format="json"
        )
    assert respuesta.status_code == 200
    assert registrar.call_args.args[:3] == (accion, "USUARIO", analista.pk)
    assert registrar.call_args.args[4] == administrador.pk
