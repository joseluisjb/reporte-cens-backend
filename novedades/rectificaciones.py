import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import fecha_str, hoy_bogota, timestamp_str


class RectificacionNoEncontrada(Exception):
    pass


class CorteNoEncontrado(Exception):
    pass


class ObligacionNoEncontrada(Exception):
    pass


class CorteNoEnviado(Exception):
    pass


class NovedadNoValida(Exception):
    pass


class RectificacionYaConfirmada(Exception):
    pass


class RectificacionDatoInvalido(Exception):
    def __init__(self, campo, mensaje):
        self.campo = campo
        super().__init__(mensaje)


_CAMPOS_RECTIFICABLES = {
    "valor_inicial": ("VALOR_INICIAL", "numero"),
    "valor_saldo": ("VALOR_SALDO", "numero"),
    "valor_mora": ("VALOR_MORA", "numero"),
    "valor_cuota": ("VALOR_CUOTA", "numero"),
    "cuotas_totales": ("CUOTAS_TOTALES", "numero"),
    "cuotas_canceladas": ("CUOTAS_CANCELADAS", "numero"),
    "cuotas_mora": ("CUOTAS_MORA", "numero"),
    "estado_tu": ("ESTADO_TU", "codigo"),
    "edad_mora_tu": ("EDAD_MORA_TU", "codigo"),
    "valor_real_pagado": ("VALOR_REAL_PAGADO", "numero"),
    "obligacion_refinanciada": ("OBLIGACION_REFINANCIADA", "codigo"),
    "fecha_exigibilidad": ("FECHA_EXIGIBILIDAD", "fecha"),
    "anios_mora": ("ANIOS_MORA", "numero"),
    "cuotas_pagadas": ("CUOTAS_PAGADAS", "numero"),
    "estado_contrato": ("ESTADO_CONTRATO", "codigo"),
    "fecha_pago": ("FECHA_PAGO", "fecha"),
    "modo_extincion": ("MODO_EXTINCION", "codigo"),
    "tipo_pago": ("TIPO_PAGO", "codigo"),
    "n_reestructuraciones": ("N_REESTRUCTURACIONES", "numero"),
    "naturaleza_reestr": ("NATURALEZA_REESTR", "codigo"),
    "edad_anterior": ("EDAD_ANTERIOR", "codigo"),
}
_LONGITUD_CODIGOS = {
    "estado_tu": 2,
    "edad_mora_tu": 2,
    "obligacion_refinanciada": 2,
    "estado_contrato": 3,
    "modo_extincion": 2,
    "tipo_pago": 2,
    "naturaleza_reestr": 2,
    "edad_anterior": 2,
}
_MAX_NUMERICOS = {
    "valor_inicial": 99_999_999_999_999,
    "valor_saldo": 99_999_999_999_999,
    "valor_mora": 99_999_999_999_999,
    "valor_cuota": 99_999_999_999_999,
    "cuotas_totales": 999,
    "cuotas_canceladas": 999,
    "cuotas_mora": 999,
    "valor_real_pagado": 99_999_999_999_999,
    "anios_mora": 99,
    "cuotas_pagadas": 999,
    "n_reestructuraciones": 999,
}
_SELECT_RECTIFICACION = (
    "r.RECTIFICACION_ID, r.NOVEDAD_ID, r.OBLIGACION_ID, "
    "o.NUMERO_OBLIGACION_TU, r.CORTE_ID, c.FECHA_CORTE, r.CAMPO, "
    "r.VALOR_ANTERIOR, r.VALOR_CORREGIDO, r.JUSTIFICACION, r.MEDIO, "
    "r.ESTADO, r.CONFIRMACION_TU, u.NOMBRE, r.FECHA_REGISTRO "
)
_FROM_RECTIFICACION = (
    "FROM NEXOVOLT.NV_RECTIFICACION r "
    "JOIN NEXOVOLT.NV_OBLIGACION o ON o.OBLIGACION_ID = r.OBLIGACION_ID "
    "JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = r.CORTE_ID "
    "LEFT JOIN NEXOVOLT.USUARIOS_USUARIO u ON u.ID = r.USUARIO_ID "
)


def _valor_anterior(valor):
    if valor is None:
        raise ValueError("El campo no tiene un valor anterior que se pueda conservar.")
    if isinstance(valor, (date,)):
        return fecha_str(valor)
    if hasattr(valor, "date"):
        return fecha_str(valor)
    return str(valor)


