from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.autenticacion import LimiteInicioSesion, LimiteInicioSesionPorCorreo
from usuarios.serializers import (
    CambioContrasenaSerializer,
    InicioSesionSerializer,
    UsuarioSerializer,
)


def _sobre_usuario(usuario):
    return {"user": UsuarioSerializer(usuario).data}


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class InicioSesionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LimiteInicioSesion, LimiteInicioSesionPorCorreo]

    def post(self, request):
        serializer = InicioSesionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if usuario is None:
            return Response(
                {"detail": "Correo o contraseña incorrectos.", "code": "authentication_failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not usuario.is_active:
            return Response(
                {
                    "detail": "Tu usuario está desactivado. Contacta al administrador.",
                    "code": "user_inactive",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        login(request, usuario)
        return Response(_sobre_usuario(usuario))


class CierreSesionView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioActualView(APIView):
    def get(self, request):
        return Response(_sobre_usuario(request.user))


class CambioContrasenaView(APIView):
    def post(self, request):
        serializer = CambioContrasenaSerializer(
            data=request.data, context={"usuario": request.user}
        )
        serializer.is_valid(raise_exception=True)
        usuario = request.user
        usuario.set_password(serializer.validated_data["new_password"])
        usuario.must_change_password = False
        usuario.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, usuario)
        return Response(status=status.HTTP_204_NO_CONTENT)
