from django.db import connection


class ReporteNoEncontrado(Exception):
    pass


class ObligacionNoEncontrada(Exception):
    pass


def listar_reportes_enviados(desde=None, hasta=None):
    sql = (
        "SELECT c.CORTE_ID, c.FECHA_CORTE, c.FECHA_ENVIO, NVL(c.TOTAL_REGISTROS, 0), "
        "c.OBSERVACION, c.GRUPO_NOMBRE, NVL(SUM(d.VALOR_SALDO), 0) "
        "FROM NEXOVOLT.NV_CORTE c "
        "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE d ON c.CORTE_ID = d.CORTE_ID "
        "WHERE c.ESTADO = 'ENVIADO'"
    )
    params = []
    if desde is not None:
        params.append(desde)
        sql += f" AND c.FECHA_ENVIO >= :{len(params)}"
    if hasta is not None:
        params.append(hasta)
        sql += f" AND c.FECHA_ENVIO <= :{len(params)}"
    sql += (
        " GROUP BY c.CORTE_ID, c.FECHA_CORTE, c.FECHA_ENVIO, c.TOTAL_REGISTROS, "
        "c.OBSERVACION, c.GRUPO_NOMBRE"
        " ORDER BY c.FECHA_ENVIO DESC"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        filas = cursor.fetchall()
    return [
        {
            "id":               row[0],
            "fecha_corte":      row[1],
            "fecha_envio":      row[2],
            "total_registros":  row[3],
            "observacion":      row[4],
            "grupo":            row[5],
            "saldo_consolidado": int(row[6]),
        }
        for row in filas
    ]


def listar_detalle_reporte(corte_id, limite=20, desplazamiento=0):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_CORTE "
            "WHERE CORTE_ID = :1 AND ESTADO = 'ENVIADO'",
            [corte_id],
        )
        if cursor.fetchone()[0] == 0:
            raise ReporteNoEncontrado()

        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_REPORTE_DETALLE WHERE CORTE_ID = :1",
            [corte_id],
        )
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT o.NUMERO_OBLIGACION_TU, rd.NOMBRE_TITULAR, rd.NUMERO_IDENTIFICACION, "
            "rd.TIPO_ID_TU, rd.TIPO_CARTERA, rd.ESTADO_TU, rd.EDAD_MORA, "
            "rd.FECHA_INICIO, rd.CUOTAS_MORA, rd.VALOR_INICIAL, rd.VALOR_MORA, "
            "rd.VALOR_SALDO, rd.VALOR_CUOTA, rd.DIAS_MORA, rd.ORIGEN_DIAS_MORA, "
            "rd.N_CREDITOS, rd.FECHA_ULTIMO_PAGO "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_OBLIGACION o ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
            "WHERE rd.CORTE_ID = :1 "
            "ORDER BY rd.OBLIGACION_ID "
            "OFFSET :2 ROWS FETCH NEXT :3 ROWS ONLY",
            [corte_id, desplazamiento, limite],
        )
        filas = cursor.fetchall()

    resultados = [
        {
            "numero_obligacion":     row[0],
            "nombre_titular":        row[1],
            "numero_identificacion": row[2],
            "tipo_id_tu":            row[3],
            "tipo_cartera":          row[4],
            "estado_tu":             row[5],
            "edad_mora":             row[6],
            "fecha_inicio":          row[7],
            "cuotas_mora":           row[8],
            "valor_inicial":         int(row[9]) if row[9] is not None else None,
            "valor_mora":            int(row[10]),
            "valor_saldo":           int(row[11]),
            "valor_cuota":           int(row[12]) if row[12] is not None else None,
            "dias_mora":             row[13],
            "origen_dias_mora":      row[14],
            "n_creditos":            row[15],
            "fecha_ultimo_pago":     row[16],
        }
        for row in filas
    ]
    return {"total": total, "resultados": resultados}


def buscar_deudores(cliente_id=None, numero_obligacion=None):
    sql = (
        "SELECT o.OBLIGACION_ID, o.NUMERO_OBLIGACION_TU, o.CLIENTE_ID, o.NUMERO_PROCESO, "
        "o.FECHA_INICIO, rd.ESTADO_TU, rd.VALOR_SALDO "
        "FROM NEXOVOLT.NV_OBLIGACION o "
        "LEFT JOIN NEXOVOLT.NV_REPORTE_DETALLE rd "
        "  ON rd.OBLIGACION_ID = o.OBLIGACION_ID "
        "  AND rd.CORTE_ID = ("
        "    SELECT MAX(rd2.CORTE_ID) FROM NEXOVOLT.NV_REPORTE_DETALLE rd2 "
        "    WHERE rd2.OBLIGACION_ID = o.OBLIGACION_ID"
        "  ) "
        "WHERE 1=1"
    )
    params = []
    if cliente_id is not None:
        params.append(cliente_id)
        sql += f" AND o.CLIENTE_ID = :{len(params)}"
    if numero_obligacion is not None:
        params.append(numero_obligacion)
        sql += f" AND o.NUMERO_OBLIGACION_TU = :{len(params)}"
    sql += " FETCH FIRST 50 ROWS ONLY"
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        filas = cursor.fetchall()
    return [
        {
            "obligacion_id":      row[0],
            "numero_obligacion":  row[1],
            "cliente_id":         row[2],
            "numero_proceso":     row[3],
            "fecha_inicio":       row[4],
            "ultimo_estado_tu":   row[5],
            "ultimo_valor_saldo": int(row[6]) if row[6] is not None else None,
        }
        for row in filas
    ]


def linea_tiempo_deudor(obligacion_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM NEXOVOLT.NV_OBLIGACION WHERE OBLIGACION_ID = :1",
            [obligacion_id],
        )
        if cursor.fetchone()[0] == 0:
            raise ObligacionNoEncontrada()

        cursor.execute(
            "SELECT c.FECHA_CORTE, rd.ESTADO_TU, rd.EDAD_MORA, rd.DIAS_MORA, "
            "rd.CUOTAS_MORA, rd.VALOR_MORA, rd.VALOR_SALDO, c.ESTADO AS ESTADO_CORTE "
            "FROM NEXOVOLT.NV_REPORTE_DETALLE rd "
            "JOIN NEXOVOLT.NV_CORTE c ON rd.CORTE_ID = c.CORTE_ID "
            "WHERE rd.OBLIGACION_ID = :1 AND c.ESTADO != 'ANULADO' "
            "ORDER BY c.FECHA_CORTE",
            [obligacion_id],
        )
        filas = cursor.fetchall()

    return [
        {
            "fecha_corte":  row[0],
            "estado_tu":    row[1],
            "edad_mora":    row[2],
            "dias_mora":    row[3],
            "cuotas_mora":  row[4],
            "valor_mora":   int(row[5]),
            "valor_saldo":  int(row[6]),
            "estado_corte": row[7],
        }
        for row in filas
    ]
