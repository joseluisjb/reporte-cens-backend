from datetime import date, datetime
from zoneinfo import ZoneInfo

from config.formatos import fecha_str, timestamp_str

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
