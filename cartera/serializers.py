from rest_framework import serializers

from config.formatos import fecha_str, timestamp_str


class RegistrarEnvioSerializer(serializers.Serializer):
    fecha_envio = serializers.DateField(
        required=False,
        allow_null=True,
        error_messages={"invalid": "La fecha de envío no es válida."},
    )


class GenerarCorteSerializer(serializers.Serializer):
    fecha_corte = serializers.DateField(
        error_messages={
            "required": "Selecciona una fecha de corte.",
            "null":     "Selecciona una fecha de corte.",
            "invalid":  "La fecha de corte no es válida.",
        },
    )
    grupo_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        error_messages={"invalid": "El grupo de conceptos no es válido."},
    )


class CorteResumenSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "id":                instance["id"],
            "fecha_corte":       fecha_str(instance["fecha_corte"]),
            "fecha_ejecucion":   timestamp_str(instance["fecha_ejecucion"]),
            "grupo":             instance["grupo"],
            "obligaciones":      instance["obligaciones"],
            "saldo_consolidado": instance["saldo_consolidado"],
            "estado":            instance["estado"],
            "ejecutada_por":     instance["ejecutada_por"],
        }
