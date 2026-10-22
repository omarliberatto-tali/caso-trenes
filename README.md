# caso-trenes — Semana 3 (M3)

Verificación de respaldo probatorio sobre expedientes judiciales. Hasta acá cubre el
primer paso, extraer las afirmaciones de hecho de una demanda, con el corpus servido por un
servidor MCP propio.

## Qué hace el agente

`agente.py` lee un escrito de demanda y devuelve la lista de sus afirmaciones de hecho, cada
una con su texto literal y la página de donde salió.

El agente no recibe el documento en el prompt: arranca `servidor_mcp.py` como subproceso
(stdio), le pide el criterio y las tools, y el primer mensaje sólo nombra el expediente. Con
`listar_documentos` ubica la demanda y con `leer_documento` la recibe como PDF, que se pasa al
modelo como bloque `document` dentro del `tool_result`. Devuelve una línea JSON por afirmación
y cierra con `<FIN>`.

El loop corta por tres condiciones explícitas: llegó `<FIN>`, una iteración no aportó ninguna
afirmación nueva —salvo que haya pedido tools—, o se alcanzó `max_iteraciones` (8 por
defecto; las llamadas a tools también cuentan). Si la respuesta se corta por `max_tokens`, el
loop la reinyecta sin la última línea, que quedó incompleta, y pide continuar desde el inciso
siguiente.

Requiere Python 3.10 o superior (lo pide `mcp`). El venv vive un nivel arriba del repo:

```
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
../.venv/bin/python agente.py C1_Impresos_y_formularios   # -> salida/<exp>/items.json
../.venv/bin/python evals.py  C1_Impresos_y_formularios   # -> salida/<exp>/eval.json
```

## El servidor MCP

`servidor_mcp.py` está hecho con FastMCP y atiende un expediente por proceso: se lanza con
`servidor_mcp.py <expediente>`. Las tres tools tienen la firma fija del enunciado y por eso no
reciben el expediente como parámetro.

| tool | devuelve |
|---|---|
| `listar_documentos()` | el índice: `id`, `titulo`, `tipo`, `path` y `paginas` de cada documento |
| `leer_documento(id)` | el PDF completo como recurso embebido (`application/pdf`); un id inexistente devuelve un resultado con `is_error` y la lista de ids válidos |
| `buscar(termino)` | hasta 30 coincidencias con `documento_id`, `pagina` y 120 caracteres de contexto a cada lado |

`buscar` es léxica y recorre todos los documentos del expediente sobre el texto de
`pdftotext`, indexado la primera vez que se usa. Ignora mayúsculas, tildes y saltos de línea,
porque en el PDF una fecha o un monto pueden quedar partidos entre dos renglones.

No se agregaron tools además de las tres: la extracción usa sólo las dos primeras, y `buscar`
queda para el verificador de la semana 4.

**Qué va en MCP y qué queda inline.** El criterio de afirmación de hecho se sirve como prompt
del servidor (`criterio_afirmacion`) porque en la semana 6 se extiende con los tres estados y
lo van a consumir también los subagentes. El rol, el formato de salida y la señal de fin
quedan en `agente.py`: son del loop de extracción, no del corpus.

**`mcp` fijado en `<2`.** La versión 2 renombró `FastMCP` a `MCPServer` y cambió otras APIs;
el enunciado y el material del curso usan la 1.x.

La demanda apartada también está cerrada del lado del servidor: con ese expediente el proceso
no arranca, salvo con `--permitir-apartada`.

## Qué contamos como afirmación de hecho

Cuenta cada inciso numerado del capítulo **«IV.- HECHOS»** del escrito de demanda, y solo
eso. El número del inciso es el identificador: el hecho 7 es `AF-07`.

Queda afuera, aunque esté afirmado o numerado: la argumentación jurídica, el encuadre de
competencia, la personería, el petitorio, la reserva del caso federal, el ofrecimiento de
prueba, las citas de jurisprudencia, y la liquidación y el detalle de facturación que viven
en capítulos posteriores.

Dos precisiones que salieron de mirar el set de referencia: cada inciso arranca con un título
corto que se reporta **separado** del cuerpo, y una afirmación que cruza el salto de página
pertenece a la página donde **arranca**.

El criterio vive en `criterio.py`, no en el prompt. En la semana 2 pasa a servirse como prompt
del servidor MCP y en la semana 6 se extiende con los tres estados: conviene que ya esté en un
solo lugar.

## Decisiones de diseño

