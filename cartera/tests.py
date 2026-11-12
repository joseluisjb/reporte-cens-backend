from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from tests.ayudas import usuario_con_rol

from cartera import servicios
from cartera.serializers import GenerarCorteSerializer, CorteResumenSerializer
from cartera.views import ArchivoViewSet, ExtraccionViewSet


# ── Helpers de test ───────────────────────────────────────────────────────────

@contextmanager
def _noop_atomic():
    yield


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


_FECHA_PASADA = date(2026, 9, 30)
_FECHA_FUTURA = date(date.today().year + 1, 1, 1)
_FECHA_GEN = datetime(2026, 10, 10, 12, 0, 0)

_RESUMEN = {
    "id": 1,
    "fecha_corte": _FECHA_PASADA,
    "fecha_ejecucion": _FECHA_GEN,
    "grupo": None,
    "obligaciones": 5,
    "saldo_consolidado": 1000000,
    "estado": "BORRADOR",
    "ejecutada_por": None,
}


# ── Serializer GenerarCorteSerializer ─────────────────────────────────────────

def test_serializer_fecha_corte_obligatoria():
    s = GenerarCorteSerializer(data={})
    assert not s.is_valid()
    assert "fecha_corte" in s.errors


def test_serializer_grupo_id_opcional():
    s = GenerarCorteSerializer(data={"fecha_corte": "2026-09-30"})
    assert s.is_valid(), s.errors
    assert "grupo_id" not in s.validated_data


def test_serializer_grupo_id_incluido():
    s = GenerarCorteSerializer(data={"fecha_corte": "2026-09-30", "grupo_id": 3})
    assert s.is_valid(), s.errors
    assert s.validated_data["grupo_id"] == 3


# ── Serializer CorteResumenSerializer ─────────────────────────────────────────

def test_resumen_serializer_sin_grupo():
    data = CorteResumenSerializer(_RESUMEN).data
    assert data["id"] == 1
    assert data["grupo"] is None
    assert data["estado"] == "BORRADOR"
    assert data["ejecutada_por"] is None
    assert data["saldo_consolidado"] == 1000000


def test_resumen_serializer_con_grupo():
    resumen = {**_RESUMEN, "grupo": {"id": 2, "nombre": "Grupo A"}}
    data = CorteResumenSerializer(resumen).data
    assert data["grupo"]["id"] == 2
    assert data["grupo"]["nombre"] == "Grupo A"


# ── Servicios — validaciones ──────────────────────────────────────────────────

def test_fecha_futura_lanza_excepcion():
    with patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.FechaInvalida):
            servicios.generar_corte(fecha_corte=_FECHA_FUTURA)


def test_grupo_inexistente_lanza_grupo_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoNoEncontrado):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=99)


def test_grupo_inactivo_lanza_grupo_inactivo():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),             # MAX(FECHA_CORTE) — sin enviados
        ("Grupo X", "N"),    # _validar_grupo — nombre, activo
    ]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.GrupoInactivo):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=5)


def test_corte_misma_fecha_estado_fijo_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),             # MAX(FECHA_CORTE) — sin enviados
        ("Grupo A", "S"),    # _validar_grupo — nombre y activo
        (7, "VALIDADO"),     # _verificar_corte_existente — corte con esa fecha
    ]
    mock_cursor.fetchall.return_value = [(30,)]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.CorteEnEstadoFijo):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=1)


def test_borrador_otra_fecha_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    otra_fecha = date(2026, 8, 31)
    mock_cursor.fetchone.side_effect = [
        (None,),                     # MAX(FECHA_CORTE) — sin enviados
        None,                        # _verificar_corte_existente — sin corte esa fecha
        (3, otra_fecha),             # _verificar_corte_existente — borrador de otra fecha
    ]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios._todos_los_conceptos_reportables", return_value="30,61"):
        with pytest.raises(servicios.BorradorOtraFecha) as exc_info:
            servicios.generar_corte(fecha_corte=_FECHA_PASADA)
    assert exc_info.value.fecha == otra_fecha


# ── Servicios — orden de operaciones ─────────────────────────────────────────

def test_corte_insertado_antes_de_vistas():
    """INSERT/UPDATE de NV_CORTE ocurre antes que SELECT de V_CALCULO_CORTE."""
    sqls_ejecutados = []

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False

    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador otra fecha
        (1,),               # _persistir_corte — NEXTVAL (INSERT no llama fetchone)
        (5, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL, FECHA_GENERACION
        (500000,),          # _finalizar_y_resumir — SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,)],     # _todos_los_conceptos_reportables
        [],                 # _insertar_obligaciones_nuevas — sin nuevas
    ]

    def capture_execute(sql, params=None):
        sqls_ejecutados.append(sql)

    mock_cursor.execute.side_effect = capture_execute

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    idx_insert_corte = next(
        i for i, s in enumerate(sqls_ejecutados) if "NV_CORTE" in s and "INSERT" in s
    )
    idx_select_vista = next(
        (i for i, s in enumerate(sqls_ejecutados) if "V_CALCULO_CORTE" in s),
        len(sqls_ejecutados),
    )
    assert idx_insert_corte < idx_select_vista, (
        "El INSERT en NV_CORTE debe ocurrir antes de leer V_CALCULO_CORTE"
    )


# ── Servicios — reemplazo de borrador ────────────────────────────────────────

def test_reemplaza_borrador_misma_fecha():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        (3, "BORRADOR"),    # _verificar_corte_existente — borrador existente
        (5, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL, FECHA_GENERACION
        (0,),               # _finalizar_y_resumir — SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,)],            # _todos_los_conceptos_reportables
        [],                 # _insertar_obligaciones_nuevas
    ]

    sqls = []
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append(sql)

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    assert any("DELETE" in s and "NV_REPORTE_DETALLE" in s for s in sqls)
    assert any("DELETE" in s and "NV_INCONSISTENCIA" in s for s in sqls)
    assert any("UPDATE" in s and "NV_CORTE" in s for s in sqls)
    assert not any("SEQ_NV_CORTE" in s for s in sqls)


