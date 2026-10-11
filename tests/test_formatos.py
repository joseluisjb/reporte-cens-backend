from datetime import date, datetime
from zoneinfo import ZoneInfo

from config.formatos import enmascarar_identificacion, fecha_str, timestamp_str

_BOGOTA = ZoneInfo("America/Bogota")


def test_fecha_str_date():
    assert fecha_str(date(2026, 9, 30)) == "2026-09-30"


def test_fecha_str_datetime():
    assert fecha_str(datetime(2026, 9, 30, 12, 0)) == "2026-09-30"


def test_fecha_str_none():
    assert fecha_str(None) is None


def test_timestamp_str_naive():
    resultado = timestamp_str(datetime(2026, 10, 10, 12, 0, 0))
    assert resultado == "2026-10-10T12:00:00-05:00"


def test_timestamp_str_aware_utc():
    from zoneinfo import ZoneInfo
    utc = ZoneInfo("UTC")
    dt_utc = datetime(2026, 10, 10, 17, 0, 0, tzinfo=utc)
    resultado = timestamp_str(dt_utc)
    assert resultado == "2026-10-10T12:00:00-05:00"


def test_timestamp_str_none():
    assert timestamp_str(None) is None


def test_timestamp_str_date():
    resultado = timestamp_str(date(2026, 9, 30))
    assert resultado == "2026-09-30"


# ── enmascarar_identificacion ─────────────────────────────────────────────────

def test_enmascarar_normal():
    assert enmascarar_identificacion("12345678") == "******5678"


def test_enmascarar_exactamente_4():
    assert enmascarar_identificacion("1234") == "******1234"


def test_enmascarar_menos_de_4():
    assert enmascarar_identificacion("123") == "***"


def test_enmascarar_1_digito():
    assert enmascarar_identificacion("9") == "*"


def test_enmascarar_none():
    assert enmascarar_identificacion(None) == "****"


def test_enmascarar_vacio():
    assert enmascarar_identificacion("") == "****"


def test_ahora_para_bd_sin_zona():
    from config.formatos import ahora_para_bd
    resultado = ahora_para_bd()
    assert resultado.tzinfo is None
