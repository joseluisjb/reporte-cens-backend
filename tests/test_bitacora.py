from datetime import datetime
from unittest.mock import MagicMock, patch

from config.bitacora import registrar_bitacora


def _mock_conn():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    return mock_conn, mock_cursor


def test_registrar_bitacora_insert_incluye_fecha():
    mock_conn, mock_cursor = _mock_conn()
    sqls = []
    params_list = []
    mock_cursor.execute.side_effect = lambda sql, params: (sqls.append(sql), params_list.append(params))
    with patch("config.bitacora.connection", mock_conn):
        registrar_bitacora("ACCION_TEST", "ENTIDAD", "123", "Detalle")
    assert len(sqls) == 1
    assert "FECHA" in sqls[0]
    assert "NV_BITACORA" in sqls[0]
    assert isinstance(params_list[0][0], datetime)
    assert params_list[0][0].tzinfo is None


def test_registrar_bitacora_usuario_none():
    mock_conn, mock_cursor = _mock_conn()
    params_list = []
    mock_cursor.execute.side_effect = lambda sql, params: params_list.append(params)
    with patch("config.bitacora.connection", mock_conn):
        registrar_bitacora("ACCION", "ENTIDAD", "1", "Detalle")
    assert params_list[0][1] is None


def test_registrar_bitacora_con_usuario():
    mock_conn, mock_cursor = _mock_conn()
    params_list = []
    mock_cursor.execute.side_effect = lambda sql, params: params_list.append(params)
    with patch("config.bitacora.connection", mock_conn):
        registrar_bitacora("ACCION", "ENTIDAD", "1", "Detalle", usuario_id=42)
    assert params_list[0][1] == 42
