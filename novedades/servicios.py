import logging

from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import fecha_str, hoy_bogota

logger = logging.getLogger(__name__)


class NovedadNoEncontrada(Exception):
    pass


class NovedadNoPendiente(Exception):
    pass


class ObligacionNoEncontrada(Exception):
    pass


class MotivoEliminacionNoEncontrado(Exception):
    pass


_TIPOS_VALIDOS = {"INCLUSION", "ACTUALIZACION", "CORRECCION", "ELIMINACION"}
_ESTADOS_VALIDOS = {"PENDIENTE", "GESTIONADA", "RECHAZADA"}

_SEL = (
    "n.NOVEDAD_ID, n.TIPO, n.SUJETO, n.OBLIGACION_ID, n.REFERENCIA, n.MOTIVO, "
    "me.CODIGO, me.DESCRIPCION, me.CONFIRMADO, "
    "n.VALORES_ENVIADOS, n.FECHA_DETECCION, n.ORIGEN, n.ESTADO, "
    "n.NUMERO_TRANSACCION_TU, n.FECHA_GESTION, n.MOTIVO_RECHAZO, n.USUARIO_NOMBRE"
)
_FROM = (
    "FROM NEXOVOLT.NV_NOVEDAD n "
    "LEFT JOIN NEXOVOLT.NV_MOTIVO_ELIMINACION me "
    "  ON me.MOTIVO_ID = n.MOTIVO_ELIMINACION_ID "
)


def _fila_a_novedad(row):
    motivo_eliminacion = None
    if row[6] is not None:
        motivo_eliminacion = {
            "codigo": row[6],
            "descripcion": row[7],
            "confirmado": row[8] == "S",
        }
    return {
        "id": row[0],
        "tipo": row[1],
        "sujeto": row[2],
        "obligacion_id": row[3],
        "referencia": row[4],
        "motivo": row[5],
        "motivo_eliminacion": motivo_eliminacion,
        "valores_enviados": row[9],
        "fecha_deteccion": fecha_str(row[10]),
        "origen": row[11],
        "estado": row[12],
        "numero_transaccion_tu": row[13],
        "fecha_gestion": fecha_str(row[14]),
        "motivo_rechazo": row[15],
        "registrada_por": row[16],
    }


def _fetch_novedad(novedad_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL} {_FROM}WHERE n.NOVEDAD_ID = %s",
            [novedad_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise NovedadNoEncontrada()
    return _fila_a_novedad(row)


def listar_novedades(estado=None, tipo=None):
    if estado is not None and estado not in _ESTADOS_VALIDOS:
        raise ValueError(f"Estado no válido: {estado}")
    if tipo is not None and tipo not in _TIPOS_VALIDOS:
        raise ValueError(f"Tipo no válido: {tipo}")

    where = []
    params = []
    if estado is not None:
        where.append("n.ESTADO = %s")
        params.append(estado)
    if tipo is not None:
        where.append("n.TIPO = %s")
        params.append(tipo)

    cond = (" WHERE " + " AND ".join(where) + " ") if where else ""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL} {_FROM}{cond}"
            "ORDER BY n.FECHA_DETECCION DESC, n.NOVEDAD_ID DESC",
            params,
        )
        filas = cursor.fetchall()
    return [_fila_a_novedad(r) for r in filas]


