from rest_framework import serializers

from config.formatos import hoy_bogota


class ModoExtincionSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    descripcion = serializers.CharField()


class ObligacionOriginalSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField(allow_null=True)
    estado_cierre = serializers.ChoiceField(choices=["02", "07"])
    modo_extincion = ModoExtincionSerializer()


class ObligacionNuevaSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    estado_tu = serializers.CharField()
    numero_reestructuraciones = serializers.IntegerField()


class NaturalezaSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    descripcion = serializers.CharField()
    confirmado = serializers.BooleanField()


class RefinanciacionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    fecha = serializers.CharField()
    fecha_registro = serializers.CharField(allow_null=True)
    registrada_por = serializers.CharField(allow_null=True)
    origen = serializers.ChoiceField(choices=["SAC", "MANUAL"])
    obligacion_original = ObligacionOriginalSerializer()
    obligacion_nueva = ObligacionNuevaSerializer()
    saldo_refinanciado = serializers.IntegerField(allow_null=True)
    naturaleza = NaturalezaSerializer()
    numero_cuotas = serializers.IntegerField(allow_null=True)


class RefinanciacionCreateSerializer(serializers.Serializer):
    obligacion_original_id = serializers.IntegerField(min_value=1)
    naturaleza = serializers.CharField(max_length=10)
    numero_cuotas = serializers.IntegerField(min_value=1, max_value=120)
    fecha = serializers.DateField(
        error_messages={"invalid": "La fecha de la refinanciación no es válida."}
    )

    def validate_naturaleza(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Selecciona la naturaleza de la reestructuración."
            )
        return value

    def validate_numero_cuotas(self, value):
        if value < 1 or value > 120:
            raise serializers.ValidationError(
                "Ingresa un número de cuotas entre 1 y 120."
            )
        return value

    def validate_fecha(self, value):
        if value > hoy_bogota():
            raise serializers.ValidationError(
                "La fecha de la refinanciación no puede ser futura."
            )
        return value
