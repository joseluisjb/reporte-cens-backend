from django.db import models


class ConceptoReportable(models.Model):
    codigo_concepto = models.SmallIntegerField(primary_key=True, db_column="CODIGO_CONCEPTO")
    descripcion     = models.CharField(max_length=60, null=True, db_column="DESCRIPCION")
    reportable      = models.CharField(max_length=1, db_column="REPORTABLE")
    observacion     = models.CharField(max_length=200, null=True, blank=True, db_column="OBSERVACION")

    class Meta:
        managed = False
        db_table = "NV_CONCEPTO_REPORTABLE"
