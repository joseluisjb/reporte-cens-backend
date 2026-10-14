"""Ayudas para las pruebas de aceptación de HU-A.

A diferencia de las pruebas unitarias de cada app, que simulan la capa de servicios, aquí se
simula únicamente **la base de datos Oracle**: la petición atraviesa la vista, el serializer y
el servicio reales. Así el caso de prueba comprueba el criterio de aceptación de punta a punta
y no la implementación de una función concreta.

Todos los datos son ficticios.
"""

from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock

# ── Datos ficticios compartidos ───────────────────────────────────────────────

CONCEPTO_CUOTA = 30          # CUOTA FINANCIACION ENERGIA
CONCEPTO_INTERES = 94        # INTERES FINANCIACION ENERGIA
FECHA_CORTE = date(2026, 9, 30)
FECHA_CORTE_ANTERIOR = date(2026, 8, 31)
FECHA_EJECUCION = datetime(2026, 10, 10, 12, 0, 0)
SALDO_CONSOLIDADO = 45_000_000
CORTE_ID = 1


@contextmanager
def sin_transaccion():
    """Reemplaza transaction.atomic: no hay base de datos real que abrir."""
    yield


class OraculoFalso:
    """Oracle simulado que devuelve, en orden, las filas que el servicio va pidiendo.

    Guarda cada sentencia ejecutada en `sentencias`, para poder afirmar sobre el SQL que el
    servicio construyó (por ejemplo, que filtró por los conceptos de energía activos).
    """

    def __init__(self, fetchone=(), fetchall=()):
        self.sentencias = []
        self.parametros = []
        self.cursor = MagicMock()
        self.cursor.fetchone.side_effect = list(fetchone)
        self.cursor.fetchall.side_effect = list(fetchall)
        self.cursor.execute.side_effect = self._registrar

        self.conexion = MagicMock()
        self.conexion.cursor.return_value.__enter__.return_value = self.cursor
        self.conexion.cursor.return_value.__exit__.return_value = False

    def _registrar(self, sql, params=None):
        self.sentencias.append(sql)
        if params:
            self.parametros.extend(params)

    @property
    def sql_completo(self):
        return "\n".join(self.sentencias)

    @property
    def conceptos_sellados_en_el_corte(self):
        """Lista de conceptos que el servicio guardó en el corte (columna CONCEPTOS_USADOS).

        Es una cadena como "30,94": la fotografía de qué conceptos de energía estaban activos
        cuando se generó el corte. Renombrar o desactivar un concepto después no reescribe el
        historial.
        """
        insertados = [p for p in self.parametros if isinstance(p, str) and "," in p]
        return insertados[0] if insertados else None


def oraculo_corte_exitoso(total_obligaciones=5, saldo=SALDO_CONSOLIDADO,
                          conceptos=(CONCEPTO_CUOTA, CONCEPTO_INTERES),
                          ultimo_enviado=None):
    """Oracle simulado para una extracción que termina bien, sin grupo.

    El orden de las filas sigue el recorrido real del servicio: último corte enviado,
    corte existente con la misma fecha, borrador de otra fecha, identificador nuevo del
    corte, totales y saldo consolidado.
    """
    return OraculoFalso(
        fetchone=[
            (ultimo_enviado,),                   # MAX(FECHA_CORTE) de los cortes enviados
            None,                                # no hay corte con esa misma fecha
            None,                                # no hay borrador con otra fecha
            (CORTE_ID,),                         # identificador nuevo del corte
            (total_obligaciones, FECHA_EJECUCION),  # total de obligaciones y fecha de ejecución
            (saldo,),                            # saldo consolidado
        ],
        fetchall=[
            [(c,) for c in conceptos],           # conceptos reportables activos
            [],                                  # obligaciones nuevas del corte
        ],
    )