**El PDF entra como bloque `document`, no como texto extraído.** La primera versión lo extraía
con `pdftotext -layout` y lo envolvía en marcadores `<pagina n="N">`. Funcionaba, pero no se
extiende: la semana 3 pide el bloque `document` con `citations` habilitado, y las citas salen de
ese bloque. Y la duplicación no empezaba en la semana 3 sino en la 2, porque `leer_documento(id)`
va a tener que devolver el bloque igual. Migrar ahora evita mantener dos caminos.

Cuesta input: la llamada pasó de ~4.000 a ~16.300 tokens de entrada. No se optimiza a mano —
eso lo resuelve `cache_control` en la semana 6, y el documento de prueba es justo el prefijo
estable de todas las llamadas.

`citations` queda detrás de la constante `CITATIONS` en `agente.py`, en `False`. La semana 3 la
pone en `True` y no hay nada más que reescribir.

**El pie de página se resuelve por prompt, no por código.** Cada hoja del corpus termina con
`DOCUMENTO SINTETICO - ejercicio de formacion…`, que al extraer quedaba pegado adentro del texto.
Con el bloque `document` ya no se puede limpiar antes, así que el criterio dice «ignorá los
encabezados y los pies de página» y el modelo lo saltea.

**`pdftotext` no se fue: cambió de rol.** `corpus.paginado()` y `corpus.paginas()` siguen en el
repo. Dejan de ser el input del agente y pasan a ser el índice para `buscar(termino)` de la
semana 2, que es búsqueda léxica y necesita texto plano.

**Al agente le entra la demanda entera, no el capítulo IV recortado.** Recortar por regex
subiría el número, pero estaría resolviendo por código justamente lo que se evalúa del agente:
distinguir un hecho de un argumento. Además en la semana 2 el documento llega por
`leer_documento(id)` sin recorte posible, así que el recorte solo estaría postergando la
caída. Se prefiere el número honesto ahora.

La otra decisión, menor: el índice de documentos (`corpus.documentos()`) se deriva del nombre
de los archivos, no se lee de `referencia.json`. El set de referencia trae un índice idéntico
—verificado, coincide en los 6 expedientes, incluido el conteo de páginas— pero es el archivo
de respuestas: la semana 2 tiene que poder construir `listar_documentos()` sin tocarlo.

## Resultado del eval

`evals.py` califica por código contra `referencia/<exp>/referencia.json`: matchea por id
`AF-NN` y exige que el texto coincida exacto después de normalizarlo (minúsculas, sin tildes
y con los espacios colapsados). Reporta dos números y cuenta faltantes, inventados y páginas
erradas. La similitud de `difflib` queda en el detalle sólo como dato de diagnóstico.

No se usa un umbral de similitud porque no distingue lo que importa: sobre los textos de C1,
negar un hecho da una similitud de 0,93 a 0,99 y cambiar un dígito de un monto da 0,99. Con
textos de 100 a 300 caracteres, cualquier umbral que tolere diferencias de espaciado también
deja pasar esos cambios.

Sobre **C1_Impresos_y_formularios**, 15 afirmaciones:

| métrica | valor |
|---|---|
| acierto de ítem | **100 %** (15/15) |
| acierto de página | **100 %** |
| faltantes / inventados | 0 / 0 |

Estable en dos corridas, y las 15 con similitud 1,0 contra el texto de referencia.

**Con el corpus por tools (M2)**, sobre las cinco demandas que no están apartadas:

| expediente | ítem | página | tokens de entrada |
|---|---|---|---|
| C1_Impresos_y_formularios | 100 % | 100 % | 22.421 |
| C2_Mobiliario_de_estaciones | 100 % | 100 % | 22.018 |
| C3_Mantenimiento_de_via | 100 % | 100 % | 22.124 |
| C5_Indemnizacion_por_despido | 100 % | 100 % | 21.659 |
| C6_Diferencias_salariales | 100 % | 100 % | 19.534 |

Cada corrida hace dos llamadas a tools (`listar_documentos` y `leer_documento("DEM")`) y
termina por la señal de fin. C1 da lo mismo en dos corridas. El número no se cayó al pasar a
tools: el agente ubica la demanda solo y la lee entera, igual que cuando venía en el prompt.
La entrada sube de ~16.300 a ~22.000 tokens: se suman las dos llamadas que piden las tools,
cada una con el sistema y las definiciones de tools; el PDF entra recién en la tercera.

### Qué caso falla

En la corrida normal, ninguno. El eval sí discrimina: con un control negativo —sacar un ítem,
mover una página, cambiar un texto y agregar uno inventado— baja a 86,7 % y marca los cuatro.

