from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from anthropic import Anthropic
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from contrato import Item, Origen

MODELO = "claude-sonnet-5"
MAX_ITERACIONES = 8
MAX_TOKENS = 4096
FIN = "<FIN>"
SERVIDOR = Path(__file__).resolve().parent / "servidor_mcp.py"

# M3 enciende esto y no hay nada mas que reescribir: el bloque document ya viaja.
CITATIONS = False

SISTEMA = """Sos un analista de escritos judiciales argentinos. Tu unica tarea es leer un
escrito de demanda y devolver la lista de sus afirmaciones de hecho. No las evaluas, no las
resumis y no opinas sobre ellas: las extraes tal como estan.

{criterio}

DOCUMENTOS
El expediente se consulta con tools. Usa listar_documentos para ubicar la demanda y
leer_documento para leerla: te llega como el PDF completo. La pagina que reportas es el
numero de pagina del PDF, empezando en 1. Las afirmaciones salen solo de la demanda.

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
Cuando emitiste la ultima afirmacion del capitulo IV, escribi una linea con {fin} y nada mas.
No escribas {fin} si todavia quedan incisos por emitir."""

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


def _a_tool_result(tool_use_id: str, resultado: CallToolResult) -> Dict:
    contenido: List[Dict] = []
    for bloque in resultado.content:
        if bloque.type == "text":
            contenido.append({"type": "text", "text": bloque.text})
        elif bloque.type == "resource" and getattr(bloque.resource, "blob", None):
            documento: Dict = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": bloque.resource.mimeType,
                    "data": bloque.resource.blob,
                },
            }
            if bloque.meta and bloque.meta.get("titulo"):
                documento["title"] = bloque.meta["titulo"]
            if CITATIONS:
                documento["citations"] = {"enabled": True}
            contenido.append(documento)
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": contenido,
        "is_error": bool(resultado.isError),
    }


async def _ejecutar_tools(sesion: ClientSession, bloques: List, verbose: bool) -> List[Dict]:
    resultados: List[Dict] = []
    for bloque in bloques:
        if bloque.type != "tool_use":
            continue
        try:
            resultado = await sesion.call_tool(bloque.name, bloque.input)
            resultados.append(_a_tool_result(bloque.id, resultado))
            error = resultado.isError
        except Exception as exc:
            resultados.append(
                {"type": "tool_result", "tool_use_id": bloque.id, "content": str(exc), "is_error": True}
            )
            error = True
        if verbose:
            print(f"    tool {bloque.name}({json.dumps(bloque.input, ensure_ascii=False)}) error={error}")
    return resultados


async def _extraer(
    expediente: str,
    documento_id: str,
    max_iteraciones: int,
    permitir_apartada: bool,
    verbose: bool,
) -> Tuple[List[Item], Dict]:
    args = [str(SERVIDOR), expediente]
    if permitir_apartada:
        args.append("--permitir-apartada")
    parametros = StdioServerParameters(command=sys.executable, args=args)

    async with stdio_client(parametros) as (lectura, escritura), ClientSession(lectura, escritura) as sesion:
        await sesion.initialize()
        tools = [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in (await sesion.list_tools()).tools
        ]
        prompt = await sesion.get_prompt("criterio_afirmacion")
        criterio = prompt.messages[0].content.text
        sistema = SISTEMA.format(criterio=criterio, fin=FIN)

        cliente = Anthropic()
        mensajes: List[Dict] = [
            {
                "role": "user",
                "content": f"Expediente {expediente}. Extrae las afirmaciones de hecho de su demanda.",
            }
        ]
        encontrados: Dict[str, Item] = {}
        traza = {"iteraciones": 0, "motivo": "", "in": 0, "out": 0, "tools": 0}

        for i in range(1, max_iteraciones + 1):
            traza["iteraciones"] = i
            rta = cliente.messages.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                system=sistema,
                tools=tools,
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

            if rta.stop_reason == "tool_use":
                resultados = await _ejecutar_tools(sesion, rta.content, verbose)
                traza["tools"] += len(resultados)
                mensajes.append({"role": "assistant", "content": rta.content})
                mensajes.append({"role": "user", "content": resultados})
                if i == max_iteraciones:
                    traza["motivo"] = "max_iteraciones"
                continue

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


def extraer(
    expediente: str,
    documento_id: str = "DEM",
    max_iteraciones: int = MAX_ITERACIONES,
    permitir_apartada: bool = False,
    verbose: bool = True,
) -> Tuple[List[Item], Dict]:
    load_dotenv()
    return asyncio.run(_extraer(expediente, documento_id, max_iteraciones, permitir_apartada, verbose))


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
    print(
        f"corte por {traza['motivo']} | {traza['tools']} tools | "
        f"tokens in {traza['in']} out {traza['out']}"
    )


if __name__ == "__main__":
    main()
