from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import ahora_para_bd, enmascarar_identificacion, fecha_str, hoy_bogota


# ── Excepciones ───────────────────────────────────────────────────────────────

class FechaInvalida(Exception):
    pass


class GrupoNoEncontrado(Exception):
    pass


class GrupoInactivo(Exception):
    pass


class CorteEnEstadoFijo(Exception):
    pass


class BorradorOtraFecha(Exception):
    def __init__(self, fecha, corte_id=None):
        self.fecha = fecha
        self.corte_id = corte_id
        super().__init__(f"Ya existe un corte en BORRADOR con fecha {fecha}.")


class CorteNoEncontrado(Exception):
    pass


class CorteNoEsBorrador(Exception):
    pass


class CorteNoEsValidado(Exception):
    pass


class CorteConErroresCorrectivos(Exception):
    def __init__(self, errores):
        self.errores = errores
        super().__init__("El corte tiene errores correctivos que deben resolverse.")


class FechaAnteriorAlUltimoEnviado(Exception):
    pass


# ── Helpers internos ──────────────────────────────────────────────────────────

def _todos_los_conceptos_reportables():
    sql = (
        "SELECT CODIGO_CONCEPTO FROM NEXOVOLT.NV_CONCEPTO_REPORTABLE "
        "WHERE REPORTABLE = 'S' ORDER BY CODIGO_CONCEPTO"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
    return ",".join(str(r[0]) for r in rows)


def _validar_grupo(grupo_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT NOMBRE, ACTIVO FROM NEXOVOLT.NV_GRUPO_CONCEPTO WHERE GRUPO_ID = %s",
            [grupo_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise GrupoNoEncontrado()
    nombre, activo = row
    if activo != "S":
        raise GrupoInactivo()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CODIGO_CONCEPTO FROM NEXOVOLT.NV_GRUPO_CONCEPTO_DET "
            "WHERE GRUPO_ID = %s ORDER BY CODIGO_CONCEPTO",
            [grupo_id],
        )
        rows = cursor.fetchall()
    conceptos_usados = ",".join(str(r[0]) for r in rows)
    return nombre, conceptos_usados


def _verificar_corte_existente(fecha_corte):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CORTE_ID, ESTADO FROM NEXOVOLT.NV_CORTE WHERE FECHA_CORTE = %s",
            [fecha_corte],
        )
        row = cursor.fetchone()
    if row is not None:
        corte_id, estado = row
        if estado == "BORRADOR":
            return corte_id, True
        raise CorteEnEstadoFijo()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CORTE_ID, FECHA_CORTE FROM NEXOVOLT.NV_CORTE "
            "WHERE ESTADO = 'BORRADOR' AND ROWNUM = 1"
        )
        row = cursor.fetchone()
    if row is not None:
        raise BorradorOtraFecha(row[1], corte_id=row[0])

    return None, False


def _limpiar_corte(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s", [corte_id]
        )
        cursor.execute(
            "DELETE FROM NEXOVOLT.NV_INCONSISTENCIA WHERE CORTE_ID = %s", [corte_id]
        )


def _persistir_corte(corte_id_existente, fecha_corte, grupo_id, grupo_nombre, conceptos_usados):
    if corte_id_existente is None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT NEXOVOLT.SEQ_NV_CORTE.NEXTVAL FROM DUAL")
            corte_id = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_CORTE "
                "(CORTE_ID, FECHA_CORTE, TIPO_REPORTE, ESTADO, FECHA_GENERACION, "
                "USUARIO_ID, TOTAL_REGISTROS, GRUPO_ID, GRUPO_NOMBRE, CONCEPTOS_USADOS) "
                "VALUES (%s, %s, '01', 'BORRADOR', %s, NULL, 0, %s, %s, %s)",
                [corte_id, fecha_corte, ahora_para_bd(), grupo_id, grupo_nombre, conceptos_usados],
            )
        return corte_id
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_CORTE "
                "SET FECHA_GENERACION = %s, TOTAL_REGISTROS = 0, "
                "GRUPO_ID = %s, GRUPO_NOMBRE = %s, CONCEPTOS_USADOS = %s "
                "WHERE CORTE_ID = %s",
                [ahora_para_bd(), grupo_id, grupo_nombre, conceptos_usados, corte_id_existente],
            )
        return corte_id_existente


