from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from django.db import IntegrityError
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol


@contextmanager
def _noop_atomic():
    yield

from parametros import servicios
from parametros.serializers import (
    ConceptoReportableSerializer,
    ConceptoActualizarSerializer,
    GrupoConceptoSerializer,
    GrupoConceptoCrearSerializer,
    GrupoConceptoActualizarSerializer,
)
from parametros.views import ConceptoViewSet, GrupoConceptoViewSet

# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

_CONCEPTO = {"codigo_concepto": 1, "descripcion": "Energía activa", "reportable": "S", "observacion": None}
_CONCEPTO_N = {"codigo_concepto": 2, "descripcion": "Energía reactiva", "reportable": "N", "observacion": "Obs"}


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

def test_repr_reportable_s_es_activo_true():
    data = ConceptoReportableSerializer(_CONCEPTO).data
    assert data["activo"] is True
    assert data["codigo"] == 1


def test_repr_reportable_n_es_activo_false():
    data = ConceptoReportableSerializer(_CONCEPTO_N).data
    assert data["activo"] is False


def test_internal_value_activo_true_a_reportable_s():
    s = ConceptoReportableSerializer(data={"codigo": 5, "descripcion": "X", "activo": True})
    assert s.is_valid(), s.errors
    assert s.validated_data["reportable"] == "S"
    assert s.validated_data["codigo_concepto"] == 5


def test_internal_value_activo_false_a_reportable_n():
    s = ConceptoReportableSerializer(data={"codigo": 5, "descripcion": "X", "activo": False})
    assert s.is_valid(), s.errors
    assert s.validated_data["reportable"] == "N"


def test_activo_default_true_cuando_no_se_envia():
    s = ConceptoReportableSerializer(data={"codigo": 5, "descripcion": "X"})
    assert s.is_valid(), s.errors
    assert s.validated_data["reportable"] == "S"


def test_codigo_cero_invalido():
    s = ConceptoReportableSerializer(data={"codigo": 0, "descripcion": "X"})
    assert not s.is_valid()
    assert "codigo" in s.errors


def test_codigo_10000_invalido():
    s = ConceptoReportableSerializer(data={"codigo": 10000, "descripcion": "X"})
    assert not s.is_valid()
    assert "codigo" in s.errors


def test_descripcion_mayor_60_invalida():
    s = ConceptoReportableSerializer(data={"codigo": 1, "descripcion": "X" * 61})
    assert not s.is_valid()
    assert "descripcion" in s.errors


def test_repr_descripcion_none_devuelve_cadena_vacia():
    concepto = {"codigo_concepto": 5, "descripcion": None, "reportable": "S", "observacion": None}
    data = ConceptoReportableSerializer(concepto).data
    assert data["descripcion"] == ""


def test_post_descripcion_vacia_o_espacios_devuelve_400():
    for valor in ("", "   "):
        request = factory.post("/api/conceptos/", {"codigo": 5, "descripcion": valor}, format="json")
        force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
        response = ConceptoViewSet.as_view({"post": "create"})(request)
        assert response.status_code == 400, f"esperado 400 para descripcion={valor!r}"
        assert "descripcion" in response.data
        assert any("blanco" in str(m).lower() for m in response.data["descripcion"])


def test_patch_descripcion_vacia_o_espacios_devuelve_400():
    for valor in ("", "   "):
        request = factory.patch("/api/conceptos/1/", {"descripcion": valor}, format="json")
        force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
        response = ConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
        assert response.status_code == 400, f"esperado 400 para descripcion={valor!r}"
        assert "descripcion" in response.data
        assert any("blanco" in str(m).lower() for m in response.data["descripcion"])


def test_actualizar_serializer_convierte_activo():
    s = ConceptoActualizarSerializer(data={"activo": False})
    assert s.is_valid(), s.errors
    assert s.validated_data["reportable"] == "N"
    assert "activo" not in s.validated_data


def test_actualizar_serializer_sin_activo_no_agrega_reportable():
    s = ConceptoActualizarSerializer(data={"descripcion": "Nuevo"})
    assert s.is_valid(), s.errors
    assert "reportable" not in s.validated_data


# ---------------------------------------------------------------------------
# Servicios — cursor simulado
# ---------------------------------------------------------------------------

def _mock_conn(fetchall=None, fetchone=None):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    if fetchall is not None:
        mock_cursor.fetchall.return_value = fetchall
    if fetchone is not None:
        mock_cursor.fetchone.return_value = fetchone
    return mock_conn, mock_cursor


def test_listar_conceptos_sin_filtro():
    filas = [(1, "Energía activa", "S", None), (2, "Reactiva", "N", "Obs")]
    mock_conn, mock_cursor = _mock_conn(fetchall=filas)
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.listar_conceptos()
    assert len(result) == 2
    assert result[0]["codigo_concepto"] == 1
    assert result[0]["reportable"] == "S"


def test_listar_conceptos_filtro_activo_true():
    mock_conn, mock_cursor = _mock_conn(fetchall=[(1, "Activa", "S", None)])
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.listar_conceptos(activo=True)
    sql_llamado = mock_cursor.execute.call_args[0][0]
    params = mock_cursor.execute.call_args[0][1]
    assert "WHERE REPORTABLE" in sql_llamado
    assert params == ["S"]
    assert len(result) == 1


