#!/usr/bin/env python3
"""
Detecta y reemplaza datos personales en los CSV de resultados antes de publicarlos.

Los resultados guardan las respuestas completas del agente. Cuando el agente
consulta el listado real de prestadores, esas respuestas incluyen nombres,
teléfonos y emails de personas reales, que no deben subirse al repositorio.

Uso:
    python scripts/anonimizar_resultados.py                      # verifica results/*.csv
    python scripts/anonimizar_resultados.py results/ciclo3.csv   # verifica archivos puntuales
    python scripts/anonimizar_resultados.py --corregir           # reemplaza en el lugar
    python scripts/anonimizar_resultados.py --nombres data/privado/prestadores_real.csv

Modo verificación (por defecto): no modifica nada. Termina con código 1 si
encuentra datos personales, para poder usarlo como control antes de un commit.

Qué detecta:
  - Emails (salvo los ficticios de @ejemplo.com).
  - Teléfonos: secuencias de 10 o más dígitos con espacios, guiones o "+".
  - Nombres de prestadores en negrita (**Nombre**) en líneas que también tienen
    una actividad (Trekking, Caminatas...) y un dato de contacto.
  - Con --nombres: cualquier aparición de los nombres del listado real.

Limitación: sin --nombres, un nombre escrito fuera de una línea de contacto
(ej. "podés llamar a Juan Pérez") no se detecta. Revisá el resultado a mano.
"""

import argparse
import csv
import glob
import re
import sys

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w/])\+?\d[\d \-]{8,}\d(?![\w/])")
BOLD = re.compile(r"\*\*([^*\n]+?)\*\*")
ACTIVITIES = re.compile(
    r"trekking|caminata|escalada|cicloturismo|kayak|canotaje|astroturismo|rappel|"
    r"espeleoturismo|tirolesa|baqueano|cabalgata|monta[nñ]ismo",
    re.IGNORECASE,
)
CONTACT = re.compile(r"\[tel[eé]fono\]|\[email\]|\btel\b|@|\d{6,}|\d{3,4}[ -]\d{2,4}-\d{3,4}", re.IGNORECASE)

PLACEHOLDER_EMAIL = "[email]"
PLACEHOLDER_PHONE = "[teléfono]"
PLACEHOLDER_NAME = "[prestador]"

# Datos ficticios permitidos (los del CSV anonimizado del repositorio)
ALLOWED_EMAIL_DOMAINS = ("@ejemplo.com",)
ALLOWED_PHONE_MARKERS = ("000-0",)


def _is_phone(match_text):
    if any(m in match_text for m in ALLOWED_PHONE_MARKERS):
        return False
    return sum(c.isdigit() for c in match_text) >= 10


def _is_real_email(match_text):
    return not match_text.lower().endswith(ALLOWED_EMAIL_DOMAINS)


def load_names(path):
    """Lee la columna 'nombre' del listado real (archivo local, no se publica)."""
    with open(path, encoding="utf-8", newline="") as f:
        names = [row["nombre"].strip() for row in csv.DictReader(f) if row.get("nombre", "").strip()]
    # Más largos primero, para no reemplazar un nombre corto dentro de uno largo
    return sorted(set(names), key=len, reverse=True)


def find_pii(text, names=()):
    """Devuelve una lista de (tipo, fragmento) con los datos personales encontrados."""
    found = []
    for m in EMAIL.finditer(text):
        if _is_real_email(m.group(0)):
            found.append(("email", m.group(0)))
    for m in PHONE.finditer(text):
        if _is_phone(m.group(0)):
            found.append(("teléfono", m.group(0).strip()))
    for line in text.splitlines():
        if ACTIVITIES.search(line) and CONTACT.search(line):
            for m in BOLD.finditer(line):
                if m.group(1).strip() != PLACEHOLDER_NAME:
                    found.append(("nombre", m.group(1).strip()))
    lowered = text.lower()
    for name in names:
        if name.lower() in lowered:
            found.append(("nombre", name))
    return found


def anonymize(text, names=()):
    """Devuelve el texto con los datos personales reemplazados por marcadores."""
    for name in names:
        text = re.sub(re.escape(name), PLACEHOLDER_NAME, text, flags=re.IGNORECASE)
    text = EMAIL.sub(lambda m: PLACEHOLDER_EMAIL if _is_real_email(m.group(0)) else m.group(0), text)

    def _phone(m):
        raw = m.group(0)
        if not _is_phone(raw):
            return raw
        # Conservar el espacio inicial o final que haya tomado la expresión
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        return lead + PLACEHOLDER_PHONE + trail

    text = PHONE.sub(_phone, text)

    lines = []
    for line in text.split("\n"):
        if ACTIVITIES.search(line) and CONTACT.search(line):
            line = BOLD.sub(f"**{PLACEHOLDER_NAME}**", line)
        lines.append(line)
    return "\n".join(lines)


def mask(fragment):
    """Muestra solo el inicio del dato encontrado, para no reimprimirlo entero."""
    return fragment[:4] + "…" if len(fragment) > 4 else "…"


def process_file(path, names, fix):
    with open(path, encoding="utf-8", newline="") as f:
        content = f.read()
    rows = list(csv.reader(content.splitlines(keepends=True)))
    if not rows:
        return 0
    header, data = rows[0], rows[1:]
    findings = 0
    changed = False
    for row in data:
        for col, value in enumerate(row):
            hits = find_pii(value, names)
            if not hits:
                continue
            findings += len(hits)
            case_id = row[0] if row else "?"
            run = row[1] if len(row) > 1 else ""
            for kind, fragment in hits:
                print(f"  {path} | {case_id} {run} | {header[col]} | {kind}: {mask(fragment)}")
            if fix:
                new_value = anonymize(value, names)
                if new_value != value:
                    row[col] = new_value
                    changed = True
    if fix and changed:
        line_end = "\r\n" if "\r\n" in content else "\n"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator=line_end)
            writer.writerow(header)
            writer.writerows(data)
    return findings


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Detecta y reemplaza datos personales en resultados.")
    parser.add_argument("paths", nargs="*", help="CSV a revisar (por defecto, results/*.csv)")
    parser.add_argument("--corregir", action="store_true", help="Reemplazar los datos en el lugar")
    parser.add_argument("--nombres", help="CSV local del listado real, con columna 'nombre'")
    args = parser.parse_args()

    paths = args.paths or sorted(glob.glob("results/*.csv"))
    if not paths:
        sys.exit("No hay archivos para revisar.")
    names = load_names(args.nombres) if args.nombres else []

    total = 0
    for path in paths:
        total += process_file(path, names, args.corregir)

    if args.corregir:
        remaining = sum(process_file(p, names, False) for p in paths) if total else 0
        print(f"\nReemplazados: {total}. Pendientes después de corregir: {remaining}.")
        sys.exit(1 if remaining else 0)

    if total:
        print(f"\n{total} datos personales encontrados. Corré con --corregir y revisá el resultado.")
        sys.exit(1)
    print(f"Sin datos personales detectados en {len(paths)} archivo(s).")


if __name__ == "__main__":
    main()
