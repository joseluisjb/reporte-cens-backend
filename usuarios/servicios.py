import secrets
import string

from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from usuarios.models import Rol, Usuario


class UsuarioYaExiste(Exception):
    def __init__(self, campo):
        self.campo = campo


class UsuarioNoEncontrado(Exception):
    pass


class AutodesactivacionProhibida(Exception):
    pass


class CambioRolProhibido(Exception):
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
    except IntegrityError:
        raise UsuarioYaExiste("email")
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
    return usuario


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
