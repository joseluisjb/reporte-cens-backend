from django.core.exceptions import ValidationError


class ValidadorMayuscula:
    mensaje = "La contraseña debe tener al menos una mayúscula."

    def validate(self, password, user=None):
        if not any(caracter.isupper() for caracter in password):
            raise ValidationError(self.mensaje, code="password_sin_mayuscula")

    def get_help_text(self):
        return self.mensaje


class ValidadorNumero:
    mensaje = "La contraseña debe tener al menos un número."

    def validate(self, password, user=None):
        if not any(caracter.isdigit() for caracter in password):
            raise ValidationError(self.mensaje, code="password_sin_numero")

    def get_help_text(self):
        return self.mensaje