def test_listar_conceptos_filtro_activo_false():
    mock_conn, mock_cursor = _mock_conn(fetchall=[])
    with patch("parametros.servicios.connection", mock_conn):
        servicios.listar_conceptos(activo=False)
    params = mock_cursor.execute.call_args[0][1]
    assert params == ["N"]


def test_crear_concepto_ejecuta_insert():
    fila = (1, "Activa", "S", None)
    mock_conn, mock_cursor = _mock_conn(fetchone=fila)
    datos = {"codigo_concepto": 1, "descripcion": "Activa", "reportable": "S", "observacion": None}
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.crear_concepto(datos)
    assert mock_cursor.execute.call_count == 2  # INSERT + SELECT
    assert result["codigo_concepto"] == 1


def test_crear_concepto_integrity_error_lanza_concepto_ya_existe():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.execute.side_effect = IntegrityError("ORA-00001")
    datos = {"codigo_concepto": 1, "descripcion": "X", "reportable": "S", "observacion": None}
    with patch("parametros.servicios.connection", mock_conn):
        with pytest.raises(servicios.ConceptoYaExiste):
            servicios.crear_concepto(datos)


def test_actualizar_concepto_genera_set_correcto():
    fila = (1, "Nuevo", "N", None)
    mock_conn, mock_cursor = _mock_conn(fetchone=fila)
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.actualizar_concepto(1, {"descripcion": "Nuevo", "reportable": "N"})
    update_sql = mock_cursor.execute.call_args_list[0][0][0]
    assert "DESCRIPCION" in update_sql
    assert "REPORTABLE" in update_sql
    assert result["descripcion"] == "Nuevo"


def test_actualizar_concepto_datos_vacios_no_ejecuta_update():
    fila = (1, "Sin cambios", "S", None)
    mock_conn, mock_cursor = _mock_conn(fetchone=fila)
    with patch("parametros.servicios.connection", mock_conn):
        servicios.actualizar_concepto(1, {})
    # Solo debe haber un execute (el SELECT de _buscar_por_codigo, no UPDATE)
    assert mock_cursor.execute.call_count == 1


# ---------------------------------------------------------------------------
# Vistas — servicios parcheados
# ---------------------------------------------------------------------------

factory = APIRequestFactory()


def test_list_responde_200_con_campo_codigo():
    request = factory.get("/api/conceptos/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_conceptos", return_value=[_CONCEPTO]):
        response = ConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data[0]["codigo"] == 1


def test_list_con_filtro_activo_true_pasa_bool_al_servicio():
    request = factory.get("/api/conceptos/", {"activo": "true"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]) as mock_listar:
        ConceptoViewSet.as_view({"get": "list"})(request)
    mock_listar.assert_called_once_with(activo=True)


def test_list_con_filtro_activo_false():
    request = factory.get("/api/conceptos/", {"activo": "false"})
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]) as mock_listar:
        ConceptoViewSet.as_view({"get": "list"})(request)
    mock_listar.assert_called_once_with(activo=False)


