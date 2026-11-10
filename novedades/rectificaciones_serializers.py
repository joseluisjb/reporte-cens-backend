from rest_framework import serializers


class RectificacionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    novedad_id = serializers.IntegerField(allow_null=True)
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    corte_id = serializers.IntegerField()
    fecha_corte = serializers.CharField()
    campo = serializers.CharField()
    valor_anterior = serializers.CharField(allow_null=True)
    valor_corregido = serializers.CharField()
    justificacion = serializers.CharField()
    medio = serializers.ChoiceField(
        choices=["ACTUALIZACION_LINEA", "PROCESO_ESPECIAL"]
    )
    estado = serializers.ChoiceField(choices=["REGISTRADA", "CONFIRMADA"])
    confirmacion_tu = serializers.CharField(allow_null=True)
    registrada_por = serializers.CharField(allow_null=True)
    fecha_registro = serializers.CharField()
    insumo = serializers.CharField(required=False)


class RectificacionCreateSerializer(serializers.Serializer):
    novedad_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    obligacion_id = serializers.IntegerField(min_value=1)
    corte_id = serializers.IntegerField(min_value=1)
    campo = serializers.CharField(max_length=40)
    valor_corregido = serializers.CharField(max_length=100)
    justificacion = serializers.CharField(max_length=500)
    medio = serializers.ChoiceField(
        choices=["ACTUALIZACION_LINEA", "PROCESO_ESPECIAL"]
    )

    def validate_campo(self, value):
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError("Selecciona un campo rectificable.")
        return value

    def validate_justificacion(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Escribe la justificación de la corrección.")
        return value


class RectificacionConfirmarSerializer(serializers.Serializer):
    confirmacion_tu = serializers.CharField(max_length=30)

    def validate_confirmacion_tu(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Ingresa el número de confirmación de TransUnion."
            )
        return value
