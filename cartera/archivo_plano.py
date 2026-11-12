"""Archivo plano del reporte total a TransUnion (RF20) y valores en miles (RF51).

Estructura del Manual del sector real v34, págs. 44-52 (Tabla 1, Tabla 2 columna «Sector Real
servicios» y registro tipo 9). Funciones puras: no leen la base de datos.
"""
from datetime import date

CODIFICACION = "cp1252"
FIN_DE_LINEA = "\r\n"

# Formatos (relleno y alineación):
#   NUM  número, a la derecha con ceros a la izquierda
#   ALF  alfanumérico en mayúsculas, a la izquierda con espacios a la derecha
#   TXT  como ALF pero sin pasar a mayúsculas (correo electrónico)
#   IDE  identificación, a la derecha con ceros a la izquierda
#   OBL  número de obligación, a la derecha con espacios a la izquierda
#   FEC  fecha AAAAMMDD
#   MIL  valor en pesos que se reporta en miles (RF51), como NUM
# Un campo sin valor (None) va en espacios, nunca en ceros. Los N/A no tienen origen.

# (id, campo, posición inicial, longitud, formato, origen)
REGISTRO_1 = (
    ("01", "tipo_registro", 1, 1, "NUM", "tipo_registro"),
    ("02", "codigo_paquete", 2, 2, "NUM", "codigo_paquete"),
    ("03", "tipo_entidad", 4, 3, "ALF", "tipo_entidad"),      # NUM en el Manual; admite el marcador XXX (RF57)
    ("04", "codigo_entidad", 7, 3, "ALF", "codigo_entidad"),  # ídem
    ("05", "reservado", 10, 10, "ALF", None),
    ("06", "tipo_reporte", 20, 2, "NUM", "tipo_reporte"),
    ("07", "fecha_corte", 22, 8, "FEC", "fecha_corte"),
)

