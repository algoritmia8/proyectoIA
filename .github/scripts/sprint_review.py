#!/usr/bin/env python3
"""
Sprint Review Agent — GitHub Actions
=====================================
Cada viernes a las 8:00 AM (hora España):
  1. Obtiene el sprint actual de Azure DevOps (equipo Grupo IA)
  2. Lee la memoria del sprint anterior (sprint-memory/estado-sprint.md)
  3. Detecta cambios (nuevos, completados, sin movimiento, eliminados)
  4. Envía correo HTML con resumen de pendientes e ítems que requieren atención
  5. Actualiza el fichero de memoria → el workflow hace commit automático
"""

import os
import re
import json
import base64
import smtplib
import html as _html_lib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ─── Configuración ────────────────────────────────────────────────────────────
ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
ADO_TEAM    = "Grupo IA"
TEAM_GUID   = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"
MEMORY_FILE = "sprint-memory/estado-sprint.md"

# Desde secrets / env
ADO_PAT       = os.environ["ADO_PAT"]
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.office365.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EMAIL_TO      = os.environ.get("EMAIL_TO", "ifont@algoritmia8.com")

DONE_STATES = {"Done", "Closed", "Resolved"}

# ─── GitHub Models AI ─────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
AI_ENDPOINT  = "https://models.inference.ai.azure.com/chat/completions"
AI_MODEL     = "gpt-4o-mini"

# ─── Helpers HTML / texto ────────────────────────────────────────────────────
class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
    def handle_data(self, d: str) -> None:
        self._parts.append(d)
    def get_data(self) -> str:
        return " ".join(self._parts)


def strip_html(text: str) -> str:
    """Elimina etiquetas HTML y decodifica entidades."""
    if not text:
        return ""
    s = _HTMLStripper()
    s.feed(_html_lib.unescape(text))
    cleaned = re.sub(r"\s+", " ", s.get_data())
    return cleaned.strip()


# ─── Helpers Azure DevOps ─────────────────────────────────────────────────────
def _ado_headers():
    token = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }


def _get(url: str) -> dict:
    req = Request(url, headers=_ado_headers())
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_ado_headers(), method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_current_sprint() -> dict | None:
    """Devuelve el sprint activo del equipo Grupo IA, o None si no hay ninguno."""
    proj = ADO_PROJECT.replace(" ", "%20")
    # Usar GUID del equipo en la URL para evitar ambigüedades con el nombre
    url_current = (
        f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations"
        f"?$timeframe=current&api-version=7.0"
    )
    try:
        data = _get(url_current)
        iterations = data.get("value", [])
        if iterations:
            return iterations[0]
    except (HTTPError, URLError) as exc:
        print(f"WARN: timeframe=current falló ({exc}), listando todas las iteraciones…")

    # Fallback: listar todas las iteraciones y devolver la marcada como 'current'
    url_all = (
        f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations"
        f"?api-version=7.0"
    )
    try:
        data = _get(url_all)
        for it in data.get("value", []):
            if it.get("attributes", {}).get("timeFrame") == "current":
                return it
        print("INFO: no hay ninguna iteración marcada como 'current'.")
    except (HTTPError, URLError) as exc:
        print(f"ERROR al obtener iteraciones: {exc}")
    return None


def get_sprint_items(iteration_path: str) -> list[dict]:
    """Recupera todos los work items del sprint dado."""
    proj = ADO_PROJECT.replace(" ", "%20")
    # WIQL — obtiene IDs
    escaped = iteration_path.replace("'", "''")
    wiql = {
        "query": (
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{ADO_PROJECT}' "
            f"AND [System.IterationPath] = '{escaped}' "
            f"ORDER BY [System.WorkItemType], [System.State]"
        )
    }
    result = _post(f"{ADO_ORG}/{proj}/_apis/wit/wiql?api-version=7.0", wiql)
    ids = [w["id"] for w in result.get("workItems", [])]
    if not ids:
        return []

    # Batch fetch detalle
    fields = (
        "System.Id,System.Title,System.State,System.AssignedTo,"
        "System.WorkItemType,System.AreaPath,System.ChangedDate,"
        "System.Description,Microsoft.VSTS.Common.AcceptanceCriteria"
    )
    items = []
    for i in range(0, len(ids), 200):
        batch   = ids[i : i + 200]
        ids_str = ",".join(map(str, batch))
        url = f"{ADO_ORG}/_apis/wit/workitems?ids={ids_str}&fields={fields}&api-version=7.0"
        data = _get(url)
        items.extend(data.get("value", []))
    return items


