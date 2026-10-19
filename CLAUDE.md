# Caso Trenes

Verifica si cada afirmación de hecho de una demanda tiene respaldo en la prueba documental del
expediente: por cada una, un veredicto `respaldada`, `sin_respaldo` o `contradicha` con la cita
exacta (documento, página y fragmento). Proyecto final del Winter AI Camp. El detalle de cada
semana está en el README.

## Cómo se corre

El venv está un nivel arriba del repo, junto con el `.env` de la API key: `../.venv/bin/python`.

```
../.venv/bin/python agente.py C2_Mobiliario_de_estaciones --reusar-items      # secuencial (M1-M3)
../.venv/bin/python orquestador.py C2_Mobiliario_de_estaciones --reusar-items --primeras 5   # fan-out (M4)
../.venv/bin/python evals.py C2_Mobiliario_de_estaciones                       # eval, no gasta API
```

- `--reusar-items` verifica el `items.json` que ya está en `salida/` sin volver a extraer.
- `agente.py` y `orquestador.py` gastan saldo de API: el tope es mensual y chico. Antes de
  correrlos, decir cuánto va a costar (una pasada secuencial de los 5 expedientes ≈ US$0,085;
  el fan-out gasta unas 6 veces más de entrada por afirmación). Depurar sobre un expediente y
  con `--primeras`, no sobre los 5.
- Después de cada corrida el hook `eval_tras_corrida` corre el eval solo y devuelve el resumen.
- `/resultados` muestra la tabla de aciertos de todos los expedientes, sin llamar a la API.
- El servidor MCP del corpus (`corpus-trenes`, en `.mcp.json`) sirve un expediente por vez:
  se elige con la variable `EXPEDIENTE` al abrir Claude Code (`EXPEDIENTE=C3_Mantenimiento_de_via claude`).

## Convenciones

- GitFlow: `main` para los cierres de semana, `develop` para integrar, `feature/mN-…` por
  módulo. Los merges van con `--no-ff`.
- Código, prompts y commits en castellano.
- `referencia/` es el set de respuestas del curso: no se edita. Una fuente válida que la
  referencia no admite va a `referencia/fuentes_extra.json`, con su justificación.
- `C4_Repuestos_de_material_rodante` es la demanda apartada: se corre una sola vez, en la
  semana 6. Un hook bloquea cualquier comando que la nombre.
- Una regla nueva del criterio (`criterio.py`) tiene que pasar la prueba del mentor: que un
  especialista la pondría en un manual para alguien que arranca, sin haber visto el caso, y
  con fuente. Se anota en el README.

## Decisiones de diseño

**Al agente se le pasa la demanda entera, no el capítulo de los hechos recortado.** Recortarlo
con una regex resolvería por código justo lo que se evalúa del agente: encontrar dónde están
las afirmaciones. Sale más caro en tokens, pero el número mide al agente y no al recorte.

**La prueba va como PDF y no como texto plano.** Con PDF se pueden usar citations, y la cita
trae la página del documento, que es lo que mide el acierto de fuente. Con texto plano la cita
devolvería posiciones de caracteres y la página habría que reconstruirla.

**En el fan-out el orquestador no ve los textos ni la evidencia.** Recibe ids, títulos y
estados; el resto va directo del sub-agente al fan-in por código. El contexto del orquestador
crece con cada ronda y no necesita nada de eso para decidir qué delegar.
