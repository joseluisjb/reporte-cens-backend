from django.db import connection, IntegrityError


class ConceptoYaExiste(Exception):
    pass


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
