from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from config.paginacion import parsear_paginacion
from usuarios.permisos import EsAnalistaOAdministrador
from cartera import servicios
from cartera.serializers import GenerarCorteSerializer, CorteResumenSerializer, RegistrarEnvioSerializer


class ExtraccionViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]
    lookup_value_regex = r"\d+"

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
                {"detail": (
                    f"Ya existe un corte en BORRADOR con fecha {exc.fecha}. "
                    "Elimínelo o complételo antes de generar otro."
                )},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.FechaAnteriorAlUltimoEnviado:
            return Response(
                {"detail": "La fecha de corte debe ser posterior a la del último corte enviado."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(CorteResumenSerializer(resumen).data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        try:
            corte = servicios.obtener_corte(int(pk))
        except ValueError:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        if corte is None:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CorteResumenSerializer(corte).data)

    @action(detail=False, methods=["get"], url_path="ultima")
    def ultima(self, request):
        corte = servicios.obtener_ultimo_corte()
        if corte is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(CorteResumenSerializer(corte).data)

    @action(detail=True, methods=["post"], url_path="validar")
    def validar(self, request, pk=None):
        try:
            resultado = servicios.validar_corte(int(pk))
        except ValueError:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEsBorrador:
            return Response(
                {"detail": "El corte no está en estado BORRADOR."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.CorteConErroresCorrectivos as exc:
            return Response(
                {
                    "detail": "El corte tiene errores correctivos que deben resolverse.",
                    "errores": exc.errores,
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response({
            **CorteResumenSerializer(resultado["corte"]).data,
            "advertencias": resultado["advertencias"],
        })

    @action(detail=True, methods=["post"], url_path="registrar-envio")
    def registrar_envio(self, request, pk=None):
        serializer = RegistrarEnvioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fecha_envio = serializer.validated_data.get("fecha_envio")
        try:
            corte = servicios.registrar_envio(int(pk), fecha_envio=fecha_envio)
        except ValueError:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEsValidado:
            return Response(
                {"detail": "El corte no está en estado VALIDADO."},
                status=status.HTTP_409_CONFLICT,
            )
        except servicios.FechaInvalida as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CorteResumenSerializer(corte).data)

    def destroy(self, request, pk=None):
        try:
            servicios.eliminar_borrador(int(pk))
        except ValueError:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEsBorrador:
            return Response(
                {"detail": "Solo se puede eliminar un corte en estado BORRADOR."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="obligaciones")
    def obligaciones(self, request, pk=None):
        limite, desplazamiento, err = parsear_paginacion(request)
        if err is not None:
            return err
        try:
            resultado = servicios.listar_obligaciones(
                int(pk), limite=limite, desplazamiento=desplazamiento
            )
        except ValueError:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except servicios.CorteNoEncontrado:
            return Response({"detail": "Corte no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(resultado)