El caso que fallaba aparece al forzar el loop. Bajando `MAX_TOKENS` a 600, la extracción se
parte en 4 iteraciones y **AF-09** se reportaba en la página 2 cuando arranca en la 3. El
acierto de ítem se mantenía en 100 %: la continuación no pierde ni duplica afirmaciones.

**Causa.** La iteración 2 se corta a mitad de la línea JSON de AF-09, antes del campo `pagina`.
Ese fragmento volvía al modelo dentro del mensaje `assistant`, y la iteración 3 reemitía AF-09
completa con la página de los incisos anteriores. AF-08 es el que cruza el salto 2→3; AF-09
ya arranca en la 3.

**Arreglo.** Cuando la respuesta termina por `max_tokens`, `agente.py` descarta la última
línea —la incompleta— antes de reinyectar el texto. La continuación arranca desde líneas
completas y el inciso cortado se emite de cero.

| corrida forzada (`MAX_TOKENS = 600`) | acierto de página |
|---|---|
| sin el arreglo | 93,3 % en 2 de 2 |
| pidiendo en la continuación que busque la página en el PDF | 100 % en 1 de 2 |
| descartando la línea incompleta | **100 % en 6 de 6** |

El caso sigue siendo el que conviene revisar cuando en la semana 3 se enciendan las
citations, donde la página deja de declararla el modelo y la devuelve la API.

## La demanda apartada

**`C4_Repuestos_de_material_rodante`**

Sorteada con `secrets.choice` sobre los 6 expedientes el 11/09/2026, antes de correr nada. Se
abre en la semana 6. `corpus.py` la bloquea: cualquier acceso levanta `ExpedienteApartado`
salvo que se pase `permitir_apartada=True`.

## M3 — la cita

Después de extraer, el agente verifica cada afirmación contra la prueba documental y devuelve
un `Veredicto` (`respaldada` · `sin_respaldo` · `contradicha`) con su evidencia: documento,
página y fragmento textual.

```
../.venv/bin/python agente.py C1_Impresos_y_formularios                 # extrae y verifica
../.venv/bin/python agente.py C1_Impresos_y_formularios --reusar-items  # solo verifica
../.venv/bin/python evals.py  C1_Impresos_y_formularios                 # los dos evals
```

**Qué cambió:**

- **Citations en el loop, no en un script aparte.** `leer_documento` devuelve el PDF como bloque
  `document` dentro del `tool_result`, y en la fase de verificación el agente le enciende
  `citations`. La extracción queda sin citations: su salida es una línea JSON por afirmación y
  ya da 100 % de página.
- **La evidencia sale de las citas de la API, no de lo que el modelo escribe.** Cada cita trae
  `document_title`, `start_page_number` y `cited_text`, que es texto literal del PDF. El título
  del documento arranca con su id (`DOC-1 · Orden de compra`) para saber de qué documento
  vino. Las citas a la demanda o a la contestación se descartan como evidencia y quedan en la
  traza.
- **El criterio de los tres estados vive en el servidor MCP**, como prompt
  `criterio_veredicto`, junto al de afirmación de hecho. Deja explícito que «no aparece» es
  `sin_respaldo` y no `contradicha`, y que la contestación va a la nota.
- **Conocimiento del dominio en el criterio.** Como no se suma material al expediente, lo que
  sabe un abogado va en el criterio. Una regla entra si un especialista la pondría en un
  manual para alguien que arranca, sin haber visto el caso, y si tiene fuente; si solo existe
  para que un ítem del eval dé bien, no entra. Reglas de derecho laboral:
  - Cualquier pago imputable a un rubro reclamado contradice que no hubo pagos.
  - La base de la indemnización por antigüedad es la mejor remuneración mensual, normal y
    habitual del último año, calculada solo con los conceptos remunerativos
    (art. 245 de la Ley de Contrato de Trabajo, Ley 20.744).
- **Qué hacer cuando el material no alcanza:** el system prompt pide `sin_respaldo` con
  confianza baja y la nota diciendo qué faltó, y prohíbe completar con lo que diría un
  documento que no se leyó.
- **Errores obvios:** `corpus.validar_pdf` distingue archivo inexistente, formato no soportado
  (no empieza con `%PDF-`) y PDF ilegible o sin capa de texto. `leer_documento` los devuelve
  como error de tool (`is_error`) y el loop sigue. Un PDF roto no tira abajo
  `listar_documentos`: figura con 0 páginas.
