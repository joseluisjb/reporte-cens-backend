from unittest.mock import patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from usuarios.models import Rol, Usuario
from usuarios.serializers import ActualizarUsuarioSerializer, CrearUsuarioSerializer
import usuarios.servicios as servicios
from usuarios.views import GestionUsuarioDetalleView, GestionUsuariosView


factory = APIRequestFactory()


def _admin(pk=1):
    u = Usuario(id=pk, email="admin@test.com", nombre="Admin", rol=Rol.ADMINISTRADOR, is_active=True, must_change_password=False)
    u.pk = pk
    return u


def _analista(pk=2):
    u = Usuario(id=pk, email="analista@test.com", nombre="Analista", rol=Rol.ANALISTA_CARTERA, is_active=True, must_change_password=False)
    u.pk = pk
    return u


def _usuario_mock(pk=10):
    u = Usuario(id=pk, email="nuevo@test.com", nombre="Carlos Ruiz", rol=Rol.ANALISTA_CARTERA, is_active=True, must_change_password=True)
    u.pk = pk
    u.last_login = None
    return u


# ── Serializer: CrearUsuarioSerializer ───────────────────────────────────────

def test_crear_serializer_valido():
    s = CrearUsuarioSerializer(data={"nombre": "Ana", "email": "ana@test.com", "rol": "ADMINISTRADOR"})
    assert s.is_valid(), s.errors


def test_crear_serializer_campos_obligatorios():
    s = CrearUsuarioSerializer(data={})
    assert not s.is_valid()
    assert "nombre" in s.errors
    assert "email" in s.errors
    assert "rol" in s.errors


def test_crear_serializer_rol_invalido():
    s = CrearUsuarioSerializer(data={"nombre": "X", "email": "x@y.com", "rol": "JEFE"})
    assert not s.is_valid()
    assert "rol" in s.errors


def test_crear_serializer_correo_invalido():
    s = CrearUsuarioSerializer(data={"nombre": "X", "email": "no-es-correo", "rol": "ADMINISTRADOR"})
    assert not s.is_valid()
    assert "email" in s.errors


# ── Serializer: ActualizarUsuarioSerializer ───────────────────────────────────

def test_actualizar_serializer_todos_opcionales():
    s = ActualizarUsuarioSerializer(data={})
    assert s.is_valid(), s.errors


def test_actualizar_serializer_solo_nombre():
    s = ActualizarUsuarioSerializer(data={"nombre": "Nuevo Nombre"})
    assert s.is_valid(), s.errors
    assert s.validated_data == {"nombre": "Nuevo Nombre"}


def test_actualizar_serializer_rol_invalido():
    s = ActualizarUsuarioSerializer(data={"rol": "INVALIDO"})
    assert not s.is_valid()
    assert "rol" in s.errors


def test_actualizar_serializer_is_active_bool():
    s = ActualizarUsuarioSerializer(data={"is_active": False})
    assert s.is_valid(), s.errors
    assert s.validated_data["is_active"] is False


# ── Vista: GET /api/users/ ────────────────────────────────────────────────────

@patch("usuarios.views.servicios.listar_usuarios")
def test_listar_devuelve_200_para_admin(mock_listar):
    mock_listar.return_value = []
    request = factory.get("/api/users/")
    force_authenticate(request, user=_admin())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 200
    assert resp.data == []


def test_listar_devuelve_403_para_analista():
    request = factory.get("/api/users/")
    force_authenticate(request, user=_analista())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 403


def test_listar_devuelve_401_sin_autenticar():
    request = factory.get("/api/users/")
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 401


# ── Vista: POST /api/users/ ───────────────────────────────────────────────────

