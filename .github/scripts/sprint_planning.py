#!/usr/bin/env python3
"""
Sprint Planning Assistant
=========================
Workflow dispatch manual. Usa velocity histórica y backlog para sugerir
qué ítems incluir en el próximo sprint basándose en capacidad del equipo.
"""

import os
import json
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import Request, urlopen

ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
TEAM_GUID   = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"
ADO_PAT     = os.environ["ADO_PAT"]

SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.office365.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EMAIL_TO      = os.environ.get("EMAIL_TO", "ifont@algoritmia8.com")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
AI_ENDPOINT  = "https://models.inference.ai.github.com/chat/completions"
AI_MODEL     = "gpt-4o-mini"

DONE_STATES = {"Done", "Closed", "Resolved"}


def _ado_headers():
    token = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _get(url):
    req = Request(url, headers=_ado_headers())
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _post(url, body):
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_ado_headers(), method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_backlog_items():
    """Get items not in any active sprint (backlog)."""
    proj = ADO_PROJECT.replace(" ", "%20")
    wiql = {"query": (
        f"SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.TeamProject] = '{ADO_PROJECT}' "
        f"AND [System.State] NOT IN ('Done','Closed','Resolved','Removed') "
        f"AND [System.IterationPath] = '{ADO_PROJECT}' "
        f"ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.CreatedDate] ASC"
    )}
    result = _post(f"{ADO_ORG}/{proj}/_apis/wit/wiql?api-version=7.0", wiql)
    ids = [w["id"] for w in result.get("workItems", [])[:50]]
    if not ids:
        return []
    fields = "System.Id,System.Title,System.State,System.WorkItemType,Microsoft.VSTS.Common.Priority,Microsoft.VSTS.Scheduling.Effort"
    url = f"{ADO_ORG}/_apis/wit/workitems?ids={','.join(map(str, ids))}&fields={fields}&api-version=7.0"
    return _get(url).get("value", [])


def load_velocity():
    try:
        with open("sprint-memory/velocity.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def ask_ai(backlog_items, velocity):
    if not GITHUB_TOKEN:
        return "*(AI no disponible)*"

    avg_vel = 0
    if velocity:
        avg_vel = round(sum(v["completed"] for v in velocity[-3:]) / min(3, len(velocity)))

    items_text = "\n".join(
        f"- #{it['id']} [{it['fields'].get('System.WorkItemType','')}] P{it['fields'].get('Microsoft.VSTS.Common.Priority',3)}: {it['fields'].get('System.Title','')}"
        for it in backlog_items[:30]
    )

    prompt = f"""Eres un asistente de planificación de sprints. El equipo tiene una velocity promedio de {avg_vel} ítems completados por sprint.

Backlog disponible (ordenado por prioridad):
{items_text}

Sugiere qué ítems incluir en el próximo sprint, considerando:
1. Velocity del equipo
2. Prioridad de los ítems
3. Mezcla equilibrada de tipos de trabajo

Responde en español. Da una lista concreta de IDs recomendados y una breve justificación."""

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Content-Type": "application/json"}
    body = json.dumps({"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 600}).encode()
    req = Request(AI_ENDPOINT, data=body, headers=headers)
    try:
        with urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"*(Error: {e})*"


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"✉️  Email enviado a {EMAIL_TO}")


def main():
    print("🗓️  Sprint Planning Assistant")
    backlog = get_backlog_items()
    if not backlog:
        print("No hay ítems en el backlog.")
        return

    velocity = load_velocity()
    print(f"📋  {len(backlog)} ítems en backlog, {len(velocity)} sprints de velocity")

    suggestion = ask_ai(backlog, velocity)
    suggestion_html = suggestion.replace("\n", "<br>")

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Segoe UI,sans-serif">
<div style="max-width:680px;margin:20px auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.08)">
<h1 style="color:#0078d4">🗓️ Asistente de Planificación</h1>
<p style="color:#6c757d">Sugerencia basada en velocity y prioridades del backlog</p>

<div style="background:#f1f3f5;padding:16px;border-radius:8px;line-height:1.6">
{suggestion_html}
</div>

<hr style="margin-top:40px;border:none;border-top:1px solid #dee2e6">
<p style="color:#adb5bd;font-size:11px">Sprint Planning Agent · GitHub Actions</p>
</div></body></html>"""

    send_email("[Sprint Planning] Sugerencia para próximo sprint", html)
    print("✅  Sugerencia enviada")


if __name__ == "__main__":
    main()
