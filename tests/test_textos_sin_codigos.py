"""Los textos que llegan a pantalla no deben llevar códigos internos del proyecto.

Revisa, con el AST de cada módulo de código (no de pruebas ni migraciones), los
literales de texto y las partes literales de los f-strings. Se ignoran los
docstrings, los mensajes de logging y los `help` de los comandos de gestión:
los comentarios, docstrings y logs PUEDEN seguir citando códigos RF, porque no
los ve el usuario. Solo se vigilan los textos en pantalla.

Prohibido en un texto: "RF11", "(RF48)", "RF45 · ", códigos HU-/CP-/DF-/MJ-/OBS-,
códigos de solicitud de cambio como "C-29" y etiquetas como "por confirmar",
"por confirmar con CENS" o "pendiente de CENS". Un literal que sea solo un
código estructural (p. ej. "RF11", el valor del campo `rf`) sí está permitido.
"""
import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIDOS = {".venv", "venv", "docs", "tests", "migrations", "__pycache__", "node_modules", "scripts"}
METODOS_LOG = {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
RAICES_LOG = {"logger", "logging", "log", "_logger", "_log"}

PROHIBIDOS = (
    re.compile(r"por confirmar|confirmar con CENS|pendiente de CENS", re.IGNORECASE),
    re.compile(r"\bC-\d+\b"),
    re.compile(r"\b(HU|CP|DF|MJ|OBS)-[A-Z0-9]"),
)


def _paquetes():
    return [
        d for d in sorted(RAIZ.iterdir())
        if d.is_dir() and d.name not in EXCLUIDOS and (d / "__init__.py").exists()
    ]


def _es_modulo_de_codigo(ruta):
    nombre = ruta.name
    if nombre == "tests.py" or nombre.startswith("test_") or nombre == "conftest.py":
        return False
    return not (set(ruta.relative_to(RAIZ).parts[:-1]) & EXCLUIDOS)


def _modulos():
    for paquete in _paquetes():
        for ruta in sorted(paquete.rglob("*.py")):
            if _es_modulo_de_codigo(ruta):
                yield ruta


def _es_llamada_de_log(nodo):
    if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)):
        return False
    if nodo.func.attr not in METODOS_LOG:
        return False
    base = nodo.func.value
    return isinstance(base, ast.Name) and base.id in RAICES_LOG


def _ids_ignorados(arbol):
    """ids de los nodos Constant que son docstrings, argumentos de log o `help = ...`."""
    ignorados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            cuerpo = nodo.body
            if (
                cuerpo and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                ignorados.add(id(cuerpo[0].value))
        elif _es_llamada_de_log(nodo):
            for hijo in ast.walk(nodo):
                ignorados.add(id(hijo))
        elif isinstance(nodo, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "help" for t in nodo.targets):
                for hijo in ast.walk(nodo.value):
                    ignorados.add(id(hijo))
    return ignorados


def _textos(arbol):
    """(linea, texto) de cada literal str o parte literal de f-string que se muestra."""
    ignorados = _ids_ignorados(arbol)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if id(nodo) not in ignorados:
                yield nodo.lineno, nodo.value


def _es_codigo_prohibido(texto):
    if re.search(r"RF\d", texto) and not re.fullmatch(r"RF\d+", texto):
        return True
    return any(p.search(texto) for p in PROHIBIDOS)


def _infracciones(fuente, nombre="<modulo>"):
    arbol = ast.parse(fuente)
    return [
        f"{nombre}:{linea}: {texto!r}"
        for linea, texto in _textos(arbol)
        if _es_codigo_prohibido(texto)
    ]


def test_se_descubren_los_modulos_de_la_aplicacion():
    nombres = {m.relative_to(RAIZ).as_posix() for m in _modulos()}
    assert "ciclo/servicios.py" in nombres
    assert "cartera/servicios.py" in nombres


def test_los_textos_de_pantalla_no_llevan_codigos_internos():
    encontrados = []
    for ruta in _modulos():
        fuente = ruta.read_text(encoding="utf-8")
        encontrados += _infracciones(fuente, ruta.relative_to(RAIZ).as_posix())
    assert not encontrados, "Textos con códigos internos:\n" + "\n".join(encontrados)


def test_el_detector_encuentra_los_casos_conocidos():
    fuente = (
        'a = f"RF11 · {x} días"\n'
        'b = "Valores (RF51)"\n'
        'c = "x [por confirmar, C-29]"\n'
        'd = "Ver HU-12"\n'
        'ok = {"rf": "RF11"}\n'
        'logger.info("RF24: aviso %s", 1)\n'
        'def f():\n    """Cita RF11 en el docstring."""\n'
    )
    lineas = sorted(i.split(":")[1] for i in _infracciones(fuente))
    assert lineas == ["1", "2", "3", "4"]


# ── Jerga del manual y del equipo ─────────────────────────────────────────────
# Segunda vigilancia: referencias al manual, códigos de error/regla, «SAC»,
# «relleno» y estados en mayúsculas dentro de frases que ve el usuario.

JERGA = (
    re.compile(r"Tabla \d"),
    re.compile(r"Manual,? p"),
    re.compile(r"\bp\. ?\d"),
    re.compile(r"\b[Ee]rror \d{3}\b"),
    re.compile(r"\bregla \d{3}\b"),
    re.compile(r"\bSAC\b"),
    re.compile(r"\bMatriz\b"),
    re.compile(r"\brelleno\b"),
    re.compile(r"estado (BORRADOR|VALIDADO|ENVIADO)"),
    re.compile(r"\[\s*'"),
)
MARCAS_SQL = ("SELECT", "INSERT", "UPDATE", "DELETE", "FROM", "WHERE", "JOIN", "NEXOVOLT.", "SAC.", "NVL(", "||")


def _es_prosa(texto):
    """Frase para una persona: con un espacio y alguna minúscula, y que no sea SQL."""
    if " " not in texto or not re.search(r"[a-záéíóúñ]", texto):
        return False
    return not any(marca in texto for marca in MARCAS_SQL)


def _infracciones_jerga(fuente, nombre="<modulo>"):
    arbol = ast.parse(fuente)
    return [
        f"{nombre}:{linea}: {texto!r}"
        for linea, texto in _textos(arbol)
        if _es_prosa(texto) and any(p.search(texto) for p in JERGA)
    ]


def test_los_textos_de_pantalla_no_llevan_jerga_del_manual():
    encontrados = []
    for ruta in _modulos():
        fuente = ruta.read_text(encoding="utf-8")
        encontrados += _infracciones_jerga(fuente, ruta.relative_to(RAIZ).as_posix())
    assert not encontrados, "Textos con jerga:\n" + "\n".join(encontrados)


def test_el_detector_de_jerga_distingue_casos():
    malos = [
        'a = "Estado no válido. Usa un código de la Tabla 4b."',
        'b = "No reconocido (Manual, p. 43)."',
        'c = "Archivo fuera de rango (p. 38-39)"',
        'd = f"Error 713: no permite pasar de {x}"',
        'e = "Cambio inválido (regla 713) en el corte"',
        'f = "Crédito caducado en el SAC sin mora"',
        'g = "la Matriz no permite el cambio"',
        'h = "datos con relleno (XXX)"',
        'i = "El corte no está en estado BORRADOR."',
        'j = "Usuario actualizado: [\'nombre\']"',
    ]
    for fuente in malos:
        assert len(_infracciones_jerga(fuente)) == 1, fuente
    buenos = [
        'a = "SELECT ESTADO_SAC FROM NEXOVOLT.NV_X WHERE A = 1"',
        "b = \"'Obligacion ' || o.NUMERO || ' ya no viene del SAC'\"",
        'c = {"regla": "CAMBIO_ESTADO_INVALIDO", "estado": "BORRADOR"}',
        'd = "SAC"',
        'e = "El corte no está en borrador."',
        'f = "TransUnion no acepta pasar de Vigente a Castigada"',
        'logger.info("Error 713 en el corte %s", 1)\n',
        'def f():\n    """Ver Manual, p. 43 y la Tabla 4b."""\n',
    ]
    for fuente in buenos:
        assert _infracciones_jerga(fuente) == [], fuente
