from collections import defaultdict

from django.db import connection, IntegrityError
from django.db import transaction

from config.formatos import ahora_para_bd


# ── Excepciones ───────────────────────────────────────────────────────────────

class ConceptoYaExiste(Exception):
    pass


class GrupoYaExiste(Exception):
    pass


class GrupoNoEncontrado(Exception):
    pass


class GrupoEnUso(Exception):
    pass


class ConceptoInvalido(Exception):
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(f"Concepto {codigo} no existe o no está activo")


_COLS = "CODIGO_CONCEPTO, DESCRIPCION, REPORTABLE, OBSERVACION"


def _fila_a_dict(row):
    return {
        "codigo_concepto": row[0],
        "descripcion":     row[1],
        "reportable":      row[2],
        "observacion":     row[3],
    }


def _buscar_por_codigo(codigo):
    sql = f"SELECT {_COLS} FROM NV_CONCEPTO_REPORTABLE WHERE CODIGO_CONCEPTO = :1"
    with connection.cursor() as cursor:
        cursor.execute(sql, [codigo])
        row = cursor.fetchone()
    return _fila_a_dict(row) if row else None


def listar_conceptos(activo=None):
    sql = f"SELECT {_COLS} FROM NV_CONCEPTO_REPORTABLE"
    params = []
    if activo is not None:
        sql += " WHERE REPORTABLE = :1"
        params.append("S" if activo else "N")
    sql += " ORDER BY CODIGO_CONCEPTO"
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()
    return [_fila_a_dict(r) for r in rows]


def crear_concepto(datos):
    sql = (
        "INSERT INTO NV_CONCEPTO_REPORTABLE "
        "(CODIGO_CONCEPTO, DESCRIPCION, REPORTABLE, OBSERVACION) "
        "VALUES (:1, :2, :3, :4)"
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [
                datos["codigo_concepto"],
                datos["descripcion"],
                datos["reportable"],
                datos.get("observacion"),
            ])
    except IntegrityError:
        raise ConceptoYaExiste()
    return _buscar_por_codigo(datos["codigo_concepto"])


