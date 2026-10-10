from django.urls import path
from rest_framework.routers import DefaultRouter

from config.views import SaludView
from parametros.views import ConceptoViewSet

router = DefaultRouter()
router.register("conceptos", ConceptoViewSet, basename="concepto")

urlpatterns = [
    path("salud/", SaludView.as_view(), name="salud"),
] + router.urls
