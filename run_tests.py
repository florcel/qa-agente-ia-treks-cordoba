#!/usr/bin/env python3
"""
Ejecuta los casos de prueba de casos_de_prueba.csv contra el agente de n8n
(vía webhook) y guarda los resultados en resultados_<fecha>.csv.

Uso:
    python run_tests.py                      # todos los casos, 3 ejecuciones
    python run_tests.py --cases TC01,TC21    # solo algunos casos
    python run_tests.py --runs 1             # una ejecución por caso
    python run_tests.py --interactive        # incluye casos con pasos manuales [..]

Configuración por variables de entorno (o archivo .env), ver .env.example.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import datetime

import requests

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

def load_dotenv(path=".env"):
    """Carga un .env simple (CLAVE=valor) sin dependencias externas."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
# Nombres de campos: VERIFICALOS en tu versión de n8n (ver README / .env.example)
MESSAGE_FIELD = os.getenv("N8N_MESSAGE_FIELD", "chatInput")
SESSION_FIELD = os.getenv("N8N_SESSION_FIELD", "sessionId")
RESPONSE_FIELD = os.getenv("N8N_RESPONSE_FIELD", "output")
EXTRA_PAYLOAD = json.loads(os.getenv("N8N_EXTRA_PAYLOAD", "{}"))  # ej. {"action": "sendMessage"}
AUTH_HEADER_NAME = os.getenv("N8N_AUTH_HEADER_NAME", "")
AUTH_HEADER_VALUE = os.getenv("N8N_AUTH_HEADER_VALUE", "")
TOOL_NAME = os.getenv("AGENT_TOOL_NAME", "buscar_treks")
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "120"))

TURN_SEPARATOR = " || "
OUTPUT_COLUMNS = [
    "id", "ejecucion", "session_id", "fecha", "categoria", "entrada",
    "resultado_esperado", "severidad_si_falla", "respuesta_obtenida",
    "resultado", "invoco_herramienta", "id_ejecucion_n8n", "observaciones",
    "defecto",
]

# --------------------------------------------------------------------------
# Comunicación con el agente
# --------------------------------------------------------------------------

def send_message(message, session_id):
    """Envía un mensaje al webhook y devuelve (texto, json_crudo, error)."""
    payload = dict(EXTRA_PAYLOAD)
    payload[MESSAGE_FIELD] = message
    payload[SESSION_FIELD] = session_id
    headers = {"Content-Type": "application/json"}
    if AUTH_HEADER_NAME:
        headers[AUTH_HEADER_NAME] = AUTH_HEADER_VALUE

    last_error = ""
    for attempt in range(3):
        try:
            r = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            try:
                data = r.json()
            except ValueError:
                return r.text, None, ""
            # n8n puede devolver un objeto o una lista con un objeto
            obj = data[0] if isinstance(data, list) and data else data
            if isinstance(obj, dict) and RESPONSE_FIELD in obj:
                return str(obj[RESPONSE_FIELD]), obj, ""
            return json.dumps(data, ensure_ascii=False), obj, f"Campo '{RESPONSE_FIELD}' no encontrado"
        except requests.RequestException as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
    return "", None, f"Error de conexión: {last_error}"


def detect_tool_call(raw):
    """
    Detecta si el agente invocó la herramienta. Solo funciona si la respuesta
    del webhook incluye los pasos intermedios del AI Agent (en muchas versiones,
    opción 'Return Intermediate Steps'). Si no, devuelve 'No verificable'.
    """
    if not isinstance(raw, dict) or "intermediateSteps" not in raw:
        return "No verificable"
    steps = raw.get("intermediateSteps") or []
    text = json.dumps(steps, ensure_ascii=False).lower()
    if not steps:
        return "No"
    return "Sí" if TOOL_NAME.lower() in text or "tool" in text else "No verificable"

# --------------------------------------------------------------------------
# Verificación automática
# --------------------------------------------------------------------------

def normalize(s):
    """
    Minúsculas, sin tildes y sin separadores dentro de los números, para comparar
    de forma tolerante. Así "1.979", "1979", "8,3" y "8.3" se comparan igual
    (el agente responde con formato numérico en español).
    """
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"(?<=\d)[.,](?=\d)", "", s)


def evaluate(response, verification, tool_status):
    """
    Interpreta la columna 'verificacion' del CSV de casos.
    Devuelve (pasa_auto: bool, requiere_manual: bool, detalle: str).
    Sintaxis (cláusulas separadas por '; '):
      contains:X            la respuesta contiene X
      contains_any:A|B      contiene al menos uno
      contains_all:A|B|C    contiene todos
      not_contains:A|B      no contiene ninguno
      check_tool_call       la herramienta fue invocada
      manual                requiere revisión humana
    """
    resp = normalize(response)
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
        if kind == "contains" and normalize(value) not in resp:
            passed = False
            details.append(f"FALLA: no contiene '{value}'")
        elif kind == "contains_any":
            if not any(normalize(t) in resp for t in terms):
                passed = False
                details.append(f"FALLA: no contiene ninguno de {terms}")
        elif kind == "contains_all":
            missing = [t for t in terms if normalize(t) not in resp]
            if missing:
                passed = False
                details.append(f"FALLA: faltan {missing}")
        elif kind == "not_contains":
            found = [t for t in terms if normalize(t) in resp]
            if found:
                passed = False
                details.append(f"FALLA: contiene texto prohibido {found}")
    return passed, manual, " | ".join(details)


SEVERITY_MAP = {"grave": "Falla grave", "leve": "Falla leve"}

# --------------------------------------------------------------------------
# Ejecución de casos
# --------------------------------------------------------------------------

