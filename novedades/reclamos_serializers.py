from rest_framework import serializers

from config.formatos import hoy_bogota


class TipologiaReclamoSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    descripcion = serializers.CharField()
    confirmado = serializers.BooleanField()


class ReclamoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField(allow_null=True)
    tipologia = TipologiaReclamoSerializer()
    fecha_radicacion = serializers.CharField()
    observacion = serializers.CharField(allow_null=True)
    estado = serializers.ChoiceField(choices=["EN_RECLAMO", "CERRADO"])
    radicado_en_tu = serializers.BooleanField()
    fecha_limite_respuesta = serializers.CharField(allow_null=True)
    vencido = serializers.BooleanField()
    resultado = serializers.CharField(allow_null=True)
    fecha_cierre = serializers.CharField(allow_null=True)
    observacion_cierre = serializers.CharField(allow_null=True)
    registrado_por = serializers.CharField(allow_null=True)
    fecha_registro = serializers.CharField()


class ReclamoCreateSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField(min_value=1)
    tipologia = serializers.CharField(max_length=20)
    fecha_radicacion = serializers.DateField(
        error_messages={"invalid": "La fecha de radicación no es válida."}
    )
    observacion = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True
    )

    def validate_tipologia(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Selecciona una tipología válida de la Ley 1266."
            )
        return value

    def validate_fecha_radicacion(self, value):
        if value > hoy_bogota():
            raise serializers.ValidationError(
                "La fecha de radicación no puede ser futura."
            )
        return value


class ReclamoCerrarSerializer(serializers.Serializer):
    resultado = serializers.CharField(max_length=30)
    fecha_cierre = serializers.DateField(
        error_messages={"invalid": "La fecha de cierre no es válida."}
    )
    observacion_cierre = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True
    )

    def validate_resultado(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Registra el resultado del reclamo.")
        return value

    def validate_observacion_cierre(self, value):
        if value and value.strip():
            raise serializers.ValidationError(
                "La base actual solo almacena el resultado del reclamo."
            )
        return value
