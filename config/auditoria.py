import json
import logging

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from config.bitacora import (
    MODULOS,
    TIPOS_ACCION,
    consultar_bitacora,
    registrar_bitacora,
    usuario_actual,
)
from config.paginacion import parsear_paginacion
from usuarios.permisos import EsAdministrador

logger = logging.getLogger(__name__)

RUTAS = {
    ("POST", "auth-login"): ("INICIO_SESION", "USUARIO"),
    ("POST", "auth-logout"): ("CIERRE_SESION", "USUARIO"),
    ("POST", "auth-change-password"): ("CONTRASENA_CAMBIADA", "USUARIO"),
    ("POST", "auth-password-reset-confirm"): ("CONTRASENA_RESTABLECIDA", "USUARIO"),
    ("POST", "concepto-list"): ("CONCEPTO_CREADO", "NV_CONCEPTO_REPORTABLE"),
    ("PATCH", "concepto-detail"): ("CONCEPTO_EDITADO", "NV_CONCEPTO_REPORTABLE"),
    ("POST", "grupo-concepto-list"): ("GRUPO_CREADO", "NV_GRUPO_CONCEPTO"),
    ("PATCH", "grupo-concepto-detail"): ("GRUPO_EDITADO", "NV_GRUPO_CONCEPTO"),
    ("DELETE", "grupo-concepto-detail"): ("GRUPO_ELIMINADO", "NV_GRUPO_CONCEPTO"),
    ("POST", "extraccion-list"): ("CORTE_GENERADO", "NV_CORTE"),
    ("POST", "extraccion-validar"): ("CORTE_VALIDADO", "NV_CORTE"),
    ("POST", "extraccion-registrar-envio"): ("ENVIO_REGISTRADO", "NV_CORTE"),
    ("GET", "extraccion-obligaciones"): ("CONSULTA_OBLIGACIONES", "NV_CORTE"),
    ("GET", "historial-reporte-detalle"): ("CONSULTA_REPORTE", "NV_CORTE"),
    ("GET", "historial-deudor-list"): ("CONSULTA_DEUDORES", "NV_OBLIGACION"),
    ("GET", "historial-deudor-detail"): ("CONSULTA_DEUDOR", "NV_OBLIGACION"),
}

DESACTIVACIONES = {
    "CONCEPTO_EDITADO": "CONCEPTO_DESACTIVADO",
    "GRUPO_EDITADO": "GRUPO_DESACTIVADO",
}

DETALLES_FIJOS = {
    "INICIO_SESION": "Acceso correcto",
    "CONTRASENA_RESTABLECIDA": "Restablecimiento con enlace del correo",
}

# Además de los PATCH, rutas cuyo cuerpo se lee para el detalle.
CUERPO_LEIDO = {("POST", "auth-logout")}

CAMPOS_EDITABLES = ("nombre", "descripcion", "observacion", "activo", "conceptos")

MENSAJE_FECHA = "Usa una fecha válida (AAAA-MM-DD)."
MENSAJE_USUARIO = "Indica el id numérico del usuario."


def _autenticado(usuario):
    return usuario if getattr(usuario, "is_authenticated", False) else None


def _detalle(accion, cuerpo, datos):
    if accion == "CIERRE_SESION":
        # Un frontend sin el campo `motivo` sigue quedando como cierre manual.
        if cuerpo.get("motivo") == "inactividad":
            return "Cierre por inactividad"
        return "Cierre manual"
    if accion in DETALLES_FIJOS:
        return DETALLES_FIJOS[accion]
    campos = [campo for campo in CAMPOS_EDITABLES if campo in cuerpo]
    if campos:
        return f"Campos: {', '.join(campos)}"
    if datos.get("fecha_corte"):
        return f"Fecha de corte {str(datos['fecha_corte'])[:10]}"
    return ""


class RegistroAuditoria:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = _autenticado(getattr(request, "user", None))
        marca = usuario_actual.set(usuario)
        try:
            respuesta = self.get_response(request)
        finally:
            usuario_actual.reset(marca)
        self._registrar(request, respuesta, usuario)
        return respuesta

    def process_view(self, request, view_func, view_args, view_kwargs):
        clave = (request.method, request.resolver_match.url_name)
        if clave not in RUTAS or (request.method != "PATCH" and clave not in CUERPO_LEIDO):
            return None
        try:
            cuerpo = json.loads(request.body or b"{}")
        except ValueError:
            cuerpo = {}
        request.cuerpo_auditoria = cuerpo if isinstance(cuerpo, dict) else {}
        return None

    def _registrar(self, request, respuesta, usuario):
        ruta = request.resolver_match
        if ruta is None or not 200 <= respuesta.status_code < 300:
            return
        evento = RUTAS.get((request.method, ruta.url_name))
        if evento is None:
            return
        accion, entidad = evento
        actor = (
            usuario
            or getattr(request, "actor_auditoria", None)
            or _autenticado(getattr(request, "user", None))
        )
        datos = getattr(respuesta, "data", None)
        datos = datos if isinstance(datos, dict) else {}
        cuerpo = getattr(request, "cuerpo_auditoria", {})
        if cuerpo.get("activo") is False:
            accion = DESACTIVACIONES.get(accion, accion)
        entidad_id = (
            ruta.kwargs.get("pk")
            or datos.get("id")
            or datos.get("codigo")
            or getattr(actor, "pk", None)
        )
        try:
            registrar_bitacora(
                accion, entidad, entidad_id, _detalle(accion, cuerpo, datos), usuario=actor
            )
        except Exception:
            logger.exception("No se pudo registrar en la bitácora la acción %s", accion)


class FiltrosAuditoriaSerializer(serializers.Serializer):
    desde = serializers.DateField(required=False, error_messages={"invalid": MENSAJE_FECHA})
    hasta = serializers.DateField(required=False, error_messages={"invalid": MENSAJE_FECHA})
    usuario = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=10**15,
        error_messages={
            "invalid": MENSAJE_USUARIO,
            "min_value": MENSAJE_USUARIO,
            "max_value": MENSAJE_USUARIO,
            "max_string_length": MENSAJE_USUARIO,
        },
    )
    tipo_accion = serializers.ChoiceField(
        choices=TIPOS_ACCION,
        required=False,
        error_messages={"invalid_choice": "Tipo de acción no válido."},
    )
    modulo = serializers.ChoiceField(
        choices=MODULOS,
        required=False,
        error_messages={"invalid_choice": "Módulo no válido."},
    )

    def validate(self, datos):
        if datos.get("desde") and datos.get("hasta") and datos["hasta"] < datos["desde"]:
            raise serializers.ValidationError(
                {"hasta": ["La fecha final no puede ser anterior a la inicial."]}
            )
        return datos


class AuditoriaView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        limite, desplazamiento, error = parsear_paginacion(request)
        if error is not None:
            return error
        filtros = FiltrosAuditoriaSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        total, resultados = consultar_bitacora(filtros.validated_data, limite, desplazamiento)
        return Response({"total": total, "resultados": resultados})