def run_case(case, run_number, interactive):
    turns = case["entrada"].split(TURN_SEPARATOR)
    session_id = f"{case['id'].lower()}-run{run_number}-{uuid.uuid4().hex[:6]}"
    responses, tool_statuses, errors = [], [], []

    for turn in turns:
        # Pasos manuales: texto entre [corchetes] al inicio del turno
        if turn.strip().startswith("["):
            action, _, turn = turn.partition("]")
            print(f"    PASO MANUAL: {action.strip('[ ')}")
            input("    Hacé el paso y presioná Enter para continuar...")
            turn = turn.strip()
        text, raw, err = send_message(turn, session_id)
        responses.append(text)
        tool_statuses.append(detect_tool_call(raw))
        if err:
            errors.append(err)

    final_response = responses[-1] if responses else ""
    full_log = "\n---\n".join(responses) if len(responses) > 1 else final_response

    # Para casos multi-turno, la herramienta debe haberse usado en todos los turnos
    if "No" in tool_statuses:
        tool_status = "No"
    elif all(t == "Sí" for t in tool_statuses):
        tool_status = "Sí"
    else:
        tool_status = "No verificable"

    if errors and not final_response:
        resultado, detalle = "Error de ejecución", " | ".join(errors)
    else:
        passed, manual, detalle = evaluate(final_response, case["verificacion"], tool_status)
        if not passed:
            resultado = SEVERITY_MAP.get(case["severidad_si_falla"].lower(), "Falla grave")
        elif manual:
            resultado = "Revisión manual"
        else:
            resultado = "Aprobado"
        if errors:
            detalle = (detalle + " | " if detalle else "") + " | ".join(errors)

    return {
        "id": case["id"],
        "ejecucion": run_number,
        "session_id": session_id,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "categoria": case["categoria"],
        "entrada": case["entrada"],
        "resultado_esperado": case["resultado_esperado"],
        "severidad_si_falla": case["severidad_si_falla"],
        "respuesta_obtenida": full_log,
        "resultado": resultado,
        "invoco_herramienta": tool_status,
        "id_ejecucion_n8n": "",
        "observaciones": detalle,
        "defecto": "",
    }


def main():
    parser = argparse.ArgumentParser(description="Ejecuta casos de prueba contra el agente de n8n.")
    parser.add_argument("--cases-file", default="casos_de_prueba.csv")
    parser.add_argument("--cases", help="IDs separados por coma, ej. TC01,TC05")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.5, help="Segundos entre llamadas")
    parser.add_argument("--interactive", action="store_true",
                        help="Incluir casos con pasos manuales [..] y pausar en ellos")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--solo-automaticos", action="store_true",
                        help="Omitir también los casos con verificación manual")
    args = parser.parse_args()

    if not WEBHOOK_URL:
        sys.exit("Falta N8N_WEBHOOK_URL (configuralo en .env).")

    with open(args.cases_file, encoding="utf-8") as f:
        cases = list(csv.DictReader(f))
    if args.cases:
        wanted = {c.strip().upper() for c in args.cases.split(",")}
        cases = [c for c in cases if c["id"].upper() in wanted]

    # Casos 100 % manuales (interfaz): nunca se envían por webhook
    manual_only = [c["id"] for c in cases if c["entrada"].startswith("[Prueba manual")]
    cases = [c for c in cases if not c["entrada"].startswith("[Prueba manual")]
    if manual_only:
        print(f"Solo manuales (probar en la interfaz): {', '.join(manual_only)}")

    if args.solo_automaticos:
        man = [c["id"] for c in cases if "manual" in c["verificacion"]]
        cases = [c for c in cases if "manual" not in c["verificacion"]]
        if man:
            print(f"Omitidos (verificación manual): {', '.join(man)}")

    skipped = []
    if not args.interactive:
        skipped = [c["id"] for c in cases if "[" in c["entrada"]]
        cases = [c for c in cases if "[" not in c["entrada"]]

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"resultados_{datetime.now():%Y-%m-%d_%H%M}.csv")

    print(f"Ejecutando {len(cases)} casos x {args.runs} ejecuciones -> {out_path}")
    if skipped:
        print(f"Omitidos (requieren pasos manuales, usar --interactive): {', '.join(skipped)}")

    rows = []
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for case in cases:
            for n in range(1, args.runs + 1):
                print(f"  {case['id']} ejecución {n}...", end=" ", flush=True)
                try:
                    row = run_case(case, n, args.interactive)
                except KeyboardInterrupt:
                    raise
                except Exception as e:  # un caso con error no corta la suite
                    row = {col: "" for col in OUTPUT_COLUMNS}
                    row.update({
                        "id": case["id"], "ejecucion": n,
                        "fecha": datetime.now().isoformat(timespec="seconds"),
                        "categoria": case["categoria"], "entrada": case["entrada"],
                        "resultado_esperado": case["resultado_esperado"],
                        "severidad_si_falla": case["severidad_si_falla"],
                        "resultado": "Error de ejecución",
                        "observaciones": f"{type(e).__name__}: {e}",
                    })
                writer.writerow(row)
                f.flush()  # si se corta, lo ya ejecutado queda guardado
                rows.append(row)
                print(row["resultado"])
                time.sleep(args.delay)

    # Resumen rápido (el informe completo es el entregable 7)
    print("\nResumen por ejecución:")
    totals = {}
    for r in rows:
        totals[r["resultado"]] = totals.get(r["resultado"], 0) + 1
    for k, v in sorted(totals.items()):
        print(f"  {k}: {v} ({v / len(rows):.0%})")


if __name__ == "__main__":
    main()
