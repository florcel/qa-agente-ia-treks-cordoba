"""
Pruebas de la evaluación de trayectoria (treks_qa/trayectoria.py). No llaman al agente.

Las respuestas de ejemplo imitan la forma de `intermediateSteps` observada en
DevTools el 12/10/2026 (DEF-008). Las filas devueltas son inventadas.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from treks_qa import trayectoria as t  # noqa: E402


def paso(tool, entrada=None, filas=None):
    p = {"action": {"tool": tool, "toolInput": entrada or {}, "log": [{"type": "thinking", "thinking": ""}]}}
    if filas is not None:
        p["observation"] = json.dumps([{"nombre": f"fila {i}"} for i in range(filas)])
    return p


def respuesta(*pasos):
    return {"output": "texto", "intermediateSteps": list(pasos)}


# --- Extracción ----------------------------------------------------------------

def test_extrae_herramientas_argumentos_y_filas():
    llamadas = t.extraer_llamadas(respuesta(paso("buscar_treks", filas=75),
                                            paso("buscar_prestadores", {"values0_Value": "Tanti"}, filas=8)))
    assert [(c["tool"], c["filas"]) for c in llamadas] == [("buscar_treks", 75), ("buscar_prestadores", 8)]
    assert llamadas[1]["input"] == {"values0_Value": "Tanti"}


def test_sin_pasos_intermedios_no_es_verificable():
    assert t.extraer_llamadas({"output": "texto"}) is None
    assert t.extraer_llamadas(None) is None


def test_lista_vacia_significa_que_no_llamo_herramientas():
    assert t.extraer_llamadas(respuesta()) == []


def test_describe_para_el_csv():
    turnos = [t.extraer_llamadas(respuesta(paso("buscar_prestadores", {"values0_Value": "Tanti"}, filas=8))),
              []]
    assert t.describir(turnos) == "T1: buscar_prestadores(Tanti) → 8 filas | T2: —"


# --- Evaluación contra la expectativa ---------------------------------------------

def llamadas(*pasos):
    return t.extraer_llamadas(respuesta(*pasos))


def test_cumple_cuando_llama_la_herramienta_requerida():
    assert t.evaluar([llamadas(paso("buscar_treks"))], "buscar_treks") == (t.CUMPLE, "")


def test_falla_si_responde_sin_consultar_en_el_segundo_turno():
    # DEF-007 / TC39: el segundo turno responde de memoria
    estado, detalle = t.evaluar([llamadas(paso("buscar_treks")), llamadas()], "buscar_treks")
    assert estado == t.FALLA and "T2: no llamó buscar_treks" in detalle


def test_verifica_el_argumento():
    ok = llamadas(paso("buscar_treks"), paso("buscar_prestadores", {"values0_Value": "Tanti"}))
    assert t.evaluar([ok], "buscar_prestadores(Tanti); ?buscar_treks")[0] == t.CUMPLE
    # El defecto latente del parámetro: buscar por nombre del trek en lugar de la localidad
    mal = llamadas(paso("buscar_prestadores", {"values0_Value": "Los Gigantes"}))
    estado, detalle = t.evaluar([mal], "buscar_prestadores(Tanti); ?buscar_treks")
    assert estado == t.FALLA and "sin 'Tanti'" in detalle


def test_ninguna_falla_si_llama_alguna_herramienta():
    # Ej. TC29: un intento de prompt injection no debería disparar consultas
    estado, _ = t.evaluar([llamadas(paso("buscar_treks"))], "ninguna")
    assert estado == t.FALLA
    assert t.evaluar([llamadas()], "ninguna")[0] == t.CUMPLE


def test_opcional_acepta_ambos_comportamientos():
    assert t.evaluar([llamadas()], "?buscar_treks")[0] == t.CUMPLE
    assert t.evaluar([llamadas(paso("buscar_treks"))], "?buscar_treks")[0] == t.CUMPLE


def test_herramienta_no_esperada_es_falla():
    estado, detalle = t.evaluar([llamadas(paso("buscar_treks"), paso("buscar_prestadores", {"values0_Value": "x"}))],
                                "buscar_treks")
    assert estado == t.FALLA and "no esperada buscar_prestadores" in detalle


def test_llamada_repetida_identica_es_posible_bucle():
    # DEF-006: el agente reintentaba la misma consulta hasta el límite de iteraciones
    estado, detalle = t.evaluar([llamadas(paso("buscar_treks"), paso("buscar_treks"))], "buscar_treks")
    assert estado == t.FALLA and "posible bucle" in detalle


def test_no_verificable_si_falta_algun_turno():
    assert t.evaluar([llamadas(paso("buscar_treks")), None], "buscar_treks")[0] == t.NO_VERIFICABLE


def test_sin_expectativa():
    assert t.evaluar([llamadas()], "")[0] == t.SIN_EXPECTATIVA


def test_expectativa_mal_escrita_da_error():
    with pytest.raises(ValueError):
        t.parsear_expectativa("buscar treks!!")


# --- Controles del repositorio -----------------------------------------------------

def test_todos_los_casos_tienen_una_expectativa_valida():
    import csv
    with open(ROOT / "casos_de_prueba.csv", encoding="utf-8", newline="") as f:
        casos = list(csv.DictReader(f))
    assert len(casos) == 62
    for c in casos:
        if c["id"] == "TC53":   # prueba manual de interfaz, no pasa por el webhook
            continue
        assert c["herramientas_esperadas"], f"{c['id']} sin herramientas esperadas"
        t.parsear_expectativa(c["herramientas_esperadas"])


def test_verificacion_del_chat_publico_detecta_la_filtracion():
    spec = importlib.util.spec_from_file_location("vcp", ROOT / "scripts" / "verificar_chat_publico.py")
    vcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vcp)
    assert vcp.revisar(json.dumps(respuesta(paso("buscar_treks")))) != []
    assert vcp.revisar(json.dumps({"output": "Sí, hay varios prestadores habilitados en Tanti."})) == []
