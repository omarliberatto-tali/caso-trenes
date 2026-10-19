---
name: resultados
description: Tabla de resultados del eval de Trenes por expediente (estado, fuente, fuente ampliada) para la version secuencial y el fan-out, leida de salida/*/eval.json sin llamar a la API. Usar cuando se pregunte como viene el eval, que acierto da, o para comparar corridas.
---

# Resultados del eval

1. Corre `python3 .claude/skills/resultados/tabla.py`. Lee los `eval.json` que ya estan en
   `salida/<expediente>/` y `salida/<expediente>/fanout/`; no corre agentes ni gasta API.
2. Mostra la tabla tal cual y, debajo, en una o dos lineas: el expediente mas bajo, y las
   afirmaciones que fallan en mas de un expediente (columna "fallan").
3. Si un expediente no tiene `eval.json`, decilo y sugeri
   `../.venv/bin/python evals.py <expediente>`, que tampoco gasta API.

No corras `agente.py` ni `orquestador.py` desde esta skill: cuestan saldo de API.
