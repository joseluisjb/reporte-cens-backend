from django.db import connection


def _filas_a_dicts(cursor):
    cols = [d[0].lower() for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def deudores_vigentes(limite=None):
    sql = (
        "SELECT CLIENTE_ID, NUMERO_PROCESO, N_CREDITOS, ESTADO_SAC, "
        "FECHA_INICIO, VALOR_INICIAL, VALOR_SALDO, CUOTAS_MORA "
        "FROM NEXOVOLT.V_DEUDOR_VIGENTE"
    )
    params = []
    if limite is not None:
        sql += " FETCH FIRST :1 ROWS ONLY"
        params.append(limite)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return _filas_a_dicts(cursor)


def creditos_energia(cliente_id=None):
    sql = (
        "SELECT CLIENTE_ID, NUMERO_PROCESO, CREDITO_ID, CORR_CREDITOS, "
        "ESTADO_SAC, PRIORIDAD, ESTADO_TU, CODIGO_CONCEPTO, OPCION_CREDITO, "
        "DEUDA_INICIAL_CAP, DEUDA_ACTUAL_CAP, VALOR_CUOTA, TOTAL_CUOTAS, "
        "ULTIMA_CUOTA, CONTATRASOS, CUOTAS_MORA, FECHA_ACTIVACION, "
        "FECHA_DESACTIVACION, FECHA_ULTIMO_PAGO, VALOR_ULTIMO_PAGO, "
        "FECHA_ULT_CUOTA_FACTURADA "
        "FROM NEXOVOLT.V_CREDITO_REPORTABLE"
    )
    params = []
    if cliente_id is not None:
        sql += " WHERE CLIENTE_ID = :1"
        params.append(cliente_id)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return _filas_a_dicts(cursor)
