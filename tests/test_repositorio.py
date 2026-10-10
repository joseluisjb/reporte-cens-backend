from unittest.mock import MagicMock, patch

from extraccion import repositorio


_COLS_DEUDOR = [
    "CLIENTE_ID", "NUMERO_PROCESO", "N_CREDITOS", "ESTADO_SAC",
    "FECHA_INICIO", "VALOR_INICIAL", "VALOR_SALDO", "CUOTAS_MORA",
]

_COLS_CREDITO = [
    "CLIENTE_ID", "NUMERO_PROCESO", "CREDITO_ID", "CORR_CREDITOS",
    "ESTADO_SAC", "PRIORIDAD", "ESTADO_TU", "CODIGO_CONCEPTO", "OPCION_CREDITO",
    "DEUDA_INICIAL_CAP", "DEUDA_ACTUAL_CAP", "VALOR_CUOTA", "TOTAL_CUOTAS",
    "ULTIMA_CUOTA", "CONTATRASOS", "CUOTAS_MORA", "FECHA_ACTIVACION",
    "FECHA_DESACTIVACION", "FECHA_ULTIMO_PAGO", "VALOR_ULTIMO_PAGO",
    "FECHA_ULT_CUOTA_FACTURADA",
]


def _mock_cursor_con_cols(cols, rows):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    mock_cursor.description = [(c,) for c in cols]
    mock_cursor.fetchall.return_value = rows
    return mock_conn, mock_cursor


# ── deudores_vigentes ─────────────────────────────────────────────────────────

class TestDeudoresVigentes:
    def test_consulta_vista_correcta(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.deudores_vigentes()
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "V_DEUDOR_VIGENTE" in sql_ejecutado

    def test_resultado_con_claves_en_minuscula(self):
        fila = (900001, 1001001, 1, "A", None, 100000, 50000, 0)
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [fila])
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.deudores_vigentes()
        assert len(resultado) == 1
        assert resultado[0]["cliente_id"] == 900001
        assert resultado[0]["valor_saldo"] == 50000

    def test_sin_limite_no_incluye_fetch_first(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.deudores_vigentes()
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "FETCH FIRST" not in sql_ejecutado

    def test_sin_limite_pasa_lista_vacia_de_params(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.deudores_vigentes()
        params = mock_cursor.execute.call_args[0][1]
        assert params == []

    def test_con_limite_incluye_fetch_first(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.deudores_vigentes(limite=5)
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "FETCH FIRST" in sql_ejecutado

    def test_con_limite_pasa_el_valor_correcto(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.deudores_vigentes(limite=5)
        params = mock_cursor.execute.call_args[0][1]
        assert params == [5]

    def test_resultado_vacio(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.deudores_vigentes()
        assert resultado == []

    def test_multiples_filas(self):
        filas = [
            (900001, 1001001, 1, "A", None, 100000, 50000, 0),
            (900002, 1001002, 2, "A", None, 200000, 80000, 1),
        ]
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_DEUDOR, filas)
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.deudores_vigentes()
        assert len(resultado) == 2
        assert resultado[1]["cliente_id"] == 900002


# ── creditos_energia ──────────────────────────────────────────────────────────

class TestCreditosEnergia:
    def test_consulta_vista_correcta(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.creditos_energia()
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "V_CREDITO_REPORTABLE" in sql_ejecutado

    def test_resultado_con_claves_en_minuscula(self):
        fila = (900001, 1001001, 9000001, 1, "A", 1, "01", 1, 1,
                100000, 50000, 1000, 12, 6, 2, 2, None, None, None, 0, None)
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [fila])
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.creditos_energia()
        assert len(resultado) == 1
        assert resultado[0]["cliente_id"] == 900001
        assert resultado[0]["credito_id"] == 9000001

    def test_sin_cliente_id_no_incluye_where(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.creditos_energia()
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "WHERE" not in sql_ejecutado

    def test_sin_cliente_id_pasa_lista_vacia_de_params(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.creditos_energia()
        params = mock_cursor.execute.call_args[0][1]
        assert params == []

    def test_con_cliente_id_incluye_where(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.creditos_energia(cliente_id=900001)
        sql_ejecutado = mock_cursor.execute.call_args[0][0]
        assert "WHERE CLIENTE_ID" in sql_ejecutado

    def test_con_cliente_id_pasa_el_valor_correcto(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            repositorio.creditos_energia(cliente_id=900001)
        params = mock_cursor.execute.call_args[0][1]
        assert params == [900001]

    def test_resultado_vacio(self):
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [])
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.creditos_energia()
        assert resultado == []

    def test_multiples_filas(self):
        fila_base = (900001, 1001001, 9000001, 1, "A", 1, "01", 1, 1,
                     100000, 50000, 1000, 12, 6, 2, 2, None, None, None, 0, None)
        fila2 = (900001, 1001001, 9000002, 2, "A", 1, "01", 2, 1,
                 80000, 30000, 800, 12, 6, 0, 0, None, None, None, 0, None)
        mock_conn, mock_cursor = _mock_cursor_con_cols(_COLS_CREDITO, [fila_base, fila2])
        with patch("extraccion.repositorio.connection", mock_conn):
            resultado = repositorio.creditos_energia(cliente_id=900001)
        assert len(resultado) == 2
        assert resultado[0]["credito_id"] == 9000001
        assert resultado[1]["credito_id"] == 9000002
