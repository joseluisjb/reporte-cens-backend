from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

_BACKENDS_NO_PRODUCCION = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
}


def verificar_email_backend_produccion(debug, backend):
    if not debug and backend in _BACKENDS_NO_PRODUCCION:
        raise ImproperlyConfigured(
            f"EMAIL_BACKEND está configurado como '{backend}', que no es apto para producción. "
            "Define DJANGO_EMAIL_BACKEND con un backend SMTP real o activa DEBUG=True para desarrollo."
        )


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "usuarios"

    def ready(self):
        from django.conf import settings
        verificar_email_backend_produccion(settings.DEBUG, settings.EMAIL_BACKEND)
