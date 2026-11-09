from rest_framework import serializers

from config.formatos import fecha_str, timestamp_str


# ── Conceptos ────────────────────────────────────────────────────────────────

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
            "descripcion": instance["descripcion"] or "",
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


# ── Grupos de conceptos ───────────────────────────────────────────────────────

class GrupoConceptoSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "id":        instance["grupo_id"],
            "nombre":    instance["nombre"],
            "activo":    instance["activo"] == "S",
            "conceptos": instance.get("conceptos", []),
            "creado":    fecha_str(instance["fecha_creacion"]),
        }


class GrupoConceptoCrearSerializer(serializers.Serializer):
    nombre    = serializers.CharField(max_length=60)
    conceptos = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=9999),
        min_length=1,
    )

    def validate_conceptos(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("No se permiten códigos repetidos.")
        return value


class GrupoConceptoActualizarSerializer(serializers.Serializer):
    nombre    = serializers.CharField(max_length=60, required=False)
    activo    = serializers.BooleanField(required=False)
    conceptos = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=9999),
        min_length=1,
        required=False,
    )

    def validate_conceptos(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("No se permiten códigos repetidos.")
        return value

    def to_internal_value(self, data):
        validated = super().to_internal_value(data)
        if "activo" in validated:
            validated["activo"] = "S" if validated["activo"] else "N"
        return validated


# ── Datos de la entidad ante TransUnion (RF57) ────────────────────────────────

MSG_ENTIDAD = {
    "tipo_entidad": "El tipo de entidad debe tener 3 dígitos (o XXX mientras TransUnion no los asigne).",
    "codigo_entidad": "El código de entidad debe tener 3 dígitos (o XXX mientras TransUnion no los asigne).",
    "codigo_sucursal": "El código de sucursal debe tener 6 caracteres (o XXXXXX mientras TransUnion no los asigne).",
}


def _campo_entidad(patron, campo):
    mensajes = {
        "invalid": MSG_ENTIDAD[campo],
        "required": "Este campo es requerido.",
        "blank": "Este campo es requerido.",
        "null": "Este campo es requerido.",
    }
    return serializers.RegexField(patron, trim_whitespace=True, error_messages=mensajes)


class EntidadActualizarSerializer(serializers.Serializer):
    tipo_entidad = _campo_entidad(r"^(\d{3}|XXX)$", "tipo_entidad")
    codigo_entidad = _campo_entidad(r"^(\d{3}|XXX)$", "codigo_entidad")
    codigo_sucursal = _campo_entidad(r"^[A-Z0-9]{6}$", "codigo_sucursal")

    def to_internal_value(self, data):
        # Igual que el frontend: la sucursal admite letras y se compara en mayúsculas.
        if isinstance(data, dict):
            data = {
                campo: valor.upper() if isinstance(valor, str) else valor
                for campo, valor in data.items()
            }
        return super().to_internal_value(data)


class EntidadSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return {
            "tipo_entidad": instance["tipo_entidad"],
            "codigo_entidad": instance["codigo_entidad"],
            "codigo_sucursal": instance["codigo_sucursal"],
            "con_marcador": instance["con_marcador"],
            "prefijo_archivo": instance["prefijo_archivo"],
            "actualizado_por": instance["actualizado_por"],
            "fecha_actualizacion": timestamp_str(instance["fecha_actualizacion"]),
        }