def test_create_responde_201():
    request = factory.post(
        "/api/conceptos/",
        {"codigo": 10, "descripcion": "Nuevo", "activo": True},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    nuevo = {"codigo_concepto": 10, "descripcion": "Nuevo", "reportable": "S", "observacion": None}
    with patch("parametros.views.servicios.crear_concepto", return_value=nuevo):
        response = ConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 201
    assert response.data["codigo"] == 10


def test_create_409_cuando_codigo_ya_existe():
    request = factory.post(
        "/api/conceptos/",
        {"codigo": 1, "descripcion": "Dup", "activo": True},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.crear_concepto", side_effect=servicios.ConceptoYaExiste):
        response = ConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_partial_update_responde_200():
    request = factory.patch(
        "/api/conceptos/1/",
        {"descripcion": "Modificado"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    actualizado = {"codigo_concepto": 1, "descripcion": "Modificado", "reportable": "S", "observacion": None}
    with patch("parametros.views.servicios.actualizar_concepto", return_value=actualizado):
        response = ConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["descripcion"] == "Modificado"


def test_partial_update_404_cuando_no_existe():
    request = factory.patch(
        "/api/conceptos/999/",
        {"descripcion": "X"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.actualizar_concepto", return_value=None):
        response = ConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="999")
    assert response.status_code == 404


# ===========================================================================
# RF43 — Grupos de conceptos
# ===========================================================================

_FECHA = datetime(2026, 10, 10, 0, 0, 0)
_GRUPO_DICT = {
    "grupo_id":       1,
    "nombre":         "Grupo A",
    "activo":         "S",
    "fecha_creacion": _FECHA,
    "conceptos":      [{"codigo": 30, "descripcion": "Energía activa"}],
}


# ---------------------------------------------------------------------------
# Serializer GrupoConceptoSerializer
# ---------------------------------------------------------------------------

def test_grupo_repr_activo_s_es_true():
    data = GrupoConceptoSerializer(_GRUPO_DICT).data
    assert data["activo"] is True
    assert data["id"] == 1
    assert data["creado"] == "2026-10-10"
    assert data["conceptos"][0]["codigo"] == 30


def test_grupo_repr_activo_n_es_false():
    grupo = {**_GRUPO_DICT, "activo": "N"}
    data = GrupoConceptoSerializer(grupo).data
    assert data["activo"] is False


def test_grupo_repr_conceptos_vacio():
    grupo = {**_GRUPO_DICT, "conceptos": []}
    data = GrupoConceptoSerializer(grupo).data
    assert data["conceptos"] == []


# ---------------------------------------------------------------------------
# Serializer GrupoConceptoCrearSerializer
# ---------------------------------------------------------------------------

def test_crear_serializer_lista_vacia_invalida():
    s = GrupoConceptoCrearSerializer(data={"nombre": "X", "conceptos": []})
    assert not s.is_valid()
    assert "conceptos" in s.errors


def test_crear_serializer_valido():
    s = GrupoConceptoCrearSerializer(data={"nombre": "Grupo", "conceptos": [30, 61]})
    assert s.is_valid(), s.errors
    assert s.validated_data["conceptos"] == [30, 61]


def test_crear_serializer_nombre_max_60():
    s = GrupoConceptoCrearSerializer(data={"nombre": "X" * 61, "conceptos": [30]})
    assert not s.is_valid()
    assert "nombre" in s.errors


# ---------------------------------------------------------------------------
# Serializer GrupoConceptoActualizarSerializer
# ---------------------------------------------------------------------------

def test_actualizar_grupo_serializer_activo_true_a_s():
    s = GrupoConceptoActualizarSerializer(data={"activo": True})
    assert s.is_valid(), s.errors
    assert s.validated_data["activo"] == "S"


def test_actualizar_grupo_serializer_activo_false_a_n():
    s = GrupoConceptoActualizarSerializer(data={"activo": False})
    assert s.is_valid(), s.errors
    assert s.validated_data["activo"] == "N"


def test_actualizar_grupo_serializer_sin_activo_no_incluye_clave():
    s = GrupoConceptoActualizarSerializer(data={"nombre": "Nuevo"})
    assert s.is_valid(), s.errors
    assert "activo" not in s.validated_data


# ---------------------------------------------------------------------------
# Servicios — _validar_conceptos
# ---------------------------------------------------------------------------

def test_validar_conceptos_lista_vacia_lanza_excepcion():
    with pytest.raises(servicios.ConceptoInvalido) as exc_info:
        servicios._validar_conceptos([])
    assert exc_info.value.codigo is None


def test_validar_conceptos_codigo_no_activo_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn(fetchall=[(30,)])  # solo 30 es válido
    with patch("parametros.servicios.connection", mock_conn):
        with pytest.raises(servicios.ConceptoInvalido) as exc_info:
            servicios._validar_conceptos([30, 99])
    assert exc_info.value.codigo == 99


def test_validar_conceptos_todos_validos():
    mock_conn, mock_cursor = _mock_conn(fetchall=[(30,), (61,)])
    with patch("parametros.servicios.connection", mock_conn):
        servicios._validar_conceptos([30, 61])  # no debe lanzar


# ---------------------------------------------------------------------------
# Servicios — listar_grupos
# ---------------------------------------------------------------------------

def test_listar_grupos_ensamblado_correcto():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchall.side_effect = [
        [(1, "Grupo A", "S", _FECHA)],
        [(1, 30, "Energía activa"), (1, 61, "Reactiva")],
    ]
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.listar_grupos()
    assert len(result) == 1
    assert result[0]["nombre"] == "Grupo A"
    assert len(result[0]["conceptos"]) == 2


def test_listar_grupos_sin_detalles():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchall.side_effect = [
        [(2, "Grupo B", "N", _FECHA)],
        [],
    ]
    with patch("parametros.servicios.connection", mock_conn):
        result = servicios.listar_grupos()
    assert result[0]["conceptos"] == []


# ---------------------------------------------------------------------------
# Servicios — crear_grupo
# ---------------------------------------------------------------------------

def test_crear_grupo_llama_insert_y_retorna_grupo():
    mock_conn, mock_cursor = _mock_conn(fetchone=(42,))
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic), \
         patch("parametros.servicios._validar_conceptos"), \
         patch("parametros.servicios._insertar_detalle"), \
         patch("parametros.servicios._buscar_grupo_por_id", return_value=_GRUPO_DICT) as mock_buscar:
        result = servicios.crear_grupo({"nombre": "Grupo A", "conceptos": [30]})
    assert result == _GRUPO_DICT
    mock_buscar.assert_called_once_with(42)


def test_crear_grupo_integrity_error_lanza_grupo_ya_existe():
    mock_conn, mock_cursor = _mock_conn(fetchone=(1,))
    mock_cursor.execute.side_effect = [
        None,                        # NEXTVAL
        IntegrityError("ORA-00001"), # INSERT
    ]
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic), \
         patch("parametros.servicios._validar_conceptos"):
        with pytest.raises(servicios.GrupoYaExiste):
            servicios.crear_grupo({"nombre": "Dup", "conceptos": [30]})


def test_crear_grupo_concepto_invalido_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn(fetchone=(1,))
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic), \
         patch("parametros.servicios._validar_conceptos",
               side_effect=servicios.ConceptoInvalido(99)):
        with pytest.raises(servicios.ConceptoInvalido) as exc_info:
            servicios.crear_grupo({"nombre": "X", "conceptos": [99]})
    assert exc_info.value.codigo == 99


# ---------------------------------------------------------------------------
# Servicios — actualizar_grupo
# ---------------------------------------------------------------------------

def test_actualizar_grupo_no_encontrado():
    mock_conn, mock_cursor = _mock_conn(fetchone=(0,))
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoNoEncontrado):
            servicios.actualizar_grupo(99, {"nombre": "X"})


def test_actualizar_grupo_nombre_duplicado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1,)  # COUNT = 1 (existe)
    mock_cursor.execute.side_effect = [
        None,                        # COUNT SELECT
        IntegrityError("ORA-00001"), # UPDATE nombre
    ]
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoYaExiste):
            servicios.actualizar_grupo(1, {"nombre": "Dup"})


