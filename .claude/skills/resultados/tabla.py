"""Tabla de aciertos por expediente y version, a partir de los eval.json de salida/."""
import json
from pathlib import Path

salida = Path(__file__).resolve().parents[3] / "salida"
print(f"{'expediente':32} {'version':10} {'estado':>7} {'fuente':>7} {'ampl.':>7}  fallan")
for exp in sorted(p for p in salida.iterdir() if p.is_dir()):
    for version, carpeta in (("secuencial", exp), ("fan-out", exp / "fanout")):
        ev = carpeta / "eval.json"
        if not ev.exists():
            continue
        v = json.loads(ev.read_text(encoding="utf-8")).get("verificacion")
        if not v:
            continue
        r = v["resumen"]
        fallan = [d["id"] for d in v["detalle"] if not d.get("faltante") and (not d["estado_ok"] or d["fuente_ok"] is False)]
        faltan = sum(1 for d in v["detalle"] if d.get("faltante"))
        extra = f" (+{faltan} sin correr)" if faltan else ""
        print(
            f"{exp.name:32} {version:10} {r['acierto_item_pct']:>6}% {r['acierto_fuente_pct']:>6}% "
            f"{r['acierto_fuente_ampliada_pct']:>6}%  {', '.join(fallan) or '-'}{extra}"
        )