def _insertar_obligaciones_nuevas():
    sql_select = (
        "SELECT CLIENTE_ID, NUMERO_PROCESO, NUMERO_OBLIGACION_PROPUESTO, FECHA_INICIO "
        "FROM NEXOVOLT.V_CALCULO_CORTE WHERE INCLUIR = 'S' AND OBLIGACION_ID IS NULL"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql_select)
        filas = cursor.fetchall()
    if not filas:
        return
    sql_insert = (
        "INSERT INTO NEXOVOLT.NV_OBLIGACION "
        "(OBLIGACION_ID, CLIENTE_ID, NUMERO_PROCESO, NUMERO_OBLIGACION_TU, FECHA_INICIO) "
        "VALUES (NEXOVOLT.SEQ_NV_OBLIGACION.NEXTVAL, %s, %s, %s, %s)"
    )
    with connection.cursor() as cursor:
        cursor.executemany(sql_insert, [(r[0], r[1], r[2], r[3]) for r in filas])


def _insertar_reporte_detalle():
    sql = (
        "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE ("
        "CORTE_ID, OBLIGACION_ID, TIPO_ID_TU, NUMERO_IDENTIFICACION, NOMBRE_TITULAR, "
        "FECHA_LIMITE_PAGO, CODIGO_SUCURSAL, CALIDAD, TIPO_CARTERA, ESTADO_TU, EDAD_MORA, "
        "FECHA_INICIO, PERIODICIDAD, CUOTAS_MORA, VALOR_INICIAL, VALOR_MORA, VALOR_SALDO, "
        "VALOR_CUOTA, LINEA_CREDITO, OBLIGACION_REFINANCIADA, CORREO, CELULAR, "
        "VALOR_REAL_PAGADO, ESTADO_SAC, N_CREDITOS, DIAS_MORA, ORIGEN_DIAS_MORA, FECHA_ULTIMO_PAGO"
        ") SELECT "
        "CORTE_ID, OBLIGACION_ID, TIPO_ID_TU, NUMERO_IDENTIFICACION, NOMBRE_TITULAR, "
        "FECHA_LIMITE_PAGO, CODIGO_SUCURSAL, CALIDAD, TIPO_CARTERA, ESTADO_TU, EDAD_MORA, "
        "FECHA_INICIO, PERIODICIDAD, CUOTAS_MORA, VALOR_INICIAL, VALOR_MORA, VALOR_SALDO, "
        "VALOR_CUOTA, LINEA_CREDITO, OBLIGACION_REFINANCIADA, CORREO, CELULAR, "
        "VALOR_REAL_PAGADO, ESTADO_SAC, N_CREDITOS, DIAS_MORA, ORIGEN_DIAS_MORA, FECHA_ULTIMO_PAGO "
        "FROM NEXOVOLT.V_CALCULO_CORTE WHERE INCLUIR = 'S'"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)


def _finalizar_y_resumir(corte_id, fecha_corte, grupo_id, grupo_nombre):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_CORTE "
            "SET TOTAL_REGISTROS = (SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s) "
            "WHERE CORTE_ID = %s",
            [corte_id, corte_id],
        )
        cursor.execute(
            "SELECT TOTAL_REGISTROS, FECHA_GENERACION FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s",
            [corte_id],
        )
        total, fecha_gen = cursor.fetchone()
        cursor.execute(
            "SELECT NVL(SUM(VALOR_SALDO), 0) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s",
            [corte_id],
        )
        saldo = cursor.fetchone()[0]
    return {
        "id":               corte_id,
        "fecha_corte":      fecha_corte,
        "fecha_ejecucion":  fecha_gen,
        "grupo":            {"id": grupo_id, "nombre": grupo_nombre} if grupo_id is not None else None,
        "obligaciones":     total or 0,
        "saldo_consolidado": int(saldo),
        "estado":           "BORRADOR",
        "ejecutada_por":    None,
    }


