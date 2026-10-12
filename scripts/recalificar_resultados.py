#!/usr/bin/env python3
"""
Recalifica resultados ya guardados con el criterio global, sin llamar al agente.

Para cada ejecución:
  resultado_recalificado = el peor entre la etiqueta original (que incluye la
  revisión manual) y el criterio global.

Además, vuelve a correr la verificación propia de cada caso con el evaluador
actual y lista las ejecuciones donde ese resultado automático no coincide con
la etiqueta original. Esas diferencias NO cambian la etiqueta: van a revisión
humana, porque pueden ser un error del evaluador anterior o del actual.

Uso:
    python scripts/recalificar_resultados.py results/ciclo2_completo_evaluado.csv
    python scripts/recalificar_resultados.py results/ciclo2_completo_evaluado.csv --casos casos_de_prueba.csv

Genera <archivo>_recalificado.csv junto al original y un resumen en consola.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from treks_qa.evaluacion import APROBADO, GRAVE, LEVE, criterio_global, evaluate, peor, split_turns  # noqa: E402

TURN_SEPARATOR_INPUT = " || "
COLUMNAS = ["id", "ejecucion", "categoria", "resultado_original", "resultado_recalificado",
            "cambio", "motivo", "fragmento", "verificacion_actual", "detalle_verificacion"]


def recalificar(filas, casos):
    salida = []
    for f in filas:
        n_turnos = len(f["entrada"].split(TURN_SEPARATOR_INPUT))
        turnos = split_turns(f["respuesta_obtenida"], n_turnos)
        original = f["resultado"]

        hallazgos = criterio_global(turnos)
        sev_global = peor(APROBADO, *[s for _, _, s in hallazgos]) if hallazgos else APROBADO
        nuevo = peor(original, sev_global)

        verif = casos.get(f["id"], {}).get("verificacion", "")
        pasa, _, detalle = evaluate(turnos, verif, f.get("invoco_herramienta", ""))
        verif_actual = "Pasa" if pasa else "Falla"

        salida.append({
            "id": f["id"], "ejecucion": f["ejecucion"], "categoria": f["categoria"],
            "resultado_original": original, "resultado_recalificado": nuevo,
            "cambio": "Sí" if nuevo != original else "No",
            "motivo": " | ".join(sorted({r for r, _, _ in hallazgos})),
            "fragmento": " | ".join(fr for _, fr, _ in hallazgos),
            "verificacion_actual": verif_actual,
            "detalle_verificacion": detalle,
        })
    return salida


def peor_por_caso(filas, columna):
    por_caso = defaultdict(list)
    for f in filas:
        por_caso[f["id"]].append(f[columna])
    return {caso: peor(*vals) for caso, vals in por_caso.items()}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Recalifica resultados guardados con el criterio global.")
    parser.add_argument("resultados")
    parser.add_argument("--casos", default="casos_de_prueba.csv")
    args = parser.parse_args()

    with open(args.resultados, encoding="utf-8", newline="") as fh:
        filas = list(csv.DictReader(fh))
    with open(args.casos, encoding="utf-8", newline="") as fh:
        casos = {c["id"]: c for c in csv.DictReader(fh)}

    salida = recalificar(filas, casos)
    destino = Path(args.resultados).with_name(Path(args.resultados).stem + "_recalificado.csv")
    with open(destino, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(salida)

    antes = peor_por_caso(salida, "resultado_original")
    despues = peor_por_caso(salida, "resultado_recalificado")
    n = len(antes)

    def resumen(d):
        c = Counter(d.values())
        return f"{c[APROBADO]} de {n} aprobados ({c[APROBADO] / n:.1%}), {c[LEVE]} leves, {c[GRAVE]} graves"

    ej_antes = Counter(f["resultado_original"] for f in salida)
    ej_despues = Counter(f["resultado_recalificado"] for f in salida)
    print(f"Por caso (peor de sus ejecuciones)\n  Antes:   {resumen(antes)}\n  Después: {resumen(despues)}")
    print(f"Por ejecución\n  Antes:   {ej_antes[APROBADO]} de {len(salida)} aprobadas"
          f"\n  Después: {ej_despues[APROBADO]} de {len(salida)} aprobadas")

    print("\nCasos que cambian:")
    for caso in sorted(antes):
        if antes[caso] != despues[caso]:
            motivos = sorted({f["motivo"] for f in salida if f["id"] == caso and f["cambio"] == "Sí"})
            print(f"  {caso}: {antes[caso]} -> {despues[caso]}  ({'; '.join(motivos)})")

    # Una etiqueta de falla en un caso con revisión manual es un juicio humano que la
    # verificación automática no puede reproducir: no se lista como diferencia.
    def es_diferencia(f):
        falla_auto = f["verificacion_actual"] == "Falla"
        falla_original = f["resultado_original"] in (LEVE, GRAVE)
        if falla_auto and not falla_original:
            return True
        manual = "manual" in casos.get(f["id"], {}).get("verificacion", "")
        return falla_original and not falla_auto and not manual and not f["motivo"]

    revisar = [f for f in salida if es_diferencia(f)]
    print(f"\nA revisar a mano: {len(revisar)} ejecuciones donde la verificación actual del caso "
          f"no coincide con la etiqueta original (no cambian la etiqueta):")
    for f in revisar:
        print(f"  {f['id']} e{f['ejecucion']}: original {f['resultado_original']}, "
              f"verificación actual {f['verificacion_actual']}. {f['detalle_verificacion']}")
    print(f"\nDetalle por ejecución en {destino}")


if __name__ == "__main__":
    main()
