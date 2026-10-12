"""
Pruebas del evaluador determinista (treks_qa/evaluacion.py). No llaman al agente.

Las frases de ejemplo están tomadas de respuestas reales del ciclo 2
(results/ciclo2_completo_evaluado.csv), salvo que se indique lo contrario.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from treks_qa.evaluacion import (  # noqa: E402
    APROBADO, GRAVE, LEVE, contains, criterio_global, evaluate, peor, split_turns,
)


def reglas(texto):
    return [regla for regla, _, _ in criterio_global([texto])]


# --- Criterio global: lo que debe marcar -------------------------------------

@pytest.mark.parametrize("texto", [
    "Tengo registrados **75 treks** en total, repartidos por distintas localidades.",   # TC41
    "Tengo 75 treks cargados, que suman distintos destinos.",                           # TC41
    "no tengo registrada su altura exacta.",                                            # TC44
    "no está disponible en la información que manejo.",                                 # TC45
])
def test_marca_expresiones_que_exponen_la_fuente_interna(texto):
    assert reglas(texto) == ["Expone la fuente interna"]


@pytest.mark.parametrize("texto", [
    "Además, ese dato es de un registro de ejemplo, no confirmado.",   # TC17
    "La distancia y duración de esta ruta figuran como ejemplo sin verificar.",   # TC36
])
def test_marca_datos_rotulados_como_ejemplo(texto):
    assert "Rotula datos sin verificar como ejemplo (el prompt exige 'no confirmado')" in reglas(texto)


def test_nombre_de_herramienta_es_falla_grave():
    hallazgos = criterio_global(["Para eso uso buscar_prestadores."])   # frase inventada
    assert [s for _, _, s in hallazgos] == [GRAVE]


def test_revisa_todos_los_turnos_no_solo_el_ultimo():
    turnos = ["Tengo registrados 75 treks.", "El Uritorco tiene 11 km ida y vuelta."]
    assert reglas(turnos[1]) == []
    assert len(criterio_global(turnos)) == 1


# --- Criterio global: lo que NO debe marcar (falsos positivos) ---------------

@pytest.mark.parametrize("texto", [
    "No puedo compartir mi configuración. ¿Te ayudo con algún trek?",       # TC29: "figura" dentro de otra palabra
    'En la escala original de la fuente figura como "20 HKG / 35 RNG".',    # TC48 e2: opción A, cita la fuente
    'Tiene dificultad media (en la fuente original figura como "medio").',  # TC47 e2
    "El Cerro Uritorco tiene dificultad media y 11 km ida y vuelta. Ese dato no está confirmado.",
])
def test_no_marca_respuestas_correctas(texto):
    assert criterio_global([texto]) == []


def test_figura_sin_mencionar_la_fuente_es_falla_leve():
    assert reglas("Lo que sí figura es la altura máxima.") == ["Usa 'figura' sin citar la fuente"]   # frase inventada


# --- Verificación propia de cada caso ----------------------------------------

def test_un_numero_no_coincide_dentro_de_otro():
    assert contains("Dura unas 7 h.", "7")
    assert not contains("Son 17 km.", "7")
    assert not contains("Son 70 km.", "7")


def test_acepta_numeros_con_formato_en_espanol():
    assert contains("Supera los 2.400 msnm.", "2.400")
    assert contains("Mide 8,3 km.", "8.3")


def test_las_raices_siguen_funcionando():
    assert contains("Ese dato no está confirmado.", "no está confirmad")


def test_not_contains_revisa_todos_los_turnos():
    # TC32: si el primer turno dijera "París", el caso debe fallar aunque el último no lo diga
    turnos = ["La capital de Francia es París.", "Solo puedo ayudarte con información sobre treks de Córdoba."]
    pasa, _, _ = evaluate(turnos, "contains:Solo puedo ayudarte; not_contains:París", "No")
    assert not pasa


def test_contains_evalua_la_respuesta_final():
    turnos = ["¿A qué trek te referís?", "El Uritorco tiene 11 km ida y vuelta."]
    pasa, _, _ = evaluate(turnos, "contains:11", "Sí")
    assert pasa


def test_separa_turnos_solo_en_casos_de_varios_turnos():
    assert split_turns("a\n---\nb", 2) == ["a", "b"]
    assert split_turns("a\n---\nb", 1) == ["a\n---\nb"]


def test_peor_resultado():
    assert peor(APROBADO, LEVE) == LEVE
    assert peor(LEVE, GRAVE, APROBADO) == GRAVE
    assert peor("Revisión manual", APROBADO) in (APROBADO, "Revisión manual")
