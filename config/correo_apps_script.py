"""Backend de correo de Django que envía por HTTPS a un script de Google Apps Script.

Sirve cuando el servidor no puede usar SMTP (por ejemplo, Render gratuito bloquea los
puertos 25, 465 y 587) y no se dispone de un dominio propio para un proveedor de correo.
El script corre en la cuenta de Gmail del proyecto y envía con MailApp.

Variables de entorno (se leen en settings.py):
  DJANGO_APPS_SCRIPT_URL    URL de la aplicación web desplegada del script
  DJANGO_APPS_SCRIPT_TOKEN  secreto compartido con el script
  DJANGO_EMAIL_TIMEOUT      segundos de espera (opcional)
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ErrorCorreoRemoto(OSError):
    """El script respondió, pero no pudo enviar el correo."""


def _nombre_remitente(from_email):
    # "NexoVolt <correo@x.com>" -> "NexoVolt"
    if from_email and "<" in from_email:
        return from_email.split("<", 1)[0].strip().strip('"') or "NexoVolt"
    return "NexoVolt"


class AppsScriptEmailBackend(BaseEmailBackend):
    def _enviar(self, url, token, mensaje, destinatario):
        carga = json.dumps({
            "token": token,
            "to": destinatario,
            "subject": mensaje.subject,
            "body": mensaje.body,
            "name": _nombre_remitente(mensaje.from_email),
        }).encode("utf-8")
        solicitud = urllib.request.Request(
            url, data=carga, method="POST",
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        timeout = getattr(settings, "EMAIL_TIMEOUT", None) or 10
        # Apps Script responde con una redirección; urllib la sigue sola.
        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            cuerpo = respuesta.read().decode("utf-8", errors="replace")
        try:
            datos = json.loads(cuerpo)
        except ValueError:
            raise ErrorCorreoRemoto("Respuesta inesperada del servicio de correo.")
        if not datos.get("ok"):
            # No se incluye el mensaje original para no filtrar contenido en los logs.
            raise ErrorCorreoRemoto("El servicio de correo rechazó el envío.")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        url = getattr(settings, "APPS_SCRIPT_URL", "")
        token = getattr(settings, "APPS_SCRIPT_TOKEN", "")
        if not url or not token:
            if self.fail_silently:
                return 0
            raise ErrorCorreoRemoto("Falta configurar APPS_SCRIPT_URL o APPS_SCRIPT_TOKEN.")
        enviados = 0
        for mensaje in email_messages:
            if not mensaje.to:
                continue
            try:
                # Un envío por destinatario, para no mostrar direcciones ajenas.
                for destinatario in mensaje.to:
                    self._enviar(url, token, mensaje, destinatario)
                enviados += 1
            except (urllib.error.URLError, OSError, TimeoutError):
                if not self.fail_silently:
                    raise
        return enviados