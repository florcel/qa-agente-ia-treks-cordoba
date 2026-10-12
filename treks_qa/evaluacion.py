"""
Verificaciones deterministas de las respuestas del agente.

Dos niveles:
  1. Verificación propia de cada caso (columna 'verificacion' de casos_de_prueba.csv).
  2. Criterio global: reglas que se aplican a TODAS las respuestas y a TODOS los
     turnos, sin importar el caso. Existe para que una misma expresión no se
     califique distinto según el caso (ver docs/defectos.md, DEF-005).

Ninguna de estas funciones llama al agente: se pueden usar sobre resultados
ya guardados (scripts/recalificar_resultados.py) y se prueban con pytest.
"""

import re
import unicodedata

TURN_SEPARATOR_LOG = "\n---\n"   # cómo guarda run_tests.py las respuestas de varios turnos

LEVE = "Falla leve"
GRAVE = "Falla grave"
APROBADO = "Aprobado"
_ORDEN = {APROBADO: 0, "Revisión manual": 0, LEVE: 1, GRAVE: 2, "Error de ejecución": 3}


def normalize(s):
    """
    Minúsculas, sin tildes y sin separadores dentro de los números, para comparar
    de forma tolerante. Así "1.979", "1979", "8,3" y "8.3" se comparan igual.
    """
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"(?<=\d)[.,](?=\d)", "", s)


def term_pattern(term):
    """
    Patrón para buscar un término en texto normalizado.
    - Siempre exige inicio de palabra: "figura" no coincide con "configuración".
    - Si el término termina en dígito, exige fin de número: "7" no coincide con "17" ni con "70".
    - Si termina en letra, no exige fin de palabra, para permitir raíces como "confirmad".
    """
    t = normalize(term)
    end = r"(?!\d)" if t and t[-1].isdigit() else ""
    start = r"(?<!\w)" if t and (t[0].isalnum() or t[0] == "_") else ""
    return re.compile(start + re.escape(t) + end)


def contains(text, term):
    return term_pattern(term).search(normalize(text)) is not None


def split_turns(response, n_turns):
    """Separa la respuesta guardada en sus turnos (solo si el caso tenía varios)."""
    if n_turns > 1 and TURN_SEPARATOR_LOG in response:
        return response.split(TURN_SEPARATOR_LOG)
    return [response]


# --------------------------------------------------------------------------
# 1. Verificación propia de cada caso
# --------------------------------------------------------------------------

def evaluate(turns, verification, tool_status):
    """
    Interpreta la columna 'verificacion' del CSV de casos.
    turns: lista de respuestas, una por turno (la última es la respuesta final).
    Devuelve (pasa_auto: bool, requiere_manual: bool, detalle: str).

    Sintaxis (cláusulas separadas por '; '):
      contains:X            la respuesta FINAL contiene X
      contains_any:A|B      la respuesta final contiene al menos uno
      contains_all:A|B|C    la respuesta final contiene todos
      not_contains:A|B      NINGÚN turno contiene ninguno
      check_tool_call       la herramienta fue invocada
      manual                requiere revisión humana
    """
    final = turns[-1] if turns else ""
    passed, manual, details = True, False, []

    for clause in [c.strip() for c in verification.split(";") if c.strip()]:
        if clause == "manual":
            manual = True
            continue
        if clause == "check_tool_call":
            if tool_status == "No":
                passed = False
                details.append("FALLA: no invocó la herramienta")
            elif tool_status == "No verificable":
                manual = True
                details.append("Herramienta: verificar en Executions de n8n")
            continue
        kind, _, value = clause.partition(":")
        terms = [t for t in value.split("|") if t]
        if kind == "contains" and not contains(final, value):
            passed = False
            details.append(f"FALLA: no contiene '{value}'")
        elif kind == "contains_any" and not any(contains(final, t) for t in terms):
            passed = False
            details.append(f"FALLA: no contiene ninguno de {terms}")
        elif kind == "contains_all":
            missing = [t for t in terms if not contains(final, t)]
            if missing:
                passed = False
                details.append(f"FALLA: faltan {missing}")
        elif kind == "not_contains":
            found = sorted({t for t in terms for turn in turns if contains(turn, t)})
            if found:
                passed = False
                details.append(f"FALLA: contiene texto prohibido {found}")
    return passed, manual, " | ".join(details)


# --------------------------------------------------------------------------
# 2. Criterio global
# --------------------------------------------------------------------------

# (nombre de la regla, patrón sobre texto normalizado, severidad)
REGLAS_GLOBALES = [
    ("Expone la configuración: nombre de herramienta",
     re.compile(r"buscar_treks|buscar_prestadores"), GRAVE),
    ("Expone la fuente interna",
     re.compile(r"(?<!\w)(registrad\w*|cargad\w*|tablas?\b|planillas?\b|filas?\b|columnas?\b|"
                r"en mi lista|segun mis datos|informacion que manejo|tengo disponibles)"), LEVE),
    ("Rotula datos sin verificar como ejemplo (el prompt exige 'no confirmado')",
     re.compile(r"(?<!\w)(de|como) ejemplo\b"), LEVE),
]

# Opción A para "figura": se acepta solo si la misma oración menciona la fuente.
_FIGURA = re.compile(r"(?<!\w)figur\w*")
_FUENTE = re.compile(r"(?<!\w)fuentes?\b")
_ORACION = re.compile(r"[^.!?\n]+")


def _figura_sin_fuente(texto_normalizado):
    for oracion in _ORACION.findall(texto_normalizado):
        m = _FIGURA.search(oracion)
        if m and not _FUENTE.search(oracion):
            return m.group(0)
    return None


def criterio_global(turns):
    """
    Aplica las reglas globales a todos los turnos.
    Devuelve una lista de (regla, fragmento, severidad); vacía si cumple.
    """
    hallazgos = []
    for turn in turns:
        texto = normalize(turn)
        for nombre, patron, severidad in REGLAS_GLOBALES:
            m = patron.search(texto)
            if m:
                hallazgos.append((nombre, _contexto(texto, m.start(), m.end()), severidad))
        figura = _figura_sin_fuente(texto)
        if figura:
            i = texto.find(figura)
            hallazgos.append(("Usa 'figura' sin citar la fuente", _contexto(texto, i, i + len(figura)), LEVE))
    return hallazgos


def _contexto(texto, start, end, margen=35):
    return texto[max(0, start - margen):end + margen].replace("\n", " ").strip()


def peor(*resultados):
    """El resultado más severo entre varios (aprobado < leve < grave < error)."""
    return max(resultados, key=lambda r: _ORDEN.get(r, 0))
