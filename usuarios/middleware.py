from django.http import JsonResponse

from usuarios.errores import MENSAJE_CAMBIO_CONTRASENA

RUTA_API = "/api/"
RUTAS_LIBRES = ("/api/auth/", "/api/salud/")


class CambioContrasenaObligatorio:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if (
            request.path.startswith(RUTA_API)
            and not request.path.startswith(RUTAS_LIBRES)
            and usuario is not None
            and usuario.is_authenticated
            and usuario.must_change_password
        ):
            return JsonResponse(
                {"detail": MENSAJE_CAMBIO_CONTRASENA, "code": "password_change_required"},
                status=403,
            )
        return self.get_response(request)