- **Traza:** `salida/<exp>/traza.json` guarda las tools que se llamaron y, por afirmación, las
  citas crudas que la sostienen y las que se descartaron.
- **Corte por `max_tokens`:** si la respuesta se corta, la última afirmación se descarta entera
  y se pide de nuevo, igual que el arreglo de AF-09 en M1.

**Cómo se mide** (`evals.py`, sección VERIFICACION):

- **Acierto de ítem:** el estado coincide con el de la referencia.
- **Acierto de fuente:** alguna evidencia cae en el documento esperado y en una de sus
  `paginas_admitidas`. Se mide solo sobre los ítems que tienen cita esperada: un `sin_respaldo`
  de la referencia no trae evidencia y queda fuera del porcentaje (el eval informa sobre cuántos
  ítems se calculó). El fragmento no se compara, porque con citations es literal del PDF por
  construcción y la referencia guarda uno solo de los pasajes válidos.

Resultado sobre C1, C2 y C3: pendiente de la primera corrida.

### Prueba con Haiku 5.5 (rama `feature/m3-haiku-5-5`, 08/10/2026)

Haiku 5.5 cuesta US$0,10 / US$0,50 por millón de tokens con prompts de hasta 100K (Haiku 4.5:
US$1 / US$5). Trae el pensamiento prendido por defecto, y el esfuerzo se fija con
`output_config.effort` (constante `ESFUERZO` en `agente.py`). Todas las corridas son con
`--reusar-items` y una sola vez por configuración. Cada celda es acierto de estado / acierto de
fuente.

| Configuración | C1 | C2 | C3 | C5 | C6 |
|---|---|---|---|---|---|
| Haiku 4.5, criterio `90eb477` | — | 93,3 / — | — | 93,3 / — | — |
| 5.5, esfuerzo bajo | — | 80 / 73,3 | — | 73,3 / 60 | — |
| 5.5, esfuerzo medio | — | 80 / 80 | — | 93,3 / 80 | — |
| 5.5, esfuerzo alto | — | 73,3 / 66,7 | — | 86,7 / 73,3 | — |
| 5.5 medio + reglas nuevas | — | 100 / 66,7 | — | 100 / 80 | — |
| + regla de citas por estado | 93,3 / 80 | 93,3 / 73,3 | 80 / 86,7 | 100 / 80 | 86,7 / 73,3 |
| + NOTA sin citas (revertida) | 100 / 66,7 | 86,7 / 86,7 | 80 / 80 | 100 / 60 | 86,7 / 80 |
| Parser sin citas de la NOTA, fuente sobre ítems con cita | 93,3 / 100 | 93,3 / 50 | 86,7 / 66,7 | 86,7 / 72,7 | 86,7 / 100 |
| + reintento de faltantes y sin cita (no se disparó) | — | 93,3 / 80 | — | 93,3 / 81,8 | — |
| + regla de conclusión jurídica (mora) | 100 / 100 | 100 / 100 | 86,7 / 77,8 | 100 / 72,7 | 86,7 / 100 |

La última fila corre solo C2 y C5. Antes de cerrar, el agente hace una vuelta más por las
afirmaciones que faltan o que quedaron `respaldada`/`contradicha` sin cita, y guarda en
`traza.json` el texto crudo de cada iteración (`textos`) y los ids reintentados (`reintento`).
En esta corrida no hizo falta: C5 trajo las 15 y C2 citó todas, así que la mejora es variación
entre corridas y el reintento queda como red. Se probó aparte con un cliente simulado.

La regla de conclusión jurídica dice que una afirmación como la constitución en mora se verifica
por su hecho principal: si ninguna prueba lo fija, es `sin_respaldo` aunque la prueba contradiga
un fundamento accesorio ("sin observación alguna"), y prevalece sobre la excepción de la postura
de parte. Con ella la fecha de mora (AF-13 en C1, C2, C3 y C5) sale bien en todos. En esa
corrida el reintento se disparó en C3, C5 y C6. Quedan C6 AF-13 (total reclamado: la referencia
espera `sin_respaldo` y el agente aplica la regla del total contradicho por un componente, que
en C2 y C3 coincide con la referencia), C6 AF-03 (tareas asignadas contra tareas ejecutadas),
C3 AF-03 y AF-15, y C3 AF-05 sin cita aun con el reintento.

La referencia de C3 AF-14 se corrigió a `sin_respaldo` (igual que C1 y C2): la columna C3 de la
última fila está recalculada con la referencia nueva; las filas anteriores, con la vieja.