# ── Servicios — conceptos sin grupo ──────────────────────────────────────────

def test_sin_grupo_conceptos_usados_son_todos_reportables():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # _persistir_corte — NEXTVAL (INSERT no llama fetchone)
        (0, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL
        (0,),               # _finalizar_y_resumir — SUM
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,), (90,)],  # _todos_los_conceptos_reportables
        [],                     # _insertar_obligaciones_nuevas
    ]

    inserts = []
    mock_cursor.execute.side_effect = lambda sql, params=None: inserts.append((sql, params))

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    insert_corte_params = next(
        params for sql, params in inserts
        if params and "INSERT" in sql and "NV_CORTE" in sql
    )
    # Orden: [corte_id, fecha_corte, fecha_gen, usuario_id, grupo_id, grupo_nombre, conceptos_usados]
    conceptos_usados = insert_corte_params[6]
    assert conceptos_usados == "30,61,90"
    assert insert_corte_params[3] is None   # usuario_id nulo (sin usuario: proceso mensual)
    assert insert_corte_params[4] is None   # grupo_id nulo
    assert insert_corte_params[5] is None   # grupo_nombre nulo


# ── Fila 42 — quién generó el corte (ejecutada_por) ──────────────────────────

def _fetchone_corte_nuevo():
    return [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # _persistir_corte — NEXTVAL
        (5, _FECHA_GEN),    # _finalizar_y_resumir — TOTAL, FECHA_GENERACION
        (0,),               # _finalizar_y_resumir — SUM
    ]


def test_generar_corte_guarda_el_usuario_de_la_sesion_y_devuelve_su_nombre():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = _fetchone_corte_nuevo()
    mock_cursor.fetchall.side_effect = [[(30,)], []]
    llamadas = []
    mock_cursor.execute.side_effect = lambda sql, params=None: llamadas.append((sql, params))
    analista = usuario_con_rol("ANALISTA_CARTERA")
    analista.pk, analista.nombre = 7, "Juan Pérez"

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA, usuario=analista)

    insert = next(p for s, p in llamadas if p and "INSERT" in s and "NV_CORTE" in s)
    assert insert[3] == 7
    assert resumen["ejecutada_por"] == "Juan Pérez"


def test_regenerar_borrador_lo_deja_a_nombre_de_quien_lo_regenero():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [(None,), (3, "BORRADOR"), (5, _FECHA_GEN), (0,)]
    mock_cursor.fetchall.side_effect = [[(30,)], []]
    llamadas = []
    mock_cursor.execute.side_effect = lambda sql, params=None: llamadas.append((sql, params))
    analista = usuario_con_rol("ANALISTA_CARTERA")
    analista.pk, analista.nombre = 9, "Laura Díaz"

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA, usuario=analista)

    sql, params = next((s, p) for s, p in llamadas if "UPDATE" in s and "NV_CORTE" in s and "USUARIO_ID" in s)
    assert params[1] == 9
    assert resumen["ejecutada_por"] == "Laura Díaz"


def test_listar_cortes_trae_el_nombre_de_quien_genero_cada_uno():
    mock_conn, mock_cursor = _mock_conn(fetchall=[
        (2, "2026-09-30", "BORRADOR", None, 5, None, None, 0, 7),
        (1, "2026-08-31", "ENVIADO", None, 3, None, None, 0, None),  # proceso mensual o anterior
    ])
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios._nombres_de_usuarios", return_value={7: "Juan Pérez"}) as nombres:
        cortes = servicios.listar_cortes()
    assert [c["ejecutada_por"] for c in cortes] == ["Juan Pérez", None]
    nombres.assert_called_once()


@pytest.mark.django_db
def test_nombres_de_usuarios_los_toma_de_la_tabla_de_django():
    from usuarios.models import Usuario
    juan = Usuario.objects.create_user("jperez@example.com", "ClaveSegura1", nombre="Juan Pérez")
    filas = [(1, None, None, None, 0, None, None, 0, juan.pk), (2, None, None, None, 0, None, None, 0, None)]
    assert servicios._nombres_de_usuarios(filas) == {juan.pk: "Juan Pérez"}
    assert servicios._nombres_de_usuarios([filas[1]]) == {}


def test_crear_corte_por_api_pasa_el_usuario_de_la_sesion():
    analista = usuario_con_rol("ANALISTA_CARTERA")
    request = factory.post("/api/extracciones/", {"fecha_corte": "2026-09-30"}, format="json")
    force_authenticate(request, user=analista)
    with patch("cartera.views.servicios.generar_corte", return_value=_RESUMEN) as generar:
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 201
    assert generar.call_args.kwargs["usuario"] is analista


# ── Servicios — resumen ───────────────────────────────────────────────────────

def test_resumen_estructura_correcta():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        None, None,         # _verificar_corte_existente
        (1,),               # NEXTVAL (INSERT no llama fetchone)
        (3, _FECHA_GEN),    # TOTAL + FECHA_GEN
        (750000,),          # SUM VALOR_SALDO
    ]
    mock_cursor.fetchall.side_effect = [[(30,)], []]

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA)

    assert set(resumen.keys()) == {
        "id", "fecha_corte", "fecha_ejecucion", "grupo",
        "obligaciones", "saldo_consolidado", "estado", "ejecutada_por",
    }
    assert resumen["estado"] == "BORRADOR"
    assert resumen["ejecutada_por"] is None
    assert resumen["grupo"] is None
    assert resumen["saldo_consolidado"] == 750000


