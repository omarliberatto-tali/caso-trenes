from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

from anthropic import Anthropic
from dotenv import load_dotenv

from agente import MODELO, _guardar, extraer, verificar
from contrato import Item, Veredicto
from criterio import ESTADOS

MAX_ITERACIONES_ORQ = 6
MAX_TOKENS_ORQ = 4096
ESFUERZO_ORQ = "low"
PARALELO = 5
DEMANDA = "DEM"

# Blast radius: ningun sub-agente escribe. El extractor solo lee la demanda que se le nombra;
# el verificador necesita las tres tools del corpus para ubicar la prueba.
TOOLS_EXTRACTOR = ["leer_documento"]
TOOLS_VERIFICADOR = ["listar_documentos", "leer_documento", "buscar"]

SISTEMA_ORQ = """Coordinas la verificacion de una demanda judicial contra la prueba documental del
expediente. No lees documentos ni decidis veredictos: delegas en dos sub-agentes por medio de
tools.

- extraer_afirmaciones: el extractor lee la demanda y devuelve sus afirmaciones de hecho (id y
  titulo).
- verificar_afirmacion: un verificador decide el estado de una sola afirmacion contra la prueba.

Primero extrae las afirmaciones. Despues pedi verificar_afirmacion para todas, juntas en una
sola respuesta: corren en paralelo. Si alguna vuelve con error, pedila otra vez, una sola vez.
Cuando todas tengan estado, responde con una linea por afirmacion: id y estado."""

TOOLS_ORQ = [
    {
        "name": "extraer_afirmaciones",
        "description": "Corre el sub-agente extractor sobre la demanda y devuelve la lista de sus "
        "afirmaciones de hecho, cada una con id y titulo.",
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string", "description": "id de la demanda en el expediente"}},
            "required": ["documento_id"],
        },
    },
    {
        "name": "verificar_afirmacion",
        "description": "Corre un sub-agente verificador sobre una sola afirmacion y devuelve su estado "
        "(respaldada, sin_respaldo o contradicha), la confianza y cuantas citas trae.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "string", "description": "id de la afirmacion, por ejemplo AF-03"}},
            "required": ["item_id"],
        },
    },
]


class Orquestador:
    """Estado del fan-out: las afirmaciones extraidas y los veredictos que van llegando.

    El orquestador (el modelo) solo ve ids, titulos y estados. El texto de cada afirmacion, la
    evidencia y la traza de cada sub-agente quedan aca, del lado del codigo, y salen en el fan-in.
    """

    def __init__(self, expediente: str, reusar_items: Path | None, primeras: int | None, permitir_apartada: bool):
        self.expediente = expediente
        self.reusar_items = reusar_items
        self.primeras = primeras
        self.permitir_apartada = permitir_apartada
        self.items: Dict[str, Item] = {}
        self.veredictos: Dict[str, Veredicto] = {}
        self.trazas: Dict[str, Dict] = {}

    def extraer_afirmaciones(self, documento_id: str) -> Dict:
        inicio = time.monotonic()
        if self.reusar_items:
            items: List[Item] = json.loads(self.reusar_items.read_text(encoding="utf-8"))
            traza: Dict = {"reusado": str(self.reusar_items)}
        else:
            items, traza = extraer(
                self.expediente,
                documento_id=documento_id,
                permitir_apartada=self.permitir_apartada,
                verbose=False,
                tools_permitidas=TOOLS_EXTRACTOR,
            )
        if self.primeras:
            items = items[: self.primeras]
        traza["segundos"] = round(time.monotonic() - inicio, 1)
        self.items = {it["id"]: it for it in items}
        self.trazas["extractor"] = traza
        print(f"  extractor: {len(items)} afirmaciones en {traza['segundos']} s")
        return {"afirmaciones": [{"id": it["id"], "titulo": it.get("titulo", "")} for it in items]}

    def verificar_afirmacion(self, item_id: str) -> Dict:
        if not self.items:
            raise ValueError("todavia no hay afirmaciones: primero extraer_afirmaciones")
        if item_id not in self.items:
            raise ValueError(f"{item_id} no esta entre las afirmaciones extraidas")
        inicio = time.monotonic()
        # El verificador recibe solo el item: el criterio lo toma del servidor MCP y no ve nada
        # del historial del orquestador ni de las otras afirmaciones.
        veredictos, traza = verificar(
            self.expediente,
            [self.items[item_id]],
            permitir_apartada=self.permitir_apartada,
            verbose=False,
            tools_permitidas=TOOLS_VERIFICADOR,
        )
        traza["inicio"] = inicio
        traza["segundos"] = round(time.monotonic() - inicio, 1)
        # Un reintento no pisa la traza del intento anterior: sus tokens tambien se pagaron.
        clave, n = item_id, 1
        while clave in self.trazas:
            n += 1
            clave = f"{item_id}#{n}"
        self.trazas[clave] = traza
        propio = [v for v in veredictos if v["item_id"] == item_id]
        if not propio:
            raise ValueError(f"el verificador no devolvio veredicto para {item_id} ({traza['motivo']})")
        v = propio[0]
        self.veredictos[item_id] = v
        print(f"  {item_id}: {v['estado']} {v['confianza']} en {traza['segundos']} s")
        return {"item_id": item_id, "estado": v["estado"], "confianza": v["confianza"], "citas": len(v["evidencia"])}

    def ejecutar(self, bloques: List, pool: ThreadPoolExecutor) -> List[Dict]:
        """Fan-out: todos los tool_use de una respuesta corren a la vez."""
        pedidos = [b for b in bloques if b.type == "tool_use"]
        futuros = [pool.submit(getattr(self, b.name), **b.input) for b in pedidos]
        resultados: List[Dict] = []
        for b, f in zip(pedidos, futuros):
            try:
                contenido, error = json.dumps(f.result(), ensure_ascii=False), False
            except Exception as exc:
                contenido, error = f"error: {exc}", True
                print(f"  {b.name}({json.dumps(b.input, ensure_ascii=False)}) error: {exc}")
            resultados.append({"type": "tool_result", "tool_use_id": b.id, "content": contenido, "is_error": error})
        return resultados

    def consolidar(self) -> List[Veredicto]:
        """Fan-in: los veredictos en el orden de las afirmaciones."""
        return [self.veredictos[i] for i in self.items if i in self.veredictos]


