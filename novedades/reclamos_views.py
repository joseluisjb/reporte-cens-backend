from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EsAnalista
from novedades import reclamos
from novedades.reclamos_serializers import (
    ReclamoCerrarSerializer,
    ReclamoCreateSerializer,
    ReclamoSerializer,
)


class ReclamosViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        estado = request.query_params.get("estado")
        try:
            filas = reclamos.listar_reclamos(estado=estado)
        except ValueError:
            return Response(
                {"estado": ["Estado no válido."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReclamoSerializer(filas, many=True).data)

    def create(self, request):
        serializer = ReclamoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = reclamos.crear_reclamo(
                serializer.validated_data, usuario=request.user
            )
        except reclamos.ObligacionNoEncontrada:
            return Response(
                {"obligacion_id": ["La obligación no existe."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except reclamos.TipologiaNoEncontrada:
            return Response(
                {
                    "tipologia": [
                        "Selecciona una tipología válida de la Ley 1266."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except reclamos.ObligacionConReclamoAbierto:
            return Response(
                {"detail": "La obligación ya tiene un reclamo abierto."},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response(
                {"fecha_radicacion": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            ReclamoSerializer(resultado).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        serializer = ReclamoCerrarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            resultado = reclamos.cerrar_reclamo(
                int(pk), serializer.validated_data, usuario=request.user
            )
        except reclamos.ReclamoNoEncontrado:
            return Response(
                {"detail": "Reclamo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except reclamos.ReclamoYaCerrado:
            return Response(
                {"detail": "El reclamo ya está cerrado."},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response(
                {"fecha_cierre": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReclamoSerializer(resultado).data)

    @action(detail=False, methods=["get"], url_path="insumo")
    def insumo(self, request):
        tipo = request.query_params.get("tipo")
        try:
            texto = reclamos.generar_insumo(tipo, usuario=request.user)
        except ValueError:
            return Response(
                {"tipo": ["Usa marcacion o desmarcacion."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except reclamos.InsumoCambiado:
            return Response(
                {"detail": "El insumo cambió mientras se generaba. Intenta de nuevo."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(texto, content_type="text/plain; charset=utf-8")
