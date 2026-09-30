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
  `paginas_admitidas`. Si la referencia es `sin_respaldo` sin evidencia, lo correcto es no
  citar nada. El fragmento no se compara, porque con citations es literal del PDF por
  construcción y la referencia guarda uno solo de los pasajes válidos.

Resultado sobre C1, C2 y C3: pendiente de la primera corrida.

## Estado del repo

```
contrato.py    las formas de la sección 4 del enunciado
criterio.py    ESTADOS, la demanda apartada y los criterios de afirmación y de veredicto
corpus.py      índice del corpus, bloque document, validación de PDF y texto paginado
servidor_mcp.py  las tres tools del corpus y los prompts de los dos criterios
agente.py      los loops de extracción y de verificación, cliente del servidor MCP
evals.py       califica extracción y verificación contra el set de referencia
corpus/        los 6 expedientes (escritos + prueba)
referencia/    el set de referencia de cada expediente
salida/        items.json, veredictos.json, traza.json y eval.json por expediente
requirements.txt  dependencias del venv
```

Pendiente de las próximas semanas: `orquestador.py` (M4) y
`correr.py` (M7).

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
