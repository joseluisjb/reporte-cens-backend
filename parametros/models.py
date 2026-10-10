from django.db import models
from django.db.models import CompositePrimaryKey


class ConceptoReportable(models.Model):
    codigo_concepto = models.SmallIntegerField(primary_key=True, db_column="CODIGO_CONCEPTO")
    descripcion     = models.CharField(max_length=60, null=True, db_column="DESCRIPCION")
    reportable      = models.CharField(max_length=1, db_column="REPORTABLE")
    observacion     = models.CharField(max_length=200, null=True, blank=True, db_column="OBSERVACION")

    class Meta:
        managed = False
        db_table = "NV_CONCEPTO_REPORTABLE"


class GrupoConcepto(models.Model):
    grupo_id       = models.IntegerField(primary_key=True, db_column="GRUPO_ID")
    nombre         = models.CharField(max_length=60, db_column="NOMBRE")
    activo         = models.CharField(max_length=1, db_column="ACTIVO")
    fecha_creacion = models.DateTimeField(db_column="FECHA_CREACION")

    class Meta:
        managed = False
        db_table = "NV_GRUPO_CONCEPTO"


class GrupoConceptoDet(models.Model):
    pk              = CompositePrimaryKey("grupo_id", "codigo_concepto")
    grupo_id        = models.IntegerField(db_column="GRUPO_ID")
    codigo_concepto = models.SmallIntegerField(db_column="CODIGO_CONCEPTO")

    class Meta:
        managed = False
        db_table = "NV_GRUPO_CONCEPTO_DET"
