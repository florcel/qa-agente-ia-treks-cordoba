#!/usr/bin/env python3
"""
Verifica que el chat público no exponga los pasos internos del agente (DEF-008).

Envía una pregunta que obliga a usar herramientas al webhook del chat PÚBLICO
(N8N_PUBLIC_CHAT_URL en .env) y falla si la respuesta HTTP incluye
`intermediateSteps` o nombres de herramientas. Es el mismo control que se hizo
a mano con DevTools, automatizado para que el defecto no vuelva sin aviso.

Uso:
    python scripts/verificar_chat_publico.py

Consume un mensaje del modelo.
"""

import json
import os
import sys
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PREGUNTA = "¿Tenés guías para ir a Los Gigantes?"   # usa buscar_treks y buscar_prestadores
PROHIBIDOS = ("intermediateSteps", "buscar_treks", "buscar_prestadores", "toolInput", "observation")


def load_dotenv(path=ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def revisar(cuerpo):
    """Devuelve la lista de términos prohibidos presentes en la respuesta."""
    return [t for t in PROHIBIDOS if t in cuerpo]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()
    url = os.getenv("N8N_PUBLIC_CHAT_URL", "")
    if not url:
        sys.exit("Falta N8N_PUBLIC_CHAT_URL en .env (la URL del Chat Trigger del workflow público).")

    payload = {
        os.getenv("N8N_MESSAGE_FIELD", "chatInput"): PREGUNTA,
        os.getenv("N8N_SESSION_FIELD", "sessionId"): f"verificacion-publico-{uuid.uuid4().hex[:6]}",
    }
    payload.update(json.loads(os.getenv("N8N_EXTRA_PAYLOAD", "{}")))
    try:
        r = requests.post(url, json=payload, timeout=int(os.getenv("REQUEST_TIMEOUT", "120")))
    except requests.ConnectionError:
        sys.exit(f"No se pudo conectar con {url}. ¿Está corriendo n8n?")
    if r.status_code == 404:
        sys.exit("404: n8n no tiene ese webhook registrado. Verificá que el workflow público esté "
                 "activo y que N8N_PUBLIC_CHAT_URL sea la Production URL de su Chat Trigger.")
    r.raise_for_status()

    encontrados = revisar(r.text)
    if encontrados:
        print(f"FALLA (DEF-008): la respuesta del chat público contiene {encontrados}.")
        sys.exit(1)
    print("OK: la respuesta del chat público no expone pasos intermedios ni herramientas.")


if __name__ == "__main__":
    main()
