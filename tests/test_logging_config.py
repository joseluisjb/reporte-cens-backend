import logging
import logging.config

from django.conf import settings
from django.test import override_settings


def test_logging_sin_db_backends_debug():
    """django.db.backends no debe estar configurado en nivel DEBUG."""
    loggers = settings.LOGGING.get("loggers", {})
    db_logger = loggers.get("django.db.backends", {})
    assert db_logger.get("level") != "DEBUG"


def test_django_request_escribe_en_consola_sin_debug():
    """django.request debe tener StreamHandler aunque DEBUG sea False."""
    with override_settings(DEBUG=False):
        logging.config.dictConfig(settings.LOGGING)
    logger = logging.getLogger("django.request")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert stream_handlers, "django.request necesita al menos un StreamHandler"
