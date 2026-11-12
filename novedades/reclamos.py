from datetime import date, timedelta

from django.conf import settings
from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import fecha_str, hoy_bogota, timestamp_str


class ReclamoNoEncontrado(Exception):
    pass


class ReclamoYaCerrado(Exception):
    pass


class ObligacionNoEncontrada(Exception):
    pass


class TipologiaNoEncontrada(Exception):
    pass


class ObligacionConReclamoAbierto(Exception):
    def __init__(self, numero_obligacion):
        self.numero_obligacion = numero_obligacion
        super().__init__(f"La obligación {numero_obligacion} ya tiene un reclamo abierto.")


class InsumoCambiado(Exception):
    pass


_DIAS_PLAZO_RESPUESTA = 15
_MES_DIA_FESTIVOS_FIJOS = (
    (1, 1, False),
    (1, 6, True),
    (3, 19, True),
    (5, 1, False),
    (6, 29, True),
    (7, 20, False),
    (8, 7, False),
    (8, 15, True),
    (10, 12, True),
    (11, 1, True),
    (11, 11, True),
    (12, 8, False),
    (12, 25, False),
)

_SELECT_RECLAMO = (
    "r.RECLAMO_ID, r.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, "
    "TRIM(tit.NOMBRES || ' ' || tit.PRIMER_APELLIDO || ' ' || "
    "NVL(tit.SEGUNDO_APELLIDO, '')) NOMBRE_TITULAR, "
    "tip.CODIGO, tip.DESCRIPCION, tip.CONFIRMADO, r.FECHA_RADICACION, "
    "r.OBSERVACION, r.ESTADO, r.MARCACION_GENERADA, r.DESMARCACION_GENERADA, "
    "r.FECHA_LIMITE_RESPUESTA, r.RESULTADO, r.FECHA_CIERRE, "
    "r.OBSERVACION_CIERRE, u.NOMBRE, r.FECHA_REGISTRO"
)
_FROM_RECLAMO = (
    "FROM NEXOVOLT.NV_RECLAMO r "
    "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = r.OBLIGACION_ID "
    "JOIN NEXOVOLT.NV_TIPOLOGIA_RECLAMO tip ON tip.TIPOLOGIA_ID = r.TIPOLOGIA_ID "
    "LEFT JOIN NEXOVOLT.NV_TITULAR tit ON tit.CLIENTE_ID = o.CLIENTE_ID "
    "LEFT JOIN NEXOVOLT.USUARIOS_USUARIO u ON u.ID = r.USUARIO_ID "
)


def _fecha_pascua(anio):
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def _lunes_siguiente(fecha):
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


def _festivos_colombia(anio):
    festivos = set()
    for mes, dia, trasladable in _MES_DIA_FESTIVOS_FIJOS:
        fecha = date(anio, mes, dia)
        festivos.add(_lunes_siguiente(fecha) if trasladable else fecha)

    pascua = _fecha_pascua(anio)
    festivos.update((pascua - timedelta(days=3), pascua - timedelta(days=2)))
    festivos.update(
        _lunes_siguiente(pascua + timedelta(days=dias))
        for dias in (39, 60, 68)
    )
    return festivos


def calcular_fecha_limite_respuesta(fecha_radicacion, dias_habiles=_DIAS_PLAZO_RESPUESTA,
                                    incluir_fecha_radicacion=None):
    if incluir_fecha_radicacion is None:
        incluir_fecha_radicacion = getattr(
            settings, "RECLAMO_CONTAR_DIA_RADICACION", False
        )

    fecha = fecha_radicacion
    dias_contados = 0
    festivos_por_anio = {}
    while dias_contados < dias_habiles:
        if not (dias_contados == 0 and incluir_fecha_radicacion):
            fecha += timedelta(days=1)
        if fecha.year not in festivos_por_anio:
            festivos_por_anio[fecha.year] = _festivos_colombia(fecha.year)
        if fecha.weekday() < 5 and fecha not in festivos_por_anio[fecha.year]:
            dias_contados += 1
    return fecha