def test_actualizar_grupo_reemplaza_conceptos():
    mock_conn, mock_cursor = _mock_conn(fetchone=(1,))
    with patch("parametros.servicios.connection", mock_conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic), \
         patch("parametros.servicios._validar_conceptos"), \
         patch("parametros.servicios._insertar_detalle") as mock_ins, \
         patch("parametros.servicios._buscar_grupo_por_id", return_value=_GRUPO_DICT):
        servicios.actualizar_grupo(1, {"conceptos": [30, 61]})
    mock_ins.assert_called_once_with(1, [30, 61])


# ---------------------------------------------------------------------------
# Servicios — eliminar_grupo
# ---------------------------------------------------------------------------

def test_eliminar_grupo_con_borrador_lanza_grupo_en_uso():
    mock_conn, mock_cursor = _mock_conn(fetchone=(1,))  # 1 corte BORRADOR
    with patch("parametros.servicios.connection", mock_conn):
        with pytest.raises(servicios.GrupoEnUso):
            servicios.eliminar_grupo(1)


def test_eliminar_grupo_no_encontrado():
    mock_conn, mock_cursor = _mock_conn(fetchone=(0,))  # sin BORRADOR
    mock_cursor.rowcount = 0  # ninguna fila borrada
    with patch("parametros.servicios.connection", mock_conn):
        with pytest.raises(servicios.GrupoNoEncontrado):
            servicios.eliminar_grupo(99)


def test_eliminar_grupo_ejecuta_delete():
    mock_conn, mock_cursor = _mock_conn(fetchone=(0,))
    mock_cursor.rowcount = 1
    with patch("parametros.servicios.connection", mock_conn):
        servicios.eliminar_grupo(1)
    calls_sql = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("DELETE" in s for s in calls_sql)


# ---------------------------------------------------------------------------
# Vistas GrupoConceptoViewSet
# ---------------------------------------------------------------------------

def test_grupo_list_200():
    request = factory.get("/api/grupos-conceptos/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_grupos", return_value=[_GRUPO_DICT]):
        response = GrupoConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data[0]["id"] == 1


