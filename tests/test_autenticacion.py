from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from usuarios.models import Rol, Usuario

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura1"
CLAVE_NUEVA = "OtraClave2026"
CORREO_ANALISTA = "jperez@example.com"
CORREO_ADMIN = "rmartinez@example.com"
CONCEPTO = {
    "codigo_concepto": 30,
    "descripcion": "Cuota",
    "reportable": "S",
    "observacion": None,
}


@pytest.fixture(autouse=True)
def limpiar_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def analista():
    return Usuario.objects.create_user(
        CORREO_ANALISTA, CLAVE, nombre="Juan Pérez", must_change_password=False
    )


@pytest.fixture
def administrador():
    return Usuario.objects.create_superuser(CORREO_ADMIN, CLAVE, nombre="Rosa Martínez")


@pytest.fixture
def usuario_temporal():
    return Usuario.objects.create_user("nuevo@example.com", CLAVE, nombre="Usuario Nuevo")


def cliente_con_csrf():
    cliente = APIClient(enforce_csrf_checks=True)
    cliente.get("/api/auth/csrf/")
    return cliente


def enviar(cliente, ruta, datos=None):
    return cliente.post(
        ruta,
        datos or {},
        format="json",
        HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value,
    )


def iniciar_sesion(email, password=CLAVE):
    cliente = cliente_con_csrf()
    respuesta = enviar(cliente, "/api/auth/login/", {"email": email, "password": password})
    return cliente, respuesta


def test_crear_usuario_guarda_el_correo_en_minusculas():
    usuario = Usuario.objects.create_user("  JPerez@Example.COM ", CLAVE, nombre="Juan Pérez")
    assert usuario.email == "jperez@example.com"


def test_guardar_normaliza_el_correo(analista):
    analista.email = "OTRO@Example.com"
    analista.save()
    analista.refresh_from_db()
    assert analista.email == "otro@example.com"


def test_correo_repetido_con_otras_mayusculas_se_rechaza(analista):
    with pytest.raises(IntegrityError):
        Usuario.objects.create_user("JPEREZ@example.com", CLAVE, nombre="Otro")


def test_nombre_es_obligatorio():
    with pytest.raises(ValueError):
        Usuario.objects.create_user("sinnombre@example.com", CLAVE, nombre="   ")


def test_correo_es_obligatorio():
    with pytest.raises(ValueError):
        Usuario.objects.create_user("", CLAVE, nombre="Sin Correo")


def test_usuario_nuevo_es_analista_y_debe_cambiar_la_contrasena(usuario_temporal):
    assert usuario_temporal.rol == Rol.ANALISTA_CARTERA
    assert usuario_temporal.must_change_password is True
    assert usuario_temporal.is_active is True
    assert usuario_temporal.is_staff is False


def test_superusuario_es_administrador(administrador):
    assert administrador.rol == Rol.ADMINISTRADOR
    assert administrador.is_staff is True
    assert administrador.must_change_password is False
    assert administrador.has_perm("usuarios.add_usuario") is True


def test_superusuario_ignora_un_rol_distinto():
    usuario = Usuario.objects.create_superuser(
        CORREO_ADMIN, CLAVE, nombre="Rosa Martínez", rol=Rol.ANALISTA_CARTERA
    )
    assert usuario.rol == Rol.ADMINISTRADOR


