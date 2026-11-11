from rest_framework import status, viewsets
from rest_framework.response import Response

from usuarios.permisos import EsAnalista
from novedades import refinanciaciones
from novedades.refinanciaciones_serializers import (
    RefinanciacionCreateSerializer,
    RefinanciacionSerializer,
)

_NOMBRES_ESTADO_TU = {
    "01": "Vigente", "02": "Saldada", "03": "Dudoso Recaudo",
    "04": "Suspendida", "06": "Castigada", "07": "Cartera Recuperada",
    "08": "Inactivo", "10": "Estado 10", "11": "Estado 11", "12": "Estado 12",
}


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
            nombre_estado = _NOMBRES_ESTADO_TU.get(estado, estado)
            nombre_cierre = "Cartera Recuperada" if cierre == "07" else "Saldada"
            return Response(
                {
                    "detail": (
                        f"TransUnion no acepta pasar de {estado} · {nombre_estado} "
                        f"a {cierre} · {nombre_cierre} (error 713). "
                        "Define el tratamiento con CENS."
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
        return Response(
            RefinanciacionSerializer(resultado).data, status=status.HTTP_201_CREATED
        )