@patch("usuarios.views.registrar_auditoria")
@patch("usuarios.views.servicios.crear_usuario")
def test_crear_devuelve_201_con_contrasena_nula(mock_crear, mock_audit):
    mock_crear.return_value = _usuario_mock()
    request = factory.post(
        "/api/users/",
        {"nombre": "Carlos Ruiz", "email": "nuevo@test.com", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    force_authenticate(request, user=_admin())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 201
    assert "user" in resp.data
    assert resp.data["temporary_password"] is None
    mock_audit.assert_called_once()


@patch("usuarios.views.servicios.crear_usuario")
def test_crear_correo_duplicado_devuelve_400(mock_crear):
    mock_crear.side_effect = servicios.UsuarioYaExiste("email")
    request = factory.post(
        "/api/users/",
        {"nombre": "X", "email": "dup@test.com", "rol": "ANALISTA_CARTERA"},
        format="json",
    )
    force_authenticate(request, user=_admin())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 400
    assert "email" in resp.data


def test_crear_sin_campos_devuelve_400():
    request = factory.post("/api/users/", {}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 400
    assert "nombre" in resp.data and "email" in resp.data and "rol" in resp.data


def test_crear_rol_invalido_devuelve_400():
    request = factory.post(
        "/api/users/",
        {"nombre": "X", "email": "x@y.com", "rol": "SUPERADMIN"},
        format="json",
    )
    force_authenticate(request, user=_admin())
    resp = GestionUsuariosView.as_view()(request)
    assert resp.status_code == 400
    assert "rol" in resp.data


# ── Vista: GET /api/users/{id}/ ───────────────────────────────────────────────

@patch("usuarios.views.servicios.obtener_usuario")
def test_obtener_devuelve_200_para_admin(mock_obtener):
    mock_obtener.return_value = _usuario_mock(pk=10)
    request = factory.get("/api/users/10/")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=10)
    assert resp.status_code == 200
    assert resp.data["id"] == 10


@patch("usuarios.views.servicios.obtener_usuario")
def test_obtener_no_encontrado_devuelve_404(mock_obtener):
    mock_obtener.side_effect = servicios.UsuarioNoEncontrado()
    request = factory.get("/api/users/999/")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=999)
    assert resp.status_code == 404


# ── Vista: PATCH /api/users/{id}/ ────────────────────────────────────────────

@patch("usuarios.views.registrar_auditoria")
@patch("usuarios.views.servicios.actualizar_usuario")
def test_patch_devuelve_200(mock_actualizar, mock_audit):
    actualizado = _usuario_mock(pk=10)
    mock_actualizar.return_value = actualizado
    request = factory.patch("/api/users/10/", {"nombre": "Nuevo"}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=10)
    assert resp.status_code == 200
    mock_audit.assert_called_once()


@patch("usuarios.views.servicios.actualizar_usuario")
def test_patch_autodesactivacion_devuelve_400(mock_actualizar):
    mock_actualizar.side_effect = servicios.AutodesactivacionProhibida()
    request = factory.patch("/api/users/1/", {"is_active": False}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=1)
    assert resp.status_code == 400
    assert "is_active" in resp.data


@patch("usuarios.views.servicios.actualizar_usuario")
def test_patch_cambio_rol_propio_devuelve_400(mock_actualizar):
    mock_actualizar.side_effect = servicios.CambioRolProhibido()
    request = factory.patch("/api/users/1/", {"rol": "ANALISTA_CARTERA"}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=1)
    assert resp.status_code == 400
    assert "rol" in resp.data


@patch("usuarios.views.servicios.actualizar_usuario")
def test_patch_correo_duplicado_devuelve_400(mock_actualizar):
    mock_actualizar.side_effect = servicios.UsuarioYaExiste("email")
    request = factory.patch("/api/users/10/", {"email": "dup@test.com"}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=10)
    assert resp.status_code == 400
    assert "email" in resp.data


@patch("usuarios.views.servicios.actualizar_usuario")
def test_patch_usuario_no_encontrado_devuelve_404(mock_actualizar):
    mock_actualizar.side_effect = servicios.UsuarioNoEncontrado()
    request = factory.patch("/api/users/999/", {"nombre": "X"}, format="json")
    force_authenticate(request, user=_admin())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=999)
    assert resp.status_code == 404


def test_patch_devuelve_403_para_analista():
    request = factory.patch("/api/users/10/", {"nombre": "X"}, format="json")
    force_authenticate(request, user=_analista())
    resp = GestionUsuarioDetalleView.as_view()(request, pk=10)
    assert resp.status_code == 403
