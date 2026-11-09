from rest_framework import serializers

from config.formatos import hoy_bogota


class ItemCatalogoONuloSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    descripcion = serializers.CharField()
    confirmado = serializers.BooleanField()


class NovedadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.CharField()
    sujeto = serializers.CharField()
    obligacion_id = serializers.IntegerField(allow_null=True)
    referencia = serializers.CharField()
    motivo = serializers.CharField()
    motivo_eliminacion = ItemCatalogoONuloSerializer(allow_null=True)
    valores_enviados = serializers.CharField(allow_null=True)
    fecha_deteccion = serializers.CharField()
    origen = serializers.CharField()
    estado = serializers.CharField()
    numero_transaccion_tu = serializers.CharField(allow_null=True)
    fecha_gestion = serializers.CharField(allow_null=True)
    motivo_rechazo = serializers.CharField(allow_null=True)
    registrada_por = serializers.CharField(allow_null=True)


class NovedadCreateSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(
        choices=["INCLUSION", "ACTUALIZACION", "CORRECCION", "ELIMINACION"]
    )
    sujeto = serializers.ChoiceField(choices=["OBLIGACION", "TITULAR"])
    obligacion_id = serializers.IntegerField(required=False, allow_null=True)
    referencia = serializers.CharField(max_length=40)
    motivo = serializers.CharField(max_length=500)
    motivo_eliminacion = serializers.CharField(
        max_length=20, required=False, allow_null=True, allow_blank=False,
        default=None,
    )
    valores_enviados = serializers.CharField(
        max_length=1000, required=False, allow_null=True, allow_blank=True,
        default=None,
    )

    def validate(self, data):
        if data.get("tipo") == "ELIMINACION" and not data.get("motivo_eliminacion"):
            raise serializers.ValidationError(
                {"motivo_eliminacion": "Selecciona el motivo de la eliminación (Tabla 28)."}
            )
        return data


class NovedadGestionarSerializer(serializers.Serializer):
    numero_transaccion_tu = serializers.CharField(max_length=30)
    fecha_gestion = serializers.DateField()

    def validate_numero_transaccion_tu(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Ingresa el número de transacción de TransUnion."
            )
        return value


class NovedadRechazarSerializer(serializers.Serializer):
    motivo_rechazo = serializers.CharField(max_length=300)

    def validate_motivo_rechazo(self, value):
        if not value.strip():
            raise serializers.ValidationError("Escribe el motivo del rechazo.")
        return value


# ── RF50: Eliminaciones ───────────────────────────────────────────────────────

class EliminacionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    obligacion_id = serializers.IntegerField(allow_null=True)
    numero_obligacion = serializers.CharField()
    fecha = serializers.CharField()
    motivo = ItemCatalogoONuloSerializer(allow_null=True)
    numero_transaccion_tu = serializers.CharField(allow_null=True)
    bloqueada = serializers.BooleanField()
    fecha_activacion = serializers.CharField(allow_null=True)
    numero_activacion_tu = serializers.CharField(allow_null=True)


class EliminacionReactivarSerializer(serializers.Serializer):
    numero_activacion_tu = serializers.CharField(max_length=30)
    fecha_activacion = serializers.DateField()

    def validate_numero_activacion_tu(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Ingresa el número de la activación en TransUnion."
            )
        return value


# ── RF23: Reclamos de Habeas Data ────────────────────────────────────────────

class ReclamoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    obligacion_id = serializers.IntegerField()
    numero_obligacion = serializers.CharField()
    nombre_titular = serializers.CharField(allow_null=True)
    tipologia = ItemCatalogoONuloSerializer()
    fecha_radicacion = serializers.CharField()
    observacion = serializers.CharField(allow_null=True)
    estado = serializers.ChoiceField(choices=["EN_RECLAMO", "CERRADO"])
    radicado_en_tu = serializers.BooleanField()
    fecha_limite_respuesta = serializers.CharField()
    vencido = serializers.BooleanField()
    resultado = serializers.CharField(allow_null=True)
    fecha_cierre = serializers.CharField(allow_null=True)
    observacion_cierre = serializers.CharField(allow_null=True)
    registrado_por = serializers.CharField(allow_null=True)
    fecha_registro = serializers.CharField()


class ReclamoCreateSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField(min_value=1)
    tipologia = serializers.CharField(max_length=20)
    fecha_radicacion = serializers.DateField()
    observacion = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True,
    )

    def validate_fecha_radicacion(self, value):
        if value > hoy_bogota():
            raise serializers.ValidationError(
                "La fecha de radicación no puede ser futura."
            )
        return value


class ReclamoCerrarSerializer(serializers.Serializer):
    resultado = serializers.CharField(max_length=30)
    fecha_cierre = serializers.DateField()
    observacion_cierre = serializers.CharField(
        max_length=500, required=False, allow_null=True, allow_blank=True,
    )

    def validate_resultado(self, value):
        if not value.strip():
            raise serializers.ValidationError("Ingresa el resultado del reclamo.")
        return value

    def validate_observacion_cierre(self, value):
        if value is not None and not value.strip():
            return None
        return value
