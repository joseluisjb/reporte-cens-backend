from rest_framework import serializers


class ConceptoReportableSerializer(serializers.Serializer):
    codigo      = serializers.IntegerField(min_value=1, max_value=9999)
    descripcion = serializers.CharField(max_length=60)
    activo      = serializers.BooleanField(default=True)
    observacion = serializers.CharField(
        max_length=200, required=False, allow_null=True, allow_blank=True, default=None
    )

    def to_representation(self, instance):
        return {
            "codigo":      instance["codigo_concepto"],
            "descripcion": instance["descripcion"],
            "activo":      instance["reportable"] == "S",
            "observacion": instance["observacion"],
        }

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        return {
            "codigo_concepto": validated["codigo"],
            "descripcion":     validated["descripcion"],
            "reportable":      "S" if validated["activo"] else "N",
            "observacion":     validated.get("observacion"),
        }


class ConceptoActualizarSerializer(serializers.Serializer):
    descripcion = serializers.CharField(max_length=60, required=False)
    activo      = serializers.BooleanField(required=False)
    observacion = serializers.CharField(
        max_length=200, required=False, allow_null=True, allow_blank=True
    )

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        if "activo" in validated:
            validated["reportable"] = "S" if validated.pop("activo") else "N"
        return validated
