"""Ayudas para armar textos en español que ve el usuario."""


def unir_en_espanol(elementos):
    """«a», «a y b», «a, b y c»."""
    items = [str(e) for e in elementos]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]
