from rest_framework import viewsets, status
from rest_framework.response import Response

from usuarios.permisos import EsAnalistaOAdministrador
from parametros import servicios
from parametros.serializers import ConceptoReportableSerializer, ConceptoActualizarSerializer


class ConceptoViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]

    def list(self, request):
        param = request.query_params.get("activo")
        activo = True if param == "true" else (False if param == "false" else None)
        conceptos = servicios.listar_conceptos(activo=activo)
        return Response(ConceptoReportableSerializer(conceptos, many=True).data)

    def create(self, request):
        serializer = ConceptoReportableSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            concepto = servicios.crear_concepto(serializer.validated_data)
        except servicios.ConceptoYaExiste:
            return Response(
                {"detail": "El código de concepto ya existe."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            ConceptoReportableSerializer(concepto).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        serializer = ConceptoActualizarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        concepto = servicios.actualizar_concepto(pk, serializer.validated_data)
        if concepto is None:
            return Response(
                {"detail": "Concepto no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ConceptoReportableSerializer(concepto).data)