def test_grupo_retrieve_200():
    request = factory.get("/api/grupos-conceptos/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.obtener_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["activo"] is True


def test_grupo_retrieve_404():
    request = factory.get("/api/grupos-conceptos/999/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.obtener_grupo", return_value=None):
        response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404


def test_grupo_create_201():
    request = factory.post(
        "/api/grupos-conceptos/",
        {"nombre": "Grupo A", "conceptos": [30]},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.crear_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 201
    assert response.data["nombre"] == "Grupo A"


def test_grupo_create_409_nombre_duplicado():
    request = factory.post(
        "/api/grupos-conceptos/",
        {"nombre": "Dup", "conceptos": [30]},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.crear_grupo",
               side_effect=servicios.GrupoYaExiste):
        response = GrupoConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_grupo_create_400_concepto_invalido():
    request = factory.post(
        "/api/grupos-conceptos/",
        {"nombre": "X", "conceptos": [99]},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.crear_grupo",
               side_effect=servicios.ConceptoInvalido(99)):
        response = GrupoConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert "99" in response.data["detail"]


def test_grupo_partial_update_200():
    request = factory.patch(
        "/api/grupos-conceptos/1/",
        {"nombre": "Nuevo nombre"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.actualizar_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 200


def test_grupo_partial_update_404():
    request = factory.patch(
        "/api/grupos-conceptos/99/",
        {"nombre": "X"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.actualizar_grupo",
               side_effect=servicios.GrupoNoEncontrado):
        response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="99")
    assert response.status_code == 404


def test_grupo_partial_update_409():
    request = factory.patch(
        "/api/grupos-conceptos/1/",
        {"nombre": "Dup"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.actualizar_grupo",
               side_effect=servicios.GrupoYaExiste):
        response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 409


def test_grupo_destroy_204():
    request = factory.delete("/api/grupos-conceptos/1/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.eliminar_grupo"):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 204


def test_grupo_destroy_409_en_uso():
    request = factory.delete("/api/grupos-conceptos/1/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.eliminar_grupo",
               side_effect=servicios.GrupoEnUso):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 409


def test_grupo_destroy_404():
    request = factory.delete("/api/grupos-conceptos/99/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    with patch("parametros.views.servicios.eliminar_grupo",
               side_effect=servicios.GrupoNoEncontrado):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="99")
    assert response.status_code == 404


def test_conceptos_sin_permiso_403():
    request = factory.get("/api/conceptos/")
    force_authenticate(request, user=usuario_con_rol("OTRO_ROL"))
    response = ConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403


# ── Corrección 1 — pk no numérico → 404 ──────────────────────────────────────

def test_retrieve_grupo_pk_no_numerico_404():
    request = factory.get("/api/grupos-conceptos/abc/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="abc")
    assert response.status_code == 404


def test_partial_update_grupo_pk_no_numerico_404():
    request = factory.patch("/api/grupos-conceptos/abc/", {"nombre": "X"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="abc")
    assert response.status_code == 404


def test_destroy_grupo_pk_no_numerico_404():
    request = factory.delete("/api/grupos-conceptos/abc/")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="abc")
    assert response.status_code == 404


def test_partial_update_concepto_pk_no_numerico_404():
    request = factory.patch("/api/conceptos/abc/", {"descripcion": "X"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = ConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="abc")
    assert response.status_code == 404


# ── Corrección 5 — Conceptos duplicados en grupos ────────────────────────────

def test_crear_grupo_conceptos_duplicados_400():
    request = factory.post(
        "/api/grupos-conceptos/",
        {"nombre": "G", "conceptos": [30, 30]},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = GrupoConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert "No se permiten códigos repetidos." in str(response.data)


def test_actualizar_grupo_conceptos_duplicados_400():
    request = factory.patch(
        "/api/grupos-conceptos/1/",
        {"conceptos": [30, 61, 30]},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ADMINISTRADOR"))
    response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 400
    assert "No se permiten códigos repetidos." in str(response.data)


# ── C1 — Permisos: analista puede leer, no puede escribir ────────────────────

def test_concepto_list_analista_200():
    request = factory.get("/api/conceptos/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]):
        response = ConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200


def test_concepto_create_analista_403():
    request = factory.post("/api/conceptos/", {"codigo": 1, "descripcion": "X"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 403


def test_concepto_partial_update_analista_403():
    request = factory.patch("/api/conceptos/1/", {"descripcion": "X"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 403


def test_grupo_list_analista_200():
    request = factory.get("/api/grupos-conceptos/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.listar_grupos", return_value=[]):
        response = GrupoConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200


def test_grupo_retrieve_analista_200():
    request = factory.get("/api/grupos-conceptos/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("parametros.views.servicios.obtener_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="1")
    assert response.status_code == 200


def test_grupo_create_analista_403():
    request = factory.post(
        "/api/grupos-conceptos/", {"nombre": "G", "conceptos": [30]}, format="json"
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = GrupoConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 403


def test_grupo_partial_update_analista_403():
    request = factory.patch(
        "/api/grupos-conceptos/1/", {"nombre": "X"}, format="json"
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 403


def test_grupo_destroy_analista_403():
    request = factory.delete("/api/grupos-conceptos/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Datos de la entidad ante TransUnion (RF57)
# ---------------------------------------------------------------------------

from parametros.serializers import EntidadActualizarSerializer
from parametros.views import EntidadView

_ENTIDAD_REAL = {
    "tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "A1B2C3",
    "con_marcador": False, "prefijo_archivo": "SSR001123",
    "actualizado_por": "Rosa Martínez", "fecha_actualizacion": datetime(2026, 11, 7, 10, 0),
}


def _cursor_entidad(filas_parametro, fila_bitacora=None):
    mock_conn = MagicMock()
    cursor = mock_conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = filas_parametro
    cursor.fetchone.return_value = fila_bitacora
    return mock_conn, cursor


@contextmanager
def _guardado_simulado(conn):
    with patch("parametros.servicios.connection", conn), \
         patch("parametros.servicios.transaction.atomic", _noop_atomic), \
         patch("parametros.servicios.tolerar_fallo_bitacora", lambda accion: _noop_atomic()), \
         patch("parametros.servicios.registrar_bitacora") as bitacora:
        yield bitacora


@pytest.mark.parametrize("valor, esperado", [
    ("XXX", True), ("XXXXXX", True), ("001", False), ("A1B2C3", False), ("XA1B2C", False), ("", False),
])
def test_es_marcador(valor, esperado):
    assert servicios.es_marcador(valor) is esperado


def test_datos_entidad_con_codigos_asignados():
    conn, _ = _cursor_entidad([
        ("TIPO_ENTIDAD", "001"), ("CODIGO_ENTIDAD", "123"), ("CODIGO_SUCURSAL", "A1B2C3"),
    ])
    with patch("parametros.servicios.connection", conn):
        entidad = servicios.datos_entidad()
    assert entidad["con_marcador"] is False
    assert entidad["prefijo_archivo"] == "SSR001123"
    assert entidad["codigo_sucursal"] == "A1B2C3"


def test_datos_entidad_valores_viejos_o_ausentes_salen_como_marcador():
    # PENDIENTE/PEND (antes del script 10) o una clave que no existe nunca dan un archivo apto.
    conn, _ = _cursor_entidad([("TIPO_ENTIDAD", "PENDIENTE"), ("CODIGO_SUCURSAL", "PEND")])
    with patch("parametros.servicios.connection", conn):
        entidad = servicios.datos_entidad()
    assert entidad["tipo_entidad"] == "XXX"
    assert entidad["codigo_entidad"] == "XXX"
    assert entidad["codigo_sucursal"] == "XXXXXX"
    assert entidad["con_marcador"] is True
    assert entidad["prefijo_archivo"] == "SSRXXXXXX"


def test_obtener_entidad_toma_quien_y_cuando_de_la_bitacora():
    fecha = datetime(2026, 11, 7, 10, 0)
    conn, _ = _cursor_entidad(
        [("TIPO_ENTIDAD", "001"), ("CODIGO_ENTIDAD", "123"), ("CODIGO_SUCURSAL", "A1B2C3")],
        ("Rosa Martínez", fecha),
    )
    with patch("parametros.servicios.connection", conn):
        entidad = servicios.obtener_entidad()
    assert entidad["actualizado_por"] == "Rosa Martínez"
    assert entidad["fecha_actualizacion"] == fecha


def test_obtener_entidad_sin_cambios_registrados():
    conn, _ = _cursor_entidad([], None)
    with patch("parametros.servicios.connection", conn):
        entidad = servicios.obtener_entidad()
    assert entidad["actualizado_por"] is None
    assert entidad["fecha_actualizacion"] is None


def test_guardar_entidad_confirma_solo_los_valores_sin_marcador():
    conn, cursor = _cursor_entidad([])
    usuario = MagicMock(nombre="Rosa Martínez", pk=1)
    datos = {"tipo_entidad": "001", "codigo_entidad": "XXX", "codigo_sucursal": "A1B2C3"}
    with _guardado_simulado(conn) as bitacora:
        entidad = servicios.guardar_entidad(datos, usuario=usuario)
    params = [c.args[1] for c in cursor.execute.call_args_list]
    assert params == [
        ["TIPO_ENTIDAD", "001", "S"],
        ["CODIGO_ENTIDAD", "XXX", "N"],
        ["CODIGO_SUCURSAL", "A1B2C3", "S"],
    ]
    bitacora.assert_called_once()
    assert bitacora.call_args.args[0] == "ENTIDAD_ACTUALIZADA"
    assert entidad["con_marcador"] is True
    assert entidad["actualizado_por"] == "Rosa Martínez"


def test_serializer_entidad_pasa_sucursal_a_mayusculas():
    s = EntidadActualizarSerializer(
        data={"tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "a1b2c3"}
    )
    assert s.is_valid(), s.errors
    assert s.validated_data["codigo_sucursal"] == "A1B2C3"


@pytest.mark.parametrize("datos, campo", [
    ({"tipo_entidad": "12", "codigo_entidad": "123", "codigo_sucursal": "A1B2C3"}, "tipo_entidad"),
    ({"tipo_entidad": "001", "codigo_entidad": "12A", "codigo_sucursal": "A1B2C3"}, "codigo_entidad"),
    ({"tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "A1B2"}, "codigo_sucursal"),
    ({"tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "A1B2-3"}, "codigo_sucursal"),
])
def test_serializer_entidad_rechaza_largo_o_tipo(datos, campo):
    s = EntidadActualizarSerializer(data=datos)
    assert not s.is_valid()
    assert list(s.errors) == [campo]


def test_serializer_entidad_campo_faltante():
    s = EntidadActualizarSerializer(data={"tipo_entidad": "001", "codigo_entidad": "123"})
    assert not s.is_valid()
    assert s.errors["codigo_sucursal"] == ["Este campo es requerido."]


def _peticion_entidad(metodo, rol, datos=None):
    factory = APIRequestFactory()
    request = getattr(factory, metodo)("/api/entidad/", datos or {}, format="json")
    usuario = usuario_con_rol(rol)
    usuario.nombre = "Rosa Martínez"
    force_authenticate(request, user=usuario)
    return EntidadView.as_view()(request)


@pytest.mark.parametrize("rol", ["ANALISTA_CARTERA", "ADMINISTRADOR"])
def test_get_entidad_ambos_roles_200(rol):
    with patch("parametros.views.servicios.obtener_entidad", return_value=_ENTIDAD_REAL):
        response = _peticion_entidad("get", rol)
    assert response.status_code == 200
    assert response.data["prefijo_archivo"] == "SSR001123"
    assert response.data["fecha_actualizacion"] == "2026-11-07T10:00:00-05:00"


def test_put_entidad_admin_guarda_codigos_reales():
    datos = {"tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "A1B2C3"}
    with patch("parametros.views.servicios.guardar_entidad", return_value=_ENTIDAD_REAL) as guardar:
        response = _peticion_entidad("put", "ADMINISTRADOR", datos)
    assert response.status_code == 200
    assert response.data["con_marcador"] is False
    assert guardar.call_args.args[0] == datos


def test_put_entidad_tipo_de_dos_digitos_400():
    datos = {"tipo_entidad": "12", "codigo_entidad": "123", "codigo_sucursal": "A1B2C3"}
    with patch("parametros.views.servicios.guardar_entidad") as guardar:
        response = _peticion_entidad("put", "ADMINISTRADOR", datos)
    assert response.status_code == 400
    assert "tipo_entidad" in response.data
    guardar.assert_not_called()


def test_put_entidad_analista_403():
    datos = {"tipo_entidad": "001", "codigo_entidad": "123", "codigo_sucursal": "A1B2C3"}
    with patch("parametros.views.servicios.guardar_entidad") as guardar:
        response = _peticion_entidad("put", "ANALISTA_CARTERA", datos)
    assert response.status_code == 403
    guardar.assert_not_called()


def test_put_entidad_volver_al_relleno():
    datos = {"tipo_entidad": "XXX", "codigo_entidad": "XXX", "codigo_sucursal": "XXXXXX"}
    conn, _ = _cursor_entidad([])
    with _guardado_simulado(conn):
        response = _peticion_entidad("put", "ADMINISTRADOR", datos)
    assert response.status_code == 200
    assert response.data["con_marcador"] is True
    assert response.data["prefijo_archivo"] == "SSRXXXXXX"
    assert response.data["actualizado_por"] == "Rosa Martínez"


# ---------------------------------------------------------------------------
# Catálogo y homologación de estados (RF48)
# ---------------------------------------------------------------------------

from parametros.views import EstadosTUView, HomologacionEstadosView, HomologacionEstadoView

# (codigo, nombre, USADO, ES_CIERRE, CONFIRMADO) como los devuelve NV_ESTADO_TU para servicios.
_FILAS_ESTADOS = [
    ("01", "Vigente", "S", "N", "S"),
    ("02", "Saldada", "S", "S", "S"),
    ("03", "Dudoso recaudo", "S", "N", "N"),
    ("04", "Suspendida por la entidad", "N", "N", "N"),
    ("06", "Castigada", "S", "N", "S"),
    ("07", "Castigada recuperada", "S", "S", "S"),
    ("08", "Inactivo", "N", "N", "S"),
    ("10", "Ley 550 de 1999", "S", "N", "N"),
    ("11", "Ley 1116 de 2006", "S", "N", "N"),
    ("12", "Ley 1564 de 2012 Insolvencia PNNC", "S", "N", "N"),
]
_ESTADOS = [
    {"codigo": c, "nombre": n, "usado": u == "S", "es_cierre": e == "S", "confirmado": f == "S"}
    for c, n, u, e, f in _FILAS_ESTADOS
]
_FILA_A = ("A", 1, "Activo (propuesto)", "ESTADO", "01", "N", None, None)


def test_listar_estados_tu_traduce_las_banderas():
    conn, _ = _cursor_entidad(_FILAS_ESTADOS)
    with patch("parametros.servicios.connection", conn):
        estados = servicios.listar_estados_tu()
    assert len(estados) == 10
    assert estados[1] == {"codigo": "02", "nombre": "Saldada", "usado": True, "es_cierre": True, "confirmado": True}
    assert [e["codigo"] for e in estados if not e["usado"]] == ["04", "08"]


def test_listar_homologaciones_pone_el_nombre_de_quien_la_cambio():
    fecha = datetime(2026, 11, 7, 10, 30)
    conn, _ = _cursor_entidad([
        ("A", 1, "Activo (propuesto)", "ESTADO", "01", "S", 1, fecha),
        ("F", 5, "Finalizado (propuesto)", "CIERRE", None, "N", None, None),
        ("B", 4, "Desconocido: preguntar a CENS", None, None, "N", None, None),
    ])
    with patch("parametros.servicios.connection", conn), \
         patch("parametros.servicios._nombres_usuarios", return_value={1: "Rosa Martínez"}):
        filas = servicios.listar_homologaciones()
    assert filas[0] == {
        "estado_sac": "A", "prioridad": 1, "descripcion": "Activo (propuesto)", "accion": "ESTADO",
        "estado_tu": "01", "confirmado": True, "actualizado_por": "Rosa Martínez", "fecha_actualizacion": fecha,
    }
    assert filas[1]["accion"] == "CIERRE" and filas[1]["estado_tu"] is None
    assert filas[2]["accion"] is None  # sin homologar: RF53 bloquea sus obligaciones


@pytest.mark.parametrize("accion, estado_tu, esperado", [
    ("ESTADO", "01", {}),
    ("ESTADO", "03", {}),
    ("CIERRE", None, {}),
    (None, None, {"accion": ["Elige cómo se reporta el estado: como estado de TransUnion o como cierre."]}),
    ("OTRA", "01", {"accion": ["Elige cómo se reporta el estado: como estado de TransUnion o como cierre."]}),
    ("ESTADO", None, {"estado_tu": ["Selecciona el estado de TransUnion."]}),
    ("ESTADO", "05", {"estado_tu": ["Ese estado no está en la Tabla 4b de TransUnion."]}),
    ("ESTADO", "08", {"estado_tu": ["El estado 08 · Inactivo no se usa en CENS: elige un estado en uso."]}),
    ("ESTADO", "04", {"estado_tu": ["El estado 04 · Suspendida por la entidad no se usa en CENS: elige un estado en uso."]}),
    ("ESTADO", "02", {"estado_tu": ["Saldada (02) y Castigada recuperada (07) se asignan con «Cierre», según el estado anterior."]}),
    ("ESTADO", "07", {"estado_tu": ["Saldada (02) y Castigada recuperada (07) se asignan con «Cierre», según el estado anterior."]}),
    ("CIERRE", "02", {"estado_tu": ["Un estado que cierra el crédito no lleva estado de TransUnion."]}),
])
def test_validar_homologacion(accion, estado_tu, esperado):
    assert servicios.validar_homologacion(accion, estado_tu, _ESTADOS) == esperado


def _actualizar(estado_sac, accion, estado_tu, confirmado=False, fila_existente=_FILA_A):
    conn, cursor = _cursor_entidad([fila_existente] if fila_existente else [])
    usuario = MagicMock(nombre="Rosa Martínez", pk=1)
    with _guardado_simulado(conn) as bitacora, \
         patch("parametros.servicios.listar_estados_tu", return_value=_ESTADOS), \
         patch("parametros.servicios._nombres_usuarios", return_value={}):
        resultado = servicios.actualizar_homologacion(estado_sac, accion, estado_tu, confirmado, usuario=usuario)
    return resultado, cursor, bitacora


def test_actualizar_homologacion_guarda_y_deja_bitacora():
    _, cursor, bitacora = _actualizar("A", "ESTADO", "01", confirmado=True)
    update = next(c for c in cursor.execute.call_args_list if c.args[0].startswith("UPDATE"))
    accion, estado_tu, confirmado, usuario_id, _, estado_sac = update.args[1]
    assert (accion, estado_tu, confirmado, usuario_id, estado_sac) == ("ESTADO", "01", "S", 1, "A")
    bitacora.assert_called_once()
    assert bitacora.call_args.args[:3] == ("HOMOLOGACION_ACTUALIZADA", "NV_HOMOLOGA_ESTADO", "A")


def test_actualizar_homologacion_cierre_guarda_estado_nulo():
    _, cursor, _ = _actualizar("F", "CIERRE", None, fila_existente=("F", 5, "Finalizado", "CIERRE", None, "N", None, None))
    update = next(c for c in cursor.execute.call_args_list if c.args[0].startswith("UPDATE"))
    assert update.args[1][:2] == ["CIERRE", None]


def test_actualizar_homologacion_estado_no_usado_no_guarda():
    with pytest.raises(servicios.HomologacionInvalida) as exc:
        _actualizar("A", "ESTADO", "08")
    assert "estado_tu" in exc.value.errores


def test_actualizar_homologacion_estado_sac_inexistente():
    with pytest.raises(servicios.EstadoSacNoEncontrado):
        _actualizar("Z", "ESTADO", "01", fila_existente=None)


def _peticion_homologacion(vista, metodo, rol, datos=None, **kwargs):
    factory = APIRequestFactory()
    request = getattr(factory, metodo)("/api/homologacion-estados/", datos or {}, format="json")
    usuario = usuario_con_rol(rol)
    usuario.nombre = "Rosa Martínez"
    force_authenticate(request, user=usuario)
    return vista.as_view()(request, **kwargs)


@pytest.mark.parametrize("vista", [EstadosTUView, HomologacionEstadosView])
def test_listados_solo_administrador(vista):
    with patch("parametros.views.servicios.listar_estados_tu", return_value=_ESTADOS), \
         patch("parametros.views.servicios.listar_homologaciones", return_value=[]):
        assert _peticion_homologacion(vista, "get", "ADMINISTRADOR").status_code == 200
        assert _peticion_homologacion(vista, "get", "ANALISTA_CARTERA").status_code == 403


def test_put_homologacion_admin_cambia_a_vigente():
    guardada = {
        "estado_sac": "A", "prioridad": 1, "descripcion": "Activo (propuesto)", "accion": "ESTADO",
        "estado_tu": "01", "confirmado": True, "actualizado_por": "Rosa Martínez",
        "fecha_actualizacion": datetime(2026, 11, 7, 10, 30),
    }
    with patch("parametros.views.servicios.actualizar_homologacion", return_value=guardada) as actualizar:
        response = _peticion_homologacion(
            HomologacionEstadoView, "put", "ADMINISTRADOR",
            {"accion": "ESTADO", "estado_tu": "01", "confirmado": True}, estado_sac="A",
        )
    assert response.status_code == 200
    assert response.data["fecha_actualizacion"] == "2026-11-07T10:30:00-05:00"
    assert actualizar.call_args.args == ("A", "ESTADO", "01", True)


def test_put_homologacion_analista_403():
    with patch("parametros.views.servicios.actualizar_homologacion") as actualizar:
        response = _peticion_homologacion(
            HomologacionEstadoView, "put", "ANALISTA_CARTERA", {"accion": "ESTADO", "estado_tu": "01"}, estado_sac="A",
        )
    assert response.status_code == 403
    actualizar.assert_not_called()


def test_put_homologacion_estado_no_usado_400_por_campo():
    errores = {"estado_tu": ["El estado 08 · Inactivo no se usa en CENS: elige un estado en uso."]}
    with patch("parametros.views.servicios.actualizar_homologacion", side_effect=servicios.HomologacionInvalida(errores)):
        response = _peticion_homologacion(
            HomologacionEstadoView, "put", "ADMINISTRADOR", {"accion": "ESTADO", "estado_tu": "08"}, estado_sac="A",
        )
    assert response.status_code == 400
    assert response.data == errores


def test_put_homologacion_estado_sac_inexistente_404():
    with patch("parametros.views.servicios.actualizar_homologacion", side_effect=servicios.EstadoSacNoEncontrado()):
        response = _peticion_homologacion(
            HomologacionEstadoView, "put", "ADMINISTRADOR", {"accion": "CIERRE", "estado_tu": None}, estado_sac="Z",
        )
    assert response.status_code == 404
    assert response.data == {"detail": "Estado del SAC no encontrado."}


def test_put_homologacion_estado_vacio_se_toma_como_nulo():
    with patch("parametros.views.servicios.actualizar_homologacion", return_value={**dict.fromkeys(
        ["estado_sac", "prioridad", "descripcion", "accion", "estado_tu", "confirmado", "actualizado_por"]),
        "fecha_actualizacion": None}) as actualizar:
        _peticion_homologacion(HomologacionEstadoView, "put", "ADMINISTRADOR", {"accion": "CIERRE", "estado_tu": ""}, estado_sac="F")
    assert actualizar.call_args.args == ("F", "CIERRE", None, False)


def test_los_sql_de_rf48_usan_las_mismas_columnas_que_el_servicio():
    # El servicio, el script 12a y su verificación deben nombrar igual las columnas de NV_ESTADO_TU.
    from pathlib import Path

    carpeta = Path(servicios.__file__).parent / "sql"
    codigo, nombre = servicios._COL_ESTADO_TU["codigo"], servicios._COL_ESTADO_TU["nombre"]
    script = (carpeta / "12a_rf48_homologacion_estados.sql").read_text(encoding="utf-8")
    verificacion = (carpeta / "verificacion_12a_rf48_homologacion_estados.sql").read_text(encoding="utf-8")
    assert f"WHEN {codigo} IN" in script
    assert f"SELECT {codigo}, {nombre}, ES_CIERRE" in verificacion
