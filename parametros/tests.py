from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError
from rest_framework.test import APIRequestFactory

from parametros import servicios
from parametros.serializers import ConceptoReportableSerializer, ConceptoActualizarSerializer
from parametros.views import ConceptoViewSet

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