REGISTRO_2 = (
    ("1", "tipo_registro", 1, 1, "NUM", "tipo_registro"),
    ("2", "tipo_identificacion", 2, 2, "NUM", "TIPO_ID_TU"),
    ("3", "numero_identificacion", 4, 15, "IDE", "NUMERO_IDENTIFICACION"),
    ("4", "nombre_titular", 19, 60, "ALF", "NOMBRE_TITULAR"),
    ("5", "reservado", 79, 2, "ALF", None),
    ("6", "fecha_limite_pago", 81, 8, "FEC", "FECHA_LIMITE_PAGO"),
    ("7", "numero_obligacion", 89, 20, "OBL", "NUMERO_OBLIGACION_TU"),
    ("8", "codigo_sucursal", 109, 6, "ALF", "codigo_sucursal"),
    ("9", "calidad", 115, 1, "ALF", "CALIDAD"),
    ("10", "calificacion", 116, 2, "ALF", None),
    ("11", "situacion_titular", 118, 2, "ALF", None),
    ("12", "estado", 120, 2, "NUM", "ESTADO_TU"),
    ("13", "edad_mora", 122, 2, "NUM", "EDAD_MORA"),
    ("14", "anios_mora", 124, 2, "NUM", "ANIOS_MORA"),
    ("15", "fecha_corte", 126, 8, "FEC", "fecha_corte"),
    ("16", "fecha_inicial", 134, 8, "FEC", "FECHA_INICIO"),
    ("17", "fecha_terminacion", 142, 8, "FEC", None),
    ("18", "fecha_exigibilidad", 150, 8, "FEC", "FECHA_EXIGIBILIDAD"),  # RF49: ver _datos_rf49
    ("19", "fecha_prescripcion", 158, 8, "FEC", None),
    ("20", "fecha_pago", 166, 8, "FEC", "FECHA_PAGO"),
    ("21", "modo_extincion", 174, 2, "NUM", "MODO_EXTINCION"),
    ("22", "tipo_pago", 176, 2, "NUM", "TIPO_PAGO"),
    ("23", "periodicidad", 178, 2, "NUM", "PERIODICIDAD"),
    ("24", "probabilidad_no_pago", 180, 3, "NUM", None),
    ("25", "cuotas_pagadas", 183, 3, "NUM", None),
    ("26", "cuotas_pactadas", 186, 3, "NUM", None),
    ("27", "cuotas_en_mora", 189, 3, "NUM", "CUOTAS_MORA"),
    ("28", "valor_inicial", 192, 12, "MIL", "VALOR_INICIAL"),
    ("29", "valor_mora", 204, 12, "MIL", "VALOR_MORA"),
    ("30", "valor_saldo", 216, 12, "MIL", "VALOR_SALDO"),
    ("31", "valor_cuota", 228, 12, "MIL", "VALOR_CUOTA"),
    ("32", "valor_cargo_fijo", 240, 12, "MIL", None),
    ("33", "linea_credito", 252, 3, "NUM", None),  # N/A en Real servicios
    ("34", "clausula_permanencia", 255, 3, "NUM", None),
    ("35", "tipo_contrato", 258, 3, "NUM", None),
    ("36", "estado_contrato", 261, 3, "NUM", None),
    ("37", "vigencia_contrato", 264, 2, "NUM", None),
    ("38", "meses_contrato", 266, 3, "NUM", None),
    ("39", "naturaleza_juridica", 269, 3, "NUM", None),
    ("40", "modalidad_credito", 272, 2, "NUM", None),
    ("41", "tipo_moneda", 274, 2, "NUM", None),
    ("42", "tipo_garantia", 276, 2, "NUM", None),
    ("43", "valor_garantia", 278, 12, "NUM", None),
    ("44", "obligacion_reestructurada", 290, 2, "NUM", "OBLIGACION_REFINANCIADA"),
    ("45", "naturaleza_reestructuracion", 292, 2, "NUM", "NATURALEZA_REESTR"),  # RF18: ver _datos_rf18
    ("46", "numero_reestructuraciones", 294, 3, "NUM", "N_REESTRUCTURACIONES"),  # RF18: ver _datos_rf18
    ("47", "clase_tarjeta", 297, 2, "NUM", None),
    ("48", "cheques_devueltos", 299, 4, "NUM", None),
    ("49", "categoria_servicios", 303, 2, "NUM", "categoria_servicios"),
    ("50", "plazo", 305, 2, "NUM", None),
    ("51", "dias_cartera", 307, 6, "NUM", None),
    ("52", "tipo_cuenta", 313, 2, "NUM", None),
    ("53", "cupo_sobregiro", 315, 12, "NUM", None),
    ("54", "dias_autorizados", 327, 3, "NUM", None),
    ("55", "direccion_casa", 330, 60, "ALF", None),
    ("56", "telefono_casa", 390, 20, "ALF", None),
    ("57", "codigo_ciudad_casa", 410, 6, "NUM", None),
    ("58", "ciudad_casa", 416, 20, "ALF", None),
    ("59", "codigo_departamento_casa", 436, 3, "NUM", None),
    ("60", "departamento_casa", 439, 20, "ALF", None),
    ("61", "nombre_empresa", 459, 60, "ALF", None),
    ("62", "direccion_empresa", 519, 60, "ALF", None),
    ("63", "telefono_empresa", 579, 20, "ALF", None),
    ("64", "codigo_ciudad_empresa", 599, 6, "NUM", None),
    ("65", "ciudad_empresa", 605, 20, "ALF", None),
    ("66", "codigo_departamento_empresa", 625, 3, "NUM", None),
    ("67", "departamento_empresa", 628, 20, "ALF", None),
    ("68", "fecha_inicio_exencion_gmf", 648, 8, "FEC", None),
    ("69", "fecha_fin_exencion_gmf", 656, 8, "FEC", None),
    ("70", "renovacion_cdt", 664, 2, "NUM", None),
    ("71", "cuenta_exenta_gmf", 666, 2, "NUM", None),
    ("72", "tipo_identificacion_originaria", 668, 2, "NUM", None),
    ("73", "numero_identificacion_originaria", 670, 14, "NUM", None),
    ("74", "tipo_entidad_originaria", 684, 3, "NUM", None),
    ("75", "codigo_entidad_originaria", 687, 3, "NUM", None),
    ("76", "tipo_fideicomiso", 690, 2, "NUM", None),
    ("77", "numero_fideicomiso", 692, 12, "NUM", None),
    ("78", "nombre_fideicomiso", 704, 60, "ALF", None),
    ("79", "tipo_deuda_cartera", 764, 4, "NUM", None),
    ("80", "tipo_poliza", 768, 4, "NUM", None),
    ("81", "codigo_ramo", 772, 6, "NUM", None),
    ("82", "numero_real_tarjeta", 778, 20, "ALF", None),
    ("83", "correo_electronico", 798, 60, "TXT", "CORREO"),
    ("84", "celular", 858, 60, "ALF", "CELULAR"),
    ("85", "valor_real_pagado", 918, 12, "MIL", "VALOR_REAL_PAGADO"),
)

