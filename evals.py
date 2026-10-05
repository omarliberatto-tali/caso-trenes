from __future__ import annotations

import argparse
import json
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

from contrato import Item, Veredicto

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


def veredictos_esperados(expediente: str) -> List[Dict]:
    datos = json.loads((REFERENCIA / expediente / "referencia.json").read_text(encoding="utf-8"))
    return datos["veredictos"]


def _fuente_ok(obtenido: Veredicto, esperado: Dict) -> bool:
    """La fuente es correcta si alguna evidencia cae en el documento esperado y en una de sus
    paginas admitidas. Si la referencia no trae evidencia (sin_respaldo), lo correcto es no
    citar nada: citar algo ahi es respaldar con material que no corresponde.

    El fragmento no se compara con el de la referencia: con citations es texto literal del
    PDF por construccion, y la referencia guarda uno solo de los pasajes validos.
    """
    if not esperado["evidencia"]:
        return not obtenido["evidencia"]
    for ev_ref in esperado["evidencia"]:
        admitidas = esperado.get("paginas_admitidas") or [ev_ref["pagina"]]
        for ev in obtenido["evidencia"]:
            if ev["documento_id"] == ev_ref["documento_id"] and ev["pagina"] in admitidas:
                return True
    return False


def fuentes_extra(expediente: str) -> Dict[str, Dict]:
    """Fuentes que se aceptan ademas de las de la referencia, justificadas una por una en
    ``referencia/fuentes_extra.json``. Solo alimentan el numero de fuente ampliada."""
    ruta = REFERENCIA / "fuentes_extra.json"
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8")).get(expediente, {})


def calificar_veredictos(
    obtenidos: List[Veredicto], referencia: List[Dict], extra: Dict[str, Dict] | None = None
) -> Tuple[Dict, List[Dict]]:
    extra = extra or {}
    por_id = {v["item_id"]: v for v in obtenidos}
    detalle: List[Dict] = []
    for esperado in referencia:
        obtenido = por_id.get(esperado["item_id"])
        if obtenido is None:
            detalle.append({"id": esperado["item_id"], "estado_ok": False, "fuente_ok": False, "faltante": True})
            continue
        fuente_ok = _fuente_ok(obtenido, esperado)
        admitidas = [tuple(a) for a in extra.get(esperado["item_id"], {}).get("admitidas", [])]
        citadas = [(e["documento_id"], e["pagina"]) for e in obtenido["evidencia"]]
        detalle.append(
            {
                "id": esperado["item_id"],
                "estado_ok": obtenido["estado"] == esperado["estado"],
                "fuente_ok": fuente_ok,
                "fuente_ampliada_ok": fuente_ok or any(c in admitidas for c in citadas),
                "estado_esperado": esperado["estado"],
                "estado_obtenido": obtenido["estado"],
                "fuente_esperada": [(e["documento_id"], e["pagina"]) for e in esperado["evidencia"]],
                "fuente_obtenida": [(e["documento_id"], e["pagina"]) for e in obtenido["evidencia"]],
                "confianza": obtenido["confianza"],
            }
        )
    total = len(referencia)
    resumen = {
        "total_referencia": total,
        "acierto_item_pct": round(100 * sum(d["estado_ok"] for d in detalle) / total, 1) if total else 0.0,
        "acierto_fuente_pct": round(100 * sum(d["fuente_ok"] for d in detalle) / total, 1) if total else 0.0,
        "acierto_fuente_ampliada_pct": (
            round(100 * sum(d.get("fuente_ampliada_ok", False) for d in detalle) / total, 1) if total else 0.0
        ),
        "faltantes": sum(1 for d in detalle if d.get("faltante")),
    }
    return resumen, detalle


def main() -> None:
    ap = argparse.ArgumentParser(description="Califica la extraccion contra el set de referencia.")
    ap.add_argument("expediente", nargs="?", default="C1_Impresos_y_formularios")
    ap.add_argument("--items", default=None)
    ap.add_argument("--veredictos", default=None)
    args = ap.parse_args()

    ruta = Path(args.items) if args.items else RAIZ / "salida" / args.expediente / "items.json"
    obtenidos: List[Item] = json.loads(ruta.read_text(encoding="utf-8"))
    resumen, detalle = calificar(obtenidos, esperados(args.expediente))

    print(f"EVAL {args.expediente}")
    print("EXTRACCION (M1/M2)")
    print(f"  acierto de afirmacion {resumen['acierto_item_pct']}%  ({resumen['aciertos']}/{resumen['total_referencia']})")
    print(f"  acierto de pagina     {resumen['acierto_pagina_pct']}%")
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
    salida = {"resumen": resumen, "detalle": detalle}

    ruta_v = Path(args.veredictos) if args.veredictos else destino / "veredictos.json"
    if ruta_v.exists():
        obtenidos_v: List[Veredicto] = json.loads(ruta_v.read_text(encoding="utf-8"))
        resumen_v, detalle_v = calificar_veredictos(
            obtenidos_v, veredictos_esperados(args.expediente), fuentes_extra(args.expediente)
        )
        print("VERIFICACION (M3)")
        print(f"  acierto de item   {resumen_v['acierto_item_pct']}%  (el estado es el correcto)")
        print(f"  acierto de fuente {resumen_v['acierto_fuente_pct']}%  (documento y pagina citados son los correctos)")
        print(f"  fuente ampliada   {resumen_v['acierto_fuente_ampliada_pct']}%  (suma referencia/fuentes_extra.json)")
        fallas_v = [d for d in detalle_v if not (d["estado_ok"] and d["fuente_ok"])]
        if fallas_v:
            print("  casos que fallan:")
            for d in fallas_v:
                if d.get("faltante"):
                    print(f"    {d['id']}  faltante")
                    continue
                print(
                    f"    {d['id']}  estado {d['estado_obtenido']} (esperado {d['estado_esperado']})"
                    f"  cita {d['fuente_obtenida']} (esperada {d['fuente_esperada']})"
                    f"  confianza {d['confianza']}"
                    + ("  [fuente admitida en fuentes_extra]" if d["fuente_ampliada_ok"] and not d["fuente_ok"] else "")
                )
        salida["verificacion"] = {"resumen": resumen_v, "detalle": detalle_v}

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "eval.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
