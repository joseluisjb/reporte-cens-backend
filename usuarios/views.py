from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.auditoria import registrar_auditoria
from usuarios.autenticacion import LimiteInicioSesion, LimiteInicioSesionPorCorreo, LimiteRecuperacion
from usuarios.permisos import EsAdministrador
from usuarios.serializers import (
    ActualizarUsuarioSerializer,
    CambioContrasenaSerializer,
    CrearUsuarioSerializer,
    InicioSesionSerializer,
    RecuperarPasswordSerializer,
    RestablecerPasswordSerializer,
    UsuarioSerializer,
)
import usuarios.servicios as servicios


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


@method_decorator(csrf_protect, name="dispatch")
class RecuperarPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LimiteRecuperacion]

    def post(self, request):
        serializer = RecuperarPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        servicios.solicitar_recuperacion_password(serializer.validated_data["email"])
        return Response(
            {"detail": "Si el correo está registrado, recibirás un enlace."},
            status=status.HTTP_202_ACCEPTED,
        )


@method_decorator(csrf_protect, name="dispatch")
class RestablecerPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LimiteRecuperacion]

    def post(self, request):
        serializer = RestablecerPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            servicios.restablecer_password(
                serializer.validated_data["token"],
                serializer.validated_data["new_password"],
            )
        except servicios.TokenInvalido:
            raise ValidationError({"token": ["El enlace no es válido o ya venció."]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class GestionUsuariosView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        usuarios = servicios.listar_usuarios()
        return Response(UsuarioSerializer(usuarios, many=True).data)

    def post(self, request):
        serializer = CrearUsuarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            usuario = servicios.crear_usuario(serializer.validated_data)
        except servicios.UsuarioYaExiste as exc:
            raise ValidationError({exc.campo: ["Ya existe un usuario con ese correo."]})
        registrar_auditoria(
            "CREAR", "USUARIO", usuario.pk,
            f"Usuario {usuario.email} creado con rol {usuario.rol}",
            request.user.pk,
        )
        return Response(
            {"user": UsuarioSerializer(usuario).data, "temporary_password": None},
            status=status.HTTP_201_CREATED,
        )


class GestionUsuarioDetalleView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request, pk):
        try:
            usuario = servicios.obtener_usuario(pk)
        except servicios.UsuarioNoEncontrado:
            raise NotFound()
        return Response(UsuarioSerializer(usuario).data)

    def patch(self, request, pk):
        serializer = ActualizarUsuarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            usuario = servicios.actualizar_usuario(pk, serializer.validated_data, request.user)
        except servicios.UsuarioNoEncontrado:
            raise NotFound()
        except servicios.AutodesactivacionProhibida:
            raise ValidationError({"is_active": ["No puedes desactivar tu propio usuario."]})
        except servicios.CambioRolProhibido:
            raise ValidationError({"rol": ["No puedes cambiar tu propio rol."]})
        except servicios.UsuarioYaExiste as exc:
            raise ValidationError({exc.campo: ["Ya existe un usuario con ese correo."]})
        registrar_auditoria(
            "EDITAR", "USUARIO", usuario.pk,
            f"Usuario {usuario.email} actualizado: {list(serializer.validated_data)}",
            request.user.pk,
        )
        return Response(UsuarioSerializer(usuario).data)