def test_resumen_grupo_presente_cuando_se_usa_grupo():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        ("Grupo A", "S"),   # _validar_grupo — nombre, activo
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # NEXTVAL (INSERT no llama fetchone)
        (2, _FECHA_GEN),    # TOTAL + FECHA_GEN
        (200000,),          # SUM
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,), (61,)],     # _validar_grupo — conceptos
        [],                 # _insertar_obligaciones_nuevas
    ]

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA, grupo_id=2)

    assert resumen["grupo"] == {"id": 2, "nombre": "Grupo A"}


# ── Vistas ────────────────────────────────────────────────────────────────────

factory = APIRequestFactory()


def test_post_201_genera_corte():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 201
    assert response.data["estado"] == "BORRADOR"


def test_post_400_fecha_futura():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": str(_FECHA_FUTURA)},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.FechaInvalida("La fecha de corte no puede ser futura.")):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert "futura" in response.data["detail"]


def test_post_404_grupo_inexistente():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30", "grupo_id": 99},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.GrupoNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 404


def test_post_409_grupo_inactivo():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30", "grupo_id": 5},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.GrupoInactivo):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_post_409_borrador_otra_fecha():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.BorradorOtraFecha(date(2026, 8, 31), corte_id=3)):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409
    assert response.data["detail"] == (
        "Ya existe un corte en borrador con fecha 2026-08-31. "
        "Elimínelo o complételo antes de generar otro."
    )
    assert "/api/" not in response.data["detail"]


def test_post_409_estado_fijo():
    request = factory.post(
        "/api/extracciones/",
        {"fecha_corte": "2026-09-30"},
        format="json",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.CorteEnEstadoFijo):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409


def test_get_list_200():
    request = factory.get("/api/extracciones/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.listar_cortes", return_value=[_RESUMEN]):
        response = ExtraccionViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data) == 1


def test_get_ultima_200():
    request = factory.get("/api/extracciones/ultima/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_ultimo_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"get": "ultima"})(request)
    assert response.status_code == 200
    assert response.data["id"] == 1


def test_get_ultima_204_sin_cortes():
    request = factory.get("/api/extracciones/ultima/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_ultimo_corte", return_value=None):
        response = ExtraccionViewSet.as_view({"get": "ultima"})(request)
    assert response.status_code == 204


def test_get_id_200():
    request = factory.get("/api/extracciones/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_corte", return_value=_RESUMEN):
        response = ExtraccionViewSet.as_view({"get": "retrieve"})(request, pk="1")
    assert response.status_code == 200


def test_get_id_404():
    request = factory.get("/api/extracciones/999/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_corte", return_value=None):
        response = ExtraccionViewSet.as_view({"get": "retrieve"})(request, pk="999")
    assert response.status_code == 404


def test_get_obligaciones_200():
    request = factory.get(
        "/api/extracciones/1/obligaciones/",
        {"limite": "10", "desplazamiento": "0"},
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    payload = {
        "total": 2,
        "resultados": [
            {
                "numero_obligacion": "OBL001",
                "nombre_titular": "Juan",
                "numero_identificacion": "12345",
                "estado_tu": "01",
                "edad_mora": "00",
                "dias_mora": 0,
                "cuotas_mora": 0,
                "valor_mora": 0,
                "valor_saldo": 500000,
                "n_creditos": 1,
            }
        ],
    }
    with patch("cartera.views.servicios.listar_obligaciones", return_value=payload):
        response = ExtraccionViewSet.as_view({"get": "obligaciones"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["total"] == 2


def test_get_obligaciones_404():
    request = factory.get("/api/extracciones/999/obligaciones/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.listar_obligaciones",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"get": "obligaciones"})(request, pk="999")
    assert response.status_code == 404


# ── Servicios — validar_corte ─────────────────────────────────────────────────

def test_validar_corte_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.validar_corte(99)


def test_validar_corte_no_es_borrador():
    mock_conn, mock_cursor = _mock_conn(fetchone=("VALIDADO",))
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEsBorrador):
            servicios.validar_corte(1)


def test_validar_corte_con_correctivas_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [("BORRADOR",), (1,)]
    mock_cursor.fetchall.return_value = [
        ("SIN_IDENTIFICACION", "CORRECTIVA", "Falta el tipo o el número de identificación", 7, "2259-1092"),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteConErroresCorrectivos) as exc_info:
            servicios.validar_corte(1)
    assert len(exc_info.value.errores) == 1
    assert exc_info.value.errores[0]["regla"] == "SIN_IDENTIFICACION"


def test_validar_corte_sin_errores_actualiza_estado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),   # SELECT ESTADO
        (1,),            # SELECT COUNT(*) FROM NV_CICLO
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0, None),  # obtener_corte
    ]
    mock_cursor.fetchall.return_value = []   # V_VALIDACION_CORTE → sin errores
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.validar_corte(1)
    sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
    assert any("ESTADO = 'VALIDADO'" in s for s in sqls)


def test_validar_corte_devuelve_advertencias():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),
        (1,),  # SELECT COUNT(*) FROM NV_CICLO
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0, None),
    ]
    mock_cursor.fetchall.return_value = [
        ("SIN_FECHA_LIMITE_PAGO", "INFORMATIVA", "No se encontró una factura", 7, "2259-1092"),
    ]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resultado = servicios.validar_corte(1)
    assert len(resultado["advertencias"]) == 1
    assert resultado["advertencias"][0]["regla"] == "SIN_FECHA_LIMITE_PAGO"