REGISTRO_9 = (
    ("01", "tipo_registro", 1, 1, "NUM", "tipo_registro"),
    ("02", "total_registros", 2, 8, "NUM", "total_registros"),
    ("03", "registros_tipo_2", 10, 8, "NUM", "registros_tipo_2"),
    ("04", "registros_tipo_3", 18, 8, "NUM", "registros_tipo_3"),
    ("05", "registros_tipo_4", 26, 8, "NUM", "registros_tipo_4"),
)

# Alerta informativa de RF51 (Manual, p. 19): valores en pesos fuera de este rango.
VALOR_MINIMO_ALERTA = 10_000
VALOR_MAXIMO_ALERTA = 99_000_000


def longitud_layout(layout):
    _, _, inicio, longitud, _, _ = layout[-1]
    return inicio + longitud - 1


class CampoInvalido(Exception):
    def __init__(self, regla, campo, mensaje):
        super().__init__(mensaje)
        self.regla = regla
        self.campo = campo
        self.mensaje = mensaje


def a_miles(valor_en_pesos, divisor):
    """Pesos → miles al millar más cercano (mitades hacia arriba); >0 nunca da 0 (P-TU-02)."""
    if valor_en_pesos is None:
        return None
    pesos = int(round(valor_en_pesos))
    miles = (abs(pesos) * 2 + divisor) // (divisor * 2)
    if pesos > 0 and miles == 0:
        return 1
    return -miles if pesos < 0 else miles


def fuera_de_rango(valor_en_pesos):
    """True si un valor > 0 cae fuera de $10.000 a $99 millones (alerta informativa, RF51)."""
    return bool(valor_en_pesos) and not (
        VALOR_MINIMO_ALERTA <= valor_en_pesos <= VALOR_MAXIMO_ALERTA
    )


def _texto(valor, formato, divisor):
    if formato == "FEC":
        return valor.strftime("%Y%m%d") if isinstance(valor, date) else str(valor)
    if formato == "MIL":
        valor = a_miles(valor, divisor)
    if formato in ("NUM", "MIL"):
        if isinstance(valor, float):
            valor = int(valor)
        texto = str(valor).strip()
        if not texto.isdigit():
            raise CampoInvalido("CAMPO_TIPO_INVALIDO", None, f"«{texto}» no es numérico")
        return texto
    texto = str(valor).strip()
    return texto if formato == "TXT" else texto.upper()


def _formatear(campo, longitud, formato, valor, divisor):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return " " * longitud
    try:
        texto = _texto(valor, formato, divisor)
    except CampoInvalido as exc:
        raise CampoInvalido(exc.regla, campo, f"El campo {campo} no es de su tipo: {exc.mensaje}.")
    if len(texto) > longitud:
        raise CampoInvalido(
            "CAMPO_EXCEDE_LONGITUD", campo,
            f"El campo {campo} tiene {len(texto)} caracteres y admite {longitud}.",
        )
    try:
        texto.encode(CODIFICACION)
    except UnicodeEncodeError:
        raise CampoInvalido(
            "CAMPO_TIPO_INVALIDO", campo,
            f"El campo {campo} tiene caracteres que no existen en Windows-1252.",
        )
    if formato in ("NUM", "MIL", "IDE"):
        return texto.rjust(longitud, "0")
    if formato == "OBL":
        return texto.rjust(longitud)
    return texto.ljust(longitud)


