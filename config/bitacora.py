import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, time, timedelta

from django.db import connection, transaction

from config.formatos import ahora_para_bd, timestamp_str

logger = logging.getLogger(__name__)

usuario_actual = ContextVar("usuario_actual", default=None)

TIPOS_ACCION = (
    "inicio_sesion",
    "cierre_sesion",
    "consulta",
    "calculo",
    "generacion",
    "exportacion",
    "modificacion",
    "correccion",
    "eliminacion",
    "creacion",
    "edicion",
    "desactivacion",
)

MODULOS = ("Seguridad", "Usuarios", "Parametrización", "Extracción")

EVENTOS = {
    "INICIO_SESION": ("Inicio de sesión", "inicio_sesion", "Seguridad"),
    "CIERRE_SESION": ("Cierre de sesión", "cierre_sesion", "Seguridad"),
    "CONTRASENA_CAMBIADA": ("Contraseña cambiada", "edicion", "Seguridad"),
    "CONTRASENA_RESTABLECIDA": ("Contraseña restablecida", "edicion", "Seguridad"),
    "CREAR": ("Usuario creado", "creacion", "Usuarios"),
    "EDITAR": ("Usuario editado", "edicion", "Usuarios"),
    "ACTIVAR": ("Usuario activado", "edicion", "Usuarios"),
    "DESACTIVAR": ("Usuario desactivado", "desactivacion", "Usuarios"),
    "CONCEPTO_CREADO": ("Concepto creado", "creacion", "Parametrización"),
    "CONCEPTO_EDITADO": ("Concepto editado", "edicion", "Parametrización"),
    "CONCEPTO_DESACTIVADO": ("Concepto desactivado", "desactivacion", "Parametrización"),
    "GRUPO_CREADO": ("Grupo de conceptos creado", "creacion", "Parametrización"),
    "GRUPO_EDITADO": ("Grupo de conceptos editado", "edicion", "Parametrización"),
    "GRUPO_DESACTIVADO": ("Grupo de conceptos desactivado", "desactivacion", "Parametrización"),
    "GRUPO_ELIMINADO": ("Grupo de conceptos eliminado", "eliminacion", "Parametrización"),
    "CORTE_GENERADO": ("Corte generado", "calculo", "Extracción"),
    "CORTE_VALIDADO": ("Corte validado", "modificacion", "Extracción"),
    "ENVIO_REGISTRADO": ("Envío registrado", "modificacion", "Extracción"),
    "ELIMINACION_BORRADOR": ("Corte eliminado", "eliminacion", "Extracción"),
    "ACTUALIZACION_MENSUAL": ("Actualización mensual", "calculo", "Extracción"),
    "CONSULTA_OBLIGACIONES": ("Consulta de obligaciones", "consulta", "Extracción"),
    "CONSULTA_REPORTE": ("Consulta de reporte enviado", "consulta", "Extracción"),
    "CONSULTA_DEUDORES": ("Consulta de deudores", "consulta", "Extracción"),
    "CONSULTA_DEUDOR": ("Consulta de historial de deudor", "consulta", "Extracción"),
}

_COLUMNAS = (
    "BITACORA_ID, FECHA, USUARIO_ID, USUARIO_NOMBRE, USUARIO_ROL, "
    "ACCION, TIPO_ACCION, MODULO, DETALLE"
)
_FILTROS_EXACTOS = {
    "usuario": "USUARIO_ID = %s",
    "tipo_accion": "TIPO_ACCION = %s",
    "modulo": "MODULO = %s",
}
_USUARIO_SISTEMA = "Sistema"


def _recortar(valor, maximo):
    return None if valor is None else str(valor)[:maximo]


def registrar_bitacora(accion, entidad, entidad_id, detalle, usuario_id=None, usuario=None):
    actor = usuario if usuario is not None else usuario_actual.get()
    if usuario_id is None:
        usuario_id = getattr(actor, "pk", None)
    es_el_actor = actor is not None and getattr(actor, "pk", None) == usuario_id
    _, tipo_accion, modulo = EVENTOS.get(accion, (accion, None, None))
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_BITACORA "
            "(BITACORA_ID, FECHA, USUARIO_ID, ACCION, ENTIDAD, ENTIDAD_ID, DETALLE, "
            "USUARIO_NOMBRE, USUARIO_ROL, TIPO_ACCION, MODULO) "
            "VALUES (NEXOVOLT.SEQ_NV_BITACORA.NEXTVAL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                ahora_para_bd(),
                usuario_id,
                _recortar(accion, 40),
                _recortar(entidad, 30),
                _recortar(entidad_id, 40),
                _recortar(detalle, 1000),
                _recortar(actor.nombre, 150) if es_el_actor else None,
                _recortar(actor.rol, 20) if es_el_actor else None,
                tipo_accion,
                modulo,
            ],
        )


@contextmanager
def tolerar_fallo_bitacora(accion):
    # El punto de guardado evita que un INSERT fallido dañe la transacción de afuera.
    try:
        with transaction.atomic():
            yield
    except Exception:
        logger.exception("No se pudo registrar en la bitácora la acción %s", accion)


def consultar_bitacora(filtros, limite, desplazamiento):
    condiciones = []
    params = []

    def agregar(condicion, valor):
        condiciones.append(condicion)
        params.append(valor)

    if filtros.get("desde") is not None:
        agregar("FECHA >= %s", datetime.combine(filtros["desde"], time.min))
    if filtros.get("hasta") is not None:
        agregar("FECHA < %s", datetime.combine(filtros["hasta"] + timedelta(days=1), time.min))
    for campo, condicion in _FILTROS_EXACTOS.items():
        if filtros.get(campo) is not None:
            agregar(condicion, filtros[campo])

    donde = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM NEXOVOLT.NV_BITACORA{donde}", params)
        total = cursor.fetchone()[0]
        cursor.execute(
            f"SELECT {_COLUMNAS} FROM NEXOVOLT.NV_BITACORA{donde} "
            "ORDER BY FECHA DESC, BITACORA_ID DESC "
            "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY",
            params + [desplazamiento, limite],
        )
        filas = cursor.fetchall()

    resultados = [
        {
            "id": fila[0],
            "fecha_hora": timestamp_str(fila[1]),
            "usuario_id": fila[2],
            "usuario": fila[3] or _USUARIO_SISTEMA,
            "rol": fila[4],
            "accion": EVENTOS.get(fila[5], (fila[5],))[0],
            "tipo_accion": fila[6],
            "modulo": fila[7],
            "detalle": fila[8] or "",
        }
        for fila in filas
    ]
    return total, resultados
