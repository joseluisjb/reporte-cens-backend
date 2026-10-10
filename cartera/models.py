from django.db import models


class Corte(models.Model):
    corte_id         = models.IntegerField(primary_key=True, db_column="CORTE_ID")
    fecha_corte      = models.DateField(db_column="FECHA_CORTE")
    tipo_reporte     = models.CharField(max_length=2, db_column="TIPO_REPORTE")
    estado           = models.CharField(max_length=10, db_column="ESTADO")
    fecha_generacion = models.DateTimeField(db_column="FECHA_GENERACION")
    usuario_id       = models.IntegerField(null=True, db_column="USUARIO_ID")
    total_registros  = models.IntegerField(null=True, db_column="TOTAL_REGISTROS")
    grupo_id         = models.IntegerField(null=True, db_column="GRUPO_ID")
    grupo_nombre     = models.CharField(max_length=60, null=True, db_column="GRUPO_NOMBRE")
    conceptos_usados = models.CharField(max_length=500, null=True, db_column="CONCEPTOS_USADOS")

    class Meta:
        managed = False
        db_table = "NV_CORTE"


class Obligacion(models.Model):
    obligacion_id        = models.IntegerField(primary_key=True, db_column="OBLIGACION_ID")
    cliente_id           = models.IntegerField(db_column="CLIENTE_ID")
    numero_proceso       = models.IntegerField(db_column="NUMERO_PROCESO")
    numero_obligacion_tu = models.CharField(max_length=20, db_column="NUMERO_OBLIGACION_TU")
    fecha_inicio         = models.DateField(null=True, db_column="FECHA_INICIO")

    class Meta:
        managed = False
        db_table = "NV_OBLIGACION"


class ReporteDetalle(models.Model):
    corte_id      = models.IntegerField(db_column="CORTE_ID")
    obligacion_id = models.IntegerField(db_column="OBLIGACION_ID")
    valor_saldo   = models.DecimalField(max_digits=14, decimal_places=0, db_column="VALOR_SALDO")

    class Meta:
        managed = False
        db_table = "NV_REPORTE_DETALLE"
