from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDeDjango
from rest_framework import serializers

from usuarios.models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = [
            "id",
            "nombre",
            "email",
            "rol",
            "is_active",
            "last_login",
            "must_change_password",
        ]
        read_only_fields = fields


class InicioSesionSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, max_length=128)


class CambioContrasenaSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, max_length=128)
    new_password = serializers.CharField(trim_whitespace=False, max_length=128)

    def validate_current_password(self, value):
        if not self.context["usuario"].check_password(value):
            raise serializers.ValidationError("La contraseña actual no es correcta.")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context["usuario"])
        except ErrorDeDjango as error:
            raise serializers.ValidationError(error.messages)
        if self.context["usuario"].check_password(value):
            raise serializers.ValidationError(
                "La nueva contraseña debe ser distinta de la actual."
            )
        return value
