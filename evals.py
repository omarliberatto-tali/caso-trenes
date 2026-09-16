from __future__ import annotations

import argparse
import json
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

from contrato import Item

RAIZ = Path(__file__).resolve().parent
REFERENCIA = RAIZ / "referencia"


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def esperados(expediente: str) -> List[Item]:
    datos = json.loads((REFERENCIA / expediente / "referencia.json").read_text(encoding="utf-8"))
    return datos["items"]


def calificar(obtenidos: List[Item], referencia: List[Item]) -> Tuple[Dict, List[Dict]]:
    por_id = {i["id"]: i for i in obtenidos}
    detalle: List[Dict] = []

    for esperado in referencia:
        obtenido = por_id.get(esperado["id"])
        if obtenido is None:
            detalle.append({"id": esperado["id"], "resultado": "faltante", "similitud": 0.0})
            continue
        sim = _similitud(obtenido["texto"], esperado["texto"])
        pagina_ok = obtenido["origen"]["pagina"] == esperado["origen"]["pagina"]
        detalle.append(
            {
                "id": esperado["id"],
                "resultado": "acierto" if _normalizar(obtenido["texto"]) == _normalizar(esperado["texto"]) else "texto_distinto",
                "similitud": round(sim, 3),
                "pagina_ok": pagina_ok,
                "pagina_esperada": esperado["origen"]["pagina"],
                "pagina_obtenida": obtenido["origen"]["pagina"],
            }
        )

    ids_ref = {i["id"] for i in referencia}
    for sobrante in sorted(set(por_id) - ids_ref):
        detalle.append({"id": sobrante, "resultado": "inventado", "similitud": 0.0})

    aciertos = [d for d in detalle if d["resultado"] == "acierto"]
    con_pagina = [d for d in detalle if d.get("pagina_ok")]
    total = len(referencia)
    resumen = {
        "total_referencia": total,
        "extraidos": len(obtenidos),
        "aciertos": len(aciertos),
        "acierto_item_pct": round(100 * len(aciertos) / total, 1) if total else 0.0,
        "acierto_pagina_pct": round(100 * len(con_pagina) / total, 1) if total else 0.0,
        "faltantes": sum(1 for d in detalle if d["resultado"] == "faltante"),
        "texto_distinto": sum(1 for d in detalle if d["resultado"] == "texto_distinto"),
        "inventados": sum(1 for d in detalle if d["resultado"] == "inventado"),
    }
    return resumen, detalle


def main() -> None:
    ap = argparse.ArgumentParser(description="Califica la extraccion contra el set de referencia.")
    ap.add_argument("expediente", nargs="?", default="C1_Impresos_y_formularios")
    ap.add_argument("--items", default=None)
    args = ap.parse_args()

    ruta = Path(args.items) if args.items else RAIZ / "salida" / args.expediente / "items.json"
    obtenidos: List[Item] = json.loads(ruta.read_text(encoding="utf-8"))
    resumen, detalle = calificar(obtenidos, esperados(args.expediente))

    print(f"EVAL {args.expediente}")
    print(f"  acierto de item   {resumen['acierto_item_pct']}%  ({resumen['aciertos']}/{resumen['total_referencia']})")
    print(f"  acierto de pagina {resumen['acierto_pagina_pct']}%")
    print(f"  extraidos {resumen['extraidos']} | faltantes {resumen['faltantes']} | texto distinto {resumen['texto_distinto']} | inventados {resumen['inventados']}")
    fallas = [d for d in detalle if d["resultado"] != "acierto" or not d.get("pagina_ok", True)]
    if fallas:
        print("  casos que fallan:")
        for d in fallas:
            extra = ""
            if d.get("pagina_ok") is False:
                extra = f" pagina {d['pagina_obtenida']} esperada {d['pagina_esperada']}"
            print(f"    {d['id']}  {d['resultado']}  sim={d['similitud']}{extra}")

    destino = RAIZ / "salida" / args.expediente
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "eval.json").write_text(
        json.dumps({"resumen": resumen, "detalle": detalle}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
