from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class Rol(models.TextChoices):
    ANALISTA_CARTERA = "ANALISTA_CARTERA", "Analista de Cartera"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


def normalizar_email(email):
    return (email or "").strip().lower()


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        email = normalizar_email(email)
        if not email:
            raise ValueError("El correo es obligatorio.")
        if not (extra.get("nombre") or "").strip():
            raise ValueError("El nombre es obligatorio.")
        usuario = self.model(email=email, **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("rol", Rol.ANALISTA_CARTERA)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["rol"] = Rol.ADMINISTRADOR
        extra.setdefault("must_change_password", False)
        return self._crear(email, password, **extra)

    def get_by_natural_key(self, email):
        return self.get(email=normalizar_email(email))


class Usuario(AbstractBaseUser):
    email = models.EmailField("correo", max_length=254, unique=True)
    nombre = models.CharField(max_length=150)
    rol = models.CharField(max_length=20, choices=Rol.choices)
    is_active = models.BooleanField("activo", default=True)
    must_change_password = models.BooleanField("debe cambiar la contraseña", default=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = normalizar_email(self.email)
        self.nombre = (self.nombre or "").strip()
        super().save(*args, **kwargs)

    @property
    def is_staff(self):
        return self.rol == Rol.ADMINISTRADOR

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_staff

    def has_module_perms(self, app_label):
        return self.is_active and self.is_staff
