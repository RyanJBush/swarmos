"""Escaped, offline HTML view of actual recorded execution events."""
import html
from pathlib import Path
from .evidence import stored


def render(history, run_id, output):
    data = stored(history, run_id)
    esc = lambda value: html.escape(str(value), quote=True)
    rows = ''.join('<tr>' + ''.join(f'<td>{esc(t.get(k, ""))}</td>' for k in
        ('sequence', 'role', 'tool', 'status', 'duration_ms', 'detail')) + '</tr>'
        for t in data.get('traces', []))
    document = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SwarmOS run timeline</title><style>
body{background:#101522;color:#e7edf8;font:16px system-ui;margin:3rem auto;max-width:1100px;padding:0 1rem}
h1{font-size:2.5rem}small{color:#96a9c8}table{width:100%;border-collapse:collapse;background:#192238}
td,th{text-align:left;padding:1rem;border-bottom:1px solid #35435c}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#192238;padding:1.5rem}
.badge{color:#8ee8ce}section{overflow:auto}</style>'''
    document += f'<small>SWARMOS / EXECUTION EVIDENCE</small><h1>Run timeline</h1><p>{esc(run_id)}</p>'
    document += f'<p class="badge">{esc(data["termination"])} · {len(data["steps"])} completed steps · {data["patches_attempted"]} patch attempt(s)</p>'
    document += '<section><table><tr><th>#</th><th>Role</th><th>Tool</th><th>Status</th><th>ms</th><th>Evidence</th></tr>'+rows+'</table></section>'
    document += f'<h2>Review decision</h2><p>{esc(data["message"])}</p><h2>Verified diff</h2><pre>{esc(data["diff"])}</pre>'
    document += '<p><small>Local deterministic fixture demonstration. Policy restrictions are not an OS sandbox.</small></p></html>'
    path = Path(output) / run_id / 'timeline.html'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding='utf-8')
    return path
