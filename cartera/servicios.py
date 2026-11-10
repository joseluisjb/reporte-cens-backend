import re
from datetime import date
from django.db import connection, transaction, IntegrityError

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import ahora_para_bd, enmascarar_identificacion, fecha_str, hoy_bogota
from usuarios.models import Usuario


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


class NumeroDuplicado(Exception):
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


def _persistir_corte(
    corte_id_existente, fecha_corte, grupo_id, grupo_nombre, conceptos_usados, usuario_id=None
):
    if corte_id_existente is None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT NEXOVOLT.SEQ_NV_CORTE.NEXTVAL FROM DUAL")
            corte_id = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_CORTE "
                "(CORTE_ID, FECHA_CORTE, TIPO_REPORTE, ESTADO, FECHA_GENERACION, "
                "USUARIO_ID, TOTAL_REGISTROS, GRUPO_ID, GRUPO_NOMBRE, CONCEPTOS_USADOS) "
                "VALUES (%s, %s, '01', 'BORRADOR', %s, %s, 0, %s, %s, %s)",
                [corte_id, fecha_corte, ahora_para_bd(), usuario_id, grupo_id, grupo_nombre,
                 conceptos_usados],
            )
        return corte_id
    else:
        # Regenerar el borrador lo deja a nombre de quien lo regeneró.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_CORTE "
                "SET FECHA_GENERACION = %s, TOTAL_REGISTROS = 0, USUARIO_ID = %s, "
                "GRUPO_ID = %s, GRUPO_NOMBRE = %s, CONCEPTOS_USADOS = %s "
                "WHERE CORTE_ID = %s",
                [ahora_para_bd(), usuario_id, grupo_id, grupo_nombre, conceptos_usados,
                 corte_id_existente],
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
    try:
        with connection.cursor() as cursor:
            cursor.executemany(sql_insert, [(r[0], r[1], r[2], r[3]) for r in filas])
    except IntegrityError:
        raise NumeroDuplicado()


def _insertar_reporte_detalle():
    sql = (
        "INSERT INTO NEXOVOLT.NV_REPORTE_DETALLE ("
        "CORTE_ID, OBLIGACION_ID, TIPO_ID_TU, NUMERO_IDENTIFICACION, NOMBRE_TITULAR, "
        "FECHA_LIMITE_PAGO, CODIGO_SUCURSAL, CALIDAD, TIPO_CARTERA, ESTADO_TU, EDAD_MORA, "
        "FECHA_INICIO, PERIODICIDAD, CUOTAS_MORA, VALOR_INICIAL, VALOR_MORA, VALOR_SALDO, "
        "VALOR_CUOTA, LINEA_CREDITO, OBLIGACION_REFINANCIADA, CORREO, CELULAR, "
        "VALOR_REAL_PAGADO, ESTADO_SAC, N_CREDITOS, DIAS_MORA, ORIGEN_DIAS_MORA, FECHA_ULTIMO_PAGO, "
        "CADUCADO, ATRASOS_PERMITIDOS"
        ") SELECT "
        "CORTE_ID, OBLIGACION_ID, TIPO_ID_TU, NUMERO_IDENTIFICACION, NOMBRE_TITULAR, "
        "FECHA_LIMITE_PAGO, CODIGO_SUCURSAL, CALIDAD, TIPO_CARTERA, ESTADO_TU, EDAD_MORA, "
        "FECHA_INICIO, PERIODICIDAD, CUOTAS_MORA, VALOR_INICIAL, VALOR_MORA, VALOR_SALDO, "
        "VALOR_CUOTA, LINEA_CREDITO, OBLIGACION_REFINANCIADA, CORREO, CELULAR, "
        "VALOR_REAL_PAGADO, ESTADO_SAC, N_CREDITOS, DIAS_MORA, ORIGEN_DIAS_MORA, FECHA_ULTIMO_PAGO, "
        "NVL(CADUCADO, 'N'), ATRASOS_PERMITIDOS "
        "FROM NEXOVOLT.V_CALCULO_CORTE WHERE INCLUIR = 'S'"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)


def _finalizar_y_resumir(corte_id, fecha_corte, grupo_id, grupo_nombre, ejecutada_por=None):
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
        "ejecutada_por":    ejecutada_por,
    }


