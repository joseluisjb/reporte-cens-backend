from rest_framework import status
from rest_framework.response import Response

_LIMITE_MAX = 100
_LIMITE_DEFAULT = 20
_DESPLAZAMIENTO_DEFAULT = 0
_MSG_TIPO = "Los parámetros limite y desplazamiento deben ser enteros."
_MSG_RANGO = "El límite debe ser mayor que 0 y el desplazamiento no puede ser negativo."


def parsear_paginacion(request):
    """Retorna (limite, desplazamiento, error_response). Si error_response no es None, retornarlo directamente."""
    try:
        limite = int(request.query_params.get("limite", _LIMITE_DEFAULT))
        desplazamiento = int(request.query_params.get("desplazamiento", _DESPLAZAMIENTO_DEFAULT))
    except (ValueError, TypeError):
        return None, None, Response({"detail": _MSG_TIPO}, status=status.HTTP_400_BAD_REQUEST)
    if limite < 1 or desplazamiento < 0:
        return None, None, Response({"detail": _MSG_RANGO}, status=status.HTTP_400_BAD_REQUEST)
    limite = min(limite, _LIMITE_MAX)
    return limite, desplazamiento, None
