"""Nombres de los estados de TransUnion tal como se muestran al usuario."""

NOMBRES_ESTADO_TU = {
    "01": "Vigente",
    "02": "Saldada",
    "03": "Dudoso recaudo",
    "04": "Suspendida",
    "06": "Castigada",
    "07": "Castigada recuperada",
    "08": "Inactivo",
    "10": "Estado 10",
    "11": "Estado 11",
    "12": "Estado 12",
}


def nombre_estado(codigo):
    """Nombre legible del estado; si no se conoce, devuelve el código recibido."""
    return NOMBRES_ESTADO_TU.get(codigo, codigo)
