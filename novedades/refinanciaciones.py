from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import fecha_str, timestamp_str


class ObligacionNoEncontrada(Exception):
    pass


class ObligacionCerrada(Exception):
    def __init__(self, numero_obligacion):
        self.numero_obligacion = numero_obligacion
        super().__init__(f"La obligación {numero_obligacion} ya está cerrada.")


class ObligacionEliminada(Exception):
    def __init__(self, numero_obligacion):
        self.numero_obligacion = numero_obligacion
        super().__init__(f"La obligación {numero_obligacion} ha sido eliminada.")


class TransicionNoPermitida(Exception):
    def __init__(self, estado_desde):
        self.estado_desde = estado_desde
        super().__init__(f"TransUnion no acepta cerrar desde estado {estado_desde}.")


class NaturalezaNoEncontrada(Exception):
    pass


# Mapea el último estado reportado al estado de cierre por refinanciación (RF12, RF15)
_CIERRE_POR_ESTADO = {
    "01": "02", "08": "02",   # Vigente/Inactivo → Saldada
    "03": "07", "06": "07",   # Dudoso Recaudo/Castigada → Cartera Recuperada
    "02": "02", "07": "07",   # Ya cerradas (no deberían llegar aquí)
}

# cols: 0=REFINANCIACION_ID, 1=FECHA, 2=FECHA_REGISTRO, 3=ORIGEN,
#       4=OBLIGACION_ORIGEN_ID, 5=o_orig.NUMERO_OBLIGACION_TU,
#       6=NOMBRE_TITULAR, 7=NVL(rd_orig.ESTADO_TU,'01'),
#       8=OBLIGACION_NUEVA_ID, 9=o_nueva.NUMERO_OBLIGACION_TU,
#       10=NVL(rd_nueva.ESTADO_TU,'01'), 11=profundidad de cadena (N_REESTRUCTURACIONES),
#       12=SALDO_REFINANCIADO, 13=NATURALEZA, 14=nat.DESCRIPCION,
#       15=nat.CONFIRMADO, 16=N_CUOTAS, 17=u.NOMBRE
_SELECT_REFINANCIACION = (
    "r.REFINANCIACION_ID, r.FECHA, r.FECHA_REGISTRO, r.ORIGEN, "
    "r.OBLIGACION_ORIGEN_ID, o_orig.NUMERO_OBLIGACION_TU, "
    "TRIM(tit.NOMBRES || ' ' || tit.PRIMER_APELLIDO || ' ' || "
    "NVL(tit.SEGUNDO_APELLIDO, '')) NOMBRE_TITULAR, "
    "NVL(rd_orig.ESTADO_TU, '01') ESTADO_TU_ORIG, "
    "r.OBLIGACION_NUEVA_ID, o_nueva.NUMERO_OBLIGACION_TU, "
    "NVL(rd_nueva.ESTADO_TU, '01') ESTADO_TU_NUEVA, "
    "(SELECT COUNT(*) FROM NEXOVOLT.NV_REFINANCIACION r_cnt "
    "START WITH r_cnt.OBLIGACION_NUEVA_ID = r.OBLIGACION_NUEVA_ID "
    "CONNECT BY r_cnt.OBLIGACION_NUEVA_ID = PRIOR r_cnt.OBLIGACION_ORIGEN_ID), "
    "r.SALDO_REFINANCIADO, r.NATURALEZA, nat.DESCRIPCION, nat.CONFIRMADO, "
    "r.N_CUOTAS, u.NOMBRE"
)
_FROM_REFINANCIACION = (
    "FROM NEXOVOLT.NV_REFINANCIACION r "
    "JOIN NEXOVOLT.NV_OBLIGACION o_orig ON o_orig.OBLIGACION_ID = r.OBLIGACION_ORIGEN_ID "
    "JOIN NEXOVOLT.NV_OBLIGACION o_nueva ON o_nueva.OBLIGACION_ID = r.OBLIGACION_NUEVA_ID "
    "LEFT JOIN NEXOVOLT.NV_TITULAR tit ON tit.CLIENTE_ID = o_orig.CLIENTE_ID "
    "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE rd_orig "
    "ON rd_orig.OBLIGACION_ID = r.OBLIGACION_ORIGEN_ID "
    "AND rd_orig.CORTE_ID = (SELECT MAX(rd2.CORTE_ID) FROM NEXOVOLT.NV_REPORTE_DETALLE rd2 "
    "WHERE rd2.OBLIGACION_ID = r.OBLIGACION_ORIGEN_ID) "
    "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE rd_nueva "
    "ON rd_nueva.OBLIGACION_ID = r.OBLIGACION_NUEVA_ID "
    "AND rd_nueva.CORTE_ID = (SELECT MAX(rd3.CORTE_ID) FROM NEXOVOLT.NV_REPORTE_DETALLE rd3 "
    "WHERE rd3.OBLIGACION_ID = r.OBLIGACION_NUEVA_ID) "
    "LEFT JOIN NEXOVOLT.NV_NATURALEZA_REESTR nat ON nat.CODIGO = r.NATURALEZA "
    "LEFT JOIN NEXOVOLT.USUARIOS_USUARIO u ON u.ID = r.USUARIO_ID "
)