_SQL_RESUMEN = (
    "SELECT c.CORTE_ID, c.FECHA_CORTE, c.ESTADO, c.FECHA_GENERACION, "
    "NVL(c.TOTAL_REGISTROS, 0), c.GRUPO_ID, c.GRUPO_NOMBRE, "
    "NVL(SUM(d.VALOR_SALDO), 0) "
    "FROM NEXOVOLT.NV_CORTE c "
    "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE d ON c.CORTE_ID = d.CORTE_ID "
)
_SQL_RESUMEN_GROUP = (
    " GROUP BY c.CORTE_ID, c.FECHA_CORTE, c.ESTADO, c.FECHA_GENERACION, "
    "c.TOTAL_REGISTROS, c.GRUPO_ID, c.GRUPO_NOMBRE"
)


def _fila_a_resumen(row):
    corte_id, fecha_corte, estado, fecha_gen, total, grupo_id, grupo_nombre, saldo = row
    return {
        "id":               corte_id,
        "fecha_corte":      fecha_corte,
        "fecha_ejecucion":  fecha_gen,
        "grupo":            {"id": grupo_id, "nombre": grupo_nombre} if grupo_id is not None else None,
        "obligaciones":     total or 0,
        "saldo_consolidado": int(saldo),
        "estado":           estado,
        "ejecutada_por":    None,
    }


# ── API pública ───────────────────────────────────────────────────────────────

def generar_corte(fecha_corte, grupo_id=None):
    with transaction.atomic():
        if fecha_corte > hoy_bogota():
            raise FechaInvalida("La fecha de corte no puede ser futura.")

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT MAX(FECHA_CORTE) FROM NEXOVOLT.NV_CORTE WHERE ESTADO = 'ENVIADO'"
            )
            row = cursor.fetchone()
        if row and row[0] is not None:
            ultimo = row[0]
            if hasattr(ultimo, "date"):
                ultimo = ultimo.date()
            if fecha_corte <= ultimo:
                raise FechaAnteriorAlUltimoEnviado()

        if grupo_id is not None:
            grupo_nombre, conceptos_usados = _validar_grupo(grupo_id)
        else:
            grupo_nombre = None
            conceptos_usados = _todos_los_conceptos_reportables()

        corte_id_existente, reemplazar = _verificar_corte_existente(fecha_corte)

        if reemplazar:
            _limpiar_corte(corte_id_existente)

        corte_id = _persistir_corte(
            corte_id_existente, fecha_corte, grupo_id, grupo_nombre, conceptos_usados
        )

        _insertar_obligaciones_nuevas()
        _insertar_reporte_detalle()
        return _finalizar_y_resumir(corte_id, fecha_corte, grupo_id, grupo_nombre)


def listar_cortes():
    sql = (
        _SQL_RESUMEN
        + "WHERE c.ESTADO != 'ANULADO'"
        + _SQL_RESUMEN_GROUP
        + " ORDER BY c.FECHA_GENERACION DESC"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
    return [_fila_a_resumen(r) for r in rows]


def obtener_corte(corte_id):
    sql = (
        _SQL_RESUMEN
        + "WHERE c.CORTE_ID = %s"
        + _SQL_RESUMEN_GROUP
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [corte_id])
        row = cursor.fetchone()
    return _fila_a_resumen(row) if row else None


def obtener_ultimo_corte():
    sql = (
        "SELECT * FROM ("
        + _SQL_RESUMEN
        + "WHERE c.ESTADO != 'ANULADO'"
        + _SQL_RESUMEN_GROUP
        + " ORDER BY FECHA_GENERACION DESC"
        + ") WHERE ROWNUM = 1"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
    return _fila_a_resumen(row) if row else None


def listar_obligaciones(corte_id, limite=20, desplazamiento=0):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s", [corte_id]
        )
        if cursor.fetchone()[0] == 0:
            raise CorteNoEncontrado()

        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s",
            [corte_id],
        )
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT o.NUMERO_OBLIGACION_TU, rd.NOMBRE_TITULAR, rd.NUMERO_IDENTIFICACION, "
            "rd.ESTADO_TU, rd.EDAD_MORA, rd.DIAS_MORA, rd.CUOTAS_MORA, "
            "rd.VALOR_MORA, rd.VALOR_SALDO, rd.N_CREDITOS "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            "WHERE rd.CORTE_ID = %s "
            "ORDER BY rd.OBLIGACION_ID "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            [corte_id, desplazamiento, limite],
        )
        filas = cursor.fetchall()

    resultados = [
        {
            "numero_obligacion":    row[0],
            "nombre_titular":       row[1],
            "numero_identificacion": enmascarar_identificacion(row[2]),
            "estado_tu":            row[3],
            "edad_mora":            row[4],
            "dias_mora":            row[5],
            "cuotas_mora":          row[6],
            "valor_mora":           int(row[7]) if row[7] is not None else None,
            "valor_saldo":          int(row[8]) if row[8] is not None else None,
            "n_creditos":           row[9],
        }
        for row in filas
    ]
    return {"total": total, "resultados": resultados}