# ─── Evaluación IA ───────────────────────────────────────────────────────────
def evaluate_with_ai(sprint_name: str, items: list[dict]) -> dict:
    """
    Llama a GitHub Models (gpt-4o-mini) para evaluar el contenido de los ítems.
    Devuelve dict con 'resumen_ejecutivo' y 'items' (por id: calidad/riesgo/coherencia/sugerencias).
    Si falla o no hay token, devuelve {}.
    """
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN no disponible — saltando evaluación IA")
        return {}

    pending = [i for i in items if i["fields"]["System.State"] not in DONE_STATES][:60]
    done    = [i for i in items if i["fields"]["System.State"] in DONE_STATES]

    items_data = []
    for item in pending:
        f = item["fields"]
        items_data.append({
            "id":                    str(item["id"]),
            "tipo":                  f.get("System.WorkItemType", ""),
            "estado":                f.get("System.State", ""),
            "titulo":                (f.get("System.Title") or "")[:120],
            "descripcion":           strip_html(f.get("System.Description") or "")[:400],
            "criterios_aceptacion":  strip_html(f.get("Microsoft.VSTS.Common.AcceptanceCriteria") or "")[:300],
        })

    done_summary = [
        {"id": str(i["id"]), "titulo": (i["fields"].get("System.Title") or "")[:80]}
        for i in done
    ]

    prompt = (
        f'Eres un Scrum Master experto analizando el sprint "{sprint_name}".\n'
        'Responde ÚNICAMENTE con un objeto JSON válido (sin markdown) con esta estructura:\n'
        '{\n'
        '  "resumen_ejecutivo": "3-5 frases: estado del sprint, completados, riesgos, recomendación.",\n'
        '  "items": {\n'
        '    "<id>": {\n'
        '      "calidad": 1,\n'
        '      "riesgo": "bajo",\n'
        '      "coherencia": true,\n'
        '      "sugerencias": ""\n'
        '    }\n'
        '  }\n'
        '}\n\n'
        'Criterios:\n'
        '- calidad: 1 (sin descripción ni criterios) a 5 (ítem perfectamente definido)\n'
        '- riesgo: "bajo" | "medio" | "alto" — considera ambigüedad, tamaño o dependencias\n'
        '- coherencia: true si encaja en el sprint, false si parece fuera de lugar\n'
        '- sugerencias: máximo 2 frases concretas de mejora, o "" si está bien\n\n'
        f'SPRINT: {sprint_name}\n\n'
        f'ÍTEMS PENDIENTES:\n{json.dumps(items_data, ensure_ascii=False)}\n\n'
        f'ÍTEMS COMPLETADOS (solo para contexto):\n{json.dumps(done_summary, ensure_ascii=False)}'
    )

    body = json.dumps({
        "model":           AI_MODEL,
        "messages":        [{"role": "user", "content": prompt}],
        "max_tokens":      4000,
        "temperature":     0.2,
        "response_format": {"type": "json_object"},
    }).encode()

    req = Request(
        AI_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=90) as r:
            resp    = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"]
        result  = json.loads(content)
        n = len(result.get("items", {}))
        print(f"🤖  Evaluación IA completada — {n} ítems evaluados")
        return result
    except Exception as exc:
        print(f"⚠️  Error en evaluación IA: {exc}")
        return {}


# ─── Memoria (lectura / escritura) ───────────────────────────────────────────
def load_memory() -> dict:
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            content = f.read()
        if "```json" in content:
            start = content.index("```json") + 7
            end   = content.index("```", start)
            return json.loads(content[start:end].strip())
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return {}


def archive_sprint(prev: dict) -> None:
    """Archiva la memoria del sprint anterior antes de reiniciar."""
    prev_sprint = prev.get("sprint", "unknown")
    archive_dir = "sprint-memory/archive"
    os.makedirs(archive_dir, exist_ok=True)
    filename = f"{archive_dir}/{prev_sprint.replace(' ', '-').replace('/', '-')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(prev, ensure_ascii=False, indent=2, fp=f)
    print(f"📁  Sprint anterior archivado: {filename}")


