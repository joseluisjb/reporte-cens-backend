from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_tz

_BOGOTA = ZoneInfo("America/Bogota")


def fecha_str(valor):
    """Oracle DATE o date → 'YYYY-MM-DD', None → None."""
    if valor is None:
        return None
    if hasattr(valor, "date"):
        return valor.date().isoformat()
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)[:10]


def timestamp_str(valor):
    """Oracle DATE (naive datetime) → ISO 8601 con offset Bogotá, e.g. '2026-10-10T12:00:00-05:00'."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=_BOGOTA)
        else:
            valor = valor.astimezone(_BOGOTA)
        return valor.isoformat()
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)[:10]


def ahora_bogota():
    """Datetime actual con zona Bogotá — reemplaza SYSDATE en INSERT/UPDATE."""
    return dj_tz.localtime(dj_tz.now())


def hoy_bogota():
    """Fecha actual en Bogotá — reemplaza date.today()."""
    return dj_tz.localdate()