_SQL_RESUMEN = (
    "SELECT c.CORTE_ID, c.FECHA_CORTE, c.ESTADO, c.FECHA_GENERACION, "
    "NVL(c.TOTAL_REGISTROS, 0), c.GRUPO_ID, c.GRUPO_NOMBRE, "
    "NVL(SUM(d.VALOR_SALDO), 0), c.USUARIO_ID "
    "FROM NEXOVOLT.NV_CORTE c "
    "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE d ON c.CORTE_ID = d.CORTE_ID "
)
_SQL_RESUMEN_GROUP = (
    " GROUP BY c.CORTE_ID, c.FECHA_CORTE, c.ESTADO, c.FECHA_GENERACION, "
    "c.TOTAL_REGISTROS, c.GRUPO_ID, c.GRUPO_NOMBRE, c.USUARIO_ID"
)


def _nombres_de_usuarios(filas):
    # El nombre se toma de la tabla de usuarios de Django (no hay columna de nombre en NV_CORTE).
    ids = {fila[8] for fila in filas if fila[8] is not None}
    if not ids:
        return {}
    return dict(Usuario.objects.filter(pk__in=ids).values_list("pk", "nombre"))


def _fila_a_resumen(row, nombres=None):
    corte_id, fecha_corte, estado, fecha_gen, total, grupo_id, grupo_nombre, saldo, usuario_id = row
    return {
        "id":               corte_id,
        "fecha_corte":      fecha_corte,
        "fecha_ejecucion":  fecha_gen,
        "grupo":            {"id": grupo_id, "nombre": grupo_nombre} if grupo_id is not None else None,
        "obligaciones":     total or 0,
        "saldo_consolidado": int(saldo),
        "estado":           estado,
        # null si lo generó el proceso mensual o si el corte es anterior a la fila 42.
        "ejecutada_por":    (nombres or {}).get(usuario_id),
    }


# ── API pública ───────────────────────────────────────────────────────────────

def generar_corte(fecha_corte, grupo_id=None, usuario=None):
    # `usuario` es el de la sesión; el proceso mensual (RF9) no lo pasa y el corte queda sin autor.
    usuario_id = getattr(usuario, "pk", None)
    ejecutada_por = getattr(usuario, "nombre", None) if usuario_id is not None else None
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
            corte_id_existente, fecha_corte, grupo_id, grupo_nombre, conceptos_usados, usuario_id
        )

        _insertar_obligaciones_nuevas()
        _insertar_reporte_detalle()
        return _finalizar_y_resumir(corte_id, fecha_corte, grupo_id, grupo_nombre, ejecutada_por)


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
    nombres = _nombres_de_usuarios(rows)
    return [_fila_a_resumen(r, nombres) for r in rows]