La última fila no se compara directo con las anteriores en fuente: el porcentaje se calcula
sobre los ítems con cita esperada (9 a 11 por expediente) y no sobre los 15. En esa corrida, C3
escribió el estado en inglés (`contradicted`) en cinco afirmaciones: el parser ahora traduce
`supported`, `unsupported` y `contradicted` al estado en español y guarda el original en la
traza como `estado_original` (C3 pasó de 46,7 a 80 sin volver a correr); C5 salteó AF-03 y AF-10; y en C2 cinco
veredictos con estado correcto no trajeron ninguna cita, ni en el pasaje ni en la NOTA.

Con esfuerzo bajo, C5 cortó en 12 de 15 veredictos. Medio quedó como valor fijo: alto gasta
casi el doble de salida y no corrige nada. Una corrida de los cinco expedientes con 5.5 cuesta
unos US$0,08.

Reglas que se sumaron a `CRITERIO_VEREDICTO`:

- Si la prueba acredita el hecho principal (acto, fecha, monto), un detalle accesorio que no
  figura no lo baja a `sin_respaldo`: va a la nota.
- Una cláusula que excluye o no prevé lo que se reclama no contradice el reclamo.
- La prueba que registra el mismo hecho sobre otro número de comprobante lo contradice.
- Un total queda contradicho si la prueba contradice uno de sus componentes.
- Un rechazo, una negativa o una observación de una parte es su postura, no prueba en contra,
  salvo que la afirmación trate de ese mismo acto de la parte.
- `respaldada` y `contradicha` citan; `sin_respaldo` no cita.

**Lo que queda abierto:**

- **Citas de la NOTA:** el modelo transcribe fragmentos en la NOTA y citations los devuelve como
  citas. Pedirle en el prompt que no cite en la NOTA hizo que también dejara de citar en las
  `contradicha`, así que se resuelve en el parser: solo cuentan como evidencia las citas del
  pasaje, entre el encabezado y la NOTA. Las de la NOTA quedan en `traza.json` como `en_nota`,
  para depurar, pero no entran al veredicto. El estado lo sigue decidiendo el modelo; el parser
  solo decide qué parte de su respuesta es evidencia, igual que ya separaba la línea de la
  demanda de la de la prueba.
- **Variación entre corridas:** C2 AF-03 dio los tres estados con el mismo criterio. Con una
  corrida por configuración, una diferencia de una afirmación (6,7 puntos) no se distingue del
  ruido.

Las salidas commiteadas en `salida/` son de la última corrida, la del parser que ignora las
citas de la NOTA.

## M4 — fan-out por afirmación

`orquestador.py` es un orchestrator-worker. El orquestador es un modelo que no lee documentos:
tiene dos tools «meta» y decide cuándo llamarlas. Cada llamada corre un sub-agente; las
`verificar_afirmacion` que pide en una misma respuesta corren a la vez, en hilos.

```
                         ┌──────────────────────────┐
                         │       orquestador        │  max 6 iteraciones
                         │ tools: extraer_afirmac.  │  ve ids, títulos y estados
                         │        verificar_afirm.  │
                         └────────────┬─────────────┘
             1) extraer_afirmaciones  │  2) verificar_afirmacion × N, en paralelo
             ┌────────────────────────┼───────────────┬──────────────┐
             ▼                        ▼               ▼              ▼
      ┌─────────────┐          ┌────────────┐  ┌────────────┐  ┌────────────┐
      │  extractor  │          │verificador │  │verificador │  │verificador │
      │ leer_doc.   │          │  AF-01     │  │  AF-02     │  │  AF-NN     │
      └──────┬──────┘          └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
             │ Item[]                └───────────────┼───────────────┘
             │                                       ▼ Veredicto
             └──────────────►  fan-in (código): veredictos en el orden de las afirmaciones
                                         salida/<exp>/fanout/
```

**Qué se comparte y qué no.**

| De → a | Pasa | No pasa |
|---|---|---|
| Orquestador → extractor | el expediente y el id de la demanda | nada del historial |
| Extractor → orquestador | id y título de cada afirmación | el texto, que queda en el código |
| Orquestador → verificador | el id de una afirmación; el código le manda el ítem entero | el historial del orquestador y las otras afirmaciones |
| Verificador → orquestador | estado, confianza y cantidad de citas | la evidencia y la nota, que van directo al fan-in |

El criterio no viaja desde el orquestador: cada sub-agente lo pide al servidor MCP como prompt,
igual que en la versión secuencial. Que el orquestador no vea textos ni evidencia es a propósito:
su contexto crece con cada ronda y no necesita nada de eso para decidir qué delegar.