def _fila_a_refinanciacion(row):
    estado_tu_orig = row[7]
    estado_cierre = _CIERRE_POR_ESTADO.get(estado_tu_orig, "02")
    return {
        "id": row[0],
        "fecha": fecha_str(row[1]),
        "fecha_registro": timestamp_str(row[2]),
        "origen": row[3],
        "obligacion_original": {
            "obligacion_id": row[4],
            "numero_obligacion": row[5],
            "nombre_titular": row[6],
            "estado_cierre": estado_cierre,
            "modo_extincion": {"codigo": "16", "descripcion": "Refinanciación"},
        },
        "obligacion_nueva": {
            "obligacion_id": row[8],
            "numero_obligacion": row[9],
            "estado_tu": row[10],
            "numero_reestructuraciones": row[11],
        },
        "saldo_refinanciado": row[12],
        "naturaleza": {
            "codigo": row[13],
            "descripcion": row[14],
            "confirmado": row[15] == "S",
        },
        "numero_cuotas": row[16],
        "registrada_por": row[17],
    }


def listar_refinanciaciones():
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_REFINANCIACION} {_FROM_REFINANCIACION}"
            "ORDER BY r.REFINANCIACION_ID DESC"
        )
        return [_fila_a_refinanciacion(row) for row in cursor.fetchall()]


