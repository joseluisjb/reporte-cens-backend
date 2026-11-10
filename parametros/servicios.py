import re
from collections import defaultdict

from django.db import connection, IntegrityError
from django.db import transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import ahora_bogota, ahora_para_bd


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
    sql = f"SELECT {_COLS} FROM NV_CONCEPTO_REPORTABLE WHERE CODIGO_CONCEPTO = %s"
    with connection.cursor() as cursor:
        cursor.execute(sql, [codigo])
        row = cursor.fetchone()
    return _fila_a_dict(row) if row else None


def listar_conceptos(activo=None):
    sql = f"SELECT {_COLS} FROM NV_CONCEPTO_REPORTABLE"
    params = []
    if activo is not None:
        sql += " WHERE REPORTABLE = %s"
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
        "VALUES (%s, %s, %s, %s)"
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
            sets.append(f"{col} = %s")
    if not sets:
        return _buscar_por_codigo(codigo)
    params.append(codigo)
    sql = (
        f"UPDATE NV_CONCEPTO_REPORTABLE SET {', '.join(sets)} "
        f"WHERE CODIGO_CONCEPTO = %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
    return _buscar_por_codigo(codigo)


# ── Grupos de conceptos ───────────────────────────────────────────────────────

def _validar_conceptos(codigos):
    if not codigos:
        raise ConceptoInvalido(None)
    placeholders = ", ".join(["%s"] * len(codigos))
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
    sql = "INSERT INTO NV_GRUPO_CONCEPTO_DET (GRUPO_ID, CODIGO_CONCEPTO) VALUES (%s, %s)"
    with connection.cursor() as cursor:
        cursor.executemany(sql, [(grupo_id, codigo) for codigo in codigos])


def _buscar_grupo_por_id(grupo_id):
    sql = (
        "SELECT g.GRUPO_ID, g.NOMBRE, g.ACTIVO, g.FECHA_CREACION, "
        "d.CODIGO_CONCEPTO, c.DESCRIPCION "
        "FROM NV_GRUPO_CONCEPTO g "
        "LEFT JOIN NV_GRUPO_CONCEPTO_DET d ON g.GRUPO_ID = d.GRUPO_ID "
        "LEFT JOIN NV_CONCEPTO_REPORTABLE c ON d.CODIGO_CONCEPTO = c.CODIGO_CONCEPTO "
        "WHERE g.GRUPO_ID = %s "
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
                    "VALUES (%s, %s, 'S', %s)",
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
                "SELECT COUNT(*) FROM NV_GRUPO_CONCEPTO WHERE GRUPO_ID = %s", [grupo_id]
            )
            if cursor.fetchone()[0] == 0:
                raise GrupoNoEncontrado()

        _MAPA = {"nombre": "NOMBRE", "activo": "ACTIVO"}
        sets, params = [], []
        for clave, col in _MAPA.items():
            if clave in datos:
                params.append(datos[clave])
                sets.append(f"{col} = %s")

        if sets:
            params.append(grupo_id)
            sql = (
                f"UPDATE NV_GRUPO_CONCEPTO SET {', '.join(sets)} "
                f"WHERE GRUPO_ID = %s"
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
                    "DELETE FROM NV_GRUPO_CONCEPTO_DET WHERE GRUPO_ID = %s", [grupo_id]
                )
            _insertar_detalle(grupo_id, datos["conceptos"])

    return _buscar_grupo_por_id(grupo_id)


def eliminar_grupo(grupo_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NV_CORTE WHERE GRUPO_ID = %s AND ESTADO = 'BORRADOR'",
            [grupo_id],
        )
        if cursor.fetchone()[0] > 0:
            raise GrupoEnUso()

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM NV_GRUPO_CONCEPTO WHERE GRUPO_ID = %s", [grupo_id]
        )
        if cursor.rowcount == 0:
            raise GrupoNoEncontrado()


# ── Datos de la entidad ante TransUnion (RF57) ────────────────────────────────

# Campo de la API → (clave en NV_PARAMETRO, marcador del mismo largo del campo).
CAMPOS_ENTIDAD = {
    "tipo_entidad":    ("TIPO_ENTIDAD", "XXX"),
    "codigo_entidad":  ("CODIGO_ENTIDAD", "XXX"),
    "codigo_sucursal": ("CODIGO_SUCURSAL", "XXXXXX"),
}
_PATRONES_ENTIDAD = {
    "tipo_entidad":    re.compile(r"^(\d{3}|XXX)$"),
    "codigo_entidad":  re.compile(r"^(\d{3}|XXX)$"),
    "codigo_sucursal": re.compile(r"^[A-Z0-9]{6}$"),
}
EVENTO_ENTIDAD = "ENTIDAD_ACTUALIZADA"