def test_rf49_validar_corte_bloquea_exigibilidad_futura():
    """Fecha de exigibilidad mayor a la fecha del sistema → V_VALIDACION_CORTE devuelve
    correctiva FECHA_EXIGIBILIDAD_FUTURA y validar_corte lanza CorteConErroresCorrectivos."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [("BORRADOR",), (1,)]
    mock_cursor.fetchall.return_value = [
        (
            "FECHA_EXIGIBILIDAD_FUTURA",
            "CORRECTIVA",
            "La fecha de exigibilidad es posterior a la fecha del sistema.",
            7,
            "2259-1092",
        ),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteConErroresCorrectivos) as exc_info:
            servicios.validar_corte(1)
    assert exc_info.value.errores[0]["regla"] == "FECHA_EXIGIBILIDAD_FUTURA"


# ── Servicios — registrar_envio ───────────────────────────────────────────────

def test_registrar_envio_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.registrar_envio(99)


def test_registrar_envio_no_es_validado():
    mock_conn, mock_cursor = _mock_conn(fetchone=("BORRADOR", date(2026, 9, 30)))
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEsValidado):
            servicios.registrar_envio(1)


def test_registrar_envio_fecha_futura():
    from datetime import timedelta
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("VALIDADO", date(2026, 9, 30))
    fecha_futura = date.today() + timedelta(days=1)
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.FechaInvalida):
            servicios.registrar_envio(1, fecha_envio=fecha_futura)


def test_registrar_envio_usa_hoy_sin_fecha():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("VALIDADO", date(2026, 9, 30)),
        (7, "S"),  # último archivo del corte, apto para envío (0.9)
        (1, "2026-09-30", "ENVIADO", None, 5, None, None, 0, None),
    ]
    with patch("cartera.servicios.connection", mock_conn),          patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.registrar_envio(1)
    sqls = [c.args[0] for c in mock_cursor.execute.call_args_list]
    assert any("ESTADO = 'ENVIADO'" in s for s in sqls)


# ── Vistas — ciclo mínimo ─────────────────────────────────────────────────────

def test_post_validar_200_sin_errores():
    request = factory.post("/api/extracciones/1/validar/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    corte_mock = {**_RESUMEN, "estado": "VALIDADO"}
    resultado = {"corte": corte_mock, "advertencias": []}
    with patch("cartera.views.servicios.validar_corte", return_value=resultado):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["estado"] == "VALIDADO"
    assert response.data["advertencias"] == []


def test_post_validar_409_correctivas():
    request = factory.post("/api/extracciones/1/validar/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    errores = [{"regla": "SIN_IDENTIFICACION", "mensaje": "Falta identificación"}]
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteConErroresCorrectivos(errores)):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 409
    assert "errores" in response.data


def test_post_validar_404():
    request = factory.post("/api/extracciones/999/validar/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="999")
    assert response.status_code == 404


def test_post_validar_409_no_borrador():
    request = factory.post("/api/extracciones/1/validar/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.validar_corte",
               side_effect=servicios.CorteNoEsBorrador):
        response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="1")
    assert response.status_code == 409


def test_post_registrar_envio_200():
    request = factory.post("/api/extracciones/1/registrar-envio/", {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    corte_mock = {**_RESUMEN, "estado": "ENVIADO"}
    with patch("cartera.views.servicios.registrar_envio", return_value=corte_mock):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["estado"] == "ENVIADO"


def test_post_registrar_envio_404():
    request = factory.post("/api/extracciones/999/registrar-envio/", {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="999")
    assert response.status_code == 404


def test_post_registrar_envio_409_no_validado():
    request = factory.post("/api/extracciones/1/registrar-envio/", {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.CorteNoEsValidado):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 409


def test_post_registrar_envio_400_fecha_futura():
    request = factory.post("/api/extracciones/1/registrar-envio/",
                           {"fecha_envio": "2099-01-01"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.registrar_envio",
               side_effect=servicios.FechaInvalida("fecha futura")):
        response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="1")
    assert response.status_code == 400


def test_extraccion_sin_permiso_403():
    request = factory.get("/api/extracciones/")
    force_authenticate(request, user=usuario_con_rol("OTRO_ROL"))
    response = ExtraccionViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 403


# ── Corrección 1 — pk no numérico → 404 ──────────────────────────────────────

def test_retrieve_pk_no_numerico_404():
    request = factory.get("/api/extracciones/abc/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"get": "retrieve"})(request, pk="abc")
    assert response.status_code == 404


def test_validar_pk_no_numerico_404():
    request = factory.post("/api/extracciones/abc/validar/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"post": "validar"})(request, pk="abc")
    assert response.status_code == 404


def test_registrar_envio_pk_no_numerico_404():
    request = factory.post("/api/extracciones/abc/registrar-envio/", {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"post": "registrar_envio"})(request, pk="abc")
    assert response.status_code == 404


def test_obligaciones_pk_no_numerico_404():
    request = factory.get("/api/extracciones/abc/obligaciones/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"get": "obligaciones"})(request, pk="abc")
    assert response.status_code == 404


# ── Corrección 2 — NULL safety en valor_mora / valor_saldo ───────────────────

def test_listar_obligaciones_valor_none():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1,),   # corte existe
        (1,),   # total
    ]
    mock_cursor.fetchall.return_value = [
        ("OBL001", "Juan", "12345", "01", "00", 0, 0, None, None, 1),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        resultado = servicios.listar_obligaciones(1)
    fila = resultado["resultados"][0]
    assert fila["valor_mora"] is None
    assert fila["valor_saldo"] is None


# ── Corrección 6 — Mensajes de error personalizados ──────────────────────────

def test_generar_corte_fecha_ausente_mensaje_personalizado():
    request = factory.post("/api/extracciones/", {}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert response.data["fecha_corte"][0] == "Selecciona una fecha de corte."


def test_generar_corte_fecha_invalida_mensaje_personalizado():
    request = factory.post("/api/extracciones/", {"fecha_corte": "no-es-fecha"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 400
    assert response.data["fecha_corte"][0] == "La fecha de corte no es válida."


# ── C1 — Enmascaramiento de numero_identificacion ────────────────────────────

def test_listar_obligaciones_enmascara_identificacion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1,),   # corte existe
        (1,),   # total
    ]
    mock_cursor.fetchall.return_value = [
        ("OBL001", "Juan", "12345678", "01", "00", 0, 0, 100, 500000, 1),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        resultado = servicios.listar_obligaciones(1)
    assert resultado["resultados"][0]["numero_identificacion"] == "******5678"


# ── C3 — validar_corte filtra por CORTE_ID ───────────────────────────────────

def test_validar_corte_filtra_por_corte_id():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),
        (1,),  # SELECT COUNT(*) FROM NV_CICLO
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0, None),
    ]
    mock_cursor.fetchall.return_value = []
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.validar_corte(42)
    sqls_con_params = [c for c in mock_cursor.execute.call_args_list if len(c[0]) > 1]
    validacion_calls = [c for c in sqls_con_params if "V_VALIDACION_CORTE" in c[0][0]]
    assert validacion_calls
    assert validacion_calls[0][0][1] == [42, 42]


# ── C4 — eliminar_borrador ────────────────────────────────────────────────────

def test_eliminar_borrador_ejecuta_deletes():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("BORRADOR", date(2026, 9, 30), "Grupo A")
    sqls = []
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append(sql)
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios.registrar_bitacora") as mock_reg:
        servicios.eliminar_borrador(7)
    assert any("DELETE" in s and "NV_REPORTE_DETALLE" in s for s in sqls)
    assert any("DELETE" in s and "NV_INCONSISTENCIA" in s for s in sqls)
    assert any("DELETE" in s and "NV_CORTE" in s for s in sqls)
    mock_reg.assert_called_once_with(
        "ELIMINACION_BORRADOR", "NV_CORTE", 7,
        "Fecha: 2026-09-30, Grupo: Grupo A",
    )


def test_eliminar_borrador_termina_aunque_falle_la_bitacora():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("BORRADOR", date(2026, 9, 30), None)
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios.registrar_bitacora",
               side_effect=RuntimeError("falta NV_BITACORA")), \
         patch("config.bitacora.logger") as mock_log:
        servicios.eliminar_borrador(7)
    mock_log.exception.assert_called_once()
    assert mock_log.exception.call_args.args[1] == "ELIMINACION_BORRADOR"


def test_eliminar_borrador_no_encontrado():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.eliminar_borrador(99)


def test_eliminar_borrador_no_es_borrador():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("VALIDADO", date(2026, 9, 30), None)
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.CorteNoEsBorrador):
            servicios.eliminar_borrador(1)


def test_destroy_204():
    request = factory.delete("/api/extracciones/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.eliminar_borrador"):
        response = ExtraccionViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 204


def test_destroy_404_no_existe():
    request = factory.delete("/api/extracciones/99/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.eliminar_borrador",
               side_effect=servicios.CorteNoEncontrado):
        response = ExtraccionViewSet.as_view({"delete": "destroy"})(request, pk="99")
    assert response.status_code == 404


def test_destroy_409_no_es_borrador():
    request = factory.delete("/api/extracciones/1/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.eliminar_borrador",
               side_effect=servicios.CorteNoEsBorrador):
        response = ExtraccionViewSet.as_view({"delete": "destroy"})(request, pk="1")
    assert response.status_code == 409
    assert "en borrador" in response.data["detail"]


def test_destroy_pk_no_numerico_404():
    request = factory.delete("/api/extracciones/abc/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    response = ExtraccionViewSet.as_view({"delete": "destroy"})(request, pk="abc")
    assert response.status_code == 404


# ── C5 — fecha posterior al último enviado ───────────────────────────────────

def test_fecha_igual_a_ultimo_enviado_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (_FECHA_PASADA,)
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.FechaAnteriorAlUltimoEnviado):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA)


def test_fecha_anterior_a_ultimo_enviado_lanza_excepcion():
    mock_conn, mock_cursor = _mock_conn()
    fecha_mas_reciente = date(2026, 10, 31)
    mock_cursor.fetchone.return_value = (fecha_mas_reciente,)
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.FechaAnteriorAlUltimoEnviado):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA)


def test_sin_cortes_enviados_no_falla():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),            # MAX(FECHA_CORTE) — sin enviados
        None,               # _verificar_corte_existente — sin misma fecha
        None,               # _verificar_corte_existente — sin borrador
        (1,),               # NEXTVAL
        (0, _FECHA_GEN),    # TOTAL + FECHA_GEN
        (0,),               # SUM
    ]
    mock_cursor.fetchall.side_effect = [[(30,)], []]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resumen = servicios.generar_corte(fecha_corte=_FECHA_PASADA)
    assert resumen["estado"] == "BORRADOR"


def test_generar_corte_409_fecha_anterior_enviado():
    request = factory.post("/api/extracciones/", {"fecha_corte": "2026-09-30"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.FechaAnteriorAlUltimoEnviado):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409
    assert "último corte enviado" in response.data["detail"]


# ── C6 — registrar_envio: existencia primero + fecha >= fecha_corte ──────────

def test_registrar_envio_404_sin_corte_antes_que_fecha():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = None
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteNoEncontrado):
            servicios.registrar_envio(99, fecha_envio=date(2099, 1, 1))


def test_registrar_envio_fecha_anterior_a_corte_400():
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = ("VALIDADO", date(2026, 9, 30))
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.FechaInvalida) as exc_info:
            servicios.registrar_envio(1, fecha_envio=date(2026, 9, 1))
    assert "anterior a la fecha de corte" in str(exc_info.value)


# ── RF13 · Saldada como cierre definitivo ────────────────────────────────────

def test_rf13_registrar_envio_marca_cierre_definitivo_en_02():
    """Al registrar el envío, marca CIERRE_DEFINITIVO='S' para las obligaciones en 02."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("VALIDADO", date(2026, 9, 30)),
        (7, "S"),  # último archivo del corte, apto para envío (0.9)
        (1, "2026-09-30", "ENVIADO", None, 5, None, None, 0, None),
    ]
    sqls = []
    orig_execute = mock_cursor.execute.side_effect
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append((sql, params))

    with patch("cartera.servicios.connection", mock_conn),          patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.registrar_envio(1, fecha_envio=date(2026, 9, 30))

    cierre_def_update = any(
        "CIERRE_DEFINITIVO" in (s or "") and "FECHA_CIERRE" in (s or "")
        for s, _ in sqls
    )
    assert cierre_def_update, "RF13: debe marcar CIERRE_DEFINITIVO='S' en NV_OBLIGACION al enviar"
    # Verifica que filtra por ESTADO_TU = '02'
    cierre_def_sql, cierre_def_params = next(
        (s, p) for s, p in sqls
        if s and "CIERRE_DEFINITIVO" in s and "FECHA_CIERRE" in s
    )
    assert "'02'" in cierre_def_sql or "02" in str(cierre_def_params)