**Tools por sub-agente (blast radius).** Ninguno escribe: las tres tools del corpus son de
lectura, y lo único que se escribe en disco lo hace el código, en el fan-in.

| Sub-agente | Tools | Sin | Por qué |
|---|---|---|---|
| Orquestador | `extraer_afirmaciones`, `verificar_afirmacion` | las tres del corpus | coordina; si leyera documentos, su contexto cargaría con PDFs que no usa |
| Extractor | `leer_documento` | `listar_documentos`, `buscar` | recibe el id de la demanda: no tiene que buscar nada ni leer la prueba |
| Verificador | `listar_documentos`, `leer_documento`, `buscar` | las meta | ubica la prueba que corresponde a su afirmación; no puede delegar ni pedir otras |

El filtro se aplica en `agente.py` (`tools_permitidas`): el modelo no recibe la definición de
las tools que no le tocan, así que no las puede pedir.

**Prompt injection.** El verificador es el que lee la prueba, y su prompt de sistema
(`SISTEMA_VERIF`) dice que lo que dicen los documentos es material a analizar y no
instrucciones, y que si un documento pide algo se ignora. Las afirmaciones también vienen de un
documento (la demanda): llegan entre etiquetas `<afirmaciones>` y el prompt las declara datos a
verificar, no instrucciones. Además, aunque una instrucción
inyectada lo convenciera, sus tools son de lectura y sólo devuelve un veredicto que el código
parsea con un formato fijo.

**Errores.** Si un verificador termina sin veredicto o el id no existe, la tool vuelve con
`is_error` y el orquestador la pide de nuevo una vez. Un reintento no pisa la traza del intento
anterior (`AF-03#2`), así sus tokens también se cuentan.

**Cómo se corre.**

```
python orquestador.py C2_Mobiliario_de_estaciones --reusar-items --primeras 5
python evals.py C2_Mobiliario_de_estaciones --veredictos salida/C2_Mobiliario_de_estaciones/fanout/veredictos.json
```

`--primeras 5` es el subconjunto para depurar; `--paralelo` fija cuántos verificadores corren a
la vez (5 por defecto). `traza.json` guarda `segundos_verificacion` (del primer verificador que
arranca al último que termina), comparable con `segundos` de la versión secuencial, y
`segundos_suma_verificadores`, lo que tardaría uno detrás de otro. Con `--veredictos`, el eval
escribe su `eval.json` en `fanout/` y no pisa el de la versión secuencial.

**Costo.** Cada verificador lee su propia prueba, así que el fan-out manda los PDFs una vez por
afirmación en vez de una vez por expediente: va a gastar bastante más entrada que la secuencial.

**Primera corrida (19/10/2026, C2, `--reusar-items --primeras 5`, Haiku 5.5).**

| | Fan-out, 5 afirmaciones | Secuencial, 15 afirmaciones |
|---|---|---|
| Tiempo de verificación | 17,7 s (66,9 s sumando los verificadores) | 84,5 s |
| Estado correcto | 5/5 | — |
| Fuente correcta | 3/4 | — |
| Entrada por afirmación | ~40.000 tokens | ~6.400 tokens |

El paralelo se nota: el tiempo lo marca el verificador más lento (AF-03, 17,7 s), no la suma.
AF-01 sale `respaldada` sin cita: el verificador transcribió el pasaje de DOC-1 entre comillas en
vez de citarlo, también en el reintento; es la misma variación entre corridas del M3. La entrada
por afirmación es unas 6 veces la de la secuencial (≈ US$0,025 la corrida). El eval da 33,3 %
porque cuenta como faltantes las 10 afirmaciones que no se corrieron.

**Corrida completa (19/10/2026, las 15 afirmaciones de las 5 demandas, `--reusar-items`).** Se
cortó en C5 por el tope mensual de la API del workspace; C5 y C6 se corrieron el mismo día,
cuando se subió el tope. La salida de C2 reemplaza a la de la primera corrida.

