from config.bitacora import registrar_bitacora


def registrar_auditoria(accion, entidad, entidad_id, detalle, usuario_id=None):
    # TODO: ajustar si cambia la firma de registrar_bitacora
    registrar_bitacora(accion, entidad, entidad_id, detalle, usuario_id)
