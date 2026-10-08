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

Lo esencial es el hecho principal: el acto, la fecha y el monto. Si la prueba acredita el hecho
principal y no dice nada sobre un detalle accesorio que la afirmacion agrega, es respaldada y el
detalle que falta va a la nota. Es sin_respaldo cuando el hecho principal no aparece.

Para contradecir, el documento tiene que referirse al mismo hecho concreto que la afirmacion.
Una clausula del contrato que excluye o no preve lo que se reclama (intereses, una tasa,
actualizaciones) no contradice el reclamo: decidir si corresponde es
del juez, no de la prueba. En ese caso, si nada mas se refiere al hecho, es sin_respaldo y la
clausula va a la nota.

Si la afirmacion atribuye un hecho a un comprobante o numero (una factura, un remito) y la
prueba registra ese mismo hecho (el mismo acto, la misma fecha) pero sobre otro numero, es
contradicha: la prueba muestra que el hecho no ocurrio como se afirma.

Un total queda contradicho si la prueba contradice alguno de sus componentes, por ejemplo la
base sobre la que se calcula, aunque ningun documento informe el total.

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
nota, no al estado. Lo mismo vale para cualquier documento en el que una parte rechaza, niega u
observa algo (un telegrama de rechazo, una nota que no conforma una entrega): muestra la postura
de esa parte, no prueba que el hecho no ocurrio. Va a la nota y no contradice. La excepcion es
cuando la afirmacion trata de ese mismo acto de la parte (por ejemplo, que presto conformidad o
que acepto algo): ahi el documento de la parte es prueba directa de ese acto y puede respaldarla
o contradecirla.

Una afirmacion puede necesitar dos documentos para quedar respaldada: cita los dos.

Las citas van segun el estado: respaldada y contradicha siempre citan el fragmento de la prueba
que decide el estado; sin_respaldo no cita nada, y lo relacionado que hayas encontrado va solo
en la nota."""
