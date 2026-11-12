from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from config.formatos import fecha_str
from config.paginacion import parsear_paginacion
from usuarios.permisos import EsAnalista
from ciclo import servicios
from ciclo.serializers import (
    CicloCreateSerializer,
    CicloResumenSerializer,
    CicloDetalleSerializer,
    MatrizEstadosSerializer,
    ObligacionResumenSerializer,
    ObligacionDetalleSerializer,
    ResumenObligacionesSerializer,
)


def _descripcion_evento(evento, nombres):
    """Nombre del estado (Tabla 4b, leído de NV_ESTADO_TU) y, si hay mora, días y cuotas."""
    nombre = nombres.get(evento["estado_tu"], evento["estado_tu"])
    dias = evento.get("dias_mora")
    if dias and int(dias) > 0:
        cuotas = evento.get("cuotas_mora") or 0
        return f"{nombre} · {int(dias)} días en mora, {int(cuotas)} cuotas"
    return nombre


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


class ObligacionesViewSet(viewsets.ViewSet):
    permission_classes = [EsAnalista]
    lookup_value_regex = r"\d+"

    def list(self, request):
        limite, desplazamiento, error = parsear_paginacion(request)
        if error:
            return error

        estado_tu = request.query_params.get("estado_tu")
        eliminada = request.query_params.get("eliminada", "false").lower() == "true"
        raw_abierta = request.query_params.get("abierta")
        if raw_abierta is not None and raw_abierta.lower() not in ("true", "false"):
            return Response(
                {"abierta": ["Debe ser true o false."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        abierta = raw_abierta is not None and raw_abierta.lower() == "true"
        q = request.query_params.get("q")

        if q is not None and len(q) > 60:
            return Response(
                {"q": ["La búsqueda no puede exceder 60 caracteres."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cuotas_mora_min = None
        raw_min = request.query_params.get("cuotas_mora_min")
        if raw_min is not None:
            try:
                cuotas_mora_min = int(raw_min)
                if cuotas_mora_min < 0:
                    raise ValueError()
            except ValueError:
                return Response(
                    {"cuotas_mora_min": ["Debe ser un entero no negativo."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            resultado = servicios.listar_obligaciones(
                limite, desplazamiento,
                estado_tu=estado_tu, eliminada=eliminada,
                cuotas_mora_min=cuotas_mora_min, q=q, abierta=abierta,
            )
        except ValueError:
            return Response(
                {"estado_tu": ["Estado no válido."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "total": resultado["total"],
            "resultados": ObligacionResumenSerializer(
                resultado["resultados"], many=True
            ).data,
        })

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        resultado = servicios.obtener_resumen_obligaciones()
        return Response(ResumenObligacionesSerializer(resultado).data)

    @action(detail=True, methods=["get"], url_path="linea-tiempo")
    def linea_tiempo(self, request, pk=None):
        from historial.servicios import linea_tiempo_deudor, ObligacionNoEncontrada
        from parametros.servicios import listar_estados_tu
        try:
            eventos = linea_tiempo_deudor(int(pk))
        except ObligacionNoEncontrada:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        nombres = {e["codigo"]: e["nombre"] for e in listar_estados_tu()}
        return Response([
            {
                "fecha": fecha_str(e["fecha_corte"]),
                "estado_tu": e["estado_tu"],
                "edad_mora": e["edad_mora"] or "00",
                "descripcion": _descripcion_evento(e, nombres),
            }
            for e in eventos
        ])

    def retrieve(self, request, pk=None):
        try:
            obl = servicios.obtener_obligacion(int(pk))
        except servicios.ObligacionNoEncontrada:
            return Response(
                {"detail": "Obligación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ObligacionDetalleSerializer(obl).data)


class PanelView(APIView):
    permission_classes = [EsAnalista]

    def get(self, request):
        return Response(servicios.obtener_panel_resumen())
