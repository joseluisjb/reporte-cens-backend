from rest_framework.test import APIRequestFactory

from config.views import SaludView


def test_salud_responde_ok():
    factory = APIRequestFactory()
    request = factory.get("/api/salud/")
    view = SaludView.as_view()
    response = view(request)
    assert response.status_code == 200
    assert response.data == {"estado": "ok"}
