from django.db import connection, transaction

from config.bitacora import registrar_bitacora, tolerar_fallo_bitacora
from config.formatos import ahora_para_bd, enmascarar_identificacion, fecha_str
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


class ObligacionNoEncontrada(Exception):
    pass


# ── Tabla 9 · RF11 ────────────────────────────────────────────────────────────

_TRAMOS_EDAD = [
    (30, "00"), (60, "01"), (90, "02"), (120, "03"),
    (150, "04"), (180, "05"), (210, "06"), (240, "07"),
    (270, "08"), (300, "09"), (330, "10"), (360, "11"),
    (540, "12"), (730, "13"),
]


def _calcular_edad_mora(dias_mora):
    """Código Tabla 9 (00–14) a partir de los días de mora reales."""
    for limite, codigo in _TRAMOS_EDAD:
        if dias_mora < limite:
            return codigo
    return "14"


_ESTADOS_VALIDOS = {"01", "02", "03", "04", "06", "07", "08", "10", "11", "12"}


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
            "WHERE CORTE_ID = %s AND REGLA IN ('PRIMER_REPORTE_INVALIDO', 'CAMBIO_ESTADO_INVALIDO')",
            [corte_id],
        )
        cursor.execute(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET PRIMER_REPORTE = 'N', REQUIERE_REVISION = 'N', MOTIVO_REVISION = NULL "
            "WHERE CORTE_ID = %s",
            [corte_id],
        )


def _cargar_obligaciones_corte(corte_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rd.OBLIGACION_ID, rd.ESTADO_TU, rd.VALOR_MORA, rd.EDAD_MORA, "
            "rd.NOMBRE_TITULAR, o.NUMERO_OBLIGACION_TU, "
            "rd.DIAS_MORA, rd.FECHA_LIMITE_PAGO, rd.VALOR_REAL_PAGADO, "
            "NVL(rd.CADUCADO, 'N'), NVL(rd.ATRASOS_PERMITIDOS, 0), rd.CUOTAS_MORA "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            "WHERE rd.CORTE_ID = %s "
            "ORDER BY rd.OBLIGACION_ID",
            [corte_id],
        )
        return cursor.fetchall()


def _cargar_datos_previos(corte_id):
    """
    Batch query that returns a dict:
      {obligacion_id: (es_primer_reporte, edad_anterior, estado_anterior, mora_anterior)}

    Uses V_ULTIMO_REPORTE to detect primer reporte and get the last reported
    estado, edad and valor_mora (needed for RF14 matrix validation).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rd.OBLIGACION_ID, "
            "CASE WHEN vu.OBLIGACION_ID IS NULL THEN 'S' ELSE 'N' END, "
            "vu.EDAD_MORA, vu.ESTADO_TU, vu.VALOR_MORA "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "LEFT JOIN NEXOVOLT.V_ULTIMO_REPORTE vu ON vu.OBLIGACION_ID = rd.OBLIGACION_ID "
            "WHERE rd.CORTE_ID = %s "
            "ORDER BY rd.OBLIGACION_ID",
            [corte_id],
        )
        rows = cursor.fetchall()
    return {
        r[0]: (r[1] == "S", r[2], r[3], int(r[4]) if r[4] is not None else 0)
        for r in rows
    }


def _marcar_primer_reporte(corte_id, obligacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET PRIMER_REPORTE = 'S' "
            "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
            [corte_id, obligacion_id],
        )


def _cargar_transiciones_permitidas():
    """Devuelve el conjunto de transiciones S de NV_TRANSICION_ESTADO para validar la Matriz."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ESTADO_DESDE, CON_MORA_DESDE, ESTADO_HACIA, CON_MORA_HACIA "
            "FROM NEXOVOLT.NV_TRANSICION_ESTADO "
            "WHERE PERMITIDA = 'S'"
        )
        rows = cursor.fetchall()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


