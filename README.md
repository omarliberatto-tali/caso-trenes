# caso-trenes — Semana 1 (M1)

Verificación de respaldo probatorio sobre expedientes judiciales. Esta entrega cubre el
primer paso: extraer las afirmaciones de hecho de una demanda.

## Qué hace el agente

`agente.py` lee un escrito de demanda y devuelve la lista de sus afirmaciones de hecho, cada
una con su texto literal y la página de donde salió.

El PDF viaja entero como bloque `document` en base64, así el modelo ve la paginación real del
archivo en vez de marcadores que ponemos nosotros. El agente devuelve una línea JSON por
afirmación y cierra con `<FIN>`.

El loop corta por tres condiciones explícitas: llegó `<FIN>`, una iteración no aportó ninguna
afirmación nueva, o se alcanzó `max_iteraciones` (5 por defecto). Si la respuesta se corta por
`max_tokens`, el loop la reinyecta y pide continuar desde el inciso siguiente.

```
../.venv/bin/python agente.py C1_Impresos_y_formularios   # -> salida/<exp>/items.json
../.venv/bin/python evals.py  C1_Impresos_y_formularios   # -> salida/<exp>/eval.json
```

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
`AF-NN` y compara el texto normalizado con `difflib` (umbral 0,85). Reporta dos números y
cuenta faltantes, inventados y páginas erradas.

Sobre **C1_Impresos_y_formularios**, 15 afirmaciones:

| métrica | valor |
|---|---|
| acierto de ítem | **100 %** (15/15) |
| acierto de página | **100 %** |
| faltantes / inventados | 0 / 0 |

Estable en dos corridas, y las 15 con similitud 1,0 contra el texto de referencia.

### Qué caso falla

En la corrida normal, ninguno. El eval sí discrimina: con un control negativo —sacar un ítem,
mover una página, cambiar un texto y agregar uno inventado— baja a 86,7 % y marca los cuatro.

El caso que falla aparece al forzar el loop. Bajando `MAX_TOKENS` a 600, la extracción se parte
en 4 iteraciones y el fallo es **AF-09**, cuya página se reporta mal: arranca en la 3. La
explicación es que AF-08 cruza el salto de página 2→3, y cuando el corte de la continuación cae
justo ahí el modelo arrastra la página del tramo anterior. El acierto de ítem se mantiene en
100 % en todos los casos: la continuación no pierde ni duplica afirmaciones, sólo se le desancla
la página.

**Con el bloque `document` el fallo pasó a ser intermitente.** Con el texto paginado era
reproducible en cada corrida forzada. Con el PDF nativo, dos corridas forzadas dieron 100 % y
93,3 % de acierto de página — mismo caso, AF-09. O sea que la paginación real ayuda pero no
resuelve el problema, que es de la continuación y no de cómo llega el documento. Queda como el
caso a vigilar cuando en la semana 3 se enciendan las citations, que es donde el anclaje de
página deja de ser algo que el modelo declara y pasa a ser algo que la API devuelve.

## La demanda apartada

**`C4_Repuestos_de_material_rodante`**

Sorteada con `secrets.choice` sobre los 6 expedientes el 11/09/2026, antes de correr nada. Se
abre en la semana 6. `corpus.py` la bloquea: cualquier acceso levanta `ExpedienteApartado`
salvo que se pase `permitir_apartada=True`.

## Estado del repo

```
contrato.py    las formas de la sección 4 del enunciado
criterio.py    ESTADOS, la demanda apartada y el criterio de afirmación de hecho
corpus.py      índice del corpus, bloque document y texto paginado (índice de M2)
agente.py      el loop de extracción
evals.py       califica contra el set de referencia
corpus/        los 6 expedientes (escritos + prueba)
referencia/    el set de referencia de cada expediente
salida/        items.json y eval.json por expediente
```

Pendiente de las próximas semanas: `servidor_mcp.py` (M2), `orquestador.py` (M4) y
`correr.py` (M7).

## Cómo se trabaja el repo

Cada módulo va en su propia rama —`m2-mcp`, `m3-citations`, `m4-fanout`…— y se mergea a `main`
al cerrar la semana, así `main` siempre tiene el último estado que anda. M1 quedó commiteado
directo sobre `main`, antes de adoptar la convención.
