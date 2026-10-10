from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from django.db import IntegrityError
from rest_framework.test import APIRequestFactory


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


def _usuario_analista():
    user = MagicMock()
    user.rol = "ANALISTA_CARTERA"
    return user


def test_list_responde_200_con_campo_codigo():
    request = factory.get("/api/conceptos/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.listar_conceptos", return_value=[_CONCEPTO]):
        response = ConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data[0]["codigo"] == 1


def test_list_con_filtro_activo_true_pasa_bool_al_servicio():
    request = factory.get("/api/conceptos/", {"activo": "true"})
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]) as mock_listar:
        ConceptoViewSet.as_view({"get": "list"})(request)
    mock_listar.assert_called_once_with(activo=True)


def test_list_con_filtro_activo_false():
    request = factory.get("/api/conceptos/", {"activo": "false"})
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]) as mock_listar:
        ConceptoViewSet.as_view({"get": "list"})(request)
    mock_listar.assert_called_once_with(activo=False)


def test_create_responde_201():
    request = factory.post(
        "/api/conceptos/",
        {"codigo": 10, "descripcion": "Nuevo", "activo": True},
        format="json",
    )
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.crear_concepto", side_effect=servicios.ConceptoYaExiste):
        response = ConceptoViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_partial_update_responde_200():
    request = factory.patch(
        "/api/conceptos/1/",
        {"descripcion": "Modificado"},
        format="json",
    )
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.listar_grupos", return_value=[_GRUPO_DICT]):
        response = GrupoConceptoViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data[0]["id"] == 1


def test_grupo_retrieve_200():
    request = factory.get("/api/grupos-conceptos/1/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.obtener_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["activo"] is True


def test_grupo_retrieve_404():
    request = factory.get("/api/grupos-conceptos/999/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.obtener_grupo", return_value=None):
        response = GrupoConceptoViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404


def test_grupo_create_201():
    request = factory.post(
        "/api/grupos-conceptos/",
        {"nombre": "Grupo A", "conceptos": [30]},
        format="json",
    )
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.actualizar_grupo", return_value=_GRUPO_DICT):
        response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 200


def test_grupo_partial_update_404():
    request = factory.patch(
        "/api/grupos-conceptos/99/",
        {"nombre": "X"},
        format="json",
    )
    request.user = _usuario_analista()
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
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.actualizar_grupo",
               side_effect=servicios.GrupoYaExiste):
        response = GrupoConceptoViewSet.as_view({"patch": "partial_update"})(request, pk="1")
    assert response.status_code == 409


def test_grupo_destroy_204():
    request = factory.delete("/api/grupos-conceptos/1/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.eliminar_grupo"):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 204


def test_grupo_destroy_409_en_uso():
    request = factory.delete("/api/grupos-conceptos/1/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.eliminar_grupo",
               side_effect=servicios.GrupoEnUso):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 409


def test_grupo_destroy_404():
    request = factory.delete("/api/grupos-conceptos/99/")
    request.user = _usuario_analista()
    with patch("parametros.views.servicios.eliminar_grupo",
               side_effect=servicios.GrupoNoEncontrado):
        response = GrupoConceptoViewSet.as_view({"delete": "destroy"})(request, pk="99")
    assert response.status_code == 404