def _datos_rf49(obligacion):
    """Fecha de exigibilidad y años en mora del registro tipo 2 (RF49).

    - Fecha de exigibilidad (campo 18): la fecha límite de pago de la cuota impaga más antigua, solo si
      la obligación tiene valor de mora y edad de mora mayores a cero; al día va vacía (Manual p. 20:
      con edad 00 TransUnion no la tiene en cuenta y genera una alerta).
    - Años en mora (campo 14): solo para la edad de mora 14 (Manual p. 13).
    """
    edad = str(obligacion.get("EDAD_MORA") or "").strip().zfill(2)
    en_mora = (obligacion.get("VALOR_MORA") or 0) > 0 and edad != "00"
    return {
        "FECHA_EXIGIBILIDAD": obligacion.get("FECHA_LIMITE_PAGO") if en_mora else None,
        "ANIOS_MORA": obligacion.get("ANIOS_MORA") if edad == "14" else None,
    }


def _datos_rf18(obligacion):
    """Naturaleza y numero de reestructuraciones del registro tipo 2 (RF18, campos 45 y 46).

    Solo se reportan cuando la obligacion esta reestructurada (campo 44 = 01) y el numero de
    reestructuraciones es mayor que cero; en los demas casos van en espacios.
    """
    reestructurada = (
        obligacion.get("OBLIGACION_REFINANCIADA") == "01"
        and (obligacion.get("N_REESTRUCTURACIONES") or 0) > 0
    )
    return {
        "NATURALEZA_REESTR": obligacion.get("NATURALEZA_REESTR") if reestructurada else None,
        "N_REESTRUCTURACIONES": obligacion.get("N_REESTRUCTURACIONES") if reestructurada else None,
    }


def armar_registro(layout, datos, divisor=1000, longitud_total=None):
    """Una línea de longitud fija (sin CRLF). Rellena con espacios hasta `longitud_total`."""
    partes = [
        _formatear(campo, longitud, formato, datos.get(origen) if origen else None, divisor)
        for _, campo, _, longitud, formato, origen in layout
    ]
    linea = "".join(partes)
    return linea.ljust(longitud_total or len(linea))


def armar_archivo(cabecera, obligaciones, divisor, longitud_tipo2):
    """Contenido completo en cp1252 y la lista de errores por obligación (vacía si salió bien).

    `cabecera`: codigo_paquete, tipo_entidad, codigo_entidad, tipo_reporte, fecha_corte,
    codigo_sucursal y categoria_servicios. `obligaciones`: dicts con las columnas de origen.
    """
    if longitud_tipo2 < longitud_layout(REGISTRO_2):
        raise ValueError("La longitud del registro tipo 2 es menor que la suma de sus campos.")
    errores = []
    lineas = [armar_registro(REGISTRO_1, {**cabecera, "tipo_registro": 1})]
    for obligacion in obligaciones:
        datos = {**cabecera, **obligacion, **_datos_rf49(obligacion),
                 **_datos_rf18(obligacion), "tipo_registro": 2}
        try:
            lineas.append(armar_registro(REGISTRO_2, datos, divisor, longitud_tipo2))
        except CampoInvalido as exc:
            errores.append({
                "regla": exc.regla,
                "mensaje": exc.mensaje,
                "obligacion_id": obligacion.get("OBLIGACION_ID"),
                "numero_obligacion": obligacion.get("NUMERO_OBLIGACION_TU"),
                "campo": exc.campo,
            })
    if errores:
        return None, errores
    n_tipo2 = len(lineas) - 1
    lineas.append(armar_registro(REGISTRO_9, {
        "tipo_registro": 9, "total_registros": n_tipo2 + 2, "registros_tipo_2": n_tipo2,
        "registros_tipo_3": 0, "registros_tipo_4": 0,
    }))
    contenido = "".join(linea + FIN_DE_LINEA for linea in lineas)
    return contenido.encode(CODIFICACION), []