def test_rf13_numero_duplicado_lanza_excepcion():
    """Un número ya registrado en UK_NV_OBLIGACION_TU lanza NumeroDuplicado (RF13)."""
    from django.db import IntegrityError as DjangoIntegrityError
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (None,),
        None, None,
        (1,),
    ]
    mock_cursor.fetchall.side_effect = [
        [(30,)],
        [("CLI01", "PROC01", "2259-1092", date(2026, 1, 15))],
    ]
    mock_cursor.executemany.side_effect = DjangoIntegrityError("ORA-00001")

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        with pytest.raises(servicios.NumeroDuplicado):
            servicios.generar_corte(fecha_corte=_FECHA_PASADA)


def test_rf13_numero_duplicado_devuelve_409():
    """NumeroDuplicado en la vista → 409 con mensaje en español."""
    request = factory.post("/api/extracciones/", {"fecha_corte": "2026-09-30"}, format="json")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.generar_corte",
               side_effect=servicios.NumeroDuplicado):
        response = ExtraccionViewSet.as_view({"post": "create"})(request)
    assert response.status_code == 409
    assert "número de obligación" in response.data["detail"].lower() or \
           "reutilizarse" in response.data["detail"]


# ── RF16 · Cartera Recuperada como cierre definitivo ─────────────────────────

