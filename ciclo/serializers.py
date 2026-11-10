import calendar
from datetime import date

from rest_framework import serializers

from config.formatos import fecha_str, timestamp_str


class CicloCreateSerializer(serializers.Serializer):
    fecha_corte = serializers.DateField()

    def validate_fecha_corte(self, value):
        _, ultimo_dia = calendar.monthrange(value.year, value.month)
        if value.day != ultimo_dia:
            ultimo = date(value.year, value.month, ultimo_dia)
            raise serializers.ValidationError(
                f"El corte es el último día del mes. "
                f"Para ese mes sería el {ultimo.strftime('%d/%m/%Y')}."
            )
        return value


class ReglaAplicadaSerializer(serializers.Serializer):
    rf = serializers.CharField()
    texto = serializers.CharField()
    por_confirmar = serializers.BooleanField()


class TransicionSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField()
    estado_anterior = serializers.CharField(allow_null=True)
    estado_nuevo = serializers.CharField()
    edad_anterior = serializers.CharField(allow_null=True)
    edad_nueva = serializers.CharField()
    primer_reporte = serializers.BooleanField()
    requiere_revision = serializers.BooleanField()
    reglas = ReglaAplicadaSerializer(many=True)


class RechazoCicloSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField()
    estado_anterior = serializers.CharField(allow_null=True)
    estado_calculado = serializers.CharField()
    codigo = serializers.CharField()
    motivo = serializers.CharField()


class CicloResumenSerializer(serializers.Serializer):
    corte_id = serializers.IntegerField()
    fecha_corte = serializers.SerializerMethodField()
    fecha_ejecucion = serializers.SerializerMethodField()
    ejecutada_por = serializers.CharField(allow_null=True)
    primer_reporte = serializers.IntegerField()
    cambios_estado = serializers.IntegerField()
    cierres = serializers.IntegerField()
    rechazados = serializers.IntegerField()

    def get_fecha_corte(self, obj):
        return fecha_str(obj["fecha_corte"])

    def get_fecha_ejecucion(self, obj):
        return timestamp_str(obj["fecha_ejecucion"])


class CicloDetalleSerializer(CicloResumenSerializer):
    con_pagos = serializers.IntegerField()
    a_dudoso = serializers.IntegerField()
    a_castigada = serializers.IntegerField()
    normalizadas = serializers.IntegerField()
    transiciones = TransicionSerializer(many=True)
    rechazos = RechazoCicloSerializer(many=True)


class TransicionMatrizSerializer(serializers.Serializer):
    desde = serializers.CharField()
    desde_con_mora = serializers.BooleanField()
    hacia = serializers.CharField()
    hacia_con_mora = serializers.BooleanField()
    permitida = serializers.BooleanField()


class MatrizEstadosSerializer(serializers.Serializer):
    tipo_cartera = serializers.IntegerField()
    estados = serializers.ListField(child=serializers.CharField())
    transiciones = TransicionMatrizSerializer(many=True)


class ConteoEstadoSerializer(serializers.Serializer):
    estado_tu = serializers.CharField()
    cantidad = serializers.IntegerField()


class PorCuotasMoraSerializer(serializers.Serializer):
    al_dia = serializers.IntegerField()
    una = serializers.IntegerField()
    dos_a_tres = serializers.IntegerField()
    cuatro_o_mas = serializers.IntegerField()


class FinanciacionNuevaSerializer(serializers.Serializer):
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField()


class ResumenObligacionesSerializer(serializers.Serializer):
    fecha_ultimo_ciclo = serializers.CharField(allow_null=True)
    total = serializers.IntegerField()
    abiertas = serializers.IntegerField()
    por_estado = ConteoEstadoSerializer(many=True)
    eliminadas = serializers.IntegerField()
    por_cuotas_mora = PorCuotasMoraSerializer()
    financiaciones_nuevas = FinanciacionNuevaSerializer(many=True)


class ObligacionResumenSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField()
    numero_identificacion = serializers.CharField()
    estado_tu = serializers.CharField()
    edad_mora = serializers.CharField()
    dias_mora = serializers.IntegerField()
    cuotas_mora = serializers.IntegerField()
    valor_mora = serializers.IntegerField()
    valor_saldo = serializers.IntegerField()
    cerrada = serializers.BooleanField()
    primer_reporte = serializers.BooleanField()
    caducado = serializers.BooleanField()
    en_reclamo = serializers.BooleanField()
    eliminada = serializers.BooleanField()
    requiere_revision = serializers.BooleanField()


class ObligacionDetalleSerializer(ObligacionResumenSerializer):
    motivo_revision = serializers.CharField(allow_null=True)
    anios_mora = serializers.IntegerField(allow_null=True)
    concepto = serializers.DictField(allow_null=True)
    fecha_ingreso = serializers.CharField(allow_null=True)
    valor_inicial = serializers.IntegerField(allow_null=True)
    valor_cuota = serializers.IntegerField()
    valor_cuota_antes_cierre = serializers.IntegerField(allow_null=True)
    fecha_exigibilidad = serializers.CharField(allow_null=True)
    atrasos_permitidos = serializers.IntegerField()
    cuotas_atrasadas = serializers.IntegerField()
    cierre = serializers.DictField(allow_null=True)
    pago_mora = serializers.DictField(allow_null=True)
    reestructuracion = serializers.DictField(allow_null=True)
    refinanciada_en = serializers.DictField(allow_null=True)
    movimiento_posterior_cierre = serializers.BooleanField()
    cuotas_vencidas = serializers.ListField(child=serializers.DictField())
    pagos = serializers.ListField(child=serializers.DictField())
    posibles_transiciones = ReglaAplicadaSerializer(many=True)
    advertencias = serializers.ListField(child=serializers.DictField())
