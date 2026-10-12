#!/usr/bin/env python3
"""
Prepara el workflow exportado de n8n para publicarlo en el repositorio.

Quita los identificadores que vinculan el workflow con tu cuenta y tus datos:
IDs de credenciales, IDs y URLs de las planillas de Google, ID de la instancia
y del workflow. No cambia el comportamiento del agente (prompt, herramientas,
filtros, modelo).

Uso:
    python scripts/sanear_workflow.py "ruta/al/export.json"
    python scripts/sanear_workflow.py export.json --salida agent/workflow/agente_treks_cordoba.json

Después de importar el archivo en n8n hay que elegir tus credenciales y tus
planillas en los nodos de Anthropic y de Google Sheets (ver README).
"""

import argparse
import json
import re
import sys

PLACEHOLDER_DOC = "REEMPLAZAR_POR_ID_DE_TU_PLANILLA"
TOP_LEVEL_DROP = ("id", "versionId", "shared")

# Patrones que no deben quedar en el archivo publicado
LEAK_PATTERNS = {
    "URL de Google Sheets": re.compile(r"docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]{20,}"),
    "ID de planilla de Google": re.compile(r"\b1[A-Za-z0-9_-]{40,}\b"),
    "clave de API": re.compile(r"sk-ant-[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]{30,}"),
}


def sanitize(workflow):
    for key in TOP_LEVEL_DROP:
        workflow.pop(key, None)
    workflow["active"] = False
    workflow["pinData"] = {}
    if isinstance(workflow.get("meta"), dict):
        workflow["meta"].pop("instanceId", None)

    for node in workflow.get("nodes", []):
        # Credenciales: se conserva solo el nombre, para saber cuál asignar al importar
        for cred_type, cred in (node.get("credentials") or {}).items():
            node["credentials"][cred_type] = {"name": cred.get("name", cred_type)}

        params = node.get("parameters", {})
        doc = params.get("documentId")
        if isinstance(doc, dict):
            doc["value"] = PLACEHOLDER_DOC
            doc["cachedResultUrl"] = ""
        sheet = params.get("sheetName")
        if isinstance(sheet, dict):
            sheet["cachedResultUrl"] = ""
        model = params.get("model")
        if isinstance(model, dict):
            model["cachedResultUrl"] = ""
    return workflow


def find_leaks(text):
    return [name for name, pattern in LEAK_PATTERNS.items() if pattern.search(text)]


def main():
    parser = argparse.ArgumentParser(description="Sanea un workflow exportado de n8n para publicarlo.")
    parser.add_argument("entrada", help="JSON exportado desde n8n")
    parser.add_argument("--salida", default="agent/workflow/agente_treks_cordoba.json")
    args = parser.parse_args()

    with open(args.entrada, encoding="utf-8") as f:
        workflow = json.load(f)

    text = json.dumps(sanitize(workflow), ensure_ascii=False, indent=2) + "\n"
    leaks = find_leaks(text)
    if leaks:
        sys.exit(f"No se guardó: el resultado todavía contiene {', '.join(leaks)}. Revisá el export.")

    with open(args.salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"Workflow saneado en {args.salida}")


if __name__ == "__main__":
    main()