def _validar_valor_corregido(campo, valor):
    if campo not in _CAMPOS_RECTIFICABLES:
        raise RectificacionDatoInvalido("campo", "El campo no se puede rectificar.")
    if not valor or not valor.strip():
        raise RectificacionDatoInvalido("valor_corregido", "Ingresa el valor corregido.")
    if len(valor) > 100:
        raise RectificacionDatoInvalido(
            "valor_corregido",
            "El valor corregido no puede superar 100 caracteres.",
        )

    _, tipo = _CAMPOS_RECTIFICABLES[campo]
    if tipo == "numero":
        try:
            numero = Decimal(valor)
        except InvalidOperation as exc:
            raise RectificacionDatoInvalido(
                "valor_corregido", "Ingresa un número entero válido."
            ) from exc
        if (
            not numero.is_finite()
            or numero != numero.to_integral_value()
            or numero < 0
            or numero > _MAX_NUMERICOS[campo]
        ):
            raise RectificacionDatoInvalido(
                "valor_corregido", "Ingresa un número entero dentro del rango permitido."
            )
        return int(numero), str(int(numero))
    if tipo == "fecha":
        try:
            normalizado = date.fromisoformat(valor)
        except ValueError as exc:
            raise RectificacionDatoInvalido(
                "valor_corregido",
                "Ingresa una fecha válida en formato AAAA-MM-DD.",
            ) from exc
        if normalizado.isoformat() != valor:
            raise RectificacionDatoInvalido(
                "valor_corregido",
                "Ingresa una fecha válida en formato AAAA-MM-DD.",
            )
        return normalizado, normalizado.isoformat()

    normalizado = valor.strip()
    maximo = _LONGITUD_CODIGOS[campo]
    if len(normalizado) > maximo or any(char in normalizado for char in "\r\n|"):
        raise RectificacionDatoInvalido(
            "valor_corregido", f"El valor debe tener máximo {maximo} caracteres."
        )
    return normalizado, normalizado


def _fila_a_rectificacion(row):
    return {
        "id": row[0],
        "novedad_id": row[1],
        "obligacion_id": row[2],
        "numero_obligacion": row[3],
        "corte_id": row[4],
        "fecha_corte": fecha_str(row[5]),
        "campo": row[6],
        "valor_anterior": row[7],
        "valor_corregido": row[8],
        "justificacion": row[9],
        "medio": row[10],
        "estado": row[11],
        "confirmacion_tu": row[12],
        "registrada_por": row[13],
        "fecha_registro": timestamp_str(row[14]),
    }


def listar_rectificaciones():
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_RECTIFICACION} {_FROM_RECTIFICACION}"
            "ORDER BY r.FECHA_REGISTRO DESC, r.RECTIFICACION_ID DESC"
        )
        return [_fila_a_rectificacion(row) for row in cursor.fetchall()]


