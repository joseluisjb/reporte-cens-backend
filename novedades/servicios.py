import logging
from decimal import Decimal

from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import fecha_str, hoy_bogota, timestamp_str
from usuarios.models import Usuario

logger = logging.getLogger(__name__)


class NovedadNoEncontrada(Exception):
    pass


class NovedadNoPendiente(Exception):
    pass


class ObligacionNoEncontrada(Exception):
    pass


class MotivoEliminacionNoEncontrado(Exception):
    pass


class EliminacionNoEncontrada(Exception):
    pass


class EliminacionYaReactivada(Exception):
    pass


class RectificacionNoEncontrada(Exception):
    pass


class CorteNoEnviado(Exception):
    pass


class RectificacionYaConfirmada(Exception):
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

_SEL_RECTIFICACION = (
    "r.RECTIFICACION_ID, r.NOVEDAD_ID, r.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, "
    "r.CORTE_ID, c.FECHA_CORTE, r.CAMPO, r.VALOR_ANTERIOR, r.VALOR_CORREGIDO, "
    "r.JUSTIFICACION, r.MEDIO, r.ESTADO, r.CONFIRMACION_TU, "
    "r.USUARIO_ID, r.FECHA_REGISTRO"
)
_FROM_RECTIFICACION = (
    "FROM NEXOVOLT.NV_RECTIFICACION r "
    "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = r.OBLIGACION_ID "
    "JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = r.CORTE_ID "
)
_CAMPOS_RECTIFICABLES = {"valor_mora": "VALOR_MORA"}


def _nombres_usuarios(usuario_ids):
    ids = {usuario_id for usuario_id in usuario_ids if usuario_id is not None}
    if not ids:
        return {}
    return dict(Usuario.objects.filter(pk__in=ids).values_list("pk", "nombre"))


def _fila_a_rectificacion(row, nombres):
    fecha_corte = row[5].date() if hasattr(row[5], "date") else row[5]
    return {
        "id": row[0],
        "novedad_id": row[1],
        "obligacion_id": row[2],
        "numero_obligacion": row[3],
        "corte_id": row[4],
        "fecha_corte": fecha_str(fecha_corte),
        "campo": row[6],
        "valor_anterior": None if row[7] is None else str(row[7]),
        "valor_corregido": str(row[8]),
        "justificacion": row[9],
        "medio": row[10],
        "estado": row[11],
        "confirmacion_tu": row[12],
        "registrada_por": nombres.get(row[13]),
        "fecha_registro": timestamp_str(row[14]),
    }


def _fetch_rectificacion(rectificacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL_RECTIFICACION} {_FROM_RECTIFICACION}"
            "WHERE r.RECTIFICACION_ID = %s",
            [rectificacion_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise RectificacionNoEncontrada()
    nombres = _nombres_usuarios([row[13]])
    return _fila_a_rectificacion(row, nombres)


def listar_rectificaciones():
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL_RECTIFICACION} {_FROM_RECTIFICACION}"
            "ORDER BY r.FECHA_REGISTRO DESC, r.RECTIFICACION_ID DESC"
        )
        filas = cursor.fetchall()
    nombres = _nombres_usuarios([fila[13] for fila in filas])
    return [_fila_a_rectificacion(fila, nombres) for fila in filas]


