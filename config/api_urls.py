from django.urls import path
from rest_framework.routers import DefaultRouter

from config.views import SaludView

router = DefaultRouter()

urlpatterns = [
    path("salud/", SaludView.as_view(), name="salud"),
] + router.urls
