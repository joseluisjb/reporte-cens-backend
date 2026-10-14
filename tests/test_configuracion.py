import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

RAIZ = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("ruta", ["/api/no-existe/", "/cualquier-cosa/"])
@override_settings(DEBUG=False)
def test_ruta_inexistente_responde_404_en_json(db, ruta):
    respuesta = APIClient().get(ruta)
    assert respuesta.status_code == 404
    assert respuesta["Content-Type"] == "application/json"
    assert respuesta.json() == {"detail": "Recurso no encontrado."}


def _importar_settings(**entorno):
    # En otro proceso, para no tocar la configuración ya cargada por las pruebas.
    return subprocess.run(
        [sys.executable, "-c", "import config.settings as s; print(s.SECRET_KEY)"],
        cwd=RAIZ,
        env={**os.environ, **entorno},
        capture_output=True,
        text=True,
    )


def test_sin_clave_y_sin_debug_no_arranca():
    resultado = _importar_settings(DJANGO_SECRET_KEY="", DJANGO_DEBUG="False")
    assert resultado.returncode != 0
    assert "Falta DJANGO_SECRET_KEY" in resultado.stderr


def test_sin_clave_en_desarrollo_usa_una_clave_local():
    resultado = _importar_settings(DJANGO_SECRET_KEY="", DJANGO_DEBUG="True")
    assert resultado.returncode == 0
    assert resultado.stdout.strip().startswith("django-insecure-")


def test_la_clave_del_entorno_se_respeta():
    resultado = _importar_settings(DJANGO_SECRET_KEY="clave-de-render", DJANGO_DEBUG="False")
    assert resultado.returncode == 0
    assert resultado.stdout.strip() == "clave-de-render"