def obtener_rectificacion(rectificacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {_SELECT_RECTIFICACION} {_FROM_RECTIFICACION}"
            "WHERE r.RECTIFICACION_ID = %s",
            [rectificacion_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise RectificacionNoEncontrada()
    return _fila_a_rectificacion(row)


def _crear_novedad_correccion(cursor, obligacion_id, numero_obligacion, campo,
                              valor_anterior, valor_corregido, justificacion,
                              usuario):
    cursor.execute("SELECT NEXOVOLT.SEQ_NV_NOVEDAD.NEXTVAL FROM DUAL")
    novedad_id = cursor.fetchone()[0]
    valores_enviados = json.dumps(
        {"campo": campo, "anterior": valor_anterior, "corregido": valor_corregido},
        ensure_ascii=False,
    )
    cursor.execute(
        "INSERT INTO NEXOVOLT.NV_NOVEDAD "
        "(NOVEDAD_ID, TIPO, SUJETO, OBLIGACION_ID, REFERENCIA, MOTIVO, "
        "MOTIVO_ELIMINACION_ID, VALORES_ENVIADOS, FECHA_DETECCION, ORIGEN, "
        "ESTADO, USUARIO_ID, USUARIO_NOMBRE) "
        "VALUES (%s, 'CORRECCION', 'OBLIGACION', %s, %s, %s, NULL, %s, "
        "%s, 'MANUAL', 'PENDIENTE', %s, %s)",
        [
            novedad_id,
            obligacion_id,
            numero_obligacion,
            justificacion,
            valores_enviados,
            hoy_bogota(),
            getattr(usuario, "pk", None),
            getattr(usuario, "nombre", None),
        ],
    )
    return novedad_id


def _validar_novedad(cursor, novedad_id, obligacion_id):
    cursor.execute(
        "SELECT TIPO, OBLIGACION_ID FROM NEXOVOLT.NV_NOVEDAD "
        "WHERE NOVEDAD_ID = %s FOR UPDATE",
        [novedad_id],
    )
    row = cursor.fetchone()
    if row is None or row[0] != "CORRECCION" or row[1] != obligacion_id:
        raise NovedadNoValida()


def crear_rectificacion(data, usuario=None):
    campo = data["campo"].strip().lower()
    columna = _CAMPOS_RECTIFICABLES.get(campo)
    if columna is None:
        raise ValueError("El campo no se puede rectificar.")
    valor_db, valor_texto = _validar_valor_corregido(
        campo, data["valor_corregido"]
    )
    justificacion = data["justificacion"].strip()
    if not justificacion:
        raise RectificacionDatoInvalido(
            "justificacion", "Escribe la justificación de la corrección."
        )
    medio = data["medio"]
    if medio not in {"ACTUALIZACION_LINEA", "PROCESO_ESPECIAL"}:
        raise RectificacionDatoInvalido(
            "medio", "Selecciona un medio de rectificación válido."
        )

    obligacion_id = data["obligacion_id"]
    corte_id = data["corte_id"]
    db_columna = columna[0]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ESTADO FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s FOR UPDATE",
                [corte_id],
            )
            corte = cursor.fetchone()
            if corte is None:
                raise CorteNoEncontrado()
            if corte[0] != "ENVIADO":
                raise CorteNoEnviado()

            cursor.execute(
                "SELECT NUMERO_OBLIGACION_TU FROM NEXOVOLT.NV_OBLIGACION "
                "WHERE OBLIGACION_ID = %s",
                [obligacion_id],
            )
            obligacion = cursor.fetchone()
            if obligacion is None:
                raise ObligacionNoEncontrada()
            numero_obligacion = obligacion[0]

            cursor.execute(
                f"SELECT {db_columna} FROM NEXOVOLT.NV_REPORTE_DETALLE "
                "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s FOR UPDATE",
                [corte_id, obligacion_id],
            )
            detalle = cursor.fetchone()
            if detalle is None:
                raise RectificacionDatoInvalido(
                    "corte_id", "La obligación no está en el corte indicado."
                )
            anterior = _valor_anterior(detalle[0])

            novedad_id = data.get("novedad_id")
            if novedad_id is None:
                novedad_id = _crear_novedad_correccion(
                    cursor,
                    obligacion_id,
                    numero_obligacion,
                    campo,
                    anterior,
                    valor_texto,
                    justificacion,
                    usuario,
                )
            else:
                _validar_novedad(cursor, novedad_id, obligacion_id)

            cursor.execute(
                "SELECT NEXOVOLT.SEQ_NV_RECTIFICACION.NEXTVAL FROM DUAL"
            )
            rectificacion_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_RECTIFICACION "
                "(RECTIFICACION_ID, NOVEDAD_ID, OBLIGACION_ID, CORTE_ID, CAMPO, "
                "VALOR_ANTERIOR, VALOR_CORREGIDO, JUSTIFICACION, MEDIO, ESTADO, "
                "USUARIO_ID) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'REGISTRADA', %s)",
                [
                    rectificacion_id,
                    novedad_id,
                    obligacion_id,
                    corte_id,
                    campo,
                    anterior,
                    valor_texto,
                    justificacion,
                    medio,
                    getattr(usuario, "pk", None),
                ],
            )
            cursor.execute(
                f"UPDATE NEXOVOLT.NV_REPORTE_DETALLE SET {db_columna} = %s "
                "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
                [valor_db, corte_id, obligacion_id],
            )

    with tolerar_fallo_bitacora("RECTIFICACION_REGISTRADA"):
        registrar_bitacora(
            "RECTIFICACION_REGISTRADA",
            "NV_RECTIFICACION",
            str(rectificacion_id),
            f"Obligación {numero_obligacion}, campo {campo}, corte {corte_id}",
            usuario=usuario,
        )

    resultado = obtener_rectificacion(rectificacion_id)
    resultado["insumo"] = _formatear_insumo_rectificacion(
        numero_obligacion, campo, valor_texto
    )
    return resultado


def _formatear_insumo_rectificacion(numero_obligacion, campo, valor_corregido):
    return f"{numero_obligacion}|{campo}|{valor_corregido}\r\n"


def confirmar_rectificacion(rectificacion_id, confirmacion_tu, usuario=None):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ESTADO FROM NEXOVOLT.NV_RECTIFICACION "
                "WHERE RECTIFICACION_ID = %s FOR UPDATE",
                [rectificacion_id],
            )
            row = cursor.fetchone()
            if row is None:
                raise RectificacionNoEncontrada()
            if row[0] == "CONFIRMADA":
                raise RectificacionYaConfirmada()
            cursor.execute(
                "UPDATE NEXOVOLT.NV_RECTIFICACION "
                "SET ESTADO = 'CONFIRMADA', CONFIRMACION_TU = %s "
                "WHERE RECTIFICACION_ID = %s",
                [confirmacion_tu, rectificacion_id],
            )

    with tolerar_fallo_bitacora("RECTIFICACION_CONFIRMADA"):
        registrar_bitacora(
            "RECTIFICACION_CONFIRMADA",
            "NV_RECTIFICACION",
            str(rectificacion_id),
            "Confirmación de TransUnion registrada.",
            usuario=usuario,
        )
    return obtener_rectificacion(rectificacion_id)