def save_memory(data: dict, sprint_name: str, items: list[dict], now: datetime) -> None:
    os.makedirs("sprint-memory", exist_ok=True)
    incomplete = [i for i in items if i["fields"]["System.State"] not in DONE_STATES]
    complete   = [i for i in items if i["fields"]["System.State"] in DONE_STATES]
    pct = round(len(complete) / len(items) * 100) if items else 0

    def _name(f: dict) -> str:
        a = f.get("System.AssignedTo") or {}
        return a.get("displayName", "—") if isinstance(a, dict) else "—"

    rows = []
    for item in sorted(items, key=lambda x: (x["fields"]["System.WorkItemType"], x["fields"]["System.State"])):
        f     = item["fields"]
        state = f.get("System.State", "")
        badge = "✅" if state in DONE_STATES else ("⚠️" if state == "New" else "🔄")
        area  = f.get("System.AreaPath", "").split("\\")[-1]
        rows.append(
            f"| #{item['id']} | {f['System.WorkItemType']} | {f['System.Title'][:60]} "
            f"| {badge} {state} | {_name(f)} | {area} |"
        )

    lines = [
        f"# Sprint Memory — {sprint_name}",
        "",
        f"> Última actualización: **{now.strftime('%Y-%m-%d %H:%M UTC')}** | "
        f"Progreso: **{pct}%** ({len(complete)}/{len(items)})",
        "",
        "## Estado del sprint",
        "",
        "| # | Tipo | Título | Estado | Asignado | Área |",
        "|---|------|--------|--------|----------|------|",
        *rows,
        "",
        f"**Total:** {len(items)} &nbsp;|&nbsp; "
        f"**Completos:** {len(complete)} &nbsp;|&nbsp; "
        f"**Pendientes:** {len(incomplete)}",
        "",
        "---",
        "## Datos internos (no editar manualmente)",
        "",
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ─── Detección de cambios ─────────────────────────────────────────────────────
def detect_changes(prev: dict, items: list[dict]) -> tuple[dict, dict]:
    prev_items = prev.get("items", {})
    changes = {"new": [], "completed": [], "state_changed": [], "removed": [], "stale": []}
    current_map: dict[str, dict] = {}

    for item in items:
        f    = item["fields"]
        iid  = str(item["id"])
        state = f.get("System.State", "")
        title = f.get("System.Title", "")
        prev_info = prev_items.get(iid, {})
        prev_state = prev_info.get("state", "")

        # stale_count: cuántas semanas consecutivas sin cambio de estado (y no done)
        if state in DONE_STATES:
            stale_count = 0
        elif prev_state == state:
            stale_count = prev_info.get("stale_count", 0) + 1
        else:
            stale_count = 0

        current_map[iid] = {"state": state, "title": title, "stale_count": stale_count}

        if iid not in prev_items:
            changes["new"].append({"id": iid, "title": title, "state": state})
        elif prev_state not in DONE_STATES and state in DONE_STATES:
            changes["completed"].append({"id": iid, "title": title})
        elif prev_state != state:
            changes["state_changed"].append({"id": iid, "title": title, "from": prev_state, "to": state})
        elif state not in DONE_STATES and stale_count >= 1:
            changes["stale"].append({"id": iid, "title": title, "state": state, "weeks": stale_count})

    for iid, info in prev_items.items():
        if iid not in current_map:
            changes["removed"].append({"id": iid, "title": info.get("title", ""), "state": info.get("state", "")})

    return changes, current_map


# ─── Construcción del email HTML ──────────────────────────────────────────────
_TABLE_HEADER = (
    '<table border="0" cellspacing="0" cellpadding="0" '
    'style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">'
    '<tr style="background:#343a40;color:white">'
    '<th style="padding:6px 8px;text-align:left">#</th>'
    '<th style="padding:6px 8px;text-align:left">Tipo</th>'
    '<th style="padding:6px 8px;text-align:left">Título</th>'
    '<th style="padding:6px 8px;text-align:left">Estado</th>'
    '<th style="padding:6px 8px;text-align:left">Asignado a</th>'
    '<th style="padding:6px 8px;text-align:left">Área</th>'
    '</tr>'
)


def _item_row(item: dict, bg: str = "#f8f9fa") -> str:
    f     = item["fields"]
    a     = f.get("System.AssignedTo") or {}
    name  = a.get("displayName", "—") if isinstance(a, dict) else "—"
    state = f.get("System.State", "")
    area  = f.get("System.AreaPath", "").split("\\")[-1]
    url   = f"https://algoritmia8.visualstudio.com/Algoritmia%20IA/_workitems/edit/{item['id']}"
    return (
        f'<tr style="background:{bg}">'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6">'
        f'<a href="{url}" style="color:#0078d4">#{item["id"]}</a></td>'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6">'
        f'{f["System.WorkItemType"]}</td>'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6">'
        f'{f["System.Title"][:70]}</td>'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6"><b>{state}</b></td>'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6">{name}</td>'
        f'<td style="padding:4px 8px;border-bottom:1px solid #dee2e6">{area}</td>'
        f'</tr>'
    )


def build_email(
    sprint_name: str,
    items: list[dict],
    changes: dict,
    now: datetime,
    ai_eval: dict | None = None,
) -> tuple[str, str]:
    incomplete  = [i for i in items if i["fields"]["System.State"] not in DONE_STATES]
    complete    = [i for i in items if i["fields"]["System.State"] in DONE_STATES]
    pct         = round(len(complete) / len(items) * 100) if items else 0

    # Ítems que requieren atención: sin asignar O en estado New
    def _unassigned(item):
        a = item["fields"].get("System.AssignedTo") or {}
        return not (a.get("displayName") if isinstance(a, dict) else a)

    attention = [
        i for i in incomplete
        if _unassigned(i) or i["fields"].get("System.State") == "New"
    ]

    # ── Sección cambios ──
    def _li_list(items_list, fmt_fn) -> str:
        return "<ul>" + "".join(f"<li>{fmt_fn(c)}</li>" for c in items_list) + "</ul>"

    changes_html = ""
    if changes["completed"]:
        changes_html += (
            f'<p>✅ <b>Completados esta semana ({len(changes["completed"])}):</b></p>'
            + _li_list(changes["completed"], lambda c: f'<b>#{c["id"]}</b> {c["title"]}')
        )
    if changes["new"]:
        changes_html += (
            f'<p>🆕 <b>Nuevos en el sprint ({len(changes["new"])}):</b></p>'
            + _li_list(changes["new"], lambda c: f'<b>#{c["id"]}</b> {c["title"]} — <i>{c["state"]}</i>')
        )
    if changes["state_changed"]:
        changes_html += (
            f'<p>🔄 <b>Cambios de estado ({len(changes["state_changed"])}):</b></p>'
            + _li_list(
                changes["state_changed"],
                lambda c: f'<b>#{c["id"]}</b> {c["title"]}: '
                          f'<s style="color:#6c757d">{c["from"]}</s> → <b>{c["to"]}</b>',
            )
        )
    if changes["stale"]:
        changes_html += (
            f'<p>⚠️ <b>Sin movimiento ({len(changes["stale"])}):</b></p>'
            + _li_list(
                changes["stale"],
                lambda c: f'<b>#{c["id"]}</b> {c["title"]} — '
                          f'lleva <b>{c["weeks"]}</b> semana(s) sin avanzar ({c["state"]})',
            )
        )
    if changes["removed"]:
        changes_html += (
            f'<p>❌ <b>Eliminados del sprint ({len(changes["removed"])}):</b></p>'
            + _li_list(changes["removed"], lambda c: f'<b>#{c["id"]}</b> {c["title"]}')
        )
    if not changes_html:
        changes_html = '<p style="color:#6c757d"><i>Sin cambios detectados respecto a la última revisión.</i></p>'

    # ── Análisis IA ──
    ai_summary_html = ""
    ai_quality_html = ""
    if ai_eval:
        summary = ai_eval.get("resumen_ejecutivo", "")
        if summary:
            ai_summary_html = (
                '<div style="background-color:#5a4fcf;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);'
                'color:#ffffff;padding:20px 24px;border-radius:8px;margin:20px 0">'
                '<div style="font-size:1.05rem;font-weight:bold;margin-bottom:8px;color:#ffffff">'
                '🤖 Análisis IA del sprint</div>'
                f'<p style="margin:0;line-height:1.7;color:#ffffff">{summary}</p>'
                '</div>'
            )

        ai_items = ai_eval.get("items", {})
        risk_colors = {"bajo": "#28a745", "medio": "#fd7e14", "alto": "#dc3545"}
        flagged = [
            (iid, info)
            for iid, info in ai_items.items()
            if info.get("calidad", 5) <= 2 or info.get("riesgo") == "alto" or not info.get("coherencia", True)
        ]
        if flagged:
            # Build a lookup title map
            title_map = {str(i["id"]): i["fields"].get("System.Title", "") for i in items}
            rows_flagged = []
            for iid, info in sorted(flagged, key=lambda x: x[1].get("calidad", 5)):
                calidad  = info.get("calidad", 0)
                riesgo   = info.get("riesgo", "")
                coherent = info.get("coherencia", True)
                sugg     = info.get("sugerencias", "")
                stars    = "★" * calidad + "☆" * (5 - calidad)
                rc       = risk_colors.get(riesgo, "#6c757d")
                badges   = f'<span style="color:{rc};font-weight:bold">[riesgo: {riesgo}]</span>'
                if not coherent:
                    badges += ' <span style="color:#6610f2;font-weight:bold">[fuera de contexto]</span>'
                item_url = f"https://algoritmia8.visualstudio.com/Algoritmia%20IA/_workitems/edit/{iid}"
                title    = (title_map.get(iid) or "")[:70]
                rows_flagged.append(
                    f'<div style="border-left:4px solid {rc};padding:8px 14px;margin:6px 0;'
                    f'background:#f8f9fa;border-radius:0 4px 4px 0">'
                    f'<b><a href="{item_url}" style="color:#0078d4">#{iid}</a> {title}</b> '
                    f'{badges} · calidad: {stars}'
                    + (f'<br><span style="color:#6c757d;font-size:12px">💡 {sugg}</span>' if sugg else "")
                    + "</div>"
                )
            ai_quality_html = (
                f'<h3>🔍 Ítems que necesitan mejora según IA ({len(flagged)})</h3>'
                + "".join(rows_flagged)
            )

    # ── Tabla pendientes ──
    def _row_bg(item):
        s = item["fields"].get("System.State", "")
        if s == "New":           return "#fff3cd"
        if "Active" in s:        return "#d1ecf1"
        return "#f8f9fa"

    incomplete_rows = "".join(_item_row(i, _row_bg(i)) for i in incomplete)
    attention_rows  = "".join(_item_row(i, "#fff3cd") for i in attention)

    board_path = sprint_name.replace("\\", "/")
    board_url  = (
        f"https://algoritmia8.visualstudio.com/Algoritmia%20IA/_sprints/taskboard/"
        f"Grupo%20IA/{board_path}"
    )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"></head>
<body style="font-family:Segoe UI,Arial,sans-serif;background-color:#ffffff;color:#212529;margin:0;padding:0">
<div style="max-width:960px;margin:auto;padding:24px;background-color:#ffffff;color:#212529">

<h2 style="color:#0078d4;border-bottom:2px solid #0078d4;padding-bottom:8px">
  📋 Revisión semanal de sprint — {sprint_name}
</h2>
<p style="color:#6c757d;margin-top:-8px">
  {now.strftime("%A %d de %B de %Y — %H:%M UTC")}
</p>

{ai_summary_html}

<!-- KPIs -->
<table style="width:100%;background:#f8f9fa;border-radius:8px;padding:16px;margin:20px 0;border-collapse:collapse">
  <tr>
    <td style="text-align:center;padding:12px">
      <div style="font-size:2rem">📦</div>
      <div style="font-size:1.6rem;font-weight:bold">{len(items)}</div>
      <div style="color:#6c757d;font-size:.85rem">Total ítems</div>
    </td>
    <td style="text-align:center;padding:12px">
      <div style="font-size:2rem">✅</div>
      <div style="font-size:1.6rem;font-weight:bold;color:#28a745">{len(complete)}</div>
      <div style="color:#6c757d;font-size:.85rem">Completados</div>
    </td>
    <td style="text-align:center;padding:12px">
      <div style="font-size:2rem">🔄</div>
      <div style="font-size:1.6rem;font-weight:bold;color:#007bff">{len(incomplete)}</div>
      <div style="color:#6c757d;font-size:.85rem">Pendientes</div>
    </td>
    <td style="text-align:center;padding:12px">
      <div style="font-size:2rem">⚠️</div>
      <div style="font-size:1.6rem;font-weight:bold;color:#dc3545">{len(attention)}</div>
      <div style="color:#6c757d;font-size:.85rem">Requieren atención</div>
    </td>
    <td style="text-align:center;padding:12px">
      <div style="font-size:2rem">📊</div>
      <div style="font-size:1.6rem;font-weight:bold;color:#17a2b8">{pct}%</div>
      <div style="color:#6c757d;font-size:.85rem">Completado</div>
    </td>
  </tr>
</table>

<!-- Novedades -->
<h3>📡 Novedades desde la última revisión</h3>
{changes_html}

{ai_quality_html}
"""

    if attention:
        html += f"""
<h3>⚠️ Requieren atención ({len(attention)})</h3>
<p style="background:#fff3cd;color:#856404;padding:10px 14px;border-radius:4px;border-left:4px solid #ffc107">
  Ítems sin asignar o todavía en estado <b>New</b> — pendientes de planificación o arranque.
</p>
{_TABLE_HEADER}{attention_rows}</table>
"""

    if incomplete_rows:
        html += f"""
<h3>📝 Todos los pendientes del sprint ({len(incomplete)})</h3>
{_TABLE_HEADER}{incomplete_rows}</table>
"""
    else:
        html += '<p style="color:#28a745;font-size:1.1rem"><b>🎉 ¡Todos los ítems del sprint están completados!</b></p>'

    html += f"""
<p style="margin-top:28px">
  <a href="{board_url}"
     style="background:#0078d4;color:white;padding:10px 20px;border-radius:4px;
            text-decoration:none;font-weight:bold;font-size:14px">
    Ver tablero del sprint →
  </a>
</p>

<hr style="margin-top:40px;border:none;border-top:1px solid #dee2e6">
<p style="color:#adb5bd;font-size:11px">
  Agente automático · <a href="https://github.com/algoritmia8/proyectoIA" style="color:#adb5bd">algoritmia8/proyectoIA</a> · GitHub Actions
</p>
</div>
</body></html>
"""

    n_pending  = len(incomplete)
    n_attention = len(attention)
    subject = (
        f"[Sprint Review] {sprint_name} · "
        f"{n_pending} pendiente{'s' if n_pending != 1 else ''}"
        + (f", {n_attention} requieren atención" if n_attention else "")
    )
    return subject, html


# ─── Envío de correo ─────────────────────────────────────────────────────────
def send_email(subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"✉️  Email enviado a {EMAIL_TO}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    now = datetime.now(timezone.utc)
    print(f"🕗  Sprint Review Agent — {now.isoformat()}")

    # DST guard: si ya se ejecutó hoy (por doble cron), salir
    prev_check = load_memory()
    last_run = prev_check.get("last_run", "")
    if last_run and last_run[:10] == now.strftime("%Y-%m-%d"):
        print("ℹ️   Ya se ejecutó hoy (doble cron DST). Saliendo.")
        return

    # 1. Sprint activo
    sprint = get_current_sprint()
    if not sprint:
        print("⚠️  No hay sprint activo. Nada que revisar.")
        return
    sprint_name     = sprint["name"]
    iteration_path  = sprint["path"]
    print(f"📅  Sprint: {sprint_name}  ({iteration_path})")

    # 2. Ítems del sprint
    items = get_sprint_items(iteration_path)
    print(f"📦  {len(items)} ítems encontrados")

    # 3. Leer memoria anterior
    prev = load_memory()
    prev_sprint = prev.get("sprint", "")
    if prev_sprint and prev_sprint != sprint_name:
        print(f"ℹ️   Sprint nuevo detectado ({prev_sprint} → {sprint_name}), archivando y reiniciando memoria")
        archive_sprint(prev)
        prev = {}

    # 4. Detectar cambios
    changes, current_map = detect_changes(prev, items)
    total_changes = sum(len(v) for v in changes.values())
    print(f"🔄  {total_changes} cambios detectados")

    # 5. Evaluación IA
    print("🤖  Evaluando contenido con GitHub Models...")
    ai_eval = evaluate_with_ai(sprint_name, items)

    # 6. Email
    subject, html = build_email(sprint_name, items, changes, now, ai_eval)
    send_email(subject, html)

    # 7. Guardar memoria
    new_data = {
        "sprint":         sprint_name,
        "iteration_path": iteration_path,
        "last_run":       now.isoformat(),
        "items":          current_map,
    }
    save_memory(new_data, sprint_name, items, now)
    print(f"💾  Memoria actualizada: {MEMORY_FILE}")


if __name__ == "__main__":
    main()