| Expediente | Estado sec. / fan-out | Fuente sec. / fan-out | Verificación sec. / fan-out | Entrada sec. / fan-out |
|---|---|---|---|---|
| C1 | 100 / 100 % | 100 / 100 % | 55,8 / 48,6 s | 63k / 620k |
| C2 | 100 / 100 % | 100 / 80 % | 84,5 / 52,2 s | 96k / 728k |
| C3 | 86,7 / 86,7 % | 77,8 / 66,7 % | 61,7 / 56,6 s | 165k / 705k |
| C5 | 100 / 100 % | 72,7 / 72,7 % | 51,4 / 39,9 s | 136k / 477k |
| C6 | 86,7 / 86,7 % | 100 / 77,8 % | 59,5 / 53,0 s | 116k / 655k |
| **Promedio** | **94,7 / 94,7 %** | **90,1 / 79,4 %** | **62,6 / 50,1 s** | **3,2 M en total** |

- El estado promedio es el mismo que en la secuencial. En C6 cambian los errores (la secuencial
  falla AF-03, el fan-out AF-15) pero no la cantidad.
- La fuente baja unos 11 puntos: `respaldada` o `contradicha` sin cita (C2 AF-01 y AF-06, C3
  AF-01, C6 AF-05 y AF-10), porque el verificador transcribe el pasaje en vez de citarlo. Con un
  ítem por verificador el reintento no alcanza.
- El paralelo gana poco, un 20 %: con `--paralelo 5` los 15 verificadores corren en tres tandas
  (la suma de los verificadores, 178-234 s, se reparte en 40-57 s), y la secuencial lee todo una
  vez y escribe los 15 veredictos en pocas vueltas.
- La entrada es entre 3,5 y 10 veces la de la secuencial: ≈ 3,2 millones de tokens y 140.000 de
  salida los cinco, unos US$0,39, contra ≈ US$0,085 de la secuencial. Cada verificador lee su
  propia prueba: es el lugar donde más pegaría el cache del M6.

## M6 — tool forzada, cache y Batch API

`estructurado.py` verifica con un request por afirmación, sin loop de tools: la prueba entera del
expediente va en el prompt y el veredicto sale por `registrar_veredicto` (en `criterio.py`), con
`tool_choice` forzado y `strict: true`. Haiku 5.5 acepta la tool forzada; con ella no piensa
antes de llamarla, así que el razonamiento va en el primer campo del esquema (`analisis`).

```
../.venv/bin/python estructurado.py C2_Mobiliario_de_estaciones --primeras 3   # tiempo real, para depurar
../.venv/bin/python estructurado.py                                          # los 5, tiempo real
../.venv/bin/python estructurado.py --batch                                  # los 5, Batch API
```

**Prompt de sistema reescrito.** Secciones con etiquetas XML (`<rol>`, `<contexto>`, `<criterio>`,
`<datos>`, `<como_responder>`, `<ejemplos>`), contexto explícito de para qué se usa el resultado,
tres ejemplos de un expediente inventado (uno por estado) y chain-of-thought en el campo
`analisis`. Sin prefill: Haiku 5.5 lo rechaza con 400.

**Validación antes de usar el veredicto.** Primero pydantic (`VeredictoModelo`): el estado dentro
del enum, la confianza entre 0 y 1, `DOC-n` como documento, y las citas según el estado
(respaldada y contradicha citan; sin_respaldo no). Después la cita contra el PDF (`_anclar`):
sin citations, la página la declara el modelo, y el código busca el fragmento en el texto del
documento. Si está en otra página vale la del texto; si no está, es un error. Un veredicto que no
pasa vuelve al modelo como `tool_result` con `is_error`, una sola vez; si la corrección tampoco
pasa, se guarda lo que validó con confianza 0 y la marca de revisar a mano. En las corridas de
abajo ninguna respuesta falló la validación; los seis casos de falla (estado fuera del enum,
confianza 1,5, respaldada sin cita, sin_respaldo con cita, fragmento inventado, cita de la
demanda) se probaron con respuestas armadas.

**Cache.** El orden del prompt es tools → system → messages, y el primer mensaje arranca con la
lista y los PDFs de la prueba: el `cache_control` va en el último PDF, y la afirmación, que es lo
único que cambia, va después. La prueba ocupa entre 22.000 y 44.000 tokens por expediente. La
primera afirmación escribe la cache y va sola; las otras 14 la leen, cinco en paralelo.

**Reintentos.** El cliente va con `max_retries=0` y `_llamar` reintenta solo 429, 5xx y fallas de
conexión, con backoff exponencial, jitter y `retry-after` como mínimo. Un 400 no se reintenta.

**Batch API.** Un batch con los cinco expedientes; `custom_id` = `<expediente>__<AF-NN>`, que es
el join (los resultados vuelven en cualquier orden). Los resultados crudos se guardan en
`salida/batch_<id>.jsonl`, porque la API los borra a los 29 días. Los que vuelven `errored`,
`expired` o `canceled` se piden de nuevo en tiempo real; `--batch-id` retoma un batch enviado.

