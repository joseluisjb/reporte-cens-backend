from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EsAnalistaOAdministrador
from cartera import servicios
from cartera.serializers import GenerarCorteSerializer, CorteResumenSerializer, RegistrarEnvioSerializer


class ExtraccionViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]

    def list(self, request):
        cortes = servicios.listar_cortes()
        return Response(CorteResumenSerializer(cortes, many=True).data)

    def create(self, request):
        serializer = GenerarCorteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        try:
            resumen = servicios.generar_corte(
                fecha_corte=datos["fecha_corte"],
                grupo_id=datos.get("grupo_id"),
            )
        except servicios.FechaInvalida as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except servicios.GrupoNoEncontrado:
            return Response(
                {"detail": "Grupo no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.GrupoInactivo:
            return Response(
                {"detail": "El grupo está inactivo."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.CorteEnEstadoFijo:
            return Response(
                {"detail": "Ya existe un corte con esa fecha en un estado que no permite reemplazo."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.BorradorOtraFecha as exc:
            return Response(
                {"detail": f"Ya existe un corte en BORRADOR con fecha {exc.fecha}. Debe completarlo o eliminarlo primero."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(CorteResumenSerializer(resumen).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        corte = servicios.obtener_corte(int(pk))
        if corte is None:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CorteResumenSerializer(corte).data)

    @action(detail=False, methods=["get"], url_path="ultima")
    def ultima(self, request):
        corte = servicios.obtener_ultimo_corte()
        if corte is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(CorteResumenSerializer(corte).data)

    @action(detail=True, methods=["get"], url_path="obligaciones")
    def obligaciones(self, request, pk=None):
        try:
            limite = int(request.query_params.get("limite", 20))
            desplazamiento = int(request.query_params.get("desplazamiento", 0))
        except (ValueError, TypeError):
            return Response(
                {"detail": "Los parámetros limite y desplazamiento deben ser enteros."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            resultado = servicios.listar_obligaciones(
                int(pk), limite=limite, desplazamiento=desplazamiento
            )
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(resultado)

    @action(detail=True, methods=["post"], url_path="validar")
    def validar(self, request, pk=None):
        try:
            resultado = servicios.validar_corte(int(pk))
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEsBorrador:
            return Response(
                {"detail": "El corte no está en estado BORRADOR."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.CorteConErroresCorrectivos as exc:
            return Response(
                {"detail": "El corte tiene errores correctivos que deben resolverse.",
                 "errores": exc.errores},
                status=status.HTTP_409_CONFLICT,
            )
        corte_data = CorteResumenSerializer(resultado["corte"]).data
        return Response({**corte_data, "advertencias": resultado["advertencias"]})

    @action(detail=True, methods=["post"], url_path="registrar-envio")
    def registrar_envio(self, request, pk=None):
        serializer = RegistrarEnvioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fecha_envio = serializer.validated_data.get("fecha_envio")
        try:
            corte = servicios.registrar_envio(int(pk), fecha_envio=fecha_envio)
        except servicios.FechaInvalida as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEsValidado:
            return Response(
                {"detail": "El corte no está en estado VALIDADO."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(CorteResumenSerializer(corte).data)
