from rest_framework import viewsets, status
from rest_framework.response import Response

from usuarios.permisos import EsAnalistaOAdministrador
from parametros import servicios
from parametros.serializers import (
    ConceptoReportableSerializer,
    ConceptoActualizarSerializer,
    GrupoConceptoSerializer,
    GrupoConceptoCrearSerializer,
    GrupoConceptoActualizarSerializer,
)


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


class GrupoConceptoViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]

    def list(self, request):
        grupos = servicios.listar_grupos()
        return Response(GrupoConceptoSerializer(grupos, many=True).data)

    def retrieve(self, request, pk=None):
        grupo = servicios.obtener_grupo(pk)
        if grupo is None:
            return Response(
                {"detail": "Grupo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(GrupoConceptoSerializer(grupo).data)

    def create(self, request):
        serializer = GrupoConceptoCrearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grupo = servicios.crear_grupo(serializer.validated_data)
        except servicios.GrupoYaExiste:
            return Response(
                {"detail": "El nombre de grupo ya existe."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.ConceptoInvalido as exc:
            return Response(
                {"detail": f"El concepto {exc.codigo} no existe o no está activo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(GrupoConceptoSerializer(grupo).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        serializer = GrupoConceptoActualizarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            grupo = servicios.actualizar_grupo(pk, serializer.validated_data)
        except servicios.GrupoNoEncontrado:
            return Response(
                {"detail": "Grupo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.GrupoYaExiste:
            return Response(
                {"detail": "El nombre de grupo ya existe."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.ConceptoInvalido as exc:
            return Response(
                {"detail": f"El concepto {exc.codigo} no existe o no está activo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(GrupoConceptoSerializer(grupo).data)

    def destroy(self, request, pk=None):
        try:
            servicios.eliminar_grupo(pk)
        except servicios.GrupoEnUso:
            return Response(
                {"detail": "El grupo está asociado a un corte en estado BORRADOR."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.GrupoNoEncontrado:
            return Response(
                {"detail": "Grupo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