def validar_corte(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ESTADO FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s", [corte_id]
        )
        row = cursor.fetchone()
    if row is None:
        raise CorteNoEncontrado()
    if row[0] != "BORRADOR":
        raise CorteNoEsBorrador()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT REGLA, SEVERIDAD, MENSAJE FROM NEXOVOLT.V_VALIDACION_CORTE "
            "WHERE CORTE_ID = %s",
            [corte_id],
        )
        filas = cursor.fetchall()

    correctivos = [
        {"regla": r[0], "mensaje": r[2]} for r in filas if r[1] == "CORRECTIVA"
    ]
    if correctivos:
        raise CorteConErroresCorrectivos(correctivos)

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_CORTE SET ESTADO = 'VALIDADO' WHERE CORTE_ID = %s",
            [corte_id],
        )

    advertencias = [
        {"regla": r[0], "mensaje": r[2]} for r in filas if r[1] == "INFORMATIVA"
    ]
    return {"corte": obtener_corte(corte_id), "advertencias": advertencias}


def registrar_envio(corte_id, fecha_envio=None):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ESTADO, FECHA_CORTE FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s",
            [corte_id],
        )
        row = cursor.fetchone()
    if row is None:
        raise CorteNoEncontrado()

    estado = row[0]
    fecha_corte_corte = row[1]
    if hasattr(fecha_corte_corte, "date"):
        fecha_corte_corte = fecha_corte_corte.date()

    if fecha_envio is None:
        fecha_envio = hoy_bogota()
    if fecha_envio > hoy_bogota():
        raise FechaInvalida("La fecha de envío no puede ser futura.")
    if fecha_envio < fecha_corte_corte:
        raise FechaInvalida("La fecha de envío no puede ser anterior a la fecha de corte.")

    if estado != "VALIDADO":
        raise CorteNoEsValidado()

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_CORTE SET ESTADO = 'ENVIADO', FECHA_ENVIO = %s "
            "WHERE CORTE_ID = %s",
            [fecha_envio, corte_id],
        )

    return obtener_corte(corte_id)


def eliminar_borrador(corte_id):
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ESTADO, FECHA_CORTE, GRUPO_NOMBRE "
                "FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s",
                [corte_id],
            )
            row = cursor.fetchone()
        if row is None:
            raise CorteNoEncontrado()
        if row[0] != "BORRADOR":
            raise CorteNoEsBorrador()

        grupo_nombre = row[2] or "todos"
        detalle = f"Fecha: {fecha_str(row[1])}, Grupo: {grupo_nombre}"

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s", [corte_id]
            )
            cursor.execute(
                "DELETE FROM NEXOVOLT.NV_INCONSISTENCIA WHERE CORTE_ID = %s", [corte_id]
            )
            cursor.execute(
                "DELETE FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s", [corte_id]
            )
        with tolerar_fallo_bitacora("ELIMINACION_BORRADOR"):
            registrar_bitacora("ELIMINACION_BORRADOR", "NV_CORTE", corte_id, detalle)
