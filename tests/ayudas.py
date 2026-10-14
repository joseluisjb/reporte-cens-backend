from unittest.mock import MagicMock

from django.db.backends.oracle.base import FormatStylePlaceholderCursor


def usuario_con_rol(rol):
    user = MagicMock()
    user.rol = rol
    user.is_authenticated = True
    user.is_active = True
    return user


def validar_sql(query, params, varios=False):
    """Valida marcadores %s y cuenta de parámetros usando _fix_for_params de Django-Oracle.

    Usa _format_params parcheado a identidad para no necesitar OracleParam.
    Con varios=True replica el camino de executemany (primer elemento de params).
    Lanza TypeError si el número de %s no coincide con los parámetros.
    """
    cursor = object.__new__(FormatStylePlaceholderCursor)
    cursor._format_params = lambda p: p  # identidad: sin conversión a OracleParam
    if varios:
        if params:
            cursor._fix_for_params(query, params[0])
    else:
        cursor._fix_for_params(query, params, unify_by_values=True)


class _ValidatingExecuteMock(MagicMock):
    """MagicMock para cursor.execute que valida SQL antes de registrar la llamada."""

    def __call__(self, query, params=None):
        validar_sql(query, params)
        if params is not None:
            return super().__call__(query, params)
        return super().__call__(query)


class _ValidatingExecutemanyMock(MagicMock):
    """MagicMock para cursor.executemany que valida SQL antes de registrar la llamada."""

    def __call__(self, query, params=None):
        if params:
            validar_sql(query, params, varios=True)
        return super().__call__(query, params)


def _mock_conn(fetchall=None, fetchone=None):
    """Cursor simulado que llama a validar_sql en execute y executemany."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute = _ValidatingExecuteMock()
    mock_cursor.executemany = _ValidatingExecutemanyMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    if fetchall is not None:
        mock_cursor.fetchall.return_value = fetchall
    if fetchone is not None:
        mock_cursor.fetchone.return_value = fetchone
    return mock_conn, mock_cursor
