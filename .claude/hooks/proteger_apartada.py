"""PreToolUse: la demanda apartada no se abre antes de la semana 6.

Bloquea (exit 2) cualquier comando que la nombre o que pase --permitir-apartada. El motivo va
por stderr y Claude lo recibe como la razon del bloqueo.
"""
import json
import sys

APARTADA = "C4_Repuestos_de_material_rodante"

entrada = json.load(sys.stdin)
comando = entrada.get("tool_input", {}).get("command", "")
if APARTADA in comando or "--permitir-apartada" in comando:
    print(
        f"{APARTADA} es la demanda apartada: se corre una sola vez, en la semana 6, con el sistema "
        "como este. Para abrirla, que Omar corra el comando a mano.",
        file=sys.stderr,
    )
    sys.exit(2)
