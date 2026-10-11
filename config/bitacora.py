from django.db import connection

from config.formatos import ahora_para_bd


def registrar_bitacora(accion, entidad, entidad_id, detalle, usuario_id=None):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_BITACORA "
            "(BITACORA_ID, FECHA, USUARIO_ID, ACCION, ENTIDAD, ENTIDAD_ID, DETALLE) "
            "VALUES (NEXOVOLT.SEQ_NV_BITACORA.NEXTVAL, :1, :2, :3, :4, :5, :6)",
            [ahora_para_bd(), usuario_id, accion, entidad, str(entidad_id), detalle],
        )
