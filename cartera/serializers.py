from rest_framework import serializers


class RegistrarEnvioSerializer(serializers.Serializer):
    fecha_envio = serializers.DateField(required=False, allow_null=True)


class GenerarCorteSerializer(serializers.Serializer):
    fecha_corte = serializers.DateField()
    grupo_id    = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class RegistrarEnvioSerializer(serializers.Serializer):
    fecha_envio = serializers.DateField(required=False, allow_null=True)


class CorteResumenSerializer(serializers.Serializer):
    def to_representation(self, instance):
        fecha_corte = instance["fecha_corte"]
        fecha_ej    = instance["fecha_ejecucion"]
        return {
            "id":               instance["id"],
            "fecha_corte":      fecha_corte.isoformat() if hasattr(fecha_corte, "isoformat") else str(fecha_corte)[:10],
            "fecha_ejecucion":  fecha_ej.isoformat() if hasattr(fecha_ej, "isoformat") else str(fecha_ej),
            "grupo":            instance["grupo"],
            "obligaciones":     instance["obligaciones"],
            "saldo_consolidado": instance["saldo_consolidado"],
            "estado":           instance["estado"],
            "ejecutada_por":    instance["ejecutada_por"],
        }