def orquestar(
    expediente: str,
    reusar_items: Path | None = None,
    primeras: int | None = None,
    paralelo: int = PARALELO,
    max_iteraciones: int = MAX_ITERACIONES_ORQ,
    permitir_apartada: bool = False,
) -> Tuple[List[Veredicto], Dict]:
    load_dotenv()
    orq = Orquestador(expediente, reusar_items, primeras, permitir_apartada)
    cliente = Anthropic()
    mensajes: List[Dict] = [
        {
            "role": "user",
            "content": f"Expediente {expediente}. La demanda es el documento {DEMANDA}. "
            f"Verifica todas sus afirmaciones de hecho.",
        }
    ]
    traza: Dict = {"iteraciones": 0, "motivo": "", "in": 0, "out": 0, "tools": [], "respuesta": ""}

    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        for i in range(1, max_iteraciones + 1):
            traza["iteraciones"] = i
            rta = cliente.messages.create(
                model=MODELO,
                max_tokens=MAX_TOKENS_ORQ,
                output_config={"effort": ESFUERZO_ORQ},
                system=SISTEMA_ORQ,
                tools=TOOLS_ORQ,
                messages=mensajes,
            )
            traza["in"] += rta.usage.input_tokens
            traza["out"] += rta.usage.output_tokens
            pedidos = [{"tool": b.name, **b.input} for b in rta.content if b.type == "tool_use"]
            traza["tools"].append(pedidos)
            print(f"iter {i}: {len(pedidos)} delegaciones, stop={rta.stop_reason}")

            if rta.stop_reason != "tool_use":
                traza["respuesta"] = "".join(b.text for b in rta.content if b.type == "text")
                traza["motivo"] = "fin del orquestador"
                break
            resultados = orq.ejecutar(rta.content, pool)
            mensajes.append({"role": "assistant", "content": rta.content})
            mensajes.append({"role": "user", "content": resultados})
            if i == max_iteraciones:
                traza["motivo"] = "max_iteraciones"

    traza["faltantes"] = [i for i in orq.items if i not in orq.veredictos]
    traza["subagentes"] = orq.trazas
    return orq.consolidar(), traza


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fan-out por afirmacion: un orquestador delega la extraccion y un verificador por afirmacion."
    )
    ap.add_argument("expediente", nargs="?", default="C1_Impresos_y_formularios")
    ap.add_argument("--reusar-items", action="store_true", help="no corre el extractor: usa salida/<exp>/items.json")
    ap.add_argument("--primeras", type=int, default=None, help="verifica solo las N primeras afirmaciones")
    ap.add_argument("--paralelo", type=int, default=PARALELO, help="verificadores a la vez")
    ap.add_argument("--max-iteraciones", type=int, default=MAX_ITERACIONES_ORQ)
    ap.add_argument("--permitir-apartada", action="store_true")
    args = ap.parse_args()
    base = Path("salida") / args.expediente
    destino = base / "fanout"

    inicio = time.monotonic()
    veredictos, traza = orquestar(
        args.expediente,
        reusar_items=base / "items.json" if args.reusar_items else None,
        primeras=args.primeras,
        paralelo=args.paralelo,
        max_iteraciones=args.max_iteraciones,
        permitir_apartada=args.permitir_apartada,
    )
    traza["segundos"] = round(time.monotonic() - inicio, 1)

    # Tiempo de la verificacion, comparable con traza.json["segundos"] de la version secuencial:
    # desde que arranca el primer verificador hasta que termina el ultimo.
    verifs = [t for k, t in traza["subagentes"].items() if k != "extractor"]
    if verifs:
        arranque = min(t["inicio"] for t in verifs)
        fin = max(t.pop("inicio") + t["segundos"] for t in verifs)
        traza["segundos_verificacion"] = round(fin - arranque, 1)
        traza["segundos_suma_verificadores"] = round(sum(t["segundos"] for t in verifs), 1)
    sub_in = sum(t.get("in", 0) for t in traza["subagentes"].values())
    sub_out = sum(t.get("out", 0) for t in traza["subagentes"].values())
    traza["total"] = {"in": traza["in"] + sub_in, "out": traza["out"] + sub_out}

    _guardar(destino, "veredictos.json", veredictos)
    _guardar(destino, "traza.json", traza)
    conteo = {e: sum(1 for v in veredictos if v["estado"] == e) for e in ESTADOS}
    print(f"{len(veredictos)} veredictos -> {destino / 'veredictos.json'}  {conteo}")
    if traza["faltantes"]:
        print(f"faltantes: {', '.join(traza['faltantes'])}")
    print(
        f"corte por {traza['motivo']} | {traza['iteraciones']} iteraciones del orquestador | "
        f"tokens in {traza['total']['in']} out {traza['total']['out']} | {traza['segundos']} s en total, "
        f"{traza.get('segundos_verificacion', 0)} s de verificacion "
        f"(suma de verificadores {traza.get('segundos_suma_verificadores', 0)} s)"
    )


if __name__ == "__main__":
    main()