def obtener_corte(corte_id):
    sql = (
        _SQL_RESUMEN
        + "WHERE c.CORTE_ID = %s"
        + _SQL_RESUMEN_GROUP
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [corte_id])
        row = cursor.fetchone()
    return _fila_a_resumen(row, _nombres_de_usuarios([row])) if row else None


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
    return _fila_a_resumen(row, _nombres_de_usuarios([row])) if row else None


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
            "SELECT COUNT(*) FROM NEXOVOLT.NV_CICLO WHERE CORTE_ID = %s", [corte_id]
        )
        tiene_ciclo = cursor.fetchone()[0] > 0

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
    if not tiene_ciclo:
        correctivos.insert(0, {
            "regla": "ACTUALIZACION_MENSUAL",
            "mensaje": "Falta ejecutar la actualización mensual de este corte.",
        })
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
        # RF13/RF16: marcar cierre definitivo para Saldada (02) y Cartera Recuperada (07)
        cursor.execute(
            "UPDATE NEXOVOLT.NV_OBLIGACION "
            "SET CIERRE_DEFINITIVO = 'S', FECHA_CIERRE = %s "
            "WHERE OBLIGACION_ID IN ("
            "  SELECT rd.OBLIGACION_ID FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "  WHERE rd.CORTE_ID = %s AND rd.ESTADO_TU IN ('02', '07')"
            ")",
            [fecha_corte_corte, corte_id],
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


# ── RF54 — Excepciones ────────────────────────────────────────────────────────

class ArchivoNoEncontrado(Exception):
    pass


class ArchivoNoEnviado(Exception):
    pass


class SinResultados(Exception):
    pass


class ArchivoDeOtroCorte(Exception):
    def __init__(self, nombre, fecha_en_archivo, fecha_corte):
        self.nombre = nombre
        self.fecha_en_archivo = fecha_en_archivo
        self.fecha_corte = fecha_corte
        super().__init__(
            f"El archivo {nombre} es del corte "
            f"{fecha_en_archivo.strftime('%d/%m/%Y')}, "
            f"no del {fecha_corte.strftime('%d/%m/%Y')}."
        )


class EstructuraInvalida(Exception):
    def __init__(self, detalle):
        self.detalle = detalle
        super().__init__(detalle)


# ── RF54 — Helpers de parseo ──────────────────────────────────────────────────

# Patrones del Manual p. 43. Orden: más específico primero.
_PATRONES_TIPO_ARCHIVO = [
    (re.compile(r"^953_Detalle_Inco_", re.IGNORECASE), "DETALLE_953"),
    (re.compile(r"^Detalle_Inco_.+_Correctivas_", re.IGNORECASE), "CORRECTIVAS"),
    (re.compile(r"^Detalle_Inco_.+_Alertas_", re.IGNORECASE), "ALERTAS"),
    (re.compile(r"^Detalle_Inco_.+_Especiales_", re.IGNORECASE), "ESPECIALES"),
    (re.compile(r"^Esta_Inco_", re.IGNORECASE), "ESTADISTICOS"),
    (re.compile(r"^est\.", re.IGNORECASE), "ESTADISTICOS"),
    (re.compile(r"^norep\.", re.IGNORECASE), "NOREP"),
    (re.compile(r"^radicacion_", re.IGNORECASE), "RADICACION"),
    (re.compile(r"^cierre_reclamo_", re.IGNORECASE), "CIERRE_RECLAMO"),
]


def _detectar_tipo_archivo(nombre):
    for patron, tipo in _PATRONES_TIPO_ARCHIVO:
        if patron.match(nombre):
            return tipo
    raise EstructuraInvalida(
        f"El archivo '{nombre}' no tiene un nombre reconocido (Manual, p. 43)."
    )


def _extraer_fecha_archivo(nombre):
    """Extrae la fecha AAAAMMDD del nombre. Acepta los formatos del Manual p. 43."""
    for m in re.finditer(r"(?<!\d)(\d{8})(?!\d)", nombre):
        fecha_s = m.group(1)
        try:
            return date(int(fecha_s[:4]), int(fecha_s[4:6]), int(fecha_s[6:]))
        except ValueError:
            continue
    return None


def _validar_fecha_archivo(nombre, fecha_corte):
    fecha_en_archivo = _extraer_fecha_archivo(nombre)
    if fecha_en_archivo is None:
        raise EstructuraInvalida(
            f"El archivo '{nombre}' no contiene una fecha válida en el nombre."
        )
    if fecha_en_archivo != fecha_corte:
        raise ArchivoDeOtroCorte(nombre, fecha_en_archivo, fecha_corte)


def _parsear_lineas_inconsistencia(nombre, lineas, tipo):
    """CORRECTIVAS y ALERTAS: cada línea es NUMERO_OBLIGACION|CODIGO|DESCRIPCION."""
    result = []
    for i, linea in enumerate(lineas, 1):
        partes = linea.split("|")
        if len(partes) < 3:
            raise EstructuraInvalida(
                f"El archivo {nombre} no tiene la estructura esperada "
                f"(línea {i}: se esperaban al menos 3 campos separados por |)."
            )
        result.append({
            "numero_obligacion": partes[0].strip(),
            "codigo": partes[1].strip(),
            "descripcion": "|".join(p.strip() for p in partes[2:]),
            "tipo": tipo,
        })
    return result


def _parsear_norep(lineas):
    """NOREP: cada línea es NUMERO_OBLIGACION."""
    return [
        {
            "numero_obligacion": l.strip(),
            "codigo": "R",
            "descripcion": "Obligación no reportada",
            "tipo": "NO_REPORTADA",
        }
        for l in lineas if l.strip()
    ]


def _parsear_archivo(nombre, contenido_bytes):
    """Returns (tipo, inconsistencias, n_filas)."""
    tipo = _detectar_tipo_archivo(nombre)
    try:
        texto = contenido_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            texto = contenido_bytes.decode("cp1252")
        except Exception:
            raise EstructuraInvalida(
                f"El archivo '{nombre}' tiene una codificación no compatible."
            )

    lineas = [l for l in texto.splitlines() if l.strip()]
    n_filas = len(lineas)

    if tipo == "CORRECTIVAS":
        inconsistencias = _parsear_lineas_inconsistencia(nombre, lineas, "CORRECTIVA")
    elif tipo == "ALERTAS":
        inconsistencias = _parsear_lineas_inconsistencia(nombre, lineas, "INFORMATIVA")
    elif tipo == "NOREP":
        inconsistencias = _parsear_norep(lineas)
    else:
        inconsistencias = []

    return tipo, inconsistencias, n_filas


def _resolver_obligacion_ids(numeros, corte_id):
    """Busca en lote los OBLIGACION_ID para un conjunto de NUMERO_OBLIGACION_TU del corte."""
    if not numeros:
        return {}
    placeholders = ",".join(["%s"] * len(numeros))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT o.NUMERO_OBLIGACION_TU, o.OBLIGACION_ID "
            "FROM NEXOVOLT.NV_OBLIGACION o "
            "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            f"WHERE rd.CORTE_ID = %s AND o.NUMERO_OBLIGACION_TU IN ({placeholders})",
            [corte_id] + list(numeros),
        )
        rows = cursor.fetchall()
    return {row[0]: row[1] for row in rows}


