from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView

from usuarios.permisos import EsAnalista
from ciclo import servicios
from ciclo.serializers import (
    CicloCreateSerializer,
    CicloResumenSerializer,
    CicloDetalleSerializer,
    MatrizEstadosSerializer,
)


class MatrizEstadosView(APIView):
    permission_classes = [EsAnalista]

    def get(self, request):
        matriz = servicios.obtener_matriz()
        return Response(MatrizEstadosSerializer(matriz).data)


class CicloViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        ciclos = servicios.listar_ciclos()
        return Response(CicloResumenSerializer(ciclos, many=True).data)

    def create(self, request):
        serializer = CicloCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fecha_corte = serializer.validated_data["fecha_corte"]

        try:
            resultado = servicios.ejecutar_ciclo(fecha_corte, usuario=request.user)
        except servicios.FechaCorteAnterior as exc:
            return Response(
                {"fecha_corte": [
                    f"La fecha de corte debe ser posterior al último corte enviado "
                    f"({exc.ultimo_enviado.strftime('%d/%m/%Y')})."
                ]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except servicios.CorteBorradorNoEncontrado:
            return Response(
                {"detail": "Primero genera la extracción de ese corte."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(CicloDetalleSerializer(resultado).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        ciclo = servicios.obtener_ciclo(int(pk))
        if ciclo is None:
            return Response(
                {"detail": "Ese corte no tiene una actualización mensual ejecutada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CicloDetalleSerializer(ciclo).data)