def _transicion_permitida(matriz, estado_desde, con_mora_desde, estado_hacia, con_mora_hacia):
    """True si la Matriz permite el cambio de estado (RF14)."""
    return (
        estado_desde,
        'S' if con_mora_desde else 'N',
        estado_hacia,
        'S' if con_mora_hacia else 'N',
    ) in matriz


def _insertar_inconsistencia_713(corte_id, obligacion_id, mensaje):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA "
            "(CORTE_ID, OBLIGACION_ID, REGLA, SEVERIDAD, MENSAJE) "
            "VALUES (%s, %s, 'CAMBIO_ESTADO_INVALIDO', 'CORRECTIVA', %s)",
            [corte_id, obligacion_id, mensaje],
        )


def _actualizar_estado_obligacion(corte_id, obligacion_id, nuevo_estado):
    """Revierte ESTADO_TU en NV_REPORTE_DETALLE cuando la Matriz rechaza la transición (713)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET ESTADO_TU = %s "
            "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
            [nuevo_estado, corte_id, obligacion_id],
        )


def _insertar_inconsistencia_881(corte_id, obligacion_id, mensaje):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_INCONSISTENCIA "
            "(CORTE_ID, OBLIGACION_ID, REGLA, SEVERIDAD, MENSAJE) "
            "VALUES (%s, %s, 'PRIMER_REPORTE_INVALIDO', 'CORRECTIVA', %s)",
            [corte_id, obligacion_id, mensaje],
        )


def _actualizar_revisiones(updates):
    """Batch UPDATE NV_REPORTE_DETALLE con REQUIERE_REVISION y MOTIVO_REVISION."""
    if not updates:
        return
    with connection.cursor() as cursor:
        cursor.executemany(
            "UPDATE NEXOVOLT.NV_REPORTE_DETALLE "
            "SET REQUIERE_REVISION = %s, MOTIVO_REVISION = %s "
            "WHERE CORTE_ID = %s AND OBLIGACION_ID = %s",
            updates,
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


def _obtener_ultimo_corte_ciclo():
    """Retorna el CORTE_ID del ciclo más reciente, o None si no hay ninguno."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CORTE_ID FROM NEXOVOLT.NV_CICLO "
            "ORDER BY FECHA_EJEC DESC FETCH FIRST 1 ROW ONLY"
        )
        row = cursor.fetchone()
    return row[0] if row else None


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
        datos_previos = _cargar_datos_previos(corte_id)
        matriz = _cargar_transiciones_permitidas()

        transiciones_data = []
        rechazos = []
        filas_insert_trans = []
        updates_revision = []
        n_primer_reporte = 0
        n_cambios_estado = 0
        n_a_dudoso = 0

        for fila in filas:
            # Los primeros 9 campos son fijos; los 3 siguientes vienen de RF14
            obligacion_id, estado_tu, valor_mora, edad_mora, nombre_titular, numero_obl, \
                dias_mora, fecha_limite_pago, valor_real_pagado, *extra = fila

            caducado_flag = extra[0] if len(extra) > 0 else 'N'
            atrasos_permitidos_int = int(extra[1]) if len(extra) > 1 and extra[1] is not None else 0
            cuotas_mora_obl = int(extra[2]) if len(extra) > 2 and extra[2] is not None else 0

            valor_mora_int = int(valor_mora) if valor_mora is not None else None
            dias_mora_int = int(dias_mora) if dias_mora is not None else 0
            valor_pagado_int = int(valor_real_pagado) if valor_real_pagado is not None else 0

            datos = datos_previos.get(obligacion_id, (True, None, None, 0))
            es_primer = datos[0]
            edad_anterior = datos[1]
            estado_anterior = datos[2] if len(datos) > 2 else None
            mora_anterior = datos[3] if len(datos) > 3 else 0

            if es_primer:
                # RF10: primer reporte
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
                requiere_revision = estado_tu == "01" and (
                    valor_mora_int is None or valor_mora_int == 0
                )
                updates_revision.append((
                    "S" if requiere_revision else "N",
                    "Vigente (01) sin mora en primer reporte; verificar si el crédito está caducado (RF14)." if requiere_revision else None,
                    corte_id, obligacion_id,
                ))
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
                        {
                            "rf": "RF10",
                            "texto": "Entra con su estado y su mora reales",
                            "por_confirmar": False,
                        }
                    ],
                })

            else:
                # ── RF14: Transición a Dudoso Recaudo ────────────────────────
                nuevo_estado = estado_tu
                regla_rf = "RF11"
                regla_texto = None
                regla_por_confirmar = False

                if caducado_flag == 'S':
                    if valor_mora_int is not None and valor_mora_int > 0:
                        # Crédito caducado con mora: intentar transición a 03
                        con_mora_ant = mora_anterior > 0
                        if not _transicion_permitida(
                            matriz, estado_anterior or estado_tu, con_mora_ant, '03', True
                        ):
                            # 713: Matriz no permite el cambio
                            _insertar_inconsistencia_713(
                                corte_id, obligacion_id,
                                f"RF14 · Cambio de estado inválido: la Matriz no permite "
                                f"pasar de {estado_anterior} a 03 (Dudoso Recaudo)",
                            )
                            rechazos.append({
                                "obligacion_id": obligacion_id,
                                "numero_obligacion": numero_obl,
                                "nombre_titular": nombre_titular,
                                "estado_anterior": estado_anterior,
                                "estado_calculado": "03",
                                "codigo": "713",
                                "motivo": (
                                    f"RF14 · Error 713: la Matriz no permite pasar de "
                                    f"{estado_anterior} a 03 (Dudoso Recaudo)"
                                ),
                            })
                            # Revertir el estado calculado por la extracción
                            if estado_tu == '03':
                                _actualizar_estado_obligacion(corte_id, obligacion_id, estado_anterior)
                            continue
                        else:
                            # Transición permitida → pasar a 03
                            if nuevo_estado != '03':
                                _actualizar_estado_obligacion(corte_id, obligacion_id, '03')
                                nuevo_estado = '03'
                            n_a_dudoso += 1
                            n_cambios_estado += 1
                            regla_rf = "RF14"
                            regla_texto = (
                                f"RF14 · Crédito caducado en el SAC "
                                f"({cuotas_mora_obl} cuotas en mora)"
                            )
                            regla_por_confirmar = True
                    else:
                        # Caducado sin mora: marcar para revisión (no pasa a 03)
                        updates_revision.append((
                            "S",
                            "Crédito caducado en el SAC sin mora; verificar si debe pasar a 03 (RF14).",
                            corte_id, obligacion_id,
                        ))
                        filas_insert_trans.append((
                            corte_id, obligacion_id, estado_anterior, nuevo_estado,
                            edad_anterior or "00", edad_mora or "00",
                            "N", "S",
                            "RF14",
                            "RF14 · Crédito caducado en el SAC sin mora; requiere revisión",
                            "S",
                        ))
                        transiciones_data.append({
                            "obligacion_id": obligacion_id,
                            "numero_obligacion": numero_obl,
                            "nombre_titular": nombre_titular,
                            "estado_anterior": estado_anterior,
                            "estado_nuevo": nuevo_estado,
                            "edad_anterior": edad_anterior or "00",
                            "edad_nueva": edad_mora or "00",
                            "primer_reporte": False,
                            "requiere_revision": True,
                            "reglas": [{
                                "rf": "RF14",
                                "texto": "RF14 · Crédito caducado en el SAC sin mora; requiere revisión",
                                "por_confirmar": True,
                            }],
                        })
                        continue

                # ── RF11: evolución mensual de la edad de mora ───────────────
                old_edad = edad_anterior or "00"
                new_edad = edad_mora or "00"
                old_idx = int(old_edad)
                new_idx = int(new_edad)

                requiere_revision = False
                motivo_revision = None

                if new_idx > old_idx + 1:
                    requiere_revision = True
                    motivo_revision = (
                        f"La edad avanzó más de un tramo "
                        f"(de {old_edad} a {new_edad}) (RF11)."
                    )
                elif new_idx < old_idx and valor_pagado_int == 0:
                    requiere_revision = True
                    motivo_revision = (
                        f"La edad bajó de {old_edad} a {new_edad} "
                        f"sin un abono en el periodo (RF11)."
                    )

                if regla_rf == "RF11":
                    fecha_fl = fecha_str(fecha_limite_pago) if fecha_limite_pago else "sin fecha"
                    regla_texto = (
                        f"RF11 · {dias_mora_int} días desde la cuota más antigua "
                        f"sin pagar ({fecha_fl}): edad {old_edad} → {new_edad}"
                    )

                updates_revision.append(
                    ("S" if requiere_revision else "N", motivo_revision, corte_id, obligacion_id)
                )
                filas_insert_trans.append((
                    corte_id, obligacion_id, estado_anterior, nuevo_estado,
                    old_edad, new_edad,
                    "N", "S" if requiere_revision else "N",
                    regla_rf, regla_texto, "S" if regla_por_confirmar else "N",
                ))
                transiciones_data.append({
                    "obligacion_id": obligacion_id,
                    "numero_obligacion": numero_obl,
                    "nombre_titular": nombre_titular,
                    "estado_anterior": estado_anterior,
                    "estado_nuevo": nuevo_estado,
                    "edad_anterior": old_edad,
                    "edad_nueva": new_edad,
                    "primer_reporte": False,
                    "requiere_revision": requiere_revision,
                    "reglas": [{"rf": regla_rf, "texto": regla_texto, "por_confirmar": regla_por_confirmar}],
                })

        _insertar_transiciones(filas_insert_trans)
        _actualizar_revisiones(updates_revision)

        conteos = {
            "primer_reporte": n_primer_reporte,
            "cambios_estado": n_cambios_estado,
            "cierres": 0,
            "rechazados": len(rechazos),
            "con_pagos": 0,
            "a_dudoso": n_a_dudoso,
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


def listar_obligaciones(
    limite, desplazamiento,
    estado_tu=None, eliminada=False, cuotas_mora_min=None, q=None
):
    if estado_tu is not None and estado_tu not in _ESTADOS_VALIDOS:
        raise ValueError(f"Estado no válido: {estado_tu}")

    ultimo_corte = _obtener_ultimo_corte_ciclo()
    if ultimo_corte is None:
        return {"total": 0, "resultados": []}

    where = "WHERE rd.CORTE_ID = %s"
    params = [ultimo_corte]

    if estado_tu is not None:
        params.append(estado_tu)
        where += " AND rd.ESTADO_TU = %s"
    if cuotas_mora_min is not None:
        params.append(cuotas_mora_min)
        where += " AND rd.CUOTAS_MORA >= %s"
    if q is not None:
        params.extend([q, q])
        where += (
            " AND (o.NUMERO_OBLIGACION_TU LIKE '%%' || %s || '%%'"
            " OR UPPER(rd.NOMBRE_TITULAR) LIKE '%%' || UPPER(%s) || '%%')"
        )

    base = (
        "FROM NEXOVOLT.NV_OBLIGACION o "
        "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
        + where
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) " + base, params)
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT o.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, "
            "rd.NOMBRE_TITULAR, rd.NUMERO_IDENTIFICACION, "
            "rd.ESTADO_TU, rd.EDAD_MORA, rd.DIAS_MORA, rd.CUOTAS_MORA, "
            "rd.VALOR_MORA, rd.VALOR_SALDO, "
            "CASE WHEN rd.ESTADO_TU IN ('02', '07') THEN 'S' ELSE 'N' END, "
            "rd.PRIMER_REPORTE, NVL(rd.REQUIERE_REVISION, 'N'), "
            "NVL(rd.CADUCADO, 'N') "
            + base +
            " ORDER BY o.NUMERO_OBLIGACION_TU "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            params + [desplazamiento, limite],
        )
        filas = cursor.fetchall()

    resultados = [
        {
            "obligacion_id": r[0],
            "numero_obligacion": r[1],
            "nombre_titular": r[2],
            "numero_identificacion": enmascarar_identificacion(r[3]),
            "estado_tu": r[4],
            "edad_mora": r[5] or "00",
            "dias_mora": int(r[6]) if r[6] is not None else 0,
            "cuotas_mora": int(r[7]) if r[7] is not None else 0,
            "valor_mora": int(r[8]) if r[8] is not None else 0,
            "valor_saldo": int(r[9]) if r[9] is not None else 0,
            "cerrada": r[10] == "S",
            "primer_reporte": r[11] == "S",
            "caducado": r[13] == "S",
            "en_reclamo": False,
            "eliminada": False,
            "requiere_revision": r[12] == "S",
        }
        for r in filas
    ]
    return {"total": total, "resultados": resultados}


