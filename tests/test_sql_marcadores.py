"""
Recorrido AST que verifica que ninguna cadena SQL pasada a cursor.execute /
cursor.executemany contenga:
  - marcadores Oracle del estilo :1, :2 o :nombre  (deben ser %s)
  - un % que no sea %s ni %%  (deben escaparse como %%)

Excluye directorios: tests, migrations, scripts (scripts usa oracledb directo,
no el cursor de Django, y su sintaxis SQL es diferente).
"""
import ast
import re
from pathlib import Path


_DIRS_EXCLUIDOS = {"tests", "migrations", "scripts", ".venv"}

# Marcador Oracle: :N o :nombre, con lookbehind negativo para no confundir
# '08:00' (dígito antes) ni 'HH24:MI' / 'HH:MI' (letra antes).
_RE_ORACLE = re.compile(r"(?<!\w)(:\d+|:[a-zA-Z_]\w*)")


def _tiene_porcentaje_desnudo(sql: str) -> bool:
    """True si el SQL contiene algún % que no sea %s ni %%."""
    limpio = re.sub(r"%%|%s", "", sql)
    return "%" in limpio


def _raiz() -> Path:
    return Path(__file__).parent.parent


def _archivos_py():
    raiz = _raiz()
    for ruta in sorted(raiz.rglob("*.py")):
        partes = set(ruta.relative_to(raiz).parts)
        if partes & _DIRS_EXCLUIDOS:
            continue
        yield ruta


def _fragmentos_constantes(nodo) -> list[str] | None:
    """Extrae los fragmentos de texto literal de un nodo AST (str, f-string,
    concatenación). Devuelve None si el nodo no es analizable estáticamente."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return [nodo.value]
    if isinstance(nodo, ast.JoinedStr):
        partes = [
            v.value
            for v in nodo.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
        return partes
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        izq = _fragmentos_constantes(nodo.left)
        der = _fragmentos_constantes(nodo.right)
        return (izq or []) + (der or [])
    return None


def _sql_calls(arbol: ast.AST):
    """Yields (lineno, sql_text) para cada llamada .execute()/.executemany()
    cuyo primer argumento sea un literal de cadena o una f-string analizable."""
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call):
            continue
        func = nodo.func
        if not (isinstance(func, ast.Attribute) and func.attr in ("execute", "executemany")):
            continue
        if not nodo.args:
            continue
        frags = _fragmentos_constantes(nodo.args[0])
        if frags is not None:
            yield nodo.lineno, "".join(frags)


def _errores_en(ruta: Path) -> list[str]:
    try:
        codigo = ruta.read_text(encoding="utf-8")
        arbol = ast.parse(codigo, filename=str(ruta))
    except SyntaxError:
        return []

    errores = []
    rel = ruta.relative_to(_raiz())
    for lineno, sql in _sql_calls(arbol):
        m = _RE_ORACLE.search(sql)
        if m:
            errores.append(f"{rel}:{lineno}: marcador Oracle '{m.group()}' en SQL")
        if _tiene_porcentaje_desnudo(sql):
            errores.append(f"{rel}:{lineno}: '%' sin escapar en SQL")
    return errores


def test_sin_marcadores_oracle_ni_porcentaje_desnudo():
    todos = []
    for ruta in _archivos_py():
        todos.extend(_errores_en(ruta))
    assert not todos, (
        f"{len(todos)} problema(s) encontrado(s):\n" + "\n".join(todos)
    )
