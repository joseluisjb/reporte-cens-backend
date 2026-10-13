from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from hashlib import sha256

from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle

from usuarios.errores import MENSAJE_CSRF
from usuarios.models import normalizar_email


class AutenticacionSesion(SessionAuthentication):
    def authenticate_header(self, request):
        return "Session"

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied:
            raise PermissionDenied(MENSAJE_CSRF, code="csrf_failed")


class LimiteInicioSesion(AnonRateThrottle):
    scope = "login"


class LimiteInicioSesionPorCorreo(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view):
        datos = request.data
        correo = datos.get("email") if hasattr(datos, "get") else None
        if not isinstance(correo, str) or not correo.strip():
            return None
        huella = sha256(normalizar_email(correo).encode()).hexdigest()
        return f"throttle_login_correo_{huella}"
