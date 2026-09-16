from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from anthropic import Anthropic
from dotenv import load_dotenv

import corpus
from contrato import Item, Origen
from criterio import CRITERIO_AFIRMACION

MODELO = "claude-sonnet-5"
MAX_ITERACIONES = 5
MAX_TOKENS = 4096
FIN = "<FIN>"

# M3 enciende esto y no hay nada mas que reescribir: el bloque document ya viaja.
CITATIONS = False

SISTEMA = f"""Sos un analista de escritos judiciales argentinos. Tu unica tarea es leer un
escrito de demanda y devolver la lista de sus afirmaciones de hecho. No las evaluas, no las
resumis y no opinas sobre ellas: las extraes tal como estan.

{CRITERIO_AFIRMACION}

El escrito te llega como el PDF completo. La pagina que reportas es el numero de pagina
del PDF, empezando en 1.

FORMATO DE SALIDA
Un objeto JSON por linea, sin fences, sin numeracion y sin texto alrededor:
{{"id": "AF-01", "grupo": "A", "titulo": "Existencia de la orden de compra", "texto": "En fecha 26 de septiembre de 2025 la demandada emitio...", "pagina": 2}}

- id: AF- seguido del numero del inciso en dos digitos.
- grupo: la letra del subtitulo que agrupa al inciso (a=A, b=B, c=C...), o "" si no hay.
- titulo: el titulo corto del inciso, sin el punto final.
- texto: el cuerpo de la afirmacion, literal del escrito, sin el numero y sin el titulo.
  Si la afirmacion sigue en la pagina siguiente, incluila entera.
- pagina: la pagina donde ARRANCA la afirmacion.

SEÑAL DE FIN
Cuando emitiste la ultima afirmacion del capitulo IV, escribi una linea con {FIN} y nada mas.
No escribas {FIN} si todavia quedan incisos por emitir."""

_LINEA = re.compile(r"^\s*\{.*\}\s*$")


def _parsear(texto: str) -> Tuple[List[Dict], bool]:
    filas: List[Dict] = []
    fin = False
    for linea in texto.splitlines():
        if linea.strip() == FIN:
            fin = True
            continue
        if not _LINEA.match(linea):
            continue
        try:
            filas.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return filas, fin


def _a_item(fila: Dict, documento_id: str) -> Item:
    item: Item = {
        "id": str(fila.get("id", "")),
        "texto": str(fila.get("texto", "")),
        "origen": Origen(documento_id=documento_id, pagina=int(fila.get("pagina", 0))),
    }
    if fila.get("grupo"):
        item["grupo"] = str(fila["grupo"])
    if fila.get("titulo"):
        item["titulo"] = str(fila["titulo"])
    return item


def extraer(
    expediente: str,
    documento_id: str = "DEM",
    max_iteraciones: int = MAX_ITERACIONES,
    permitir_apartada: bool = False,
    verbose: bool = True,
) -> Tuple[List[Item], Dict]:
    load_dotenv()
    cliente = Anthropic()
    documento = corpus.bloque_documento(
        expediente, documento_id, permitir_apartada, citations=CITATIONS
    )

    mensajes: List[Dict] = [
        {
            "role": "user",
            "content": [
                documento,
                {
                    "type": "text",
                    "text": f"Escrito de demanda del expediente {expediente}. "
                    "Extrae sus afirmaciones de hecho.",
                },
            ],
        }
    ]

    encontrados: Dict[str, Item] = {}
    traza = {"iteraciones": 0, "motivo": "", "in": 0, "out": 0}

    for i in range(1, max_iteraciones + 1):
        traza["iteraciones"] = i
        rta = cliente.messages.create(
            model=MODELO,
            max_tokens=MAX_TOKENS,
            system=SISTEMA,
            messages=mensajes,
        )
        traza["in"] += rta.usage.input_tokens
        traza["out"] += rta.usage.output_tokens
        texto = "".join(b.text for b in rta.content if b.type == "text")
        filas, fin = _parsear(texto)

        nuevos = 0
        for fila in filas:
            item = _a_item(fila, documento_id)
            if item["id"] and item["id"] not in encontrados:
                encontrados[item["id"]] = item
                nuevos += 1

        if verbose:
            print(f"  iter {i}: {nuevos} nuevos (total {len(encontrados)}), fin={fin}, stop={rta.stop_reason}")

        if fin:
            traza["motivo"] = "señal de fin"
            break
        if nuevos == 0:
            traza["motivo"] = "sin progreso"
            break
        if i == max_iteraciones:
            traza["motivo"] = "max_iteraciones"
            break

        ultimo = max(encontrados)
        if rta.stop_reason == "max_tokens":
            texto = texto.rsplit("\n", 1)[0]
        mensajes.append({"role": "assistant", "content": texto})
        mensajes.append(
            {
                "role": "user",
                "content": f"Seguiste hasta {ultimo}. Continua desde el inciso siguiente, "
                f"mismo formato, sin repetir los que ya emitiste. Si {ultimo} era el ultimo "
                f"del capitulo IV, respondé solo {FIN}.",
            }
        )

    items = [encontrados[k] for k in sorted(encontrados)]
    return items, traza


def main() -> None:
    ap = argparse.ArgumentParser(description="Extrae las afirmaciones de hecho de una demanda.")
    ap.add_argument("expediente", nargs="?", default="C1_Impresos_y_formularios")
    ap.add_argument("--max-iteraciones", type=int, default=MAX_ITERACIONES)
    ap.add_argument("--permitir-apartada", action="store_true")
    args = ap.parse_args()

    print(f"Extrayendo {args.expediente} con {MODELO}")
    items, traza = extraer(
        args.expediente,
        max_iteraciones=args.max_iteraciones,
        permitir_apartada=args.permitir_apartada,
    )

    destino = Path("salida") / args.expediente
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "items.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(items)} afirmaciones -> {destino / 'items.json'}")
    print(f"corte por {traza['motivo']} | tokens in {traza['in']} out {traza['out']}")


if __name__ == "__main__":
    main()