def _fila_a_reclamo(row):
    # cols: 0=RECLAMO_ID, 1=OBLIGACION_ID, 2=NUMERO_OBLIGACION_TU, 3=NOMBRE_TITULAR,
    #       4=tip.CODIGO, 5=tip.DESCRIPCION, 6=tip.CONFIRMADO,
    #       7=FECHA_RADICACION, 8=OBSERVACION, 9=ESTADO,
    #       10=MARCACION_GENERADA, 11=DESMARCACION_GENERADA,
    #       12=FECHA_LIMITE_RESPUESTA, 13=RESULTADO, 14=FECHA_CIERRE,
    #       15=OBSERVACION_CIERRE, 16=u.NOMBRE, 17=FECHA_REGISTRO
    fecha_limite = row[12]
    if hasattr(fecha_limite, "date"):
        fecha_limite = fecha_limite.date()
    return {
        "id": row[0],
        "obligacion_id": row[1],
        "numero_obligacion": row[2],
        "nombre_titular": row[3],
        "tipologia": {
            "codigo": row[4],
            "descripcion": row[5],
            "confirmado": row[6] == "S",
        },
        "fecha_radicacion": fecha_str(row[7]),
        "observacion": row[8],
        "estado": row[9],
        "marcacion_generada": row[10] == "S",
        "desmarcacion_generada": row[11] == "S",
        "fecha_limite_respuesta": fecha_str(row[12]),
        "vencido": (
            row[9] == "EN_RECLAMO"
            and fecha_limite is not None
            and fecha_limite < hoy_bogota()
        ),
        "resultado": row[13],
        "fecha_cierre": fecha_str(row[14]),
        "observacion_cierre": row[15],
        "registrado_por": row[16],
        "fecha_registro": timestamp_str(row[17]),
    }


def listar_reclamos(estado=None):
    if estado is not None and estado not in {"EN_RECLAMO", "CERRADO"}:
        raise ValueError("Estado no válido.")

    where = "WHERE r.ESTADO = %s " if estado is not None else ""
    params = [estado] if estado is not None else []
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_RECLAMO} {_FROM_RECLAMO}{where}"
            "ORDER BY r.FECHA_REGISTRO DESC, r.RECLAMO_ID DESC",
            params,
        )
        return [_fila_a_reclamo(row) for row in cursor.fetchall()]


def obtener_reclamo(reclamo_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_RECLAMO} {_FROM_RECLAMO}WHERE r.RECLAMO_ID = %s",
            [reclamo_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise ReclamoNoEncontrado()
    return _fila_a_reclamo(row)


def crear_reclamo(data, usuario=None):
    obligacion_id = data["obligacion_id"]
    fecha_radicacion = data["fecha_radicacion"]
    tipologia_codigo = data["tipologia"]

    if fecha_radicacion > hoy_bogota():
        raise ValueError("La fecha de radicación no puede ser futura.")

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT NUMERO_OBLIGACION_TU FROM NEXOVOLT.NV_OBLIGACION "
                "WHERE OBLIGACION_ID = %s FOR UPDATE",
                [obligacion_id],
            )
            obligacion = cursor.fetchone()
            if obligacion is None:
                raise ObligacionNoEncontrada()

            cursor.execute(
                "SELECT TIPOLOGIA_ID FROM NEXOVOLT.NV_TIPOLOGIA_RECLAMO "
                "WHERE CODIGO = %s AND CONFIRMADO = 'S'",
                [tipologia_codigo],
            )
            tipologia = cursor.fetchone()
            if tipologia is None:
                raise TipologiaNoEncontrada()

            cursor.execute(
                "SELECT RECLAMO_ID FROM NEXOVOLT.NV_RECLAMO "
                "WHERE OBLIGACION_ID = %s AND ESTADO = 'EN_RECLAMO'",
                [obligacion_id],
            )
            if cursor.fetchone() is not None:
                raise ObligacionConReclamoAbierto(obligacion[0])

            cursor.execute("SELECT NEXOVOLT.SEQ_NV_RECLAMO.NEXTVAL FROM DUAL")
            reclamo_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_RECLAMO "
                "(RECLAMO_ID, OBLIGACION_ID, TIPOLOGIA_ID, FECHA_RADICACION, "
                "OBSERVACION, ESTADO, FECHA_LIMITE_RESPUESTA, USUARIO_ID) "
                "VALUES (%s, %s, %s, %s, %s, 'EN_RECLAMO', %s, %s)",
                [
                    reclamo_id,
                    obligacion_id,
                    tipologia[0],
                    fecha_radicacion,
                    data.get("observacion"),
                    calcular_fecha_limite_respuesta(fecha_radicacion),
                    getattr(usuario, "pk", None),
                ],
            )

    with tolerar_fallo_bitacora("RECLAMO_REGISTRADO"):
        registrar_bitacora(
            "RECLAMO_REGISTRADO",
            "NV_RECLAMO",
            str(reclamo_id),
            f"Tipología {tipologia_codigo}",
            usuario=usuario,
        )
    return obtener_reclamo(reclamo_id)


