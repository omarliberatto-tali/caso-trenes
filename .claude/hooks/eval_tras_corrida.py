"""PostToolUse: despues de una corrida de agente.py, orquestador.py o estructurado.py, el eval corre solo.

El eval no llama a la API: califica lo que la corrida dejo en salida/. Su resumen vuelve a
Claude como contexto adicional, asi el numero aparece sin que nadie lo pida.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

entrada = json.load(sys.stdin)
comando = entrada.get("tool_input", {}).get("command", "")
m = re.search(r"\b(agente|orquestador|estructurado)\.py\b(?:\s+(C\d_\w+))?", comando)
if not m:
    sys.exit(0)

raiz = Path(entrada.get("cwd") or ".")
for p in [raiz, *raiz.parents]:
    if (p / "evals.py").exists():
        raiz = p
        break
expediente = m.group(2) or "C1_Impresos_y_formularios"
args = [str(raiz.parent / ".venv" / "bin" / "python"), "evals.py", expediente]
if m.group(1) == "orquestador":
    args += ["--veredictos", f"salida/{expediente}/fanout/veredictos.json"]
if m.group(1) == "estructurado":
    carpeta = "batch" if "--batch" in comando else "estructurado"
    args += ["--veredictos", f"salida/{expediente}/{carpeta}/veredictos.json"]
if not (raiz / "salida" / expediente / "items.json").exists():
    sys.exit(0)

r = subprocess.run(args, cwd=raiz, capture_output=True, text=True, timeout=50)
salida = r.stdout if r.returncode == 0 else f"el eval fallo:\n{r.stderr[-1500:]}"
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": f"Eval automatico de {expediente} (hook eval_tras_corrida):\n{salida}",
    }
}))