def test_rf16_registrar_envio_marca_cierre_definitivo_en_07():
    """Al registrar el envío, marca CIERRE_DEFINITIVO='S' para las obligaciones en 07 (RF16)."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("VALIDADO", date(2026, 9, 30)),
        (7, "S"),  # último archivo del corte, apto para envío (0.9)
        (1, "2026-09-30", "ENVIADO", None, 5, None, None, 0, None),
    ]
    sqls = []
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append((sql, params))

    with patch("cartera.servicios.connection", mock_conn),          patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.registrar_envio(1, fecha_envio=date(2026, 9, 30))

    cierre_def_sql, _ = next(
        (s, p) for s, p in sqls
        if s and "CIERRE_DEFINITIVO" in s and "FECHA_CIERRE" in s
    )
    assert "'07'" in cierre_def_sql, "RF16: debe incluir estado 07 en el UPDATE de CIERRE_DEFINITIVO"
    assert "'02'" in cierre_def_sql, "RF16: debe seguir cubriendo estado 02 (RF13)"


def test_rf16_registrar_envio_cubre_02_y_07_en_una_sola_sentencia():
    """Un único UPDATE cubre ambos estados de cierre definitivo (02 y 07) sin duplicar código."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("VALIDADO", date(2026, 9, 30)),
        (7, "S"),  # último archivo del corte, apto para envío (0.9)
        (1, "2026-09-30", "ENVIADO", None, 5, None, None, 0, None),
    ]
    sqls = []
    mock_cursor.execute.side_effect = lambda sql, params=None: sqls.append((sql, params))

    with patch("cartera.servicios.connection", mock_conn),          patch("cartera.servicios.transaction.atomic", _noop_atomic):
        servicios.registrar_envio(1, fecha_envio=date(2026, 9, 30))

    cierre_sqls = [s for s, _ in sqls if s and "CIERRE_DEFINITIVO" in s]
    assert len(cierre_sqls) == 1, "RF16: un único UPDATE debe cubrir 02 y 07 (no duplicar lógica)"


# ── Casos RF19 ────────────────────────────────────────────────────────────────

def test_rf19_validar_corte_707_bloquea_edad_sin_valor_mora():
    """Edad 01 con valor de mora cero → V_VALIDACION_CORTE devuelve CORRECTIVA 707;
    validar_corte lanza CorteConErroresCorrectivos y bloquea el corte (RF19, RF53).
    """
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [("BORRADOR",), (1,)]
    mock_cursor.fetchall.return_value = [
        ("EDAD_SIN_VALOR_MORA", "CORRECTIVA",
         "Obligación 2258-7731 tiene edad 01 con valor de mora 0 (regla 707)", 3, "2258-7731"),
    ]
    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.CorteConErroresCorrectivos) as exc_info:
            servicios.validar_corte(1)
    assert len(exc_info.value.errores) == 1
    assert exc_info.value.errores[0]["regla"] == "EDAD_SIN_VALOR_MORA"


def test_rf19_validar_corte_cuotas_mora_incoherente_es_informativa():
    """Valor de mora cero con 2 cuotas en mora → V_VALIDACION_CORTE devuelve
    INFORMATIVA CUOTAS_MORA_INCOHERENTE; validar_corte no bloquea y devuelve la alerta.
    """
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        ("BORRADOR",),
        (1,),  # SELECT COUNT(*) FROM NV_CICLO
        (1, "2026-09-30", "VALIDADO", None, 5, None, None, 0, None),
    ]
    mock_cursor.fetchall.return_value = [
        ("CUOTAS_MORA_INCOHERENTE", "INFORMATIVA",
         "Obligación 2263-9004 tiene cuotas_mora=2 con valor de mora 0", 4, "2263-9004"),
    ]
    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic):
        resultado = servicios.validar_corte(1)
    assert len(resultado["advertencias"]) == 1
    assert resultado["advertencias"][0]["regla"] == "CUOTAS_MORA_INCOHERENTE"


