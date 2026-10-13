import secrets
import string

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from usuarios.models import Rol, Usuario, normalizar_email


class UsuarioYaExiste(Exception):
    def __init__(self, campo):
        self.campo = campo


class UsuarioNoEncontrado(Exception):
    pass


class AutodesactivacionProhibida(Exception):
    pass


class CambioRolProhibido(Exception):
    pass


class TokenInvalido(Exception):
    pass


class EnvioCorreoFallido(Exception):
    pass


_SIMBOLOS = "!@#$%^&*()-_=+"
_ALFABETO = string.ascii_letters + string.digits + _SIMBOLOS


def _generar_contrasena_temporal():
    obligatorios = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SIMBOLOS),
    ]
    resto = [secrets.choice(_ALFABETO) for _ in range(8)]
    combinado = obligatorios + resto
    secrets.SystemRandom().shuffle(combinado)
    return "".join(combinado)


def listar_usuarios():
    return list(Usuario.objects.all().order_by("id"))


def obtener_usuario(usuario_id):
    try:
        return Usuario.objects.get(pk=usuario_id)
    except Usuario.DoesNotExist:
        raise UsuarioNoEncontrado()


def crear_usuario(datos):
    contrasena = _generar_contrasena_temporal()
    try:
        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                email=datos["email"],
                password=contrasena,
                nombre=datos["nombre"],
                rol=datos["rol"],
                must_change_password=True,
            )
            send_mail(
                subject="Tu cuenta en NexoVolt",
                message=(
                    f"Hola {usuario.nombre},\n\n"
                    "Tu cuenta en NexoVolt ha sido creada. Tu contraseña temporal es:\n\n"
                    f"    {contrasena}\n\n"
                    "Debes cambiarla al iniciar sesión por primera vez.\n\n"
                    "Si no solicitaste esta cuenta, contacta al administrador."
                ),
                from_email=None,
                recipient_list=[usuario.email],
                fail_silently=False,
            )
    except IntegrityError:
        raise UsuarioYaExiste("email")
    except Exception as exc:
        raise EnvioCorreoFallido() from exc
    return usuario


def solicitar_recuperacion_password(email):
    try:
        usuario = Usuario.objects.get(email=normalizar_email(email), is_active=True)
    except Usuario.DoesNotExist:
        return

    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    token_completo = f"{uid}.{token}"
    enlace = f"{settings.FRONTEND_URL}/restablecer?token={token_completo}"

    send_mail(
        subject="Recuperación de contraseña — NexoVolt",
        message=(
            f"Hola {usuario.nombre},\n\n"
            "Recibimos una solicitud para restablecer tu contraseña en NexoVolt.\n\n"
            f"Usa el siguiente enlace (válido por 30 minutos):\n\n    {enlace}\n\n"
            "Si no realizaste esta solicitud, ignora este correo."
        ),
        from_email=None,
        recipient_list=[usuario.email],
        fail_silently=False,
    )


def restablecer_password(token_completo, nueva_password):
    partes = token_completo.split(".", 1)
    if len(partes) != 2:
        raise TokenInvalido()
    uid_b64, token = partes

    try:
        uid = force_str(urlsafe_base64_decode(uid_b64))
        usuario = Usuario.objects.get(pk=uid)
    except (ValueError, TypeError, OverflowError, Usuario.DoesNotExist):
        raise TokenInvalido()

    if not default_token_generator.check_token(usuario, token):
        raise TokenInvalido()

    usuario.set_password(nueva_password)
    usuario.must_change_password = False
    usuario.save(update_fields=["password", "must_change_password"])


def actualizar_usuario(usuario_id, datos, solicitante):
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
    except Usuario.DoesNotExist:
        raise UsuarioNoEncontrado()

    if "is_active" in datos and not datos["is_active"] and solicitante.pk == usuario.pk:
        raise AutodesactivacionProhibida()

    if "rol" in datos and datos["rol"] != Rol.ADMINISTRADOR and solicitante.pk == usuario.pk:
        raise CambioRolProhibido()

    for campo in ("nombre", "email", "rol", "is_active"):
        if campo in datos:
            setattr(usuario, campo, datos[campo])

    try:
        with transaction.atomic():
            usuario.save()
    except IntegrityError:
        raise UsuarioYaExiste("email")

    return usuario
