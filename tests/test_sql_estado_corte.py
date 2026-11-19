"""El script 25 deja NV_CORTE.ESTADO con espacio para todos los estados de CK_NV_CORTE_ESTADO (RF54)."""
import re
from pathlib import Path

_SQL = Path(__file__).parent.parent / "config" / "sql"


def _estados_permitidos():
    texto = (_SQL / "11_iter2_tablas_nuevas.sql").read_text(encoding="utf-8")
    restriccion = re.search(r"CK_NV_CORTE_ESTADO CHECK \(ESTADO IN \(([^)]*)\)\)", texto).group(1)
    return re.findall(r"'+([A-Z_]+)'+", restriccion)


def test_el_script_25_amplia_estado_al_estado_mas_largo():
    texto = (_SQL / "25_rf54_nv_corte_estado_largo.sql").read_text(encoding="utf-8")
    largo = int(re.search(r"MODIFY \(ESTADO VARCHAR2\((\d+) CHAR\)\)", texto).group(1))
    estados = _estados_permitidos()
    assert "ENVIADO_CON_INCONSISTENCIAS" in estados
    assert largo >= max(len(e) for e in estados)


def test_el_codigo_no_usa_estados_que_no_quepan():
    largo = 30
    for archivo in (Path(__file__).parent.parent / "cartera").glob("*.py"):
        for estado in re.findall(r"'(ENVIADO[A-Z_]*|VALIDADO|BORRADOR|ANULADO|RECHAZADO)'", archivo.read_text(encoding="utf-8")):
            assert len(estado) <= largo, (archivo.name, estado)


def test_el_script_25_recrea_el_indice_de_un_solo_borrador():
    # Oracle no amplía una columna con índice basado en función (ORA-30556): se quita y se recrea.
    texto = (_SQL / "25_rf54_nv_corte_estado_largo.sql").read_text(encoding="utf-8")
    assert "DROP INDEX NEXOVOLT.UK_NV_CORTE_UN_BORRADOR" in texto
    assert texto.count("CREATE UNIQUE INDEX NEXOVOLT.UK_NV_CORTE_UN_BORRADOR") == 1
    assert "CASE ESTADO WHEN ''BORRADOR'' THEN 1 END" in texto
