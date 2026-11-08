from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import ahora_para_bd, timestamp_str
from usuarios.models import Usuario


# ── Excepciones ───────────────────────────────────────────────────────────────

class CorteBorradorNoEncontrado(Exception):
    pass


class FechaCorteAnterior(Exception):
    def __init__(self, ultimo_enviado):
        self.ultimo_enviado = ultimo_enviado
        super().__init__(f"La fecha de corte debe ser posterior al último corte enviado.")


class CicloNoEncontrado(Exception):
    pass


# ── Validación 881 (primer reporte) ──────────────────────────────────────────

def _valida_881(estado_tu, valor_mora, edad_mora):
    """True si el estado + comportamiento están permitidos en primer reporte (Manual p. 38-39)."""
    if estado_tu == "01":
        return True
    if estado_tu == "03":
        return valor_mora is not None and valor_mora > 0
    if estado_tu == "06":
        return (
            edad_mora is not None and edad_mora > "00"
            and valor_mora is not None and valor_mora > 0
        )
    if estado_tu == "07":
        return False
    # 02, 04, 08, 10, 11, 12: por confirmar con TransUnion
    return True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _obtener_corte_borrador(fecha_corte):
    """Devuelve corte_id si existe un BORRADOR con esa fecha; lanza CorteBorradorNoEncontrado si no."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CORTE_ID FROM NEXOVOLT.NV_CORTE "
            "WHERE FECHA_CORTE = %s AND ESTADO = 'BORRADOR'",
            [fecha_corte],
        )
        row = cursor.fetchone()
    if row is None:
        raise CorteBorradorNoEncontrado()
    return row[0]


def _verificar_fecha_posterior(fecha_corte):
    """Lanza FechaCorteAnterior si fecha_corte no es posterior al último corte ENVIADO."""
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
            raise FechaCorteAnterior(ultimo)


def _limpiar_ciclo_anterior(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM NEXOVOLT.NV_CICLO_TRANSICION WHERE CORTE_ID = %s", [corte_id]
        )
        cursor.execute(
            "DELETE FROM NEXOVOLT.NV_INCONSISTENCIA "
            "WHERE CORTE_ID = %s AND REGLA = 'PRIMER_REPORTE_INVALIDO'",
            [corte_id],
        )
        cursor.execute(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET PRIMER_REPORTE = 'N' WHERE CORTE_ID = %s",
            [corte_id],
        )


def _cargar_obligaciones_corte(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rd.OBLIGACION_ID, rd.ESTADO_TU, rd.VALOR_MORA, rd.EDAD_MORA, "
            "rd.NOMBRE_TITULAR, o.NUMERO_OBLIGACION_TU "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            "WHERE rd.CORTE_ID = %s "
            "ORDER BY rd.OBLIGACION_ID",
            [corte_id],
        )
        return cursor.fetchall()


def _es_primer_reporte(obligacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_CORTE c ON rd.CORTE_ID = c.CORTE_ID "
            "WHERE rd.OBLIGACION_ID = %s AND c.ESTADO = 'ENVIADO'",
            [obligacion_id],
        )
        return cursor.fetchone()[0] == 0


def _marcar_primer_reporte(corte_id, obligacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET PRIMER_REPORTE = 'S' "
            "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
            [corte_id, obligacion_id],
        )


def _insertar_inconsistencia_881(corte_id, obligacion_id, mensaje):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA "
            "(CORTE_ID, OBLIGACION_ID, REGLA, SEVERIDAD, MENSAJE) "
            "VALUES (%s, %s, 'PRIMER_REPORTE_INVALIDO', 'CORRECTIVA', %s)",
            [corte_id, obligacion_id, mensaje],
        )


def _guardar_ciclo(corte_id, fecha_ejecucion, usuario_id, conteos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_CICLO WHERE CORTE_ID = %s", [corte_id]
        )
        existe = cursor.fetchone()[0] > 0

    if existe:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE NEXOVOLT.NV_CICLO "
                "SET FECHA_EJEC = %s, USUARIO_ID = %s, "
                "PRIMER_REPORTE = %s, CAMBIOS_ESTADO = %s, CIERRES = %s, RECHAZADOS = %s, "
                "CON_PAGOS = %s, A_DUDOSO = %s, A_CASTIGADA = %s, NORMALIZADAS = %s "
                "WHERE CORTE_ID = %s",
                [
                    fecha_ejecucion, usuario_id,
                    conteos["primer_reporte"], conteos["cambios_estado"],
                    conteos["cierres"], conteos["rechazados"],
                    conteos["con_pagos"], conteos["a_dudoso"],
                    conteos["a_castigada"], conteos["normalizadas"],
                    corte_id,
                ],
            )
    else:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO NEXOVOLT.NV_CICLO "
                "(CORTE_ID, FECHA_EJEC, USUARIO_ID, "
                "PRIMER_REPORTE, CAMBIOS_ESTADO, CIERRES, RECHAZADOS, "
                "CON_PAGOS, A_DUDOSO, A_CASTIGADA, NORMALIZADAS) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    corte_id, fecha_ejecucion, usuario_id,
                    conteos["primer_reporte"], conteos["cambios_estado"],
                    conteos["cierres"], conteos["rechazados"],
                    conteos["con_pagos"], conteos["a_dudoso"],
                    conteos["a_castigada"], conteos["normalizadas"],
                ],
            )


def _insertar_transiciones(transiciones):
    if not transiciones:
        return
    sql = (
        "INSERT INTO NEXOVOLT.NV_CICLO_TRANSICION "
        "(CORTE_ID, OBLIGACION_ID, ESTADO_ANTERIOR, ESTADO_NUEVO, "
        "EDAD_ANTERIOR, EDAD_NUEVA, PRIMER_REPORTE, REQUIERE_REVISION, "
        "REGLA_RF, REGLA_TEXTO, REGLA_POR_CONFIRMAR) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    with connection.cursor() as cursor:
        cursor.executemany(sql, transiciones)


def _nombres_usuarios(ids):
    if not ids:
        return {}
    return dict(Usuario.objects.filter(pk__in=ids).values_list("pk", "nombre"))


def _fila_ciclo_a_resumen(row, nombres=None):
    corte_id, fecha_corte, fecha_ejec, usuario_id, primer_rep, cambios, cierres, rechazados = row
    return {
        "corte_id": corte_id,
        "fecha_corte": fecha_corte,
        "fecha_ejecucion": fecha_ejec,
        "ejecutada_por": (nombres or {}).get(usuario_id),
        "primer_reporte": primer_rep or 0,
        "cambios_estado": cambios or 0,
        "cierres": cierres or 0,
        "rechazados": rechazados or 0,
    }


def _fila_ciclo_a_detalle(row, nombres, transiciones, rechazos):
    resumen = _fila_ciclo_a_resumen(row[:8], nombres)
    _, _, _, _, _, _, _, _, con_pagos, a_dudoso, a_castigada, normalizadas = row
    resumen.update({
        "con_pagos": con_pagos or 0,
        "a_dudoso": a_dudoso or 0,
        "a_castigada": a_castigada or 0,
        "normalizadas": normalizadas or 0,
        "transiciones": transiciones,
        "rechazos": rechazos,
    })
    return resumen


# ── API pública ───────────────────────────────────────────────────────────────

def ejecutar_ciclo(fecha_corte, usuario=None):
    usuario_id = getattr(usuario, "pk", None)
    ejecutada_por = getattr(usuario, "nombre", None) if usuario_id is not None else None
    fecha_ejecucion = ahora_para_bd()

    with transaction.atomic():
        _verificar_fecha_posterior(fecha_corte)
        corte_id = _obtener_corte_borrador(fecha_corte)
        _limpiar_ciclo_anterior(corte_id)

        filas = _cargar_obligaciones_corte(corte_id)

        transiciones_data = []
        rechazos = []
        filas_insert_trans = []
        n_primer_reporte = 0

        for fila in filas:
            obligacion_id, estado_tu, valor_mora, edad_mora, nombre_titular, numero_obl = fila
            valor_mora_int = int(valor_mora) if valor_mora is not None else None

            if _es_primer_reporte(obligacion_id):
                if not _valida_881(estado_tu, valor_mora_int, edad_mora):
                    _insertar_inconsistencia_881(
                        corte_id, obligacion_id,
                        "Estado y comportamiento no permitido en primer reporte",
                    )
                    rechazos.append({
                        "obligacion_id": obligacion_id,
                        "numero_obligacion": numero_obl,
                        "nombre_titular": nombre_titular,
                        "estado_anterior": None,
                        "estado_calculado": estado_tu,
                        "codigo": "881",
                        "motivo": "Error 881: estado no permitido en primer reporte",
                    })
                    continue

                _marcar_primer_reporte(corte_id, obligacion_id)
                n_primer_reporte += 1

                requiere_revision = estado_tu == "01" and (valor_mora_int is None or valor_mora_int == 0)
                filas_insert_trans.append((
                    corte_id, obligacion_id, None, estado_tu,
                    None, edad_mora or "00",
                    "S", "S" if requiere_revision else "N",
                    "RF10", "Entra con su estado y su mora reales", "N",
                ))
                transiciones_data.append({
                    "obligacion_id": obligacion_id,
                    "numero_obligacion": numero_obl,
                    "nombre_titular": nombre_titular,
                    "estado_anterior": None,
                    "estado_nuevo": estado_tu,
                    "edad_anterior": None,
                    "edad_nueva": edad_mora or "00",
                    "primer_reporte": True,
                    "requiere_revision": requiere_revision,
                    "reglas": [
                        {"rf": "RF10", "texto": "Entra con su estado y su mora reales",
                         "por_confirmar": False}
                    ],
                })

        _insertar_transiciones(filas_insert_trans)

        conteos = {
            "primer_reporte": n_primer_reporte,
            "cambios_estado": 0,
            "cierres": 0,
            "rechazados": len(rechazos),
            "con_pagos": 0,
            "a_dudoso": 0,
            "a_castigada": 0,
            "normalizadas": 0,
        }
        _guardar_ciclo(corte_id, fecha_ejecucion, usuario_id, conteos)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT FECHA_CORTE FROM NEXOVOLT.NV_CORTE WHERE CORTE_ID = %s", [corte_id]
        )
        fecha_corte_bd = cursor.fetchone()[0]

    with tolerar_fallo_bitacora("ACTUALIZACION_MENSUAL"):
        registrar_bitacora(
            "ACTUALIZACION_MENSUAL", "NV_CICLO", str(corte_id),
            f"Fecha: {fecha_corte}, primeros: {n_primer_reporte}, rechazados: {len(rechazos)}",
            usuario=usuario,
        )

    return {
        "corte_id": corte_id,
        "fecha_corte": fecha_corte_bd if hasattr(fecha_corte_bd, "date") else fecha_corte,
        "fecha_ejecucion": fecha_ejecucion,
        "ejecutada_por": ejecutada_por,
        **conteos,
        "transiciones": transiciones_data,
        "rechazos": rechazos,
    }


def listar_ciclos():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ci.CORTE_ID, c.FECHA_CORTE, ci.FECHA_EJEC, ci.USUARIO_ID, "
            "ci.PRIMER_REPORTE, ci.CAMBIOS_ESTADO, ci.CIERRES, ci.RECHAZADOS "
            "FROM NEXOVOLT.NV_CICLO ci "
            "JOIN NEXOVOLT.NV_CORTE c ON ci.CORTE_ID = c.CORTE_ID "
            "ORDER BY ci.FECHA_EJEC DESC"
        )
        rows = cursor.fetchall()
    ids = {r[3] for r in rows if r[3] is not None}
    nombres = _nombres_usuarios(ids)
    return [_fila_ciclo_a_resumen(r, nombres) for r in rows]


def obtener_ciclo(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ci.CORTE_ID, c.FECHA_CORTE, ci.FECHA_EJEC, ci.USUARIO_ID, "
            "ci.PRIMER_REPORTE, ci.CAMBIOS_ESTADO, ci.CIERRES, ci.RECHAZADOS, "
            "ci.CON_PAGOS, ci.A_DUDOSO, ci.A_CASTIGADA, ci.NORMALIZADAS "
            "FROM NEXOVOLT.NV_CICLO ci "
            "JOIN NEXOVOLT.NV_CORTE c ON ci.CORTE_ID = c.CORTE_ID "
            "WHERE ci.CORTE_ID = %s",
            [corte_id],
        )
        row = cursor.fetchone()
    if row is None:
        return None

    nombres = _nombres_usuarios({row[3]} if row[3] else set())

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ct.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, rd.NOMBRE_TITULAR, "
            "ct.ESTADO_ANTERIOR, ct.ESTADO_NUEVO, ct.EDAD_ANTERIOR, ct.EDAD_NUEVA, "
            "ct.PRIMER_REPORTE, ct.REQUIERE_REVISION, "
            "ct.REGLA_RF, ct.REGLA_TEXTO, ct.REGLA_POR_CONFIRMAR "
            "FROM NEXOVOLT.NV_CICLO_TRANSICION ct "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON ct.OBLIGACION_ID = o.OBLIGACION_ID "
            "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd "
            "  ON rd.OBLIGACION_ID = ct.OBLIGACION_ID AND rd.CORTE_ID = ct.CORTE_ID "
            "WHERE ct.CORTE_ID = %s "
            "ORDER BY ct.TRANSICION_ID",
            [corte_id],
        )
        trans_rows = cursor.fetchall()

    transiciones = [
        {
            "obligacion_id": r[0],
            "numero_obligacion": r[1],
            "nombre_titular": r[2],
            "estado_anterior": r[3],
            "estado_nuevo": r[4],
            "edad_anterior": r[5],
            "edad_nueva": r[6],
            "primer_reporte": r[7] == "S",
            "requiere_revision": r[8] == "S",
            "reglas": [{"rf": r[9], "texto": r[10], "por_confirmar": r[11] == "S"}]
            if r[9] else [],
        }
        for r in trans_rows
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT i.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, rd.NOMBRE_TITULAR, "
            "i.REGLA, i.MENSAJE "
            "FROM NEXOVOLT.NV_INCONSISTENCIA i "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON i.OBLIGACION_ID = o.OBLIGACION_ID "
            "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd "
            "  ON rd.OBLIGACION_ID = i.OBLIGACION_ID AND rd.CORTE_ID = i.CORTE_ID "
            "WHERE i.CORTE_ID = %s AND i.REGLA = 'PRIMER_REPORTE_INVALIDO' "
            "ORDER BY i.OBLIGACION_ID",
            [corte_id],
        )
        rechazo_rows = cursor.fetchall()

    estados_rechazados = {}
    if rechazo_rows:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rd.OBLIGACION_ID, rd.ESTADO_TU "
                "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
                "WHERE rd.CORTE_ID = %s "
                "AND rd.OBLIGACION_ID IN ("
                + ",".join(["%s"] * len(rechazo_rows))
                + ")",
                [corte_id] + [r[0] for r in rechazo_rows],
            )
            estados_rechazados = dict(cursor.fetchall())

    rechazos = [
        {
            "obligacion_id": r[0],
            "numero_obligacion": r[1],
            "nombre_titular": r[2],
            "estado_anterior": None,
            "estado_calculado": estados_rechazados.get(r[0], ""),
            "codigo": "881",
            "motivo": "Error 881: estado no permitido en primer reporte",
        }
        for r in rechazo_rows
    ]

    return _fila_ciclo_a_detalle(row, nombres, transiciones, rechazos)


def obtener_matriz():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA, PERMITIDA "
            "FROM NEXOVOLT.NV_TRANSICION_ESTADO "
            "ORDER BY ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA"
        )
        rows = cursor.fetchall()
    transiciones = [
        {
            "desde": r[0],
            "desde_con_mora": r[1] == "S",
            "hacia": r[2],
            "hacia_con_mora": r[3] == "S",
            "permitida": r[4] == "S",
        }
        for r in rows
    ]
    return {
        "tipo_cartera": 2,
        "estados": ["01", "02", "04", "08", "06", "07", "03", "10", "11", "12"],
        "transiciones": transiciones,
    }

