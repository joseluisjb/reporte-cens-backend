from django.urls import path
from rest_framework.routers import DefaultRouter

from config.views import SaludView
from parametros.views import ConceptoViewSet, GrupoConceptoViewSet
from cartera.views import ExtraccionViewSet
from historial.views import ReporteViewSet, DeudorViewSet
from usuarios.views import (
    CambioContrasenaView,
    CierreSesionView,
    CsrfView,
    InicioSesionView,
    UsuarioActualView,
)

router = DefaultRouter()
router.register("conceptos", ConceptoViewSet, basename="concepto")
router.register("grupos-conceptos", GrupoConceptoViewSet, basename="grupo-concepto")
router.register("extracciones", ExtraccionViewSet, basename="extraccion")
router.register("historial/reportes", ReporteViewSet, basename="historial-reporte")
router.register("historial/deudores", DeudorViewSet, basename="historial-deudor")

urlpatterns = [
    path("salud/", SaludView.as_view(), name="salud"),
    path("auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", InicioSesionView.as_view(), name="auth-login"),
    path("auth/logout/", CierreSesionView.as_view(), name="auth-logout"),
    path("auth/me/", UsuarioActualView.as_view(), name="auth-me"),
    path("auth/change-password/", CambioContrasenaView.as_view(), name="auth-change-password"),
] + router.urls
