from __future__ import annotations

from typing import List, TypedDict


class Documento(TypedDict):
    id: str
    titulo: str
    tipo: str
    path: str
    paginas: int


class Origen(TypedDict):
    documento_id: str
    pagina: int


class _ItemBase(TypedDict):
    id: str
    texto: str
    origen: Origen


class Item(_ItemBase, total=False):
    grupo: str
    titulo: str


class Evidencia(TypedDict):
    documento_id: str
    pagina: int
    fragmento: str


class Veredicto(TypedDict):
    item_id: str
    estado: str
    evidencia: List[Evidencia]
    confianza: float
    nota: str
