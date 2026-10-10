from rest_framework import serializers


class ReporteEnviadoSerializer(serializers.Serializer):
    def to_representation(self, instance):
        fecha_corte = instance["fecha_corte"]
        fecha_envio = instance["fecha_envio"]
        return {
            "id":               instance["id"],
            "fecha_corte":      fecha_corte.isoformat() if hasattr(fecha_corte, "isoformat") else str(fecha_corte)[:10],
            "fecha_envio":      fecha_envio.isoformat() if hasattr(fecha_envio, "isoformat") else str(fecha_envio)[:10],
            "total_registros":  instance["total_registros"],
            "saldo_consolidado": instance["saldo_consolidado"],
            "grupo":            instance["grupo"],
            "observacion":      instance["observacion"],
        }


class DeudorSerializer(serializers.Serializer):
    def to_representation(self, instance):
        fecha = instance["fecha_inicio"]
        return {
            "obligacion_id":      instance["obligacion_id"],
            "numero_obligacion":  instance["numero_obligacion"],
            "cliente_id":         instance["cliente_id"],
            "numero_proceso":     instance["numero_proceso"],
            "fecha_inicio":       fecha.isoformat() if hasattr(fecha, "isoformat") else (str(fecha)[:10] if fecha else None),
            "ultimo_estado_tu":   instance["ultimo_estado_tu"],
            "ultimo_valor_saldo": instance["ultimo_valor_saldo"],
        }