def obtener_obligacion(obligacion_id):
    ultimo_corte = _obtener_ultimo_corte_ciclo()
    if ultimo_corte is None:
        raise ObligacionNoEncontrada()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT o.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, "
            "rd.NOMBRE_TITULAR, rd.NUMERO_IDENTIFICACION, "
            "rd.ESTADO_TU, rd.EDAD_MORA, rd.DIAS_MORA, rd.CUOTAS_MORA, "
            "rd.VALOR_MORA, rd.VALOR_SALDO, "
            "CASE WHEN rd.ESTADO_TU IN ('02', '07') THEN 'S' ELSE 'N' END, "
            "rd.PRIMER_REPORTE, NVL(rd.REQUIERE_REVISION, 'N'), "
            "rd.MOTIVO_REVISION, "
            "rd.FECHA_INICIO, rd.VALOR_INICIAL, rd.VALOR_CUOTA, rd.FECHA_LIMITE_PAGO, "
            "NVL(rd.CADUCADO, 'N'), NVL(rd.ATRASOS_PERMITIDOS, 0) "
            "FROM NEXOVOLT.NV_OBLIGACION o "
            "JOIN NEXOVOLT.NV_REPORTE_DETALLE rd ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            "WHERE rd.OBLIGACION_ID = %s AND rd.CORTE_ID = %s",
            [obligacion_id, ultimo_corte],
        )
        row = cursor.fetchone()

    if row is None:
        raise ObligacionNoEncontrada()

    dias_mora = int(row[6]) if row[6] is not None else 0
    edad_mora = row[5] or "00"
    anios_mora = dias_mora // 365 if edad_mora == "14" else None
    caducado = row[18] == "S"
    atrasos_permitidos = int(row[19]) if row[19] is not None else 0

    return {
        "obligacion_id": row[0],
        "numero_obligacion": row[1],
        "nombre_titular": row[2],
        "numero_identificacion": enmascarar_identificacion(row[3]),
        "estado_tu": row[4],
        "edad_mora": edad_mora,
        "dias_mora": dias_mora,
        "cuotas_mora": int(row[7]) if row[7] is not None else 0,
        "valor_mora": int(row[8]) if row[8] is not None else 0,
        "valor_saldo": int(row[9]) if row[9] is not None else 0,
        "cerrada": row[10] == "S",
        "primer_reporte": row[11] == "S",
        "caducado": caducado,
        "en_reclamo": False,
        "eliminada": False,
        "requiere_revision": row[12] == "S",
        "motivo_revision": row[13],
        "anios_mora": anios_mora,
        "concepto": None,
        "fecha_ingreso": fecha_str(row[14]),
        "valor_inicial": int(row[15]) if row[15] is not None else None,
        "valor_cuota": int(row[16]) if row[16] is not None else 0,
        "valor_cuota_antes_cierre": None,
        "fecha_exigibilidad": fecha_str(row[17]),
        "atrasos_permitidos": atrasos_permitidos,
        "cuotas_atrasadas": int(row[7]) if row[7] is not None else 0,
        "cierre": None,
        "pago_mora": None,
        "reestructuracion": None,
        "refinanciada_en": None,
        "movimiento_posterior_cierre": False,
        "cuotas_vencidas": [],
        "pagos": [],
        "posibles_transiciones": [],
        "advertencias": [],
    }
