from rest_framework import status, viewsets
from rest_framework.response import Response

from config.estados_tu import nombre_estado
from usuarios.permisos import EsAnalista
from novedades import refinanciaciones
from novedades.refinanciaciones_serializers import (
    RefinanciacionCreateSerializer,
    RefinanciacionSerializer,
)

class RefinanciacionesViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        resultado = refinanciaciones.listar_refinanciaciones()
        return Response(RefinanciacionSerializer(resultado, many=True).data)

    def create(self, request):
        serializer = RefinanciacionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = refinanciaciones.crear_refinanciacion(
                serializer.validated_data, usuario=request.user
            )
        except refinanciaciones.ObligacionNoEncontrada:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except refinanciaciones.ObligacionEliminada as exc:
            return Response(
                {
                    "detail": (
                        f"La obligación {exc.numero_obligacion} ha sido eliminada en TransUnion: "
                        "no se puede refinanciar."
                    ),
                    "code": "obligacion_eliminada",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except refinanciaciones.ObligacionCerrada as exc:
            return Response(
                {
                    "detail": (
                        f"La obligación {exc.numero_obligacion} ya está cerrada: "
                        "no se puede refinanciar."
                    ),
                    "code": "obligacion_cerrada",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except refinanciaciones.TransicionNoPermitida as exc:
            estado = exc.estado_desde
            cierre = "07" if estado in ("03", "06") else "02"
            return Response(
                {
                    "detail": (
                        f"TransUnion no acepta pasar de {nombre_estado(estado)} "
                        f"a {nombre_estado(cierre)}. "
                        "Consulta con CENS cómo tratar esta obligación antes de refinanciarla."
                    ),
                    "code": "transicion_no_permitida",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except refinanciaciones.NaturalezaNoEncontrada:
            return Response(
                {"naturaleza": ["Selecciona la naturaleza de la reestructuración."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValueError as exc:
            return Response(
                {"fecha": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            RefinanciacionSerializer(resultado).data, status=status.HTTP_201_CREATED
        )
