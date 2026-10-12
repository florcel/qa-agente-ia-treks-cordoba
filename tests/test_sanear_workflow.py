"""Pruebas del saneado del workflow y control del archivo publicado (sin API)."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sanear", ROOT / "scripts" / "sanear_workflow.py")
sanear = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sanear)

WORKFLOW_PUBLICADO = ROOT / "agent" / "workflow" / "agente_treks_cordoba.json"


def test_quita_ids_de_credenciales_y_planillas():
    wf = {
        "id": "abc", "versionId": "v", "active": True, "meta": {"instanceId": "xyz"},
        "nodes": [{
            "name": "buscar_treks",
            "parameters": {"documentId": {"value": "1" + "a" * 43, "cachedResultUrl": "https://docs.google.com/x"}},
            "credentials": {"googleSheetsOAuth2Api": {"id": "secreto", "name": "Google Sheets account"}},
        }],
    }
    out = sanear.sanitize(wf)
    texto = json.dumps(out)
    assert "secreto" not in texto and "xyz" not in texto and "docs.google.com" not in texto
    assert out["nodes"][0]["credentials"]["googleSheetsOAuth2Api"] == {"name": "Google Sheets account"}
    assert out["active"] is False and "id" not in out


def test_detecta_filtraciones():
    assert sanear.find_leaks("https://docs.google.com/spreadsheets/d/" + "A" * 44) != []
    assert sanear.find_leaks('{"value": "REEMPLAZAR_POR_ID_DE_TU_PLANILLA"}') == []


def test_el_workflow_publicado_no_tiene_identificadores():
    texto = WORKFLOW_PUBLICADO.read_text(encoding="utf-8")
    assert sanear.find_leaks(texto) == []
    wf = json.loads(texto)
    for node in wf["nodes"]:
        for cred in (node.get("credentials") or {}).values():
            assert set(cred) == {"name"}, f"Credencial con ID en {node['name']}"
