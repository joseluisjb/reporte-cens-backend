from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EsAnalista
from novedades import rectificaciones
from novedades.rectificaciones_serializers import (
    RectificacionConfirmarSerializer,
    RectificacionCreateSerializer,
    RectificacionSerializer,
)


class RectificacionesViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        resultado = rectificaciones.listar_rectificaciones()
        return Response(RectificacionSerializer(resultado, many=True).data)

    def create(self, request):
        serializer = RectificacionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = rectificaciones.crear_rectificacion(
                serializer.validated_data, usuario=request.user
            )
        except rectificaciones.CorteNoEncontrado:
            return Response(
                {"detail": "Corte no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except rectificaciones.CorteNoEnviado:
            return Response(
                {
                    "detail": (
                        "Solo se rectifican cortes ya enviados a TransUnion."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        except rectificaciones.ObligacionNoEncontrada:
            return Response(
                {"obligacion_id": ["La obligación no existe."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except rectificaciones.NovedadNoValida:
            return Response(
                {"novedad_id": ["La novedad debe ser una corrección de esta obligación."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except rectificaciones.RectificacionDatoInvalido as exc:
            return Response(
                {exc.campo: [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {"campo": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            RectificacionSerializer(resultado).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        serializer = RectificacionConfirmarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = rectificaciones.confirmar_rectificacion(
                int(pk),
                serializer.validated_data["confirmacion_tu"],
                usuario=request.user,
            )
        except rectificaciones.RectificacionNoEncontrada:
            return Response(
                {"detail": "Rectificación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except rectificaciones.RectificacionYaConfirmada:
            return Response(
                {"detail": "La rectificación ya está confirmada."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(RectificacionSerializer(resultado).data)
