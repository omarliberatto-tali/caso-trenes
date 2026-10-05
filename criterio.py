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

CRITERIO_VEREDICTO = """Cada afirmacion de hecho recibe exactamente uno de tres estados:

- respaldada: un documento de prueba dice lo mismo que la afirmacion en lo esencial (el acto,
  la fecha, el monto, la cantidad, el numero de comprobante).
- contradicha: un documento de prueba dice algo incompatible con la afirmacion: otra fecha,
  otro monto, otra cantidad, o muestra que el hecho no ocurrio como se afirma. Tambien cuando
  el monto o la cantidad no figura escrito pero surge de la prueba (por ejemplo, sumando
  facturas) y da otro valor.
- sin_respaldo: ningun documento de prueba se refiere al hecho. No aparece no es lo mismo que
  la prueba dice lo contrario: si no encontras nada, es sin_respaldo, no contradicha.

Para contradecir, el documento tiene que referirse al mismo hecho concreto que la afirmacion.
Una clausula general sobre un tema relacionado no la contradice: por ejemplo, que el contrato
diga que el precio no genera intereses no contradice un reclamo de intereses por pagar tarde.
En ese caso, si nada mas se refiere al hecho, es sin_respaldo.

Un documento que solo menciona a otro (por ejemplo, una factura que cita el numero de un
remito) no reemplaza al documento mencionado. Si el documento que acredita el hecho no esta
en el expediente, es sin_respaldo.

Cualquier pago imputable a un rubro reclamado (por ejemplo, la liquidacion final, las
vacaciones o el aguinaldo proporcionales) contradice la afirmacion de que no hubo pagos.

La base de la indemnizacion por antiguedad (art. 245 de la Ley de Contrato de Trabajo) es la
mejor remuneracion mensual, normal y habitual del ultimo año, y se calcula solo con los
conceptos remunerativos. Si la afirmacion toma un monto que incluye conceptos no remunerativos
y la prueba informa la base remunerativa, es contradicha.

Solo cuentan como prueba los documentos de tipo "prueba" (DOC-1, DOC-2, ...). La demanda es de
donde salen las afirmaciones y la contestacion dice que discute la demandada: ninguna de las
dos decide el estado ni se cita como evidencia. Que la contestacion niegue un hecho va a la
nota, no al estado.

Una afirmacion puede necesitar dos documentos para quedar respaldada: cita los dos."""
