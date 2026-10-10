from unittest.mock import MagicMock

from config.paginacion import parsear_paginacion


def _req(limite=None, desplazamiento=None):
    req = MagicMock()
    params = {}
    if limite is not None:
        params["limite"] = str(limite)
    if desplazamiento is not None:
        params["desplazamiento"] = str(desplazamiento)
    req.query_params = params
    return req


def test_defaults():
    l, d, err = parsear_paginacion(_req())
    assert l == 20 and d == 0 and err is None


def test_valores_explicitos():
    l, d, err = parsear_paginacion(_req(limite=10, desplazamiento=5))
    assert l == 10 and d == 5 and err is None


def test_limite_cap_100():
    l, d, err = parsear_paginacion(_req(limite=200))
    assert l == 100 and err is None


def test_limite_exactamente_100():
    l, d, err = parsear_paginacion(_req(limite=100))
    assert l == 100 and err is None


def test_no_entero_limite_400():
    _, _, err = parsear_paginacion(_req(limite="abc"))
    assert err.status_code == 400
    assert "enteros" in err.data["detail"]


def test_no_entero_desplazamiento_400():
    _, _, err = parsear_paginacion(_req(desplazamiento="xyz"))
    assert err.status_code == 400


def test_limite_cero_400():
    _, _, err = parsear_paginacion(_req(limite=0))
    assert err.status_code == 400
    assert "mayor que 0" in err.data["detail"]


def test_limite_negativo_400():
    _, _, err = parsear_paginacion(_req(limite=-5))
    assert err.status_code == 400


def test_desplazamiento_negativo_400():
    _, _, err = parsear_paginacion(_req(desplazamiento=-1))
    assert err.status_code == 400
