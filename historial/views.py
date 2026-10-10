from datetime import date

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from config.paginacion import parsear_paginacion
from usuarios.permisos import EsAnalistaOAdministrador
from historial import servicios
from historial.serializers import ReporteEnviadoSerializer, DeudorSerializer


class ReporteViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]
    lookup_value_regex = r"\d+"

    def list(self, request):
        desde = request.query_params.get("desde")
        hasta = request.query_params.get("hasta")
        try:
            desde_date = date.fromisoformat(desde) if desde else None
            hasta_date = date.fromisoformat(hasta) if hasta else None
        except ValueError:
            return Response(
                {"detail": "Los parámetros desde y hasta deben ser fechas en formato AAAA-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reportes = servicios.listar_reportes_enviados(desde=desde_date, hasta=hasta_date)
        return Response(ReporteEnviadoSerializer(reportes, many=True).data)

    @action(detail=True, methods=["get"], url_path="detalle")
    def detalle(self, request, pk=None):
        limite, desplazamiento, err = parsear_paginacion(request)
        if err is not None:
            return err
        try:
            resultado = servicios.listar_detalle_reporte(
                int(pk), limite=limite, desplazamiento=desplazamiento
            )
        except ValueError:
            return Response(
                {"detail": "Reporte no encontrado o no está en estado ENVIADO."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.ReporteNoEncontrado:
            return Response(
                {"detail": "Reporte no encontrado o no está en estado ENVIADO."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(resultado)


class DeudorViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalistaOAdministrador]
    lookup_value_regex = r"\d+"

    def list(self, request):
        cliente_id = request.query_params.get("cliente_id")
        numero_obligacion = request.query_params.get("numero_obligacion")
        if not cliente_id and not numero_obligacion:
            return Response(
                {"detail": "Debe proporcionar al menos cliente_id o numero_obligacion."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            cliente_id_int = int(cliente_id) if cliente_id else None
        except ValueError:
            return Response(
                {"detail": "cliente_id debe ser un entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limite, desplazamiento, err = parsear_paginacion(request)
        if err is not None:
            return err
        resultado = servicios.buscar_deudores(
            cliente_id=cliente_id_int,
            numero_obligacion=numero_obligacion or None,
            limite=limite,
            desplazamiento=desplazamiento,
        )
        return Response({
            "total": resultado["total"],
            "resultados": DeudorSerializer(resultado["resultados"], many=True).data,
        })

    def retrieve(self, request, pk=None):
        try:
            linea = servicios.linea_tiempo_deudor(int(pk))
        except ValueError:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except servicios.ObligacionNoEncontrada:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(linea)
