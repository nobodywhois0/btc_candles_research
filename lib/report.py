"""make_report() ensambla el registro de un experimento en un único HTML
autocontenido (figuras embebidas en base64, sin dependencias externas).
Las conclusiones e interpretación las escribe el investigador (el
propio run.py del experimento) — este módulo nunca las genera solo.
"""
from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd

_CSS = """
:root{
  --paper:#EEF0EC;--ink:#14171A;--ink-muted:#4B5259;--ink-faint:#767D80;
  --line:#D3D7D0;--accent:#B5792A;--accent-ink:#7E5218;--accent-wash:rgba(181,121,42,.10);
  --green:#2F7A4F;--green-wash:rgba(47,122,79,.10);--red:#B33A3A;--red-wash:rgba(179,58,58,.09);
  --font-display:"Cambria","Constantia",Georgia,serif;
  --font-body:"Charter","Iowan Old Style",Georgia,serif;
  --font-mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){
  :root{--paper:#14161A;--ink:#E9E7DF;--ink-muted:#A8AEA8;--ink-faint:#767D78;--line:#31352F;
  --accent:#D9A354;--accent-ink:#E9BE84;--accent-wash:rgba(217,163,84,.13);
  --green:#5CAE7E;--green-wash:rgba(92,174,126,.13);--red:#D2726A;--red-wash:rgba(210,114,106,.12);}
}
*{box-sizing:border-box;}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--font-body);
  font-size:16.5px;line-height:1.6;padding:48px 24px 100px;}
.wrap{max-width:820px;margin:0 auto;}
.eyebrow{font-family:var(--font-mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--accent-ink);margin-bottom:10px;}
h1{font-family:var(--font-display);font-size:clamp(26px,4vw,36px);font-weight:700;margin:0 0 8px;}
h2{font-family:var(--font-display);font-size:21px;font-weight:700;margin:38px 0 14px;
  border-top:1px solid var(--line);padding-top:28px;}
h2:first-of-type{border-top:none;padding-top:0;}
.hypothesis{font-size:18px;color:var(--ink-muted);max-width:66ch;margin:0 0 24px;}
dl.registro{display:grid;grid-template-columns:180px 1fr;gap:8px 16px;font-size:14.5px;margin:16px 0;}
dl.registro dt{font-family:var(--font-mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--ink-faint);padding-top:2px;}
dl.registro dd{margin:0 0 6px;color:var(--ink-muted);}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:14px 0;}
th{text-align:left;font-family:var(--font-mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--ink-faint);background:rgba(0,0,0,.02);padding:8px 10px;border-bottom:1px solid var(--line);}
td{padding:8px 10px;border-bottom:1px solid var(--line);color:var(--ink-muted);
  font-variant-numeric:tabular-nums;}
figure{margin:20px 0;}
figure img{max-width:100%;border:1px solid var(--line);border-radius:8px;}
figcaption{font-family:var(--font-mono);font-size:12px;color:var(--ink-faint);margin-top:8px;}
.pill{font-family:var(--font-mono);font-size:11px;text-transform:uppercase;padding:3px 10px;
  border-radius:20px;border:1px solid;display:inline-block;}
.pill--lvl0,.pill--lvl1{color:var(--ink-muted);border-color:var(--line);}
.pill--lvl2,.pill--lvl3{color:var(--accent-ink);border-color:var(--accent);background:var(--accent-wash);}
.pill--lvl4{color:var(--green);border-color:var(--green);background:var(--green-wash);}
.pill--reject{color:var(--red);border-color:var(--red);background:var(--red-wash);}
.callout{border-left:3px solid var(--accent);background:var(--accent-wash);padding:14px 18px;
  border-radius:2px;margin:16px 0;font-size:14.5px;}
.callout.risk{border-left-color:var(--red);background:var(--red-wash);}
footer{font-family:var(--font-mono);font-size:11.5px;color:var(--ink-faint);margin-top:48px;
  border-top:1px solid var(--line);padding-top:16px;}
"""

_LEVEL_PILL = {
    0: "lvl0", 1: "lvl1", 2: "lvl2", 3: "lvl3", 4: "lvl4", "rechazada": "reject",
}


def _img_to_data_uri(path: Path) -> str:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def make_report(
    *,
    title: str,
    hypothesis: str,
    registro: dict,
    tables: dict[str, pd.DataFrame],
    figures: dict[str, Path],
    devils_advocate: list[str],
    out_path: str | Path,
) -> Path:
    level = registro.get("nivel_de_evidencia", 0)
    level_key = _LEVEL_PILL.get(level, "lvl0")

    registro_html = "".join(
        f"<dt>{k.replace('_', ' ')}</dt><dd>{v}</dd>" for k, v in registro.items()
    )

    tables_html = ""
    for caption, df in tables.items():
        tables_html += f"<h2>{caption}</h2>" + df.to_html(index=False, float_format=lambda x: f"{x:.4f}")

    figures_html = ""
    for caption, path in figures.items():
        uri = _img_to_data_uri(path)
        figures_html += f'<figure><img src="{uri}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'

    devils_html = "<ol>" + "".join(f"<li>{r}</li>" for r in devils_advocate) + "</ol>"

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><style>{_CSS}</style></head><body><div class="wrap">
<div class="eyebrow">Registro de experimento &middot; research/</div>
<h1>{title}</h1>
<p class="hypothesis">{hypothesis}</p>
<span class="pill pill--{level_key}">Nivel de evidencia: {level}</span>

<h2>Registro del experimento</h2>
<dl class="registro">{registro_html}</dl>

<h2>Las cinco mejores razones por las que este resultado probablemente sea falso</h2>
<div class="callout risk">{devils_html}</div>

{tables_html}
{figures_html}

<footer>Generado por lib/report.py &middot; research/001_survival &middot; sin edición manual posterior.</footer>
</div></body></html>"""

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
