from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) == "ADMINISTRADOR"


class EsAnalista(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) == "ANALISTA_CARTERA"


class EsAnalistaOAdministrador(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "rol", None) in ("ANALISTA_CARTERA", "ADMINISTRADOR")
