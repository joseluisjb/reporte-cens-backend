import os

from django.core.management.base import BaseCommand

from usuarios.models import Rol, Usuario


class Command(BaseCommand):
    help = "Crea usuarios iniciales leyendo variables de entorno. Idempotente: omite si el correo ya existe."

    def handle(self, *args, **options):
        specs = [
            {
                "env_prefix": "SEED_ADMIN",
                "rol": Rol.ADMINISTRADOR,
                "label": "Administrador",
            },
            {
                "env_prefix": "SEED_ANALISTA",
                "rol": Rol.ANALISTA_CARTERA,
                "label": "Analista de Cartera",
            },
        ]

        for spec in specs:
            prefix = spec["env_prefix"]
            email = os.environ.get(f"{prefix}_EMAIL", "").strip()
            password = os.environ.get(f"{prefix}_PASSWORD", "").strip()
            nombre = os.environ.get(f"{prefix}_NOMBRE", "").strip()

            if not email:
                self.stdout.write(f"[seed] {spec['label']}: sin {prefix}_EMAIL, se omite.")
                continue
            if not password:
                self.stderr.write(f"[seed] {spec['label']}: falta {prefix}_PASSWORD, se omite.")
                continue
            if not nombre:
                self.stderr.write(f"[seed] {spec['label']}: falta {prefix}_NOMBRE, se omite.")
                continue

            if Usuario.objects.filter(email=email.lower()).exists():
                self.stdout.write(f"[seed] {spec['label']}: {email} ya existe, se omite.")
                continue

            Usuario.objects.create_user(
                email=email,
                password=password,
                nombre=nombre,
                rol=spec["rol"],
                must_change_password=True,
            )
            self.stdout.write(f"[seed] {spec['label']}: {email} creado.")