def crear_rectificacion(data, usuario=None):
    columna = _CAMPOS_RECTIFICABLES.get(data["campo"])
    if columna is None:
        raise ValueError(f"Campo no corregible: {data['campo']}")

    usuario_id = getattr(usuario, "pk", None)
    usuario_nombre = getattr(usuario, "nombre", None)
    valor_corregido = data["valor_corregido"]
    if not isinstance(valor_corregido, Decimal):
        valor_corregido = Decimal(str(valor_corregido))

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.ESTADO, c.FECHA_CORTE, o.NUMERO_OBLIGACION_TU, "
                f"rd.{columna} "
                "FROM NEXOVOLT.NV_CORTE c "
                "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd ON rd.CORTE_ID = c.CORTE_ID "
                "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = rd.OBLIGACION_ID "
                "WHERE c.CORTE_ID = %s AND rd.OBLIGACION_ID = %s "
                f"FOR UPDATE OF rd.{columna}",
                [data["corte_id"], data["obligacion_id"]],
            )
            fila = cursor.fetchone()
            if fila is None:
                raise RectificacionNoEncontrada()
            if fila[0] not in {"ENVIADO", "ENVIADO_CON_INCONSISTENCIAS"}:
                raise CorteNoEnviado()

            valor_anterior = fila[3]
            if valor_anterior is None:
                raise ValueError("El campo del corte no tiene un valor anterior.")
            if Decimal(str(valor_anterior)) == valor_corregido:
                raise ValueError("El valor corregido debe ser distinto al valor reportado.")

            cursor.execute("SELECT NEXOVOLT.SEQ_NV_NOVEDAD.NEXTVAL FROM DUAL")
            novedad_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_NOVEDAD "
                "(NOVEDAD_ID, TIPO, SUJETO, OBLIGACION_ID, REFERENCIA, MOTIVO, "
                "VALORES_ENVIADOS, FECHA_DETECCION, ORIGEN, ESTADO, USUARIO_ID, "
                "USUARIO_NOMBRE) "
                "VALUES (%s, 'CORRECCION', 'OBLIGACION', %s, %s, %s, %s, %s, "
                "'MANUAL', 'PENDIENTE', %s, %s)",
                [
                    novedad_id,
                    data["obligacion_id"],
                    fila[2],
                    data["justificacion"],
                    f"{data['campo']}={format(valor_corregido, 'f')}",
                    hoy_bogota(),
                    usuario_id,
                    usuario_nombre,
                ],
            )
            cursor.execute("SELECT NEXOVOLT.SEQ_NV_RECTIFICACION.NEXTVAL FROM DUAL")
            rectificacion_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_RECTIFICACION "
                "(RECTIFICACION_ID, NOVEDAD_ID, OBLIGACION_ID, CORTE_ID, CAMPO, "
                "VALOR_ANTERIOR, VALOR_CORREGIDO, JUSTIFICACION, MEDIO, ESTADO, USUARIO_ID) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'REGISTRADA', %s)",
                [
                    rectificacion_id,
                    novedad_id,
                    data["obligacion_id"],
                    data["corte_id"],
                    data["campo"],
                    str(valor_anterior),
                    format(valor_corregido, "f"),
                    data["justificacion"],
                    data["medio"],
                    usuario_id,
                ],
            )
            cursor.execute(
                f"UPDATE NEXOVOLT.NV_REPORTE_DETALLE SET {columna} = %s "
                "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
                [valor_corregido, data["corte_id"], data["obligacion_id"]],
            )

    with tolerar_fallo_bitacora("RECTIFICACION_REGISTRADA"):
        registrar_bitacora(
            "RECTIFICACION_REGISTRADA",
            "NV_RECTIFICACION",
            str(rectificacion_id),
            f"Obligación {fila[2]}, campo {data['campo']}, corte {data['corte_id']}",
            usuario=usuario,
        )
    return _fetch_rectificacion(rectificacion_id)


def confirmar_rectificacion(rectificacion_id, confirmacion_tu, usuario=None):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ESTADO, NOVEDAD_ID FROM NEXOVOLT.NV_RECTIFICACION "
                "WHERE RECTIFICACION_ID = %s FOR UPDATE",
                [rectificacion_id],
            )
            fila = cursor.fetchone()
            if fila is None:
                raise RectificacionNoEncontrada()
            if fila[0] == "CONFIRMADA":
                raise RectificacionYaConfirmada()
            cursor.execute(
                "UPDATE NEXOVOLT.NV_RECTIFICACION "
                "SET ESTADO = 'CONFIRMADA', CONFIRMACION_TU = %s "
                "WHERE RECTIFICACION_ID = %s",
                [confirmacion_tu, rectificacion_id],
            )
            cursor.execute(
                "UPDATE NEXOVOLT.NV_NOVEDAD "
                "SET ESTADO = 'GESTIONADA', NUMERO_TRANSACCION_TU = %s, "
                "FECHA_GESTION = %s WHERE NOVEDAD_ID = %s",
                [confirmacion_tu, hoy_bogota(), fila[1]],
            )

    with tolerar_fallo_bitacora("RECTIFICACION_CONFIRMADA"):
        registrar_bitacora(
            "RECTIFICACION_CONFIRMADA",
            "NV_RECTIFICACION",
            str(rectificacion_id),
            f"Confirmación TransUnion: {confirmacion_tu}",
            usuario=usuario,
        )
    return _fetch_rectificacion(rectificacion_id)


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

        # RF50: si es eliminación de obligación, registrar en NV_ELIMINACION
        if nov["tipo"] == "ELIMINACION" and nov["obligacion_id"] is not None:
            _registrar_eliminacion(
                obligacion_id=nov["obligacion_id"],
                novedad_id=novedad_id,
                fecha=fecha_gestion,
                motivo_eliminacion=nov.get("motivo_eliminacion"),
                numero_transaccion_tu=numero_transaccion_tu,
                usuario=usuario,
            )

    with tolerar_fallo_bitacora("NOVEDAD_GESTIONADA"):
        registrar_bitacora(
            "NOVEDAD_GESTIONADA", "NV_NOVEDAD", str(novedad_id),
            f"Transacción TU: {numero_transaccion_tu}",
            usuario=usuario,
        )

    return _fetch_novedad(novedad_id)