def _construir_resultado(archivo_id, corte_id, fecha_corte, estado_corte, usuario_id,
                          fecha_carga, archivos_cargados, all_inconsistencias, recibidos):
    cargado_por = None
    if usuario_id is not None:
        nombres = dict(Usuario.objects.filter(pk=usuario_id).values_list("pk", "nombre"))
        cargado_por = nombres.get(usuario_id)

    no_reportadas = sum(1 for i in all_inconsistencias if i["tipo"] == "NO_REPORTADA")
    cargados = max(0, recibidos - no_reportadas)
    con_inconsistencias = len(all_inconsistencias)

    return {
        "archivo_id": archivo_id,
        "corte_id": corte_id,
        "fecha_corte": fecha_corte,
        "fecha_carga": fecha_carga,
        "cargado_por": cargado_por,
        "estado_corte": estado_corte,
        "archivos_cargados": archivos_cargados,
        "recibidos": recibidos,
        "cargados": cargados,
        "con_inconsistencias": con_inconsistencias,
        "no_reportadas": no_reportadas,
        "inconsistencias": all_inconsistencias,
    }


# ── RF54 — API pública ────────────────────────────────────────────────────────

def cargar_resultados(archivo_id, archivos_subidos, usuario):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.CORTE_ID, c.FECHA_CORTE, c.ESTADO, a.ENVIADO "
            "FROM NEXOVOLT.NV_ARCHIVO a "
            "JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = a.CORTE_ID "
            "WHERE a.ARCHIVO_ID = %s",
            [archivo_id],
        )
        row = cursor.fetchone()

    if row is None:
        raise ArchivoNoEncontrado()

    corte_id, fecha_corte, _estado_actual, enviado = row
    if hasattr(fecha_corte, "date"):
        fecha_corte = fecha_corte.date()

    if enviado != "S":
        raise ArchivoNoEnviado()

    # Parsear y validar todos los archivos antes de escribir nada.
    parsed = []
    for archivo in archivos_subidos:
        nombre = archivo.name
        contenido = archivo.read()
        _validar_fecha_archivo(nombre, fecha_corte)
        tipo, inconsistencias, n_filas = _parsear_archivo(nombre, contenido)
        parsed.append((nombre, tipo, inconsistencias, n_filas))

    usuario_id = getattr(usuario, "pk", None)
    fecha_carga = ahora_para_bd()

    with transaction.atomic():
        all_inconsistencias = []
        archivos_cargados_result = []

        for nombre, tipo, inconsistencias, n_filas in parsed:
            with connection.cursor() as cursor:
                cursor.execute("SELECT NEXOVOLT.SEQ_NV_CARGUE_RESULTADO.NEXTVAL FROM DUAL")
                cargue_id = cursor.fetchone()[0]

            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO NEXOVOLT.NV_CARGUE_RESULTADO "
                    "(CARGUE_ID, ARCHIVO_ID, CORTE_ID, TIPO_ARCHIVO, NOMBRE_ARCHIVO, "
                    "FECHA_CARGA, USUARIO_ID, N_FILAS) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    [cargue_id, archivo_id, corte_id, tipo, nombre,
                     fecha_carga, usuario_id, n_filas],
                )

            archivos_cargados_result.append({
                "nombre_archivo": nombre,
                "tipo_archivo": tipo,
                "n_filas": n_filas,
            })

            if inconsistencias:
                numeros = {inc["numero_obligacion"] for inc in inconsistencias}
                id_map = _resolver_obligacion_ids(numeros, corte_id)

                for inc in inconsistencias:
                    obligacion_id = id_map.get(inc["numero_obligacion"])
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT NEXOVOLT.SEQ_NV_CARGUE_INCONSISTENCIA.NEXTVAL FROM DUAL"
                        )
                        inc_id = cursor.fetchone()[0]
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO NEXOVOLT.NV_CARGUE_INCONSISTENCIA "
                            "(ID, CARGUE_ID, CORTE_ID, OBLIGACION_ID, NUMERO_OBLIGACION_TU, "
                            "CODIGO, DESCRIPCION, TIPO) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            [inc_id, cargue_id, corte_id, obligacion_id,
                             inc["numero_obligacion"], inc["codigo"],
                             inc["descripcion"], inc["tipo"]],
                        )
                    all_inconsistencias.append({
                        "obligacion_id": obligacion_id,
                        "numero_obligacion": inc["numero_obligacion"],
                        "tipo": inc["tipo"],
                        "codigo": inc["codigo"],
                        "descripcion": inc["descripcion"],
                    })

        # Consulta todas las correctivas de este archivo (incluye uploads previos)
        # para que un segundo POST sin correctivas no revierta ENVIADO_CON_INCONSISTENCIAS.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) "
                "FROM NEXOVOLT.NV_CARGUE_INCONSISTENCIA i "
                "JOIN NEXOVOLT.NV_CARGUE_RESULTADO cr ON cr.CARGUE_ID = i.CARGUE_ID "
                "WHERE cr.ARCHIVO_ID = %s AND i.TIPO = 'CORRECTIVA'",
                [archivo_id],
            )
            tiene_correctivas = cursor.fetchone()[0] > 0
        nuevo_estado = "ENVIADO_CON_INCONSISTENCIAS" if tiene_correctivas else "ENVIADO"

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_CORTE SET ESTADO = %s WHERE CORTE_ID = %s",
                [nuevo_estado, corte_id],
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s",
                [corte_id],
            )
            recibidos = cursor.fetchone()[0]

    with tolerar_fallo_bitacora("CARGUE_RESULTADOS"):
        registrar_bitacora(
            "CARGUE_RESULTADOS", "NV_CARGUE_RESULTADO", archivo_id,
            f"Archivos: {len(parsed)}, Inconsistencias: {len(all_inconsistencias)}",
        )

    return _construir_resultado(
        archivo_id, corte_id, fecha_corte, nuevo_estado, usuario_id,
        fecha_carga, archivos_cargados_result, all_inconsistencias, recibidos,
    )