def actualizar_concepto(codigo, datos):
    _MAPA = {"descripcion": "DESCRIPCION", "reportable": "REPORTABLE", "observacion": "OBSERVACION"}
    sets, params = [], []
    for clave, col in _MAPA.items():
        if clave in datos:
            params.append(datos[clave])
            sets.append(f"{col} = :{len(params)}")
    if not sets:
        return _buscar_por_codigo(codigo)
    params.append(codigo)
    sql = (
        f"UPDATE NV_CONCEPTO_REPORTABLE SET {', '.join(sets)} "
        f"WHERE CODIGO_CONCEPTO = :{len(params)}"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
    return _buscar_por_codigo(codigo)


# ── Grupos de conceptos ───────────────────────────────────────────────────────

def _validar_conceptos(codigos):
    if not codigos:
        raise ConceptoInvalido(None)
    placeholders = ", ".join([f":{i + 1}" for i in range(len(codigos))])
    sql = (
        f"SELECT CODIGO_CONCEPTO FROM NV_CONCEPTO_REPORTABLE "
        f"WHERE CODIGO_CONCEPTO IN ({placeholders}) AND REPORTABLE = 'S'"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, list(codigos))
        validos = {row[0] for row in cursor.fetchall()}
    for codigo in codigos:
        if codigo not in validos:
            raise ConceptoInvalido(codigo)


def _insertar_detalle(grupo_id, codigos):
    sql = "INSERT INTO NV_GRUPO_CONCEPTO_DET (GRUPO_ID, CODIGO_CONCEPTO) VALUES (:1, :2)"
    with connection.cursor() as cursor:
        cursor.executemany(sql, [(grupo_id, codigo) for codigo in codigos])


def _buscar_grupo_por_id(grupo_id):
    sql = (
        "SELECT g.GRUPO_ID, g.NOMBRE, g.ACTIVO, g.FECHA_CREACION, "
        "d.CODIGO_CONCEPTO, c.DESCRIPCION "
        "FROM NV_GRUPO_CONCEPTO g "
        "LEFT JOIN NV_GRUPO_CONCEPTO_DET d ON g.GRUPO_ID = d.GRUPO_ID "
        "LEFT JOIN NV_CONCEPTO_REPORTABLE c ON d.CODIGO_CONCEPTO = c.CODIGO_CONCEPTO "
        "WHERE g.GRUPO_ID = :1 "
        "ORDER BY d.CODIGO_CONCEPTO"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [grupo_id])
        rows = cursor.fetchall()
    if not rows:
        return None
    g_id, nombre, activo, fecha = rows[0][:4]
    conceptos = [
        {"codigo": row[4], "descripcion": row[5]}
        for row in rows
        if row[4] is not None
    ]
    return {
        "grupo_id":       g_id,
        "nombre":         nombre,
        "activo":         activo,
        "fecha_creacion": fecha,
        "conceptos":      conceptos,
    }


def listar_grupos():
    sql_grupos = (
        "SELECT GRUPO_ID, NOMBRE, ACTIVO, FECHA_CREACION "
        "FROM NV_GRUPO_CONCEPTO ORDER BY GRUPO_ID"
    )
    sql_det = (
        "SELECT d.GRUPO_ID, d.CODIGO_CONCEPTO, c.DESCRIPCION "
        "FROM NV_GRUPO_CONCEPTO_DET d "
        "JOIN NV_CONCEPTO_REPORTABLE c ON d.CODIGO_CONCEPTO = c.CODIGO_CONCEPTO "
        "ORDER BY d.GRUPO_ID, d.CODIGO_CONCEPTO"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql_grupos, [])
        grupo_rows = cursor.fetchall()
        cursor.execute(sql_det, [])
        det_rows = cursor.fetchall()

    conceptos_por_grupo = defaultdict(list)
    for g_id, codigo, descripcion in det_rows:
        conceptos_por_grupo[g_id].append({"codigo": codigo, "descripcion": descripcion})

    return [
        {
            "grupo_id":       g_id,
            "nombre":         nombre,
            "activo":         activo,
            "fecha_creacion": fecha,
            "conceptos":      conceptos_por_grupo[g_id],
        }
        for g_id, nombre, activo, fecha in grupo_rows
    ]


def obtener_grupo(grupo_id):
    return _buscar_grupo_por_id(grupo_id)


def crear_grupo(datos):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT SEQ_NV_GRUPO_CONCEPTO.NEXTVAL FROM DUAL")
            grupo_id = cursor.fetchone()[0]

        _validar_conceptos(datos["conceptos"])

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO NV_GRUPO_CONCEPTO "
                    "(GRUPO_ID, NOMBRE, ACTIVO, FECHA_CREACION) "
                    "VALUES (:1, :2, 'S', :3)",
                    [grupo_id, datos["nombre"], ahora_para_bd()],
                )
        except IntegrityError:
            raise GrupoYaExiste()

        _insertar_detalle(grupo_id, datos["conceptos"])

    return _buscar_grupo_por_id(grupo_id)


def actualizar_grupo(grupo_id, datos):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM NV_GRUPO_CONCEPTO WHERE GRUPO_ID = :1", [grupo_id]
            )
            if cursor.fetchone()[0] == 0:
                raise GrupoNoEncontrado()

        _MAPA = {"nombre": "NOMBRE", "activo": "ACTIVO"}
        sets, params = [], []
        for clave, col in _MAPA.items():
            if clave in datos:
                params.append(datos[clave])
                sets.append(f"{col} = :{len(params)}")

        if sets:
            params.append(grupo_id)
            sql = (
                f"UPDATE NV_GRUPO_CONCEPTO SET {', '.join(sets)} "
                f"WHERE GRUPO_ID = :{len(params)}"
            )
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
            except IntegrityError:
                raise GrupoYaExiste()

        if "conceptos" in datos:
            _validar_conceptos(datos["conceptos"])
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM NV_GRUPO_CONCEPTO_DET WHERE GRUPO_ID = :1", [grupo_id]
                )
            _insertar_detalle(grupo_id, datos["conceptos"])

    return _buscar_grupo_por_id(grupo_id)


def eliminar_grupo(grupo_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NV_CORTE WHERE GRUPO_ID = :1 AND ESTADO = 'BORRADOR'",
            [grupo_id],
        )
        if cursor.fetchone()[0] > 0:
            raise GrupoEnUso()

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM NV_GRUPO_CONCEPTO WHERE GRUPO_ID = :1", [grupo_id]
        )
        if cursor.rowcount == 0:
            raise GrupoNoEncontrado()
