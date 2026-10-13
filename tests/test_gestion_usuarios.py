from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura1"
CORREO_ADMIN = "admin@nexovolt.co"
CORREO_ANALISTA = "analista@nexovolt.co"


@pytest.fixture(autouse=True)
def sin_auditoria():
    with patch("usuarios.views.registrar_auditoria"):
        yield


@pytest.fixture(autouse=True)
def sin_correo():
    with patch("usuarios.servicios.send_mail"):
        yield


@pytest.fixture
def administrador():
    return Usuario.objects.create_superuser(CORREO_ADMIN, CLAVE, nombre="Admin NexoVolt")


@pytest.fixture
def analista():
    return Usuario.objects.create_user(
        CORREO_ANALISTA, CLAVE, nombre="Analista NexoVolt", must_change_password=False
    )


def _cliente_autenticado(usuario):
    cliente = APIClient()
    cliente.force_login(usuario)
    return cliente


# ── GET /api/users/ ──────────────────────────────────────────────────────────

def test_admin_lista_usuarios(administrador, analista):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.get("/api/users/")
    assert respuesta.status_code == 200
    data = respuesta.json()
    assert isinstance(data, list)
    correos = [u["email"] for u in data]
    assert CORREO_ADMIN in correos
    assert CORREO_ANALISTA in correos


def test_analista_no_puede_listar_usuarios(analista):
    cliente = _cliente_autenticado(analista)
    respuesta = cliente.get("/api/users/")
    assert respuesta.status_code == 403


def test_listar_sin_sesion_responde_401():
    respuesta = APIClient().get("/api/users/")
    assert respuesta.status_code == 401


def test_usuario_con_contrasena_temporal_no_puede_listar(administrador):
    administrador.must_change_password = True
    administrador.save(update_fields=["must_change_password"])
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.get("/api/users/")
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "password_change_required"


# ── POST /api/users/ ─────────────────────────────────────────────────────────

def test_admin_crea_usuario(administrador, sin_correo):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.post(
        "/api/users/",
        {"nombre": "Carlos Ruiz", "email": "cruiz@nexovolt.co", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    assert respuesta.status_code == 201
    data = respuesta.json()
    assert "user" in data
    assert data["temporary_password"] is None
    usuario = data["user"]
    assert set(usuario) >= {"id", "nombre", "email", "rol", "is_active", "last_login", "must_change_password"}
    assert usuario["email"] == "cruiz@nexovolt.co"
    assert usuario["rol"] == "ANALISTA_CARTERA"
    assert usuario["must_change_password"] is True
    assert "password" not in usuario


def test_crear_usuario_envía_correo(administrador):
    cliente = _cliente_autenticado(administrador)
    with patch("usuarios.servicios.send_mail") as mock_mail:
        cliente.post(
            "/api/users/",
            {"nombre": "Dana", "email": "dana@nexovolt.co", "rol": "ANALISTA_CARTERA"},
            format="json",
        )
    mock_mail.assert_called_once()
    args, kwargs = mock_mail.call_args
    destinatarios = kwargs.get("recipient_list") or args[3]
    assert "dana@nexovolt.co" in destinatarios
    assert "password" not in str(kwargs.get("subject", "")).lower()


def test_crear_usuario_correo_duplicado_devuelve_400(administrador):
    cliente = _cliente_autenticado(administrador)
    cliente.post(
        "/api/users/",
        {"nombre": "Juan", "email": "juan@nexovolt.co", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    respuesta = cliente.post(
        "/api/users/",
        {"nombre": "Juan Copia", "email": "juan@nexovolt.co", "rol": "ADMINISTRADOR"},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "email" in respuesta.json()


def test_crear_usuario_normaliza_correo_a_minusculas(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.post(
        "/api/users/",
        {"nombre": "María", "email": "Maria@NexoVolt.CO", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["user"]["email"] == "maria@nexovolt.co"


def test_crear_usuario_contrasena_no_aparece_en_respuesta(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.post(
        "/api/users/",
        {"nombre": "Test", "email": "test@nexovolt.co", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    cuerpo = respuesta.content.decode()
    assert respuesta.json()["temporary_password"] is None
    assert "password" not in respuesta.json()["user"]


def test_crear_usuario_con_rol_invalido_devuelve_400(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.post(
        "/api/users/",
        {"nombre": "X", "email": "x@nexovolt.co", "rol": "SUPERADMIN"},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "rol" in respuesta.json()


def test_crear_usuario_sin_campos_devuelve_400(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.post("/api/users/", {}, format="json")
    assert respuesta.status_code == 400


# ── GET /api/users/{id}/ ─────────────────────────────────────────────────────

def test_admin_obtiene_usuario_por_id(administrador, analista):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.get(f"/api/users/{analista.pk}/")
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == CORREO_ANALISTA


def test_obtener_usuario_inexistente_devuelve_404(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.get("/api/users/99999/")
    assert respuesta.status_code == 404


# ── PATCH /api/users/{id}/ ───────────────────────────────────────────────────

def test_admin_edita_nombre_de_usuario(administrador, analista):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{analista.pk}/",
        {"nombre": "Analista Editado"},
        format="json",
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Analista Editado"
    analista.refresh_from_db()
    assert analista.nombre == "Analista Editado"


def test_admin_desactiva_usuario(administrador, analista):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{analista.pk}/",
        {"is_active": False},
        format="json",
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["is_active"] is False
    analista.refresh_from_db()
    assert analista.is_active is False


def test_admin_no_puede_desactivarse_a_si_mismo(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{administrador.pk}/",
        {"is_active": False},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "is_active" in respuesta.json()


def test_admin_no_puede_quitarse_el_rol(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{administrador.pk}/",
        {"rol": "ANALISTA_CARTERA"},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "rol" in respuesta.json()


def test_admin_puede_cambiarse_a_administrador_sin_error(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{administrador.pk}/",
        {"rol": "ADMINISTRADOR"},
        format="json",
    )
    assert respuesta.status_code == 200


def test_patch_correo_duplicado_devuelve_400(administrador, analista):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch(
        f"/api/users/{analista.pk}/",
        {"email": CORREO_ADMIN},
        format="json",
    )
    assert respuesta.status_code == 400
    assert "email" in respuesta.json()


def test_patch_usuario_inexistente_devuelve_404(administrador):
    cliente = _cliente_autenticado(administrador)
    respuesta = cliente.patch("/api/users/99999/", {"nombre": "X"}, format="json")
    assert respuesta.status_code == 404


def test_analista_no_puede_hacer_patch(analista):
    cliente = _cliente_autenticado(analista)
    respuesta = cliente.patch(f"/api/users/{analista.pk}/", {"nombre": "X"}, format="json")
    assert respuesta.status_code == 403