def cerrar_reclamo(reclamo_id, data, usuario=None):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT FECHA_RADICACION, ESTADO FROM NEXOVOLT.NV_RECLAMO "
                "WHERE RECLAMO_ID = %s FOR UPDATE",
                [reclamo_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise ReclamoNoEncontrado()
            fecha_radicacion, estado = row
            if estado != "EN_RECLAMO":
                raise ReclamoYaCerrado()
            if data["fecha_cierre"] < fecha_radicacion:
                raise ValueError(
                    "La fecha de cierre no puede ser anterior a la de radicación."
                )

            cursor.execute(
                "UPDATE NEXOVOLT.NV_RECLAMO SET ESTADO = 'CERRADO', RESULTADO = %s, "
                "FECHA_CIERRE = %s, OBSERVACION_CIERRE = %s, DESMARCACION_GENERADA = 'N' "
                "WHERE RECLAMO_ID = %s",
                [data["resultado"], data["fecha_cierre"], data.get("observacion_cierre"), reclamo_id],
            )

    with tolerar_fallo_bitacora("RECLAMO_CERRADO"):
        registrar_bitacora(
            "RECLAMO_CERRADO",
            "NV_RECLAMO",
            str(reclamo_id),
            f"Resultado: {data['resultado']}",
            usuario=usuario,
        )
    return obtener_reclamo(reclamo_id)


def _formatear_insumo_reclamo(fila):
    numero_obligacion, tipologia, fecha_radicacion = fila
    return f"{numero_obligacion}|{tipologia}|{fecha_radicacion:%Y%m%d}\r\n"


def generar_insumo(tipo, usuario=None):
    if tipo not in {"marcacion", "desmarcacion"}:
        raise ValueError("Usa marcacion o desmarcacion.")

    es_marcacion = tipo == "marcacion"
    flag = "MARCACION_GENERADA" if es_marcacion else "DESMARCACION_GENERADA"
    estado = "EN_RECLAMO" if es_marcacion else "CERRADO"
    accion = "RECLAMO_INSUMO_GENERADO"

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT o.NUMERO_OBLIGACION_TU, tip.CODIGO, r.FECHA_RADICACION, "
                "r.RECLAMO_ID FROM NEXOVOLT.NV_RECLAMO r "
                "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = r.OBLIGACION_ID "
                "JOIN NEXOVOLT.NV_TIPOLOGIA_RECLAMO tip "
                "ON tip.TIPOLOGIA_ID = r.TIPOLOGIA_ID "
                f"WHERE r.ESTADO = %s AND r.{flag} = 'N' "
                "ORDER BY r.RECLAMO_ID FOR UPDATE OF r.RECLAMO_ID",
                [estado],
            )
            filas = cursor.fetchall()
            texto = "".join(_formatear_insumo_reclamo(fila[:3]) for fila in filas)
            if filas:
                cursor.executemany(
                    f"UPDATE NEXOVOLT.NV_RECLAMO SET {flag} = 'S' "
                    "WHERE RECLAMO_ID = %s AND ESTADO = %s AND "
                    f"{flag} = 'N'",
                    [(fila[3], estado) for fila in filas],
                )
                if cursor.rowcount != len(filas):
                    raise InsumoCambiado()

    if filas:
        with tolerar_fallo_bitacora(accion):
            registrar_bitacora(
                accion,
                "NV_RECLAMO",
                tipo,
                f"Tipo: {tipo}, registros: {len(filas)}",
                usuario=usuario,
            )
    return texto