def test_comando_createsuperuser_crea_el_administrador_inicial(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", CLAVE)
    call_command(
        "createsuperuser", interactive=False, email="Inicial@Example.com", nombre="Admin Inicial"
    )
    usuario = Usuario.objects.get(email="inicial@example.com")
    assert usuario.rol == Rol.ADMINISTRADOR
    assert usuario.check_password(CLAVE)


def test_contrasena_se_guarda_con_argon2(analista):
    assert analista.password.startswith("argon2")
    assert CLAVE not in analista.password
    assert analista.check_password(CLAVE)


@pytest.mark.parametrize(
    "password, mensaje",
    [
        ("Corta1A", "La contraseña es demasiado corta. Debe contener por lo menos 8 caracteres."),
        ("sinmayuscula1", "La contraseña debe tener al menos una mayúscula."),
        ("SinNumeroAqui", "La contraseña debe tener al menos un número."),
    ],
)
def test_reglas_de_contrasena(password, mensaje):
    with pytest.raises(ValidationError) as error:
        validate_password(password)
    assert mensaje in error.value.messages


def test_contrasena_valida_cumple_las_reglas():
    validate_password(CLAVE)


def test_configuracion_de_sesion():
    assert settings.SESSION_COOKIE_AGE == 600
    assert settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.CSRF_COOKIE_HTTPONLY is False


def test_csrf_entrega_la_cookie():
    respuesta = APIClient().get("/api/auth/csrf/")
    assert respuesta.status_code == 204
    assert respuesta.cookies["csrftoken"].value
    assert respuesta.cookies["csrftoken"]["samesite"] == "Lax"


def test_login_correcto_devuelve_el_usuario_y_abre_la_sesion(analista):
    cliente, respuesta = iniciar_sesion(CORREO_ANALISTA)
    assert respuesta.status_code == 200
    usuario = respuesta.json()["user"]
    assert set(usuario) == {
        "id",
        "nombre",
        "email",
        "rol",
        "is_active",
        "last_login",
        "must_change_password",
    }
    assert usuario["id"] == analista.id
    assert usuario["nombre"] == "Juan Pérez"
    assert usuario["email"] == CORREO_ANALISTA
    assert usuario["rol"] == "ANALISTA_CARTERA"
    assert usuario["is_active"] is True
    assert usuario["must_change_password"] is False
    assert usuario["last_login"] is not None
    cookie = respuesta.cookies["sessionid"]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Lax"
    assert cookie["max-age"] == 600
    assert cliente.get("/api/auth/me/").status_code == 200


def test_login_no_devuelve_la_contrasena(analista):
    _, respuesta = iniciar_sesion(CORREO_ANALISTA)
    assert "password" not in respuesta.json()["user"]
    assert CLAVE not in respuesta.content.decode()


def test_login_acepta_el_correo_en_mayusculas(analista):
    _, respuesta = iniciar_sesion("JPEREZ@EXAMPLE.COM")
    assert respuesta.status_code == 200


def test_login_con_contrasena_incorrecta(analista):
    cliente, respuesta = iniciar_sesion(CORREO_ANALISTA, "ClaveMala1")
    assert respuesta.status_code == 401
    assert respuesta.json() == {
        "detail": "Correo o contraseña incorrectos.",
        "code": "authentication_failed",
    }
    assert "sessionid" not in respuesta.cookies
    assert cliente.get("/api/auth/me/").status_code == 401


def test_login_con_correo_inexistente_responde_igual(analista):
    _, respuesta = iniciar_sesion("nadie@example.com")
    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Correo o contraseña incorrectos."


def test_login_de_usuario_desactivado_con_contrasena_correcta(analista):
    Usuario.objects.filter(pk=analista.pk).update(is_active=False)
    cliente, respuesta = iniciar_sesion(CORREO_ANALISTA)
    assert respuesta.status_code == 403
    assert respuesta.json() == {
        "detail": "Tu usuario está desactivado. Contacta al administrador.",
        "code": "user_inactive",
    }
    assert cliente.get("/api/auth/me/").status_code == 401


def test_login_de_usuario_desactivado_con_contrasena_incorrecta_no_revela_nada(analista):
    Usuario.objects.filter(pk=analista.pk).update(is_active=False)
    _, respuesta = iniciar_sesion(CORREO_ANALISTA, "ClaveMala1")
    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "Correo o contraseña incorrectos."


def test_login_sin_campos_responde_400_en_espanol():
    cliente = cliente_con_csrf()
    respuesta = enviar(cliente, "/api/auth/login/")
    assert respuesta.status_code == 400
    assert respuesta.json() == {
        "email": ["Este campo es requerido."],
        "password": ["Este campo es requerido."],
    }


def test_login_con_correo_mal_escrito_responde_400():
    cliente = cliente_con_csrf()
    respuesta = enviar(cliente, "/api/auth/login/", {"email": "no-es-correo", "password": CLAVE})
    assert respuesta.status_code == 400
    assert respuesta.json() == {"email": ["Introduzca una dirección de correo electrónico válida."]}


def test_login_sin_token_csrf_se_rechaza(analista):
    cliente = APIClient(enforce_csrf_checks=True)
    respuesta = cliente.post(
        "/api/auth/login/", {"email": CORREO_ANALISTA, "password": CLAVE}, format="json"
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "csrf_failed"
    assert "sessionid" not in respuesta.cookies


def test_login_limita_los_intentos(analista):
    cliente = cliente_con_csrf()
    datos = {"email": CORREO_ANALISTA, "password": "ClaveMala1"}
    for _ in range(10):
        assert enviar(cliente, "/api/auth/login/", datos).status_code == 401
    respuesta = enviar(cliente, "/api/auth/login/", datos)
    assert respuesta.status_code == 429
    assert respuesta.json() == {
        "detail": "Demasiados intentos. Intenta de nuevo en unos minutos.",
        "code": "throttled",
    }


def intento_fallido(cliente, email, **extra):
    return cliente.post(
        "/api/auth/login/",
        {"email": email, "password": "ClaveMala1"},
        format="json",
        HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value,
        **extra,
    )


def test_limite_de_login_ignora_x_forwarded_for_inventado():
    cliente = cliente_con_csrf()
    for i in range(10):
        respuesta = intento_fallido(
            cliente, f"persona{i}@example.com", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}"
        )
        assert respuesta.status_code == 401
    respuesta = intento_fallido(
        cliente, "persona10@example.com", HTTP_X_FORWARDED_FOR="10.0.0.10"
    )
    assert respuesta.status_code == 429


def test_limite_de_login_por_correo_aunque_cambie_la_ip(analista):
    cliente = cliente_con_csrf()
    for i in range(10):
        respuesta = intento_fallido(cliente, CORREO_ANALISTA, REMOTE_ADDR=f"10.0.0.{i}")
        assert respuesta.status_code == 401
    respuesta = intento_fallido(cliente, CORREO_ANALISTA.upper(), REMOTE_ADDR="10.0.0.10")
    assert respuesta.status_code == 429
    assert respuesta.json()["code"] == "throttled"


def test_limite_por_correo_no_bloquea_a_otros_usuarios(analista, administrador):
    cliente = cliente_con_csrf()
    for i in range(10):
        intento_fallido(cliente, CORREO_ANALISTA, REMOTE_ADDR=f"10.0.0.{i}")
    otro = cliente_con_csrf()
    respuesta = otro.post(
        "/api/auth/login/",
        {"email": CORREO_ADMIN, "password": CLAVE},
        format="json",
        HTTP_X_CSRFTOKEN=otro.cookies["csrftoken"].value,
        REMOTE_ADDR="10.0.1.1",
    )
    assert respuesta.status_code == 200


def test_limite_de_login_con_proxy_usa_la_ip_que_agrega_el_proxy(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    cliente = cliente_con_csrf()
    for i in range(10):
        respuesta = intento_fallido(
            cliente, f"persona{i}@example.com", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.7"
        )
        assert respuesta.status_code == 401
    bloqueada = intento_fallido(
        cliente, "persona10@example.com", HTTP_X_FORWARDED_FOR="10.0.0.10, 203.0.113.7"
    )
    assert bloqueada.status_code == 429
    otra_ip = intento_fallido(
        cliente, "persona11@example.com", HTTP_X_FORWARDED_FOR="10.0.0.11, 203.0.113.8"
    )
    assert otra_ip.status_code == 401


def test_login_con_cuerpo_que_no_es_objeto_responde_400():
    cliente = cliente_con_csrf()
    respuesta = cliente.post(
        "/api/auth/login/",
        ["no", "es", "objeto"],
        format="json",
        HTTP_X_CSRFTOKEN=cliente.cookies["csrftoken"].value,
    )
    assert respuesta.status_code == 400


def test_panel_admin_no_esta_expuesto():
    assert APIClient().get("/admin/login/").status_code == 404
    assert APIClient().get("/admin/").status_code == 404


def test_me_sin_sesion_responde_401():
    respuesta = APIClient().get("/api/auth/me/")
    assert respuesta.status_code == 401
    assert respuesta["WWW-Authenticate"] == "Session"
    assert respuesta.json() == {
        "detail": "Tu sesión venció. Inicia sesión de nuevo.",
        "code": "not_authenticated",
    }


def test_me_devuelve_el_usuario_de_la_sesion(administrador):
    cliente, _ = iniciar_sesion(CORREO_ADMIN)
    respuesta = cliente.get("/api/auth/me/")
    assert respuesta.status_code == 200
    assert respuesta.json()["user"]["email"] == CORREO_ADMIN
    assert respuesta.json()["user"]["rol"] == "ADMINISTRADOR"


def test_logout_invalida_la_sesion_en_el_servidor(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    clave_sesion = cliente.cookies["sessionid"].value
    respuesta = enviar(cliente, "/api/auth/logout/")
    assert respuesta.status_code == 204
    assert not Session.objects.filter(session_key=clave_sesion).exists()
    assert cliente.get("/api/auth/me/").status_code == 401


def test_cookie_de_sesion_robada_no_sirve_despues_del_logout(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    clave_sesion = cliente.cookies["sessionid"].value
    enviar(cliente, "/api/auth/logout/")
    otro = APIClient()
    otro.cookies["sessionid"] = clave_sesion
    assert otro.get("/api/auth/me/").status_code == 401


def test_logout_sin_sesion_responde_401():
    cliente = cliente_con_csrf()
    assert enviar(cliente, "/api/auth/logout/").status_code == 401


def test_logout_sin_token_csrf_se_rechaza(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = cliente.post("/api/auth/logout/", {}, format="json")
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "csrf_failed"
    assert cliente.get("/api/auth/me/").status_code == 200


def test_sesion_vencida_por_inactividad_responde_401(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
    respuesta = cliente.get("/api/auth/me/")
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "not_authenticated"


def test_cada_peticion_renueva_la_sesion(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    Session.objects.update(expire_date=timezone.now() + timedelta(seconds=30))
    respuesta = cliente.get("/api/auth/me/")
    assert respuesta.status_code == 200
    assert respuesta.cookies["sessionid"]["max-age"] == 600
    restante = Session.objects.get().expire_date - timezone.now()
    assert restante > timedelta(minutes=9)


def test_usuario_desactivado_pierde_la_sesion_abierta(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    Usuario.objects.filter(pk=analista.pk).update(is_active=False)
    assert cliente.get("/api/auth/me/").status_code == 401


def test_endpoint_de_negocio_sin_sesion_responde_401():
    respuesta = APIClient().get("/api/conceptos/")
    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "not_authenticated"


def test_analista_puede_leer_conceptos(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    with patch("parametros.views.servicios.listar_conceptos", return_value=[CONCEPTO]):
        respuesta = cliente.get("/api/conceptos/")
    assert respuesta.status_code == 200
    assert respuesta.json()[0]["codigo"] == 30


def test_analista_recibe_403_en_endpoint_de_administracion(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    with patch("parametros.views.servicios.crear_concepto") as crear:
        respuesta = enviar(cliente, "/api/conceptos/", {"codigo": 30, "descripcion": "Cuota"})
    assert respuesta.status_code == 403
    assert respuesta.json() == {
        "detail": "No tienes permiso para realizar esta acción.",
        "code": "permission_denied",
    }
    crear.assert_not_called()


def test_administrador_puede_usar_endpoint_de_administracion(administrador):
    cliente, _ = iniciar_sesion(CORREO_ADMIN)
    with patch("parametros.views.servicios.crear_concepto", return_value=CONCEPTO) as crear:
        respuesta = enviar(cliente, "/api/conceptos/", {"codigo": 30, "descripcion": "Cuota"})
    assert respuesta.status_code == 201
    crear.assert_called_once()


def test_contrasena_temporal_bloquea_el_resto_de_la_api(usuario_temporal):
    cliente, respuesta = iniciar_sesion("nuevo@example.com")
    assert respuesta.status_code == 200
    assert respuesta.json()["user"]["must_change_password"] is True
    with patch("parametros.views.servicios.listar_conceptos") as listar:
        bloqueada = cliente.get("/api/conceptos/")
    assert bloqueada.status_code == 403
    assert bloqueada.json() == {
        "detail": "Debes cambiar tu contraseña temporal antes de continuar.",
        "code": "password_change_required",
    }
    listar.assert_not_called()
    assert cliente.get("/api/auth/me/").status_code == 200


def test_contrasena_temporal_permite_cerrar_sesion(usuario_temporal):
    cliente, _ = iniciar_sesion("nuevo@example.com")
    assert enviar(cliente, "/api/auth/logout/").status_code == 204


def test_cambiar_la_contrasena_temporal_desbloquea_la_api(usuario_temporal):
    cliente, _ = iniciar_sesion("nuevo@example.com")
    respuesta = enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert respuesta.status_code == 204
    usuario_temporal.refresh_from_db()
    assert usuario_temporal.must_change_password is False
    assert usuario_temporal.check_password(CLAVE_NUEVA)
    assert usuario_temporal.password.startswith("argon2")
    assert cliente.get("/api/auth/me/").json()["user"]["must_change_password"] is False
    with patch("parametros.views.servicios.listar_conceptos", return_value=[]):
        assert cliente.get("/api/conceptos/").status_code == 200


def test_cambio_de_contrasena_mantiene_la_sesion_y_cambia_el_acceso(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert respuesta.status_code == 204
    assert cliente.get("/api/auth/me/").status_code == 200
    assert iniciar_sesion(CORREO_ANALISTA, CLAVE)[1].status_code == 401
    assert iniciar_sesion(CORREO_ANALISTA, CLAVE_NUEVA)[1].status_code == 200


def test_cambio_de_contrasena_cierra_las_otras_sesiones(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    otro, _ = iniciar_sesion(CORREO_ANALISTA)
    enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert otro.get("/api/auth/me/").status_code == 401


def test_cambio_con_contrasena_actual_incorrecta(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": "ClaveMala1", "new_password": CLAVE_NUEVA},
    )
    assert respuesta.status_code == 400
    assert respuesta.json() == {"current_password": ["La contraseña actual no es correcta."]}
    analista.refresh_from_db()
    assert analista.check_password(CLAVE)


@pytest.mark.parametrize(
    "nueva, mensaje",
    [
        ("Corta1A", "La contraseña es demasiado corta. Debe contener por lo menos 8 caracteres."),
        ("sinmayuscula1", "La contraseña debe tener al menos una mayúscula."),
        ("SinNumeroAqui", "La contraseña debe tener al menos un número."),
        (CLAVE, "La nueva contraseña debe ser distinta de la actual."),
    ],
)
def test_cambio_con_contrasena_nueva_invalida(analista, nueva, mensaje):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": nueva},
    )
    assert respuesta.status_code == 400
    assert mensaje in respuesta.json()["new_password"]
    analista.refresh_from_db()
    assert analista.check_password(CLAVE)


def test_cambio_sin_campos_responde_400_en_espanol(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = enviar(cliente, "/api/auth/change-password/")
    assert respuesta.status_code == 400
    assert respuesta.json() == {
        "current_password": ["Este campo es requerido."],
        "new_password": ["Este campo es requerido."],
    }


def test_cambio_de_contrasena_sin_sesion_responde_401():
    cliente = cliente_con_csrf()
    respuesta = enviar(
        cliente,
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert respuesta.status_code == 401


def test_cambio_de_contrasena_sin_token_csrf_se_rechaza(analista):
    cliente, _ = iniciar_sesion(CORREO_ANALISTA)
    respuesta = cliente.post(
        "/api/auth/change-password/",
        {"current_password": CLAVE, "new_password": CLAVE_NUEVA},
        format="json",
    )
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "csrf_failed"
    analista.refresh_from_db()
    assert analista.check_password(CLAVE)


def test_salud_sigue_publica():
    respuesta = APIClient().get("/api/salud/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