# ── RF54 · Resultados del cargue de TransUnion ───────────────────────────────

@contextmanager
def _noop_tolerar_rf54(accion):
    yield


def _make_archivo(nombre, contenido):
    """Crea un archivo simulado para los tests de upload."""
    mock = MagicMock()
    mock.name = nombre
    mock.read.return_value = contenido.encode("utf-8")
    return mock


_FECHA_CORTE_RF54 = date(2026, 8, 31)
_FECHA_CARGA_RF54 = datetime(2026, 9, 5, 14, 0, 0)


def test_rf54_cargar_correctivas_pasa_a_enviado_con_inconsistencias():
    """Cargar archivo de correctivas → corte pasa a ENVIADO_CON_INCONSISTENCIAS."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1, _FECHA_CORTE_RF54, "ENVIADO", "S"),  # SELECT archivo+corte
        (101,),     # SEQ_NV_CARGUE_RESULTADO
        (201,),     # SEQ_NV_CARGUE_INCONSISTENCIA
        (1,),       # COUNT correctivas (hay 1)
        (9,),       # COUNT NV_REPORTE_DETALLE
    ]
    mock_cursor.fetchall.return_value = [("2258-7731", 2)]  # resolver obligacion_ids

    archivo = _make_archivo(
        "Detalle_Inco_CSR_001_123_Correctivas_20260831.txt",
        "2258-7731|707|VALOR DE MORA ES REQUERIDO",
    )

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios.registrar_bitacora"), \
         patch("cartera.servicios.tolerar_fallo_bitacora", _noop_tolerar_rf54), \
         patch("cartera.servicios.Usuario") as mock_usuario:
        mock_usuario.objects.filter.return_value.values_list.return_value = []
        result = servicios.cargar_resultados(1, [archivo], usuario=None)

    assert result["estado_corte"] == "ENVIADO_CON_INCONSISTENCIAS"
    assert len(result["inconsistencias"]) == 1
    assert result["inconsistencias"][0]["tipo"] == "CORRECTIVA"
    assert result["inconsistencias"][0]["codigo"] == "707"
    assert result["inconsistencias"][0]["obligacion_id"] == 2
    assert result["con_inconsistencias"] == 1
    assert result["no_reportadas"] == 0
    assert result["recibidos"] == 9
    assert result["cargados"] == 9


def test_rf54_cargar_sin_correctivas_queda_enviado():
    """Cargar archivo estadísticos sin inconsistencias → corte queda ENVIADO."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1, _FECHA_CORTE_RF54, "ENVIADO", "S"),  # SELECT archivo+corte
        (102,),     # SEQ_NV_CARGUE_RESULTADO
        (0,),       # COUNT correctivas (no hay)
        (9,),       # COUNT NV_REPORTE_DETALLE
    ]

    archivo = _make_archivo(
        "Esta_Inco_CSR_001_123_Alertas_20260831.txt",
        "2258-7731|CARGADO\n2259-0001|CARGADO",
    )

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios.registrar_bitacora"), \
         patch("cartera.servicios.tolerar_fallo_bitacora", _noop_tolerar_rf54), \
         patch("cartera.servicios.Usuario") as mock_usuario:
        mock_usuario.objects.filter.return_value.values_list.return_value = []
        result = servicios.cargar_resultados(1, [archivo], usuario=None)

    assert result["estado_corte"] == "ENVIADO"
    assert result["inconsistencias"] == []
    assert result["con_inconsistencias"] == 0
    assert result["recibidos"] == 9
    assert result["cargados"] == 9


def test_rf54_archivo_de_otro_corte_lanza_excepcion():
    """Archivo con fecha distinta al corte → ArchivoDeOtroCorte (422)."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1, _FECHA_CORTE_RF54, "ENVIADO", "S")

    # El nombre tiene 20260731 pero el corte es 2026-08-31
    archivo = _make_archivo(
        "Detalle_Inco_CSR_001_123_Correctivas_20260731.txt",
        "2258-7731|707|VALOR DE MORA ES REQUERIDO",
    )

    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.ArchivoDeOtroCorte) as exc_info:
            servicios.cargar_resultados(1, [archivo], usuario=None)

    assert "20260731" in str(exc_info.value) or "31/07/2026" in str(exc_info.value)


def test_rf54_estructura_invalida_lanza_excepcion():
    """Archivo de correctivas con formato incorrecto → EstructuraInvalida (422)."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.return_value = (1, _FECHA_CORTE_RF54, "ENVIADO", "S")

    # Falta el campo DESCRIPCION (solo 2 campos separados por |)
    archivo = _make_archivo(
        "Detalle_Inco_CSR_001_123_Correctivas_20260831.txt",
        "2258-7731|707",
    )

    with patch("cartera.servicios.connection", mock_conn):
        with pytest.raises(servicios.EstructuraInvalida):
            servicios.cargar_resultados(1, [archivo], usuario=None)


def test_rf54_norep_aparece_como_no_reportada():
    """Cargar archivo norep con una obligación → aparece como NO_REPORTADA."""
    mock_conn, mock_cursor = _mock_conn()
    mock_cursor.fetchone.side_effect = [
        (1, _FECHA_CORTE_RF54, "ENVIADO", "S"),  # SELECT archivo+corte
        (103,),     # SEQ_NV_CARGUE_RESULTADO
        (202,),     # SEQ_NV_CARGUE_INCONSISTENCIA
        (0,),       # COUNT correctivas (norep no es correctiva)
        (9,),       # COUNT NV_REPORTE_DETALLE
    ]
    mock_cursor.fetchall.return_value = [("2260-5543", 4)]  # resolver obligacion_ids

    archivo = _make_archivo("norep.001.123.CODIGOPRODUCTO.20260831.0.txt", "2260-5543")

    with patch("cartera.servicios.connection", mock_conn), \
         patch("cartera.servicios.transaction.atomic", _noop_atomic), \
         patch("cartera.servicios.registrar_bitacora"), \
         patch("cartera.servicios.tolerar_fallo_bitacora", _noop_tolerar_rf54), \
         patch("cartera.servicios.Usuario") as mock_usuario:
        mock_usuario.objects.filter.return_value.values_list.return_value = []
        result = servicios.cargar_resultados(1, [archivo], usuario=None)

    assert result["estado_corte"] == "ENVIADO"
    assert result["no_reportadas"] == 1
    assert result["cargados"] == 9 - 1
    assert result["inconsistencias"][0]["tipo"] == "NO_REPORTADA"
    assert result["inconsistencias"][0]["numero_obligacion"] == "2260-5543"
    assert result["inconsistencias"][0]["obligacion_id"] == 4


