"""
Evaluación de la trayectoria del agente: qué herramientas llamó, cuántas veces y
con qué argumentos, en cada turno.

Fuente: el campo `intermediateSteps` que devuelve el AI Agent de n8n cuando
tiene activado "Return Intermediate Steps" (solo en el workflow de pruebas; ver
DEF-008). Cada paso tiene esta forma (simplificada):

    {"action": {"tool": "buscar_prestadores",
                "toolInput": {"values0_Value": "Tanti"},
                "log": [...]},
     "observation": "..."}

Expectativa por caso (columna `herramientas_esperadas` de casos_de_prueba.csv),
cláusulas separadas por '; ' y aplicadas a CADA turno del caso:

    buscar_treks                 la herramienta debe llamarse
    buscar_prestadores(Tanti)    debe llamarse con un argumento que contenga "Tanti"
    ?buscar_treks                puede llamarse o no (opcional)
    ninguna                      no debe llamarse ninguna herramienta

Cualquier herramienta llamada que no figure en la expectativa es una falla.
Llamar dos veces a la misma herramienta con el mismo argumento en un turno se
marca como posible bucle (ver DEF-006).
"""

import json
import re

from treks_qa.evaluacion import normalize

CUMPLE = "Cumple"
FALLA = "Falla"
NO_VERIFICABLE = "No verificable"
SIN_EXPECTATIVA = "Sin expectativa"

_CLAUSULA = re.compile(r"^(\?)?([\w-]+)(?:\((.*)\))?$")


def extraer_llamadas(raw):
    """
    Devuelve la lista de llamadas de una respuesta del webhook, o None si la
    respuesta no trae pasos intermedios (no se puede verificar).
    Cada llamada: {"tool": str, "input": dict|str, "filas": int|None}.
    """
    if not isinstance(raw, dict) or "intermediateSteps" not in raw:
        return None
    llamadas = []
    for paso in raw.get("intermediateSteps") or []:
        if not isinstance(paso, dict):
            continue
        accion = paso.get("action") if isinstance(paso.get("action"), dict) else paso
        tool = accion.get("tool")
        if not tool:
            continue
        llamadas.append({
            "tool": tool,
            "input": accion.get("toolInput", accion.get("tool_input", {})),
            "filas": _contar_filas(paso.get("observation")),
        })
    return llamadas


def _contar_filas(observacion):
    """Cantidad de filas devueltas, si la observación es una lista JSON."""
    if observacion is None:
        return None
    if isinstance(observacion, str):
        try:
            observacion = json.loads(observacion)
        except ValueError:
            return None
    return len(observacion) if isinstance(observacion, list) else None


def _valores(entrada):
    if isinstance(entrada, dict):
        return [str(v) for v in entrada.values()]
    return [str(entrada)] if entrada not in (None, "") else []


def describir(llamadas_por_turno):
    """Texto legible para el CSV: 'T1: buscar_treks() | T2: —'."""
    partes = []
    for i, llamadas in enumerate(llamadas_por_turno, 1):
        if llamadas is None:
            partes.append(f"T{i}: ?")
        elif not llamadas:
            partes.append(f"T{i}: —")
        else:
            textos = []
            for c in llamadas:
                args = ", ".join(_valores(c["input"]))
                filas = f" → {c['filas']} filas" if c["filas"] is not None else ""
                textos.append(f"{c['tool']}({args}){filas}")
            partes.append(f"T{i}: " + "; ".join(textos))
    return " | ".join(partes)


def parsear_expectativa(texto):
    """Devuelve (requeridas, opcionales, ninguna). requeridas: lista de (tool, argumento|None)."""
    requeridas, opcionales, ninguna = [], set(), False
    for clausula in [c.strip() for c in (texto or "").split(";") if c.strip()]:
        if clausula == "ninguna":
            ninguna = True
            continue
        m = _CLAUSULA.match(clausula)
        if not m:
            raise ValueError(f"Expectativa de herramientas inválida: '{clausula}'")
        opcional, tool, arg = m.groups()
        if opcional:
            opcionales.add(tool)
        else:
            requeridas.append((tool, arg.strip() if arg else None))
    return requeridas, opcionales, ninguna


def evaluar(llamadas_por_turno, expectativa):
    """
    Compara las llamadas de cada turno con la expectativa del caso.
    Devuelve (estado, detalle), con estado Cumple / Falla / No verificable / Sin expectativa.
    """
    if not (expectativa or "").strip():
        return SIN_EXPECTATIVA, ""
    if any(llamadas is None for llamadas in llamadas_por_turno):
        return NO_VERIFICABLE, "La respuesta no trae intermediateSteps (¿workflow de pruebas?)"

    requeridas, opcionales, ninguna = parsear_expectativa(expectativa)
    permitidas = {t for t, _ in requeridas} | opcionales
    problemas = []

    for i, llamadas in enumerate(llamadas_por_turno, 1):
        llamadas_turno = [c["tool"] for c in llamadas]
        if ninguna and llamadas_turno and not permitidas:
            problemas.append(f"T{i}: llamó {', '.join(llamadas_turno)} y no debía llamar ninguna")
            continue
        for tool, arg in requeridas:
            del_tool = [c for c in llamadas if c["tool"] == tool]
            if not del_tool:
                problemas.append(f"T{i}: no llamó {tool}")
            elif arg and not any(normalize(arg) in normalize(v) for c in del_tool for v in _valores(c["input"])):
                usados = "; ".join(", ".join(_valores(c["input"])) or "sin argumentos" for c in del_tool)
                problemas.append(f"T{i}: llamó {tool} sin '{arg}' (usó: {usados})")
        inesperadas = sorted({t for t in llamadas_turno if t not in permitidas})
        if inesperadas and not (ninguna and not permitidas):
            problemas.append(f"T{i}: herramienta no esperada {', '.join(inesperadas)}")
        vistas = set()
        for c in llamadas:
            clave = (c["tool"], json.dumps(c["input"], sort_keys=True, ensure_ascii=False))
            if clave in vistas:
                problemas.append(f"T{i}: llamó dos veces {c['tool']} con el mismo argumento (posible bucle)")
                break
            vistas.add(clave)

    return (FALLA, " | ".join(problemas)) if problemas else (CUMPLE, "")
