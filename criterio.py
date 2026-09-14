from __future__ import annotations

from typing import List

ESTADOS: List[str] = ["respaldada", "sin_respaldo", "contradicha"]

APARTADA = "C4_Repuestos_de_material_rodante"

CRITERIO_AFIRMACION = """Una afirmacion de hecho es un enunciado de la parte actora sobre algo que ocurrio:
un acto, una fecha, un monto, una entrega, una comunicacion o un incumplimiento.

Cuentan como afirmacion de hecho:
- Los incisos numerados del capitulo "IV.- HECHOS" del escrito de demanda, y solo esos.

No cuentan, aunque aparezcan numerados o afirmados en otra parte del escrito:
- La argumentacion juridica y el encuadre normativo.
- El planteo de competencia y la personeria.
- El petitorio, la reserva del caso federal y el ofrecimiento de prueba.
- Las citas de jurisprudencia y de doctrina.
- La liquidacion, los intereses y los detalles de facturacion que viven fuera del capitulo IV.

Cada inciso numerado del capitulo IV es exactamente una afirmacion, y su numero la identifica:
el hecho 7 es AF-07.

Cada inciso arranca con un titulo corto terminado en punto, y despues el cuerpo de la afirmacion.
El titulo y el cuerpo se reportan por separado.

Una afirmacion que arranca en una pagina y termina en la siguiente pertenece a la pagina donde
arranca.

Ignora los encabezados y los pies de pagina: no forman parte del texto de ninguna afirmacion."""