**Resultados (22/10/2026, Haiku 5.5, las 75 afirmaciones).**

| | M4 secuencial | M6 tiempo real | M6 batch sin precalentar | M6 batch precalentado |
|---|---|---|---|---|
| Estado | 94,7 % | 92,0 % | 92,0 % | 89,3 % |
| Fuente | 90,1 % | 82,7 % | 82,7 % | 82,3 % |
| Fuente ampliada | — | 88,5 % | 88,5 % | 88,1 % |
| Costo de los 5 | ≈ US$0,085 | US$0,068 | US$0,168 | US$0,061 |
| Costo por afirmación | ≈ US$0,0011 | US$0,0009 | US$0,0022 | US$0,0008 |
| Tiempo | ~5 min | 1 min 50 s | 3 min 15 s | 6 min 35 s |

- Sin cache, los mismos 2,7 millones de tokens de entrada costarían unos US$0,29 en tiempo real:
  la cache baja la corrida un 77 %.
- El batch sin precalentar salió más caro que el tiempo real. Procesa los requests en paralelo,
  así que los 15 de un expediente escriben la cache a la vez (a 2x, con TTL de 1 hora) y casi
  ninguno la lee: es el caso en que la cache encarece. Precalentado —la primera afirmación de
  cada expediente en tiempo real, el resto por el batch— cada expediente escribe una vez y las
  otras 14 leen. Contra el tiempo real ahorra un 11 %, no la mitad: con la cache, la entrada ya
  cuesta poco y lo que el batch abarata es lo que queda.
- El estado baja 2,7 puntos y la fuente 7 contra la secuencial del M4. Las fallas se concentran
  en C2 (AF-08, AF-09 y AF-12 salen sin_respaldo) y en C5, que cita páginas que tienen el pasaje
  pero no son las de la referencia. Este modo no tiene `buscar` ni piensa antes de la tool; no
  está medido cuál de las dos pesa.
- Entre las dos corridas por batch cambian C5 y C6 con el mismo prompt: es la variación entre
  corridas, del orden de una o dos afirmaciones por expediente.
- La extracción sigue siendo la del M1 (JSON por línea): con `--reusar-items` no se corre, y para
  la demanda apartada se corre una vez antes de verificar.

## Estado del repo

```
contrato.py    las formas de la sección 4 del enunciado
criterio.py    ESTADOS, la demanda apartada y los criterios de afirmación y de veredicto
corpus.py      índice del corpus, bloque document, validación de PDF y texto paginado
servidor_mcp.py  las tres tools del corpus y los prompts de los dos criterios
agente.py      los loops de extracción y de verificación, cliente del servidor MCP
orquestador.py el fan-out por afirmación (M4): orquestador, extractor y verificadores
estructurado.py la verificación con tool forzada, cache y Batch API (M6)
CLAUDE.md      cómo se corre, convenciones y decisiones de diseño, para Claude Code (M5)
.mcp.json      el servidor MCP del corpus conectado a Claude Code; el expediente sale de EXPEDIENTE
.claude/       settings (permisos y hooks), hooks/ (apartada bloqueada, eval tras cada corrida),
               skills/resultados (tabla de aciertos sin gastar API)
evals.py       califica extracción y verificación contra el set de referencia
corpus/        los 6 expedientes (escritos + prueba)
referencia/    el set de referencia de cada expediente
salida/        items.json, veredictos.json, traza.json y eval.json por expediente; fanout/,
               estructurado/ y batch/ por modo
requirements.txt  dependencias del venv
```

Pendiente de las próximas semanas: `correr.py` (M7).

## Cómo se trabaja el repo

GitFlow, con las tres ramas y sus roles:

| Rama | Para qué |
|---|---|
| `main` | Los cierres de semana. Cada módulo entregado se mergea acá y queda como el estado presentable. |
| `develop` | Integración. Es de donde salen y a donde vuelven las features. |
| `feature/mN-…` | Un módulo. `feature/m2-mcp`, `feature/m3-citations`, `feature/m4-fanout`, `feature/m5-claude-code`, `feature/m6-structured`, `feature/m7-corrida`. |

El ciclo de cada semana: `feature/mN-…` sale de `develop`, se trabaja ahí, se mergea a `develop`
cuando el eval da, y al cerrar la semana `develop` va a `main`.

M1 quedó commiteado directo sobre `main`, antes de adoptar la convención.