def obtener_refinanciacion(refinanciacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_REFINANCIACION} {_FROM_REFINANCIACION}"
            "WHERE r.REFINANCIACION_ID = %s",
            [refinanciacion_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise ObligacionNoEncontrada()
    return _fila_a_refinanciacion(row)


def crear_refinanciacion(data, usuario=None):
    obligacion_id = data["obligacion_original_id"]
    naturaleza_codigo = data["naturaleza"]
    numero_cuotas = data["numero_cuotas"]
    fecha = data["fecha"]

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT o.CLIENTE_ID, o.NUMERO_PROCESO, o.NUMERO_OBLIGACION_TU, "
                "o.CIERRE_DEFINITIVO, o.ELIMINADA, o.FECHA_INICIO "
                "FROM NEXOVOLT.NV_OBLIGACION o "
                "WHERE o.OBLIGACION_ID = %s FOR UPDATE",
                [obligacion_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise ObligacionNoEncontrada()
            cliente_id, numero_proceso, numero_obligacion, cierre_definitivo, eliminada, fecha_inicio = row

            if eliminada == "S":
                raise ObligacionEliminada(numero_obligacion)
            if cierre_definitivo == "S":
                raise ObligacionCerrada(numero_obligacion)

            if fecha_inicio is not None:
                if hasattr(fecha_inicio, "date"):
                    fecha_inicio = fecha_inicio.date()
                if fecha < fecha_inicio:
                    raise ValueError(
                        f"La fecha no puede ser anterior al ingreso de la obligación "
                        f"({fecha_str(fecha_inicio)})."
                    )

            cursor.execute(
                "SELECT MAX(FECHA_CORTE) FROM NEXOVOLT.NV_CORTE "
                "WHERE ESTADO IN ('ENVIADO', 'ENVIADO_CON_INCONSISTENCIAS')",
            )
            fecha_corte_row = cursor.fetchone()
            fecha_ultimo_enviado = fecha_corte_row[0] if fecha_corte_row else None
            if fecha_ultimo_enviado is not None:
                if hasattr(fecha_ultimo_enviado, "date"):
                    fecha_ultimo_enviado = fecha_ultimo_enviado.date()
                if fecha < fecha_ultimo_enviado:
                    raise ValueError(
                        f"La fecha no puede ser anterior al último corte enviado "
                        f"({fecha_str(fecha_ultimo_enviado)})."
                    )

            cursor.execute(
                "SELECT ESTADO_TU, VALOR_SALDO FROM NEXOVOLT.NV_REPORTE_DETALLE "
                "WHERE OBLIGACION_ID = %s "
                "ORDER BY CORTE_ID DESC FETCH FIRST 1 ROW ONLY",
                [obligacion_id],
            )
            estado_row = cursor.fetchone()
            estado_actual = estado_row[0] if estado_row else None
            saldo_refinanciado = int(estado_row[1]) if estado_row and estado_row[1] is not None else None

            if estado_actual in ("02", "07"):
                raise ObligacionCerrada(numero_obligacion)
            if estado_actual in ("04", "10", "11", "12"):
                raise TransicionNoPermitida(estado_actual)

            cursor.execute(
                "SELECT DESCRIPCION FROM NEXOVOLT.NV_NATURALEZA_REESTR "
                "WHERE CODIGO = %s",
                [naturaleza_codigo],
            )
            if cursor.fetchone() is None:
                raise NaturalezaNoEncontrada()

            cursor.execute(
                "SELECT NEXOVOLT.SEQ_NV_REFINANCIACION.NEXTVAL FROM DUAL"
            )
            refinanciacion_id = cursor.fetchone()[0]

            cursor.execute(
                "SELECT NEXOVOLT.SEQ_NV_OBLIGACION.NEXTVAL FROM DUAL"
            )
            nueva_obligacion_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_OBLIGACION "
                "(OBLIGACION_ID, CLIENTE_ID, NUMERO_PROCESO, NUMERO_OBLIGACION_TU, FECHA_INICIO) "
                "VALUES (%s, %s, %s, %s, %s)",
                [nueva_obligacion_id, cliente_id, numero_proceso,
                 f"REFI-{refinanciacion_id}", fecha],
            )

            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_REFINANCIACION "
                "(REFINANCIACION_ID, OBLIGACION_ORIGEN_ID, OBLIGACION_NUEVA_ID, "
                "FECHA, NATURALEZA, N_CUOTAS, SALDO_REFINANCIADO, ORIGEN, USUARIO_ID) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'MANUAL', %s)",
                [refinanciacion_id, obligacion_id, nueva_obligacion_id,
                 fecha, naturaleza_codigo, numero_cuotas, saldo_refinanciado,
                 getattr(usuario, "pk", None)],
            )

            cursor.execute(
                "UPDATE NEXOVOLT.NV_OBLIGACION "
                "SET CIERRE_DEFINITIVO = 'S', FECHA_CIERRE = %s "
                "WHERE OBLIGACION_ID = %s",
                [fecha, obligacion_id],
            )

    with tolerar_fallo_bitacora("REFINANCIACION_REGISTRADA"):
        registrar_bitacora(
            "REFINANCIACION_REGISTRADA",
            "NV_REFINANCIACION",
            str(refinanciacion_id),
            f"Obligación original {obligacion_id}",
            usuario=usuario,
        )
    return obtener_refinanciacion(refinanciacion_id)
