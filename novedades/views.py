from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from config.paginacion import parsear_paginacion
from usuarios.permisos import EsAnalista
from novedades import servicios
from novedades.serializers import (
    EliminacionReactivarSerializer,
    EliminacionSerializer,
    NovedadSerializer,
    NovedadCreateSerializer,
    NovedadGestionarSerializer,
    NovedadRechazarSerializer,
)


class NovedadesViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        estado = request.query_params.get("estado")
        tipo = request.query_params.get("tipo")
        try:
            novedades = servicios.listar_novedades(estado=estado, tipo=tipo)
        except ValueError as exc:
            msg = str(exc)
            if "Estado" in msg:
                return Response(
                    {"estado": ["Estado no válido."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"tipo": ["Tipo no válido."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(NovedadSerializer(novedades, many=True).data)

    def create(self, request):
        serializer = NovedadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            novedad = servicios.crear_novedad(
                serializer.validated_data, usuario=request.user
            )
        except servicios.ObligacionNoEncontrada:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.MotivoEliminacionNoEncontrado:
            return Response(
                {"motivo_eliminacion": ["Código de motivo de eliminación no encontrado."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            NovedadSerializer(novedad).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"])
    def gestionar(self, request, pk=None):
        serializer = NovedadGestionarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            novedad = servicios.gestionar_novedad(
                int(pk),
                serializer.validated_data["numero_transaccion_tu"],
                serializer.validated_data["fecha_gestion"],
                usuario=request.user,
            )
        except servicios.NovedadNoEncontrada:
            return Response(
                {"detail": "Novedad no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.NovedadNoPendiente:
            return Response(
                {"detail": "La novedad no está pendiente."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(NovedadSerializer(novedad).data)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        serializer = NovedadRechazarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            novedad = servicios.rechazar_novedad(
                int(pk),
                serializer.validated_data["motivo_rechazo"],
                usuario=request.user,
            )
        except servicios.NovedadNoEncontrada:
            return Response(
                {"detail": "Novedad no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.NovedadNoPendiente:
            return Response(
                {"detail": "La novedad no está pendiente."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(NovedadSerializer(novedad).data)


# ── RF50: Eliminaciones ───────────────────────────────────────────────────────

class EliminacionesViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        limite, desplazamiento, err = parsear_paginacion(request)
        if err is not None:
            return err
        resultado = servicios.listar_eliminaciones(limite, desplazamiento)
        return Response({
            "total": resultado["total"],
            "resultados": EliminacionSerializer(resultado["resultados"], many=True).data,
        })

    @action(detail=True, methods=["post"])
    def reactivar(self, request, pk=None):
        serializer = EliminacionReactivarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            eliminacion = servicios.reactivar_eliminacion(
                int(pk),
                serializer.validated_data["numero_activacion_tu"],
                serializer.validated_data["fecha_activacion"],
                usuario=request.user,
            )
        except servicios.EliminacionNoEncontrada:
            return Response(
                {"detail": "Eliminación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.EliminacionYaReactivada:
            return Response(
                {"detail": "La obligación ya fue reactivada."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(EliminacionSerializer(eliminacion).data)
