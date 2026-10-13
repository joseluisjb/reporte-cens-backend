from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def bitacora():
    with patch("config.auditoria.registrar_bitacora") as registro:
        yield registro
