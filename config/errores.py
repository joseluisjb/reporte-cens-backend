from django.http import JsonResponse


def no_encontrado(request, exception):
    return JsonResponse({"detail": "Recurso no encontrado."}, status=404)