def crear_novedad(data, usuario=None):
    tipo = data["tipo"]
    sujeto = data["sujeto"]
    obligacion_id = data.get("obligacion_id")
    referencia = data["referencia"]
    motivo = data["motivo"]
    motivo_eliminacion_codigo = data.get("motivo_eliminacion")
    valores_enviados = data.get("valores_enviados")

    # Si sujeto=OBLIGACION y tipo!=INCLUSION, la obligación debe existir (RF24)
    if sujeto == "OBLIGACION" and tipo != "INCLUSION" and obligacion_id is not None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM NEXOVOLT.NV_OBLIGACION WHERE OBLIGACION_ID = %s",
                [obligacion_id],
            )
            if cursor.fetchone()[0] == 0:
                raise ObligacionNoEncontrada()

    # Resolver motivo_eliminacion_id desde el catálogo
    motivo_eliminacion_id = None
    if motivo_eliminacion_codigo is not None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MOTIVO_ID FROM NEXOVOLT.NV_MOTIVO_ELIMINACION "
                "WHERE CODIGO = %s",
                [motivo_eliminacion_codigo],
            )
            row = cursor.fetchone()
        if row is None:
            raise MotivoEliminacionNoEncontrado()
        motivo_eliminacion_id = row[0]

    usuario_id = getattr(usuario, "pk", None)
    usuario_nombre = getattr(usuario, "nombre", None)
    fecha_hoy = hoy_bogota()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT NEXOVOLT.SEQ_NV_NOVEDAD.NEXTVAL FROM DUAL")
            novedad_id = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_NOVEDAD "
                "(NOVEDAD_ID, TIPO, SUJETO, OBLIGACION_ID, REFERENCIA, MOTIVO, "
                "MOTIVO_ELIMINACION_ID, VALORES_ENVIADOS, FECHA_DETECCION, "
                "ORIGEN, ESTADO, USUARIO_ID, USUARIO_NOMBRE) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'MANUAL', 'PENDIENTE', %s, %s)",
                [
                    novedad_id, tipo, sujeto, obligacion_id, referencia, motivo,
                    motivo_eliminacion_id, valores_enviados, fecha_hoy,
                    usuario_id, usuario_nombre,
                ],
            )

    with tolerar_fallo_bitacora("NOVEDAD_REGISTRADA"):
        registrar_bitacora(
            "NOVEDAD_REGISTRADA", "NV_NOVEDAD", str(novedad_id),
            f"Tipo: {tipo}, Referencia: {referencia}",
            usuario=usuario,
        )

    return _fetch_novedad(novedad_id)


def gestionar_novedad(novedad_id, numero_transaccion_tu, fecha_gestion, usuario=None):
    nov = _fetch_novedad(novedad_id)
    if nov["estado"] != "PENDIENTE":
        raise NovedadNoPendiente()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_NOVEDAD "
                "SET ESTADO = 'GESTIONADA', NUMERO_TRANSACCION_TU = %s, FECHA_GESTION = %s "
                "WHERE NOVEDAD_ID = %s",
                [numero_transaccion_tu, fecha_gestion, novedad_id],
            )

    with tolerar_fallo_bitacora("NOVEDAD_GESTIONADA"):
        registrar_bitacora(
            "NOVEDAD_GESTIONADA", "NV_NOVEDAD", str(novedad_id),
            f"Transacción TU: {numero_transaccion_tu}",
            usuario=usuario,
        )

    return _fetch_novedad(novedad_id)


def rechazar_novedad(novedad_id, motivo_rechazo, usuario=None):
    nov = _fetch_novedad(novedad_id)
    if nov["estado"] != "PENDIENTE":
        raise NovedadNoPendiente()

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_NOVEDAD "
                "SET ESTADO = 'RECHAZADA', MOTIVO_RECHAZO = %s, FECHA_GESTION = %s "
                "WHERE NOVEDAD_ID = %s",
                [motivo_rechazo, hoy_bogota(), novedad_id],
            )

    with tolerar_fallo_bitacora("NOVEDAD_RECHAZADA"):
        registrar_bitacora(
            "NOVEDAD_RECHAZADA", "NV_NOVEDAD", str(novedad_id),
            f"Motivo: {motivo_rechazo}",
            usuario=usuario,
        )

    return _fetch_novedad(novedad_id)


def crear_novedad_automatica(obligacion_id, referencia, usuario_id=None):
    """Detecta pago posterior al corte y registra novedad AUTOMATICA (RF24)."""
    fecha_hoy = hoy_bogota()
    motivo = (
        "Pago del titular posterior al corte: "
        "se actualiza sin esperar al próximo reporte"
    )
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT NEXOVOLT.SEQ_NV_NOVEDAD.NEXTVAL FROM DUAL")
            novedad_id = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_NOVEDAD "
                "(NOVEDAD_ID, TIPO, SUJETO, OBLIGACION_ID, REFERENCIA, MOTIVO, "
                "MOTIVO_ELIMINACION_ID, VALORES_ENVIADOS, FECHA_DETECCION, "
                "ORIGEN, ESTADO, USUARIO_ID, USUARIO_NOMBRE) "
                "VALUES (%s, 'ACTUALIZACION', 'OBLIGACION', %s, %s, %s, "
                "NULL, NULL, %s, 'AUTOMATICA', 'PENDIENTE', %s, NULL)",
                [novedad_id, obligacion_id, referencia, motivo, fecha_hoy, usuario_id],
            )

    with tolerar_fallo_bitacora("NOVEDAD_REGISTRADA"):
        registrar_bitacora(
            "NOVEDAD_REGISTRADA", "NV_NOVEDAD", str(novedad_id),
            f"Automática: Obligación {obligacion_id}, Referencia: {referencia}",
            usuario_id=usuario_id,
        )
