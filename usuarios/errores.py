from django.http import JsonResponse

MENSAJE_CSRF = "No se pudo verificar la seguridad de la solicitud. Recarga la página e intenta de nuevo."
MENSAJE_CAMBIO_CONTRASENA = "Debes cambiar tu contraseña temporal antes de continuar."

MENSAJES_POR_CODIGO = {
    "not_authenticated": "Tu sesión venció. Inicia sesión de nuevo.",
    "permission_denied": "No tienes permiso para realizar esta acción.",
    "throttled": "Demasiados intentos. Intenta de nuevo en unos minutos.",
}


def manejador_errores(exc, context):
    from rest_framework.views import exception_handler

    respuesta = exception_handler(exc, context)
    if respuesta is None or not isinstance(respuesta.data, dict):
        return respuesta
    detalle = respuesta.data.get("detail")
    codigo = getattr(detalle, "code", None)
    if codigo is None:
        return respuesta
    respuesta.data = {
        "detail": MENSAJES_POR_CODIGO.get(codigo, str(detalle)),
        "code": codigo,
    }
    return respuesta


def csrf_fallido(request, reason=""):
    return JsonResponse({"detail": MENSAJE_CSRF, "code": "csrf_failed"}, status=403)
