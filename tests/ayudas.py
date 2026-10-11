from unittest.mock import MagicMock


def usuario_con_rol(rol):
    user = MagicMock()
    user.rol = rol
    user.is_authenticated = True
    user.is_active = True
    return user
