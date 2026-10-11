from rest_framework import serializers

from config.formatos import fecha_str


class ReporteEnviadoSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "id":               instance["id"],
            "fecha_corte":      fecha_str(instance["fecha_corte"]),
            "fecha_envio":      fecha_str(instance["fecha_envio"]),
            "total_registros":  instance["total_registros"],
            "saldo_consolidado": instance["saldo_consolidado"],
            "grupo":            instance["grupo"],
            "observacion":      instance["observacion"],
        }


class DeudorSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "obligacion_id":      instance["obligacion_id"],
            "numero_obligacion":  instance["numero_obligacion"],
            "cliente_id":         instance["cliente_id"],
            "numero_proceso":     instance["numero_proceso"],
            "fecha_inicio":       fecha_str(instance["fecha_inicio"]),
            "ultimo_estado_tu":   instance["ultimo_estado_tu"],
            "ultimo_valor_saldo": instance["ultimo_valor_saldo"],
        }
