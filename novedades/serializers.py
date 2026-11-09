from rest_framework import serializers


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


# ── RF55: Rectificaciones ────────────────────────────────────────────────────

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
    medio = serializers.ChoiceField(choices=["ACTUALIZACION_LINEA", "PROCESO_ESPECIAL"])
    estado = serializers.ChoiceField(choices=["REGISTRADA", "CONFIRMADA"])
    confirmacion_tu = serializers.CharField(allow_null=True)
    registrada_por = serializers.CharField(allow_null=True)
    fecha_registro = serializers.CharField()


class RectificacionCreateSerializer(serializers.Serializer):
    obligacion_id = serializers.IntegerField(min_value=1)
    corte_id = serializers.IntegerField(min_value=1)
    campo = serializers.ChoiceField(choices=["valor_mora"])
    valor_corregido = serializers.DecimalField(
        max_digits=14, decimal_places=0, min_value=0
    )
    justificacion = serializers.CharField(max_length=500)
    medio = serializers.ChoiceField(
        choices=["ACTUALIZACION_LINEA", "PROCESO_ESPECIAL"]
    )

    def validate_justificacion(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Escribe la justificación de la corrección."
            )
        return value


class RectificacionConfirmarSerializer(serializers.Serializer):
    confirmacion_tu = serializers.CharField(max_length=30)

    def validate_confirmacion_tu(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Ingresa el número de confirmación de TransUnion."
            )
        return value.strip()
