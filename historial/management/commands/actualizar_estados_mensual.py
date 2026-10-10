from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from config.formatos import hoy_bogota

from cartera.servicios import (
    BorradorOtraFecha,
    CorteEnEstadoFijo,
    FechaInvalida,
    GrupoInactivo,
    GrupoNoEncontrado,
    generar_corte,
)


def _registrar_bitacora(resultado):
    grupo_nombre = resultado["grupo"]["nombre"] if resultado["grupo"] else "todos"
    detalle = (
        f"Obligaciones: {resultado['obligaciones']}, "
        f"Saldo: {resultado['saldo_consolidado']}, "
        f"Grupo: {grupo_nombre}"
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO NEXOVOLT.NV_BITACORA "
            "(BITACORA_ID, USUARIO_ID, ACCION, ENTIDAD, ENTIDAD_ID, DETALLE) "
            "VALUES (NEXOVOLT.SEQ_NV_BITACORA.NEXTVAL, NULL, :1, :2, :3, :4)",
            ["ACTUALIZACION_MENSUAL", "NV_CORTE", str(resultado["id"]), detalle],
        )


class Command(BaseCommand):
    help = "Genera el corte mensual de cartera (RF9)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fecha-corte",
            dest="fecha_corte",
            default=None,
            help="Fecha de corte YYYY-MM-DD (por defecto: último día del mes anterior)",
        )
        parser.add_argument(
            "--grupo",
            dest="grupo_id",
            type=int,
            default=None,
            help="ID del grupo de conceptos de energía (opcional)",
        )
        parser.add_argument(
            "--simular",
            action="store_true",
            default=False,
            help="Ejecuta todo en una transacción y la revierte sin guardar cambios",
        )

    def handle(self, *args, **options):
        fecha_corte_str = options["fecha_corte"]
        grupo_id = options["grupo_id"]
        simular = options["simular"]

        if fecha_corte_str is not None:
            try:
                fecha_corte = date.fromisoformat(fecha_corte_str)
            except ValueError:
                raise CommandError(
                    f"Fecha inválida: '{fecha_corte_str}'. Use el formato YYYY-MM-DD."
                )
        else:
            hoy = hoy_bogota()
            fecha_corte = hoy.replace(day=1) - timedelta(days=1)

        self.stdout.write(f"Fecha de corte : {fecha_corte}")
        self.stdout.write(
            f"Grupo          : {grupo_id if grupo_id is not None else 'todos los conceptos reportables'}"
        )
        self.stdout.write(f"Modo           : {'SIMULACIÓN' if simular else 'REAL'}")

        try:
            with transaction.atomic():
                resultado = generar_corte(fecha_corte=fecha_corte, grupo_id=grupo_id)

                if not simular:
                    _registrar_bitacora(resultado)

                if simular:
                    transaction.set_rollback(True)
        except FechaInvalida as e:
            raise CommandError(str(e))
        except GrupoNoEncontrado:
            raise CommandError(f"Grupo {grupo_id} no encontrado.")
        except GrupoInactivo:
            raise CommandError(f"El grupo {grupo_id} está inactivo.")
        except CorteEnEstadoFijo:
            raise CommandError(
                f"Ya existe un corte en estado no reversible para {fecha_corte}."
            )
        except BorradorOtraFecha as e:
            raise CommandError(
                f"Ya existe un BORRADOR con fecha {e.fecha}. Resuélvalo primero."
            )

        self.stdout.write(f"Obligaciones     : {resultado['obligaciones']}")
        self.stdout.write(f"Saldo consolidado: {resultado['saldo_consolidado']}")
        self.stdout.write(f"Estado           : {resultado['estado']}")

        if simular:
            self.stdout.write("SIMULACIÓN completada — ningún cambio fue guardado.")
        else:
            self.stdout.write(f"Corte {resultado['id']} generado correctamente.")