def _registrar_eliminacion(obligacion_id, novedad_id, fecha, motivo_eliminacion,
                            numero_transaccion_tu, usuario=None):
    """RF50: crea NV_ELIMINACION y marca NV_OBLIGACION.ELIMINADA='S'."""
    usuario_id = getattr(usuario, "pk", None)
    motivo_id = None
    if motivo_eliminacion is not None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MOTIVO_ID FROM NEXOVOLT.NV_MOTIVO_ELIMINACION WHERE CODIGO = %s",
                [motivo_eliminacion["codigo"]],
            )
            row = cursor.fetchone()
            if row:
                motivo_id = row[0]

    with connection.cursor() as cursor:
        cursor.execute("SELECT NEXOVOLT.SEQ_NV_ELIMINACION.NEXTVAL FROM DUAL")
        eliminacion_id = cursor.fetchone()[0]

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_ELIMINACION "
            "(ELIMINACION_ID, OBLIGACION_ID, NOVEDAD_ID, FECHA, MOTIVO_ID, "
            "NUMERO_TRANSACCION_TU, BLOQUEADA, USUARIO_ID) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'S', %s)",
            [eliminacion_id, obligacion_id, novedad_id, fecha,
             motivo_id, numero_transaccion_tu, usuario_id],
        )
        cursor.execute(
            "UPDATE NEXOVOLT.NV_OBLIGACION SET ELIMINADA = 'S' WHERE OBLIGACION_ID = %s",
            [obligacion_id],
        )

    with tolerar_fallo_bitacora("ELIMINACION_OBLIGACION"):
        registrar_bitacora(
            "ELIMINACION_OBLIGACION", "NV_ELIMINACION", str(eliminacion_id),
            f"Obligación {obligacion_id}, TU: {numero_transaccion_tu}",
            usuario=usuario,
        )


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


# ── RF50: Eliminaciones ───────────────────────────────────────────────────────

_SEL_ELIM = (
    "e.ELIMINACION_ID, e.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, e.FECHA, "
    "me.CODIGO, me.DESCRIPCION, me.CONFIRMADO, "
    "e.NUMERO_TRANSACCION_TU, e.BLOQUEADA, e.FECHA_ACTIVACION, e.NUMERO_ACTIVACION_TU"
)
_FROM_ELIM = (
    "FROM NEXOVOLT.NV_ELIMINACION e "
    "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = e.OBLIGACION_ID "
    "LEFT JOIN NEXOVOLT.NV_MOTIVO_ELIMINACION me ON me.MOTIVO_ID = e.MOTIVO_ID "
)


def _fila_a_eliminacion(row):
    motivo = None
    if row[4] is not None:
        motivo = {
            "codigo": row[4],
            "descripcion": row[5],
            "confirmado": row[6] == "S",
        }
    return {
        "id": row[0],
        "obligacion_id": row[1],
        "numero_obligacion": row[2],
        "fecha": fecha_str(row[3]),
        "motivo": motivo,
        "numero_transaccion_tu": row[7],
        "bloqueada": row[8] == "S",
        "fecha_activacion": fecha_str(row[9]),
        "numero_activacion_tu": row[10],
    }


def listar_eliminaciones(limite, desplazamiento):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) {_FROM_ELIM}")
        total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT {_SEL_ELIM} {_FROM_ELIM}"
            "ORDER BY e.FECHA DESC "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [desplazamiento, limite],
        )
        rows = cursor.fetchall()

    return {"total": total, "resultados": [_fila_a_eliminacion(r) for r in rows]}


def reactivar_eliminacion(eliminacion_id, numero_activacion_tu, fecha_activacion,
                           usuario=None):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL_ELIM} {_FROM_ELIM}WHERE e.ELIMINACION_ID = %s",
            [eliminacion_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise EliminacionNoEncontrada()

    if row[8] != "S":
        raise EliminacionYaReactivada()

    obligacion_id = row[1]

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_ELIMINACION "
                "SET BLOQUEADA = 'N', FECHA_ACTIVACION = %s, NUMERO_ACTIVACION_TU = %s "
                "WHERE ELIMINACION_ID = %s",
                [fecha_activacion, numero_activacion_tu, eliminacion_id],
            )
            cursor.execute(
                "UPDATE NEXOVOLT.NV_OBLIGACION SET ELIMINADA = 'N' "
                "WHERE OBLIGACION_ID = %s",
                [obligacion_id],
            )

    with tolerar_fallo_bitacora("REACTIVACION_OBLIGACION"):
        registrar_bitacora(
            "REACTIVACION_OBLIGACION", "NV_ELIMINACION", str(eliminacion_id),
            f"Obligación {obligacion_id}, activación TU: {numero_activacion_tu}",
            usuario=usuario,
        )

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SEL_ELIM} {_FROM_ELIM}WHERE e.ELIMINACION_ID = %s",
            [eliminacion_id],
        )
        return _fila_a_eliminacion(cursor.fetchone())