def es_marcador(valor):
    """Un valor hecho solo de X es el marcador: TransUnion todavía no asignó el código."""
    return bool(valor) and set(valor) == {"X"}


def _normalizar_valor(campo, valor):
    # Un valor guardado que no cumple el formato (por ejemplo el PENDIENTE/PEND anterior al
    # script 10) se trata como marcador, para que el archivo nunca salga apto por error.
    valor = (valor or "").strip().upper()
    if _PATRONES_ENTIDAD[campo].match(valor):
        return valor
    return CAMPOS_ENTIDAD[campo][1]


def _armar_entidad(valores, actualizado_por=None, fecha_actualizacion=None):
    return {
        **valores,
        "con_marcador": any(es_marcador(v) for v in valores.values()),
        "prefijo_archivo": f"SSR{valores['tipo_entidad']}{valores['codigo_entidad']}",
        "actualizado_por": actualizado_por,
        "fecha_actualizacion": fecha_actualizacion,
    }


def _leer_valores_entidad():
    claves = [clave for clave, _ in CAMPOS_ENTIDAD.values()]
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CLAVE, VALOR FROM NEXOVOLT.NV_PARAMETRO WHERE CLAVE IN (%s, %s, %s)",
            claves,
        )
        guardados = dict(cursor.fetchall())
    return {
        campo: _normalizar_valor(campo, guardados.get(clave))
        for campo, (clave, _) in CAMPOS_ENTIDAD.items()
    }


def datos_entidad():
    """Tipo, código y sucursal vigentes, con `con_marcador` y `prefijo_archivo`.

    Es la única lectura de estos datos: el generador del archivo plano (RF20) debe usarla.
    """
    return _armar_entidad(_leer_valores_entidad())


def _ultima_actualizacion_entidad():
    # NV_PARAMETRO no guarda quién cambió el valor: se toma del último registro en la bitácora.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT USUARIO_NOMBRE, FECHA FROM NEXOVOLT.NV_BITACORA "
            "WHERE ACCION = %s ORDER BY FECHA DESC, BITACORA_ID DESC "
            "FETCH FIRST 1 ROWS ONLY",
            [EVENTO_ENTIDAD],
        )
        fila = cursor.fetchone()
    return fila if fila else (None, None)


def obtener_entidad():
    actualizado_por, fecha = _ultima_actualizacion_entidad()
    return _armar_entidad(_leer_valores_entidad(), actualizado_por, fecha)


