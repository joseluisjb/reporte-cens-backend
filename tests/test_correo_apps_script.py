import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from django.core.mail import EmailMessage
from django.test import override_settings

from config.correo_apps_script import AppsScriptEmailBackend, ErrorCorreoRemoto

CFG = dict(APPS_SCRIPT_URL="https://script.google.com/macros/s/ID/exec",
           APPS_SCRIPT_TOKEN="secreto-de-prueba", EMAIL_TIMEOUT=5)


def _respuesta(cuerpo):
    r = MagicMock()
    r.read.return_value = json.dumps(cuerpo).encode()
    r.__enter__.return_value = r
    return r


def _mensaje(**kw):
    datos = dict(subject="Tu contraseña temporal", body="Clave: X", from_email="NexoVolt <n@x.co>", to=["ana@x.co"])
    datos.update(kw)
    return EmailMessage(**datos)


@override_settings(**CFG)
def test_envia_un_post_con_el_secreto_y_el_destinatario():
    with patch("urllib.request.urlopen", return_value=_respuesta({"ok": True})) as u:
        n = AppsScriptEmailBackend().send_messages([_mensaje()])
    assert n == 1
    solicitud = u.call_args[0][0]
    assert solicitud.get_method() == "POST"
    carga = json.loads(solicitud.data)
    assert carga["to"] == "ana@x.co" and carga["token"] == "secreto-de-prueba"
    assert carga["name"] == "NexoVolt"
    assert u.call_args[1]["timeout"] == 5


@override_settings(**CFG)
def test_un_envio_por_destinatario():
    with patch("urllib.request.urlopen", return_value=_respuesta({"ok": True})) as u:
        AppsScriptEmailBackend().send_messages([_mensaje(to=["a@x.co", "b@x.co"])])
    assert u.call_count == 2


@override_settings(**CFG)
def test_si_el_script_rechaza_lanza_error_sin_el_contenido():
    with patch("urllib.request.urlopen", return_value=_respuesta({"ok": False, "error": "no autorizado"})):
        with pytest.raises(ErrorCorreoRemoto) as e:
            AppsScriptEmailBackend().send_messages([_mensaje()])
    assert "Clave: X" not in str(e.value)


@override_settings(**CFG)
def test_error_de_red_se_propaga_como_oserror():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("sin red")):
        with pytest.raises(OSError):
            AppsScriptEmailBackend().send_messages([_mensaje()])


@override_settings(**CFG)
def test_tiempo_agotado_se_propaga():
    with patch("urllib.request.urlopen", side_effect=TimeoutError()):
        with pytest.raises(TimeoutError):
            AppsScriptEmailBackend().send_messages([_mensaje()])


@override_settings(**CFG)
def test_respuesta_que_no_es_json():
    r = MagicMock(); r.read.return_value = b"<html>error</html>"; r.__enter__.return_value = r
    with patch("urllib.request.urlopen", return_value=r):
        with pytest.raises(ErrorCorreoRemoto):
            AppsScriptEmailBackend().send_messages([_mensaje()])


@override_settings(APPS_SCRIPT_URL="", APPS_SCRIPT_TOKEN="")
def test_sin_configuracion_falla_con_mensaje_claro():
    with pytest.raises(ErrorCorreoRemoto):
        AppsScriptEmailBackend().send_messages([_mensaje()])


@override_settings(**CFG)
def test_fail_silently_no_lanza():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("x")):
        assert AppsScriptEmailBackend(fail_silently=True).send_messages([_mensaje()]) == 0


@override_settings(**CFG)
def test_lista_vacia():
    assert AppsScriptEmailBackend().send_messages([]) == 0