from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List

from contrato import Documento
from criterio import APARTADA

RAIZ = Path(__file__).resolve().parent
CORPUS = RAIZ / "corpus"

_PIE = re.compile(r"^\s*DOCUMENTO SINTETICO.*$", re.MULTILINE)
_PRUEBA = re.compile(r"^Prueba_(\d+)_(.+)\.pdf$")


class ExpedienteApartado(RuntimeError):
    pass


def expedientes() -> List[str]:
    return sorted(d.name for d in CORPUS.iterdir() if d.is_dir())


def _ruta(expediente: str, permitir_apartada: bool = False) -> Path:
    if expediente == APARTADA and not permitir_apartada:
        raise ExpedienteApartado(
            f"{expediente} es la demanda apartada: se abre en la semana 6. "
            "Pasa permitir_apartada=True si esa es la corrida."
        )
    ruta = CORPUS / expediente
    if not ruta.is_dir():
        raise FileNotFoundError(f"no existe el expediente {expediente}")
    return ruta


def _paginas(pdf: Path) -> int:
    return len(_crudo(pdf))


def _crudo(pdf: Path) -> List[str]:
    salida = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [p for p in salida.split("\f") if p.strip()]


def documentos(expediente: str, permitir_apartada: bool = False) -> List[Documento]:
    ruta = _ruta(expediente, permitir_apartada)
    indice: List[Documento] = []
    for pdf in sorted((ruta / "escritos").glob("*.pdf")):
        if pdf.name.startswith("Demanda"):
            indice.append(
                Documento(
                    id="DEM",
                    titulo="Escrito de demanda",
                    tipo="demanda",
                    path=f"escritos/{pdf.name}",
                    paginas=_paginas(pdf),
                )
            )
        elif pdf.name.startswith("Contestacion"):
            indice.append(
                Documento(
                    id="CON",
                    titulo="Contestacion de demanda",
                    tipo="contestacion",
                    path=f"escritos/{pdf.name}",
                    paginas=_paginas(pdf),
                )
            )
    for pdf in sorted((ruta / "prueba").glob("*.pdf")):
        m = _PRUEBA.match(pdf.name)
        if not m:
            continue
        indice.append(
            Documento(
                id=f"DOC-{int(m.group(1))}",
                titulo=m.group(2).replace("_", " "),
                tipo="prueba",
                path=f"prueba/{pdf.name}",
                paginas=_paginas(pdf),
            )
        )
    indice.sort(key=lambda d: (d["tipo"] != "demanda", d["tipo"] != "contestacion", d["id"]))
    return indice


def _pdf(expediente: str, documento_id: str, permitir_apartada: bool = False) -> Path:
    ruta = _ruta(expediente, permitir_apartada)
    for doc in documentos(expediente, permitir_apartada):
        if doc["id"] == documento_id:
            return ruta / doc["path"]
    raise FileNotFoundError(f"no existe el documento {documento_id} en {expediente}")


def paginas(expediente: str, documento_id: str, permitir_apartada: bool = False) -> Dict[int, str]:
    crudo = _crudo(_pdf(expediente, documento_id, permitir_apartada))
    limpio: Dict[int, str] = {}
    for n, pagina in enumerate(crudo, start=1):
        texto = _PIE.sub("", pagina).strip("\n")
        limpio[n] = "\n".join(l.rstrip() for l in texto.splitlines() if l.strip())
    return limpio


def paginado(expediente: str, documento_id: str, permitir_apartada: bool = False) -> str:
    bloques = [
        f'<pagina n="{n}">\n{t}\n</pagina>'
        for n, t in paginas(expediente, documento_id, permitir_apartada).items()
    ]
    return "\n\n".join(bloques)
