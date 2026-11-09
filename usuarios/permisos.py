from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) == "ADMINISTRADOR"


class EsAnalistaOAdministrador(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) in ("ANALISTA_CARTERA", "ADMINISTRADOR")