def guardar_entidad(datos, usuario=None):
    """Reemplaza los tres datos. Con los tres marcadores se «vuelve al relleno»."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            for campo, (clave, _) in CAMPOS_ENTIDAD.items():
                valor = datos[campo]
                confirmado = "N" if es_marcador(valor) else "S"
                cursor.execute(
                    "MERGE INTO NEXOVOLT.NV_PARAMETRO d "
                    "USING (SELECT %s AS CLAVE, %s AS VALOR, %s AS CONFIRMADO FROM DUAL) s "
                    "ON (d.CLAVE = s.CLAVE) "
                    "WHEN MATCHED THEN UPDATE SET d.VALOR = s.VALOR, "
                    "d.CONFIRMADO = s.CONFIRMADO, d.FECHA_MODIFICACION = SYSTIMESTAMP "
                    "WHEN NOT MATCHED THEN INSERT (CLAVE, VALOR, CONFIRMADO) "
                    "VALUES (s.CLAVE, s.VALOR, s.CONFIRMADO)",
                    [clave, valor, confirmado],
                )
        valores = {campo: datos[campo] for campo in CAMPOS_ENTIDAD}
        with tolerar_fallo_bitacora(EVENTO_ENTIDAD):
            registrar_bitacora(
                EVENTO_ENTIDAD, "NV_PARAMETRO", "ENTIDAD",
                "Tipo {tipo_entidad}, código {codigo_entidad}, sucursal {codigo_sucursal}".format(**valores),
                usuario=usuario,
            )
    return _armar_entidad(valores, getattr(usuario, "nombre", None), ahora_bogota())


# ── Catálogo y homologación de estados (RF48) ─────────────────────────────────

# Columnas de NV_ESTADO_TU que no están documentadas en el repo (la tabla viene del script base, que
# no está versionado). Confirmarlas con la sección 0 de parametros/sql/verificacion_12a_*.sql.
_COL_ESTADO_TU = {"codigo": "CODIGO_ESTADO", "nombre": "NOMBRE"}

ACCIONES_HOMOLOGACION = ("ESTADO", "CIERRE")
ESTADOS_DE_CIERRE = ("02", "07")
EVENTO_HOMOLOGACION = "HOMOLOGACION_ACTUALIZADA"

# Mismos textos que el frontend (features/state-mapping/stateMappingValidation.js) y el contrato 0.9.1.
MSG_HOMOLOGACION = {
    "accion": "Elige cómo se reporta el estado: como estado de TransUnion o como cierre.",
    "estado_tu": "Selecciona el estado de TransUnion.",
    "no_existe": "Ese estado no está en la Tabla 4b de TransUnion.",
    "no_usado": "El estado {codigo} · {nombre} no se usa en CENS: elige un estado en uso.",
    "cierre_con_estado": "Un estado que cierra el crédito no lleva estado de TransUnion.",
    "estado_de_cierre": "Saldada (02) y Castigada recuperada (07) se asignan con «Cierre», según el estado anterior.",
}

# Tipo de cartera de CENS (2 = servicios), desde NV_PARAMETRO.
_TIPO_CARTERA = "(SELECT TO_NUMBER(VALOR) FROM NEXOVOLT.NV_PARAMETRO WHERE CLAVE = 'TIPO_CARTERA')"


class EstadoSacNoEncontrado(Exception):
    pass


class HomologacionInvalida(Exception):
    """Combinación de acción y estado que no se acepta. `errores` va por campo, como DRF."""

    def __init__(self, errores):
        self.errores = errores
        super().__init__(str(errores))


def listar_estados_tu():
    """Los 10 estados de la Tabla 4b (servicios) con su uso en CENS, por código."""
    codigo, nombre = _COL_ESTADO_TU["codigo"], _COL_ESTADO_TU["nombre"]
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {codigo}, {nombre}, USADO, ES_CIERRE, CONFIRMADO "
            f"FROM NEXOVOLT.NV_ESTADO_TU WHERE TIPO_CARTERA = {_TIPO_CARTERA} "
            f"ORDER BY {codigo}"
        )
        filas = cursor.fetchall()
    return [
        {
            "codigo": fila[0],
            "nombre": fila[1],
            "usado": fila[2] == "S",
            "es_cierre": fila[3] == "S",
            "confirmado": fila[4] == "S",
        }
        for fila in filas
    ]


_COLS_HOMOLOGACION = (
    "h.ESTADO_SAC, h.PRIORIDAD, h.DESCRIPCION_SAC, h.ACCION, h.ESTADO_TU, h.CONFIRMADO, "
    "h.USUARIO_ID, h.FECHA_ACTUALIZACION"
)


def _fila_a_homologacion(fila, nombres):
    return {
        "estado_sac": fila[0],
        "prioridad": fila[1],
        "descripcion": fila[2],
        "accion": fila[3],
        "estado_tu": fila[4],
        "confirmado": fila[5] == "S",
        "actualizado_por": nombres.get(fila[6]),
        "fecha_actualizacion": fila[7],
    }


def _nombres_usuarios(ids):
    from usuarios.models import Usuario

    ids = [i for i in ids if i is not None]
    if not ids:
        return {}
    return dict(Usuario.objects.filter(pk__in=ids).values_list("pk", "nombre"))


def _leer_homologaciones(estado_sac=None):
    condicion, params = "", []
    if estado_sac is not None:
        condicion, params = " WHERE h.ESTADO_SAC = %s", [estado_sac]
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_COLS_HOMOLOGACION} FROM NEXOVOLT.NV_HOMOLOGA_ESTADO h{condicion} "
            "ORDER BY h.PRIORIDAD, h.ESTADO_SAC",
            params,
        )
        filas = cursor.fetchall()
    nombres = _nombres_usuarios({fila[6] for fila in filas})
    return [_fila_a_homologacion(fila, nombres) for fila in filas]


def listar_homologaciones():
    """Cada estado del SAC con su equivalente en TransUnion, por prioridad."""
    return _leer_homologaciones()


def validar_homologacion(accion, estado_tu, estados):
    """{campo: [mensaje]} si la combinación no se acepta; {} si está bien (contrato 0.9.1)."""
    if accion not in ACCIONES_HOMOLOGACION:
        return {"accion": [MSG_HOMOLOGACION["accion"]]}
    if accion == "CIERRE":
        return {"estado_tu": [MSG_HOMOLOGACION["cierre_con_estado"]]} if estado_tu else {}
    if not estado_tu:
        return {"estado_tu": [MSG_HOMOLOGACION["estado_tu"]]}
    estado = next((e for e in estados if e["codigo"] == estado_tu), None)
    if estado is None:
        return {"estado_tu": [MSG_HOMOLOGACION["no_existe"]]}
    if estado_tu in ESTADOS_DE_CIERRE:
        return {"estado_tu": [MSG_HOMOLOGACION["estado_de_cierre"]]}
    if not estado["usado"]:
        return {"estado_tu": [MSG_HOMOLOGACION["no_usado"].format(codigo=estado_tu, nombre=estado["nombre"])]}
    return {}


_CATALOGOS_BD = {
    "naturalezas-reestructuracion": (
        "SELECT CODIGO, DESCRIPCION, CONFIRMADO FROM NEXOVOLT.NV_NATURALEZA_REESTR ORDER BY CODIGO"
    ),
    "motivos-eliminacion": (
        "SELECT CODIGO, DESCRIPCION, CONFIRMADO FROM NEXOVOLT.NV_MOTIVO_ELIMINACION ORDER BY CODIGO"
    ),
    "tipologias-reclamo": (
        "SELECT CODIGO, DESCRIPCION, CONFIRMADO FROM NEXOVOLT.NV_TIPOLOGIA_RECLAMO ORDER BY CODIGO"
    ),
}
# Tablas del Manual Sector Real v34: los códigos los fija TransUnion, así que van confirmados.
# Qué modos usa CENS en la práctica es otra pregunta (hoy 01 en los pagos y 16 en las refinanciaciones).
_MODOS_EXTINCION = (  # Tabla 10, Modo de extinción
    ("01", "Voluntario"),
    ("02", "Proceso ejecutivo"),
    ("03", "Mandatoria de pago"),
    ("04", "Proceso ejecutivo con excepción"),
    ("05", "Prescripción"),
    ("07", "Dación en pago (solo aplica para créditos de vivienda)"),
    ("11", "Novación"),
    ("12", "Transacción"),
    ("13", "Compensación"),
    ("14", "Confusión"),
    ("15", "Remisión"),
    ("16", "Refinanciación"),
    ("17", "Dada en cesión"),
)
_TIPOS_PAGO = (  # Tabla 15, Tipo de pago
    ("01", "Voluntario"),
    ("02", "No voluntario"),
)
_CATALOGOS_FIJOS = {
    "modos-extincion": [
        {"codigo": c, "descripcion": d, "confirmado": True} for c, d in _MODOS_EXTINCION
    ],
    "tipos-pago": [
        {"codigo": c, "descripcion": d, "confirmado": True} for c, d in _TIPOS_PAGO
    ],
}


def listar_catalogo(nombre):
    """Items de un catálogo por nombre. None si el nombre no existe."""
    if nombre in _CATALOGOS_FIJOS:
        return _CATALOGOS_FIJOS[nombre]
    sql = _CATALOGOS_BD.get(nombre)
    if sql is None:
        return None
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [{"codigo": r[0], "descripcion": r[1], "confirmado": r[2] == "S"} for r in cursor.fetchall()]


def actualizar_homologacion(estado_sac, accion, estado_tu, confirmado=False, usuario=None):
    """Reemplaza la acción, el estado y si CENS lo confirmó. La prioridad no se cambia aquí."""
    if not _leer_homologaciones(estado_sac):
        raise EstadoSacNoEncontrado()
    errores = validar_homologacion(accion, estado_tu, listar_estados_tu())
    if errores:
        raise HomologacionInvalida(errores)
    estado_tu = estado_tu if accion == "ESTADO" else None
    usuario_id = getattr(usuario, "pk", None)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_HOMOLOGA_ESTADO "
                "SET ACCION = %s, ESTADO_TU = %s, CONFIRMADO = %s, USUARIO_ID = %s, FECHA_ACTUALIZACION = %s "
                "WHERE ESTADO_SAC = %s",
                [accion, estado_tu, "S" if confirmado else "N", usuario_id, ahora_para_bd(), estado_sac],
            )
        destino = estado_tu if accion == "ESTADO" else "cierre"
        with tolerar_fallo_bitacora(EVENTO_HOMOLOGACION):
            registrar_bitacora(
                EVENTO_HOMOLOGACION, "NV_HOMOLOGA_ESTADO", estado_sac,
                f"Estado {estado_sac} del SAC → {destino}" + (" (confirmado)" if confirmado else ""),
                usuario=usuario,
            )
    return _leer_homologaciones(estado_sac)[0]