# ── RF54 · Vistas ─────────────────────────────────────────────────────────────

_RESULTADO_MOCK = {
    "archivo_id": 1,
    "corte_id": 1,
    "fecha_corte": _FECHA_CORTE_RF54,
    "fecha_carga": _FECHA_CARGA_RF54,
    "cargado_por": "Carlos Sánchez",
    "estado_corte": "ENVIADO_CON_INCONSISTENCIAS",
    "archivos_cargados": [
        {"nombre_archivo": "Detalle_Inco_CSR_001_123_Correctivas_20260831.txt", "tipo_archivo": "CORRECTIVAS", "n_filas": 1},
    ],
    "recibidos": 9,
    "cargados": 8,
    "con_inconsistencias": 1,
    "no_reportadas": 0,
    "inconsistencias": [
        {"obligacion_id": 2, "numero_obligacion": "2258-7731",
         "tipo": "CORRECTIVA", "codigo": "707", "descripcion": "VALOR DE MORA ES REQUERIDO"},
    ],
}


def test_rf54_get_con_resultados_200():
    """GET /archivos/{id}/resultados/ con resultados → 200."""
    request = factory.get("/archivos/1/resultados/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_resultados", return_value=_RESULTADO_MOCK):
        response = ArchivoViewSet.as_view({"get": "resultados"})(request, pk="1")
    assert response.status_code == 200
    assert response.data["estado_corte"] == "ENVIADO_CON_INCONSISTENCIAS"
    assert response.data["recibidos"] == 9
    assert len(response.data["inconsistencias"]) == 1


def test_rf54_get_sin_resultados_404():
    """GET /archivos/{id}/resultados/ sin resultados → 404."""
    request = factory.get("/archivos/1/resultados/")
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.obtener_resultados",
               side_effect=servicios.SinResultados):
        response = ArchivoViewSet.as_view({"get": "resultados"})(request, pk="1")
    assert response.status_code == 404
    assert "resultados cargados" in response.data["detail"]


def test_rf54_post_correctivas_201():
    """POST /archivos/{id}/resultados/ exitoso → 201."""
    request = factory.post(
        "/archivos/1/resultados/",
        {"archivos": [MagicMock(name="correctivas_SSR00112320260831.txt")]},
        format="multipart",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.cargar_resultados", return_value=_RESULTADO_MOCK):
        response = ArchivoViewSet.as_view({"post": "resultados"})(request, pk="1")
    assert response.status_code == 201
    assert response.data["estado_corte"] == "ENVIADO_CON_INCONSISTENCIAS"


def test_rf54_post_archivo_no_encontrado_404():
    """POST /archivos/{id}/resultados/ con id inexistente → 404."""
    request = factory.post(
        "/archivos/99/resultados/",
        {"archivos": [MagicMock()]},
        format="multipart",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.cargar_resultados",
               side_effect=servicios.ArchivoNoEncontrado):
        response = ArchivoViewSet.as_view({"post": "resultados"})(request, pk="99")
    assert response.status_code == 404
    assert response.data["detail"] == "Archivo no encontrado."


def test_rf54_post_archivo_no_enviado_409():
    """POST /archivos/{id}/resultados/ con archivo no enviado → 409."""
    request = factory.post(
        "/archivos/1/resultados/",
        {"archivos": [MagicMock()]},
        format="multipart",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    with patch("cartera.views.servicios.cargar_resultados",
               side_effect=servicios.ArchivoNoEnviado):
        response = ArchivoViewSet.as_view({"post": "resultados"})(request, pk="1")
    assert response.status_code == 409
    assert "envío" in response.data["detail"]


def test_rf54_post_archivo_de_otro_corte_422():
    """POST /archivos/{id}/resultados/ con archivo de otro corte → 422."""
    request = factory.post(
        "/archivos/1/resultados/",
        {"archivos": [MagicMock()]},
        format="multipart",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    exc = servicios.ArchivoDeOtroCorte(
        "Detalle_Inco_CSR_001_123_Correctivas_20260731.txt",
        date(2026, 7, 31),
        date(2026, 8, 31),
    )
    with patch("cartera.views.servicios.cargar_resultados", side_effect=exc):
        response = ArchivoViewSet.as_view({"post": "resultados"})(request, pk="1")
    assert response.status_code == 422
    assert response.data["code"] == "archivo_de_otro_corte"


def test_rf54_post_estructura_invalida_422():
    """POST /archivos/{id}/resultados/ con estructura inválida → 422."""
    request = factory.post(
        "/archivos/1/resultados/",
        {"archivos": [MagicMock()]},
        format="multipart",
    )
    force_authenticate(request, user=usuario_con_rol("ANALISTA_CARTERA"))
    exc = servicios.EstructuraInvalida(
        "El archivo correctivas.txt no tiene la estructura esperada (línea 1: "
        "se esperaban al menos 3 campos separados por |)."
    )
    with patch("cartera.views.servicios.cargar_resultados", side_effect=exc):
        response = ArchivoViewSet.as_view({"post": "resultados"})(request, pk="1")
    assert response.status_code == 422
    assert response.data["code"] == "estructura_invalida"
