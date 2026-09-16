from __future__ import annotations

import argparse
import unicodedata
from typing import Dict, List, Tuple

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import BlobResourceContents, EmbeddedResource

import corpus
from contrato import Documento
from criterio import CRITERIO_AFIRMACION

CONTEXTO = 120
MAX_COINCIDENCIAS = 30

mcp = FastMCP("caso-trenes")

_estado: Dict[str, object] = {"expediente": "", "permitir_apartada": False}
_indice: Dict[str, List[Tuple[str, int, str, str]]] = {}


def _expediente() -> Tuple[str, bool]:
    return str(_estado["expediente"]), bool(_estado["permitir_apartada"])


def _plegar(texto: str) -> str:
    return "".join(unicodedata.normalize("NFD", c)[0].lower() for c in texto)


def _paginas_indexadas() -> List[Tuple[str, int, str, str]]:
    expediente, permitir = _expediente()
    if expediente not in _indice:
        filas: List[Tuple[str, int, str, str]] = []
        for doc in corpus.documentos(expediente, permitir):
            for n, texto in corpus.paginas(expediente, doc["id"], permitir).items():
                plano = " ".join(texto.split())
                filas.append((doc["id"], n, plano, _plegar(plano)))
        _indice[expediente] = filas
    return _indice[expediente]


@mcp.tool()
def listar_documentos() -> List[Documento]:
    """Indice del expediente: id, titulo, tipo (demanda, contestacion o prueba), path y
    cantidad de paginas de cada documento. Es la forma de saber que documentos hay."""
    expediente, permitir = _expediente()
    return corpus.documentos(expediente, permitir)


@mcp.tool()
def leer_documento(id: str) -> EmbeddedResource:
    """Devuelve el documento completo como PDF. `id` es el que figura en listar_documentos
    (DEM, CON, DOC-1, ...). Las paginas se cuentan desde 1."""
    expediente, permitir = _expediente()
    doc = next((d for d in corpus.documentos(expediente, permitir) if d["id"] == id), None)
    if doc is None:
        ids = ", ".join(d["id"] for d in corpus.documentos(expediente, permitir))
        raise ToolError(f"no existe el documento {id!r}. Ids validos: {ids}")
    bloque = corpus.bloque_documento(expediente, id, permitir)
    return EmbeddedResource(
        type="resource",
        resource=BlobResourceContents(
            uri=f"corpus://{expediente}/{id}",
            mimeType="application/pdf",
            blob=bloque["source"]["data"],
        ),
        _meta={"titulo": doc["titulo"]},
    )


@mcp.tool()
def buscar(termino: str) -> List[Dict]:
    """Busqueda lexica en todos los documentos del expediente. Ignora mayusculas, tildes
    y saltos de linea. Sirve para identificadores exactos: fechas, montos, numeros de
    factura o de expediente. Devuelve documento_id, pagina y el fragmento alrededor."""
    aguja = _plegar(" ".join(termino.split()))
    if not aguja:
        raise ToolError("el termino de busqueda esta vacio")
    coincidencias: List[Dict] = []
    for documento_id, pagina, plano, plegado in _paginas_indexadas():
        desde = 0
        while (pos := plegado.find(aguja, desde)) != -1:
            ini = max(0, pos - CONTEXTO)
            fin = min(len(plano), pos + len(aguja) + CONTEXTO)
            coincidencias.append(
                {"documento_id": documento_id, "pagina": pagina, "fragmento": plano[ini:fin]}
            )
            if len(coincidencias) == MAX_COINCIDENCIAS:
                return coincidencias
            desde = pos + len(aguja)
    return coincidencias


@mcp.prompt()
def criterio_afirmacion() -> str:
    """Que cuenta como afirmacion de hecho en una demanda y que queda afuera."""
    return CRITERIO_AFIRMACION


def main() -> None:
    ap = argparse.ArgumentParser(description="Servidor MCP del corpus de un expediente.")
    ap.add_argument("expediente")
    ap.add_argument("--permitir-apartada", action="store_true")
    args = ap.parse_args()
    corpus.documentos(args.expediente, args.permitir_apartada)
    _estado["expediente"] = args.expediente
    _estado["permitir_apartada"] = args.permitir_apartada
    mcp.run()


if __name__ == "__main__":
    main()
