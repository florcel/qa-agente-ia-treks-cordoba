"""
Pruebas del script de anonimización (no llaman al agente ni consumen API).

Ejecutar desde la raíz del repositorio:
    pytest -v
"""

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("anon", ROOT / "scripts" / "anonimizar_resultados.py")
anon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anon)

# Línea con el mismo formato que usa el agente al listar prestadores (datos inventados)
LINEA_PRESTADOR = "1. **Gomez Ana Laura** – Trekking, Escalada – Tel: 54 9 351 123-4567 – ana.gomez@gmail.com"


def tipos(texto, nombres=()):
    return sorted({tipo for tipo, _ in anon.find_pii(texto, nombres)})


# --- Detección: lo que SÍ es un dato personal ---------------------------------

def test_detecta_nombre_telefono_y_email_en_linea_de_prestador():
    assert tipos(LINEA_PRESTADOR) == ["email", "nombre", "teléfono"]


def test_detecta_telefono_sin_separadores():
    assert tipos("Contacto: 54 9 3548546298") == ["teléfono"]


def test_detecta_nombre_del_listado_real_fuera_de_una_linea_de_contacto():
    assert tipos("Podés consultar con Gomez Ana Laura.", ["Gomez Ana Laura"]) == ["nombre"]


# --- Detección: lo que NO es un dato personal (falsos positivos) --------------

def test_no_marca_datos_de_treks():
    texto = "- **Los Gigantes**: 14 km ida y vuelta, unas 7 h. Altura: 2.374 msnm."
    assert anon.find_pii(texto) == []


def test_no_marca_fechas_ni_ids_de_sesion():
    assert anon.find_pii("2026-10-12T19:40:00 tc55-run1-50b87e") == []


def test_no_marca_los_datos_ficticios_del_repositorio():
    texto = "Prestador de ejemplo 01 – Caminatas – 54 9 351 000-0001 – prestador01@ejemplo.com"
    assert anon.find_pii(texto) == []


def test_no_marca_marcadores_ya_anonimizados():
    assert anon.find_pii("1. **[prestador]** – Trekking – Tel: [teléfono] – [email]") == []


# --- Reemplazo ----------------------------------------------------------------

def test_reemplaza_con_los_marcadores_del_ciclo_2():
    assert anon.anonymize(LINEA_PRESTADOR) == "1. **[prestador]** – Trekking, Escalada – Tel: [teléfono] – [email]"


def test_el_texto_anonimizado_ya_no_tiene_datos_personales():
    texto = LINEA_PRESTADOR + "\nTe recomiendo confirmar en Córdoba Turismo."
    assert anon.find_pii(anon.anonymize(texto)) == []


def test_no_modifica_respuestas_sin_datos_personales():
    texto = "El Cerro Uritorco tiene dificultad media y 11 km ida y vuelta."
    assert anon.anonymize(texto) == texto


# --- Control del repositorio --------------------------------------------------

def test_los_resultados_publicables_no_tienen_datos_personales():
    """Los CSV de results/ que se suben al repo (no las corridas crudas) deben estar anonimizados."""
    publicables = [p for p in sorted((ROOT / "results").glob("*.csv")) if not p.name.startswith("resultados_")]
    assert publicables, "No se encontraron resultados para revisar"
    encontrados = []
    for path in publicables:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                for valor in row:
                    encontrados += [(path.name, row[0], tipo) for tipo, _ in anon.find_pii(valor)]
    assert encontrados == [], f"Datos personales en resultados publicables: {encontrados}"