def obtener_resultados(archivo_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.CORTE_ID, c.FECHA_CORTE, c.ESTADO "
            "FROM NEXOVOLT.NV_ARCHIVO a "
            "JOIN NEXOVOLT.NV_CORTE c ON c.CORTE_ID = a.CORTE_ID "
            "WHERE a.ARCHIVO_ID = %s",
            [archivo_id],
        )
        row = cursor.fetchone()

    if row is None:
        raise ArchivoNoEncontrado()

    corte_id, fecha_corte, estado_corte = row
    if hasattr(fecha_corte, "date"):
        fecha_corte = fecha_corte.date()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT cr.TIPO_ARCHIVO, cr.NOMBRE_ARCHIVO, cr.N_FILAS, "
            "cr.FECHA_CARGA, cr.USUARIO_ID "
            "FROM NEXOVOLT.NV_CARGUE_RESULTADO cr "
            "WHERE cr.ARCHIVO_ID = %s "
            "ORDER BY cr.CARGUE_ID",
            [archivo_id],
        )
        cargue_rows = cursor.fetchall()

    if not cargue_rows:
        raise SinResultados()

    archivos_cargados = [
        {"nombre_archivo": r[1], "tipo_archivo": r[0], "n_filas": r[2]}
        for r in cargue_rows
    ]
    fecha_carga = cargue_rows[-1][3]
    usuario_id = cargue_rows[-1][4]

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.OBLIGACION_ID, i.NUMERO_OBLIGACION_TU, i.TIPO, i.CODIGO, i.DESCRIPCION "
            "FROM NEXOVOLT.NV_CARGUE_INCONSISTENCIA i "
            "JOIN NEXOVOLT.NV_CARGUE_RESULTADO cr ON cr.CARGUE_ID = i.CARGUE_ID "
            "WHERE cr.ARCHIVO_ID = %s "
            "ORDER BY i.ID",
            [archivo_id],
        )
        inc_rows = cursor.fetchall()

    all_inconsistencias = [
        {
            "obligacion_id": r[0],
            "numero_obligacion": r[1],
            "tipo": r[2],
            "codigo": r[3],
            "descripcion": r[4],
        }
        for r in inc_rows
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = %s",
            [corte_id],
        )
        recibidos = cursor.fetchone()[0]

    return _construir_resultado(
        archivo_id, corte_id, fecha_corte, estado_corte, usuario_id,
        fecha_carga, archivos_cargados, all_inconsistencias, recibidos,
    )
