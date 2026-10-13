from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.throttling import AnonRateThrottle

from usuarios.errores import MENSAJE_CSRF


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
