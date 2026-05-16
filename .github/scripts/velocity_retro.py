#!/usr/bin/env python3
"""
Velocity Tracking & Retrospectiva Auto-generada
================================================
Se ejecuta al cierre de sprint. Calcula velocity y genera retrospectiva con IA.
"""

import os
import json
import base64
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import Request, urlopen

ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
TEAM_GUID   = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"
ADO_PAT     = os.environ["ADO_PAT"]
ARCHIVE_DIR = "sprint-memory/archive"

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


def load_archives():
    """Load all archived sprint data."""
    archives = []
    if not os.path.isdir(ARCHIVE_DIR):
        return archives
    for f in sorted(os.listdir(ARCHIVE_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(ARCHIVE_DIR, f), "r", encoding="utf-8") as fh:
                archives.append(json.load(fh))
    return archives


def calculate_velocity(archives):
    """Returns list of {sprint, completed, total, velocity%}."""
    velocities = []
    for arch in archives:
        items = arch.get("items", {})
        total = len(items)
        completed = sum(1 for v in items.values() if v.get("state") in DONE_STATES)
        velocities.append({
            "sprint": arch.get("sprint", "?"),
            "completed": completed,
            "total": total,
            "pct": round(completed / total * 100) if total else 0,
        })
    return velocities


def generate_retro(sprint_name, velocities, last_archive):
    """Use AI to generate retrospective."""
    if not GITHUB_TOKEN:
        return "*(AI no disponible — GITHUB_TOKEN no configurado)*"

    items = last_archive.get("items", {})
    completed = [f"- {v.get('title','?')} [{v.get('type','?')}]" for v in items.values() if v.get("state") in DONE_STATES]
    incomplete = [f"- {v.get('title','?')} [{v.get('type','?')}] (estado: {v.get('state','?')})" for v in items.values() if v.get("state") not in DONE_STATES]

    vel_text = "\n".join(f"  {v['sprint']}: {v['completed']}/{v['total']} ({v['pct']}%)" for v in velocities[-5:])

    prompt = f"""Genera una retrospectiva breve del sprint "{sprint_name}" para un equipo de desarrollo.

Velocity últimos sprints:
{vel_text}

Completados este sprint ({len(completed)}):
{chr(10).join(completed[:20])}

No completados ({len(incomplete)}):
{chr(10).join(incomplete[:20])}

Formato: secciones "✅ Qué salió bien", "⚠️ Qué mejorar", "💡 Acciones sugeridas". Responde en español, máximo 300 palabras."""

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"model": AI_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800}).encode()
    req = Request(AI_ENDPOINT, data=body, headers=headers)
    try:
        with urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"*(Error AI: {e})*"


def build_html(sprint_name, velocities, retro_text):
    vel_rows = "".join(
        f'<tr><td style="padding:6px 12px">{v["sprint"]}</td>'
        f'<td style="padding:6px 12px;text-align:center">{v["completed"]}/{v["total"]}</td>'
        f'<td style="padding:6px 12px;text-align:center">{v["pct"]}%</td></tr>'
        for v in velocities[-8:]
    )

    retro_html = retro_text.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Segoe UI,sans-serif">
<div style="max-width:680px;margin:20px auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.08)">
<h1 style="color:#0078d4;margin-bottom:4px">📊 Velocity & Retrospectiva</h1>
<h2 style="color:#6c757d;font-weight:normal">{sprint_name}</h2>

<h3>🚀 Velocity Tracking</h3>
<table style="border-collapse:collapse;width:100%">
<tr style="background:#0078d4;color:#fff">
  <th style="padding:8px 12px;text-align:left">Sprint</th>
  <th style="padding:8px 12px;text-align:center">Completados</th>
  <th style="padding:8px 12px;text-align:center">%</th>
</tr>
{vel_rows}
</table>

<h3 style="margin-top:24px">🔍 Retrospectiva Auto-generada</h3>
<div style="background:#f1f3f5;padding:16px;border-radius:8px;line-height:1.6">
{retro_html}
</div>

<hr style="margin-top:40px;border:none;border-top:1px solid #dee2e6">
<p style="color:#adb5bd;font-size:11px">Agente automático · GitHub Actions</p>
</div></body></html>"""


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


def save_velocity(velocities):
    os.makedirs("sprint-memory", exist_ok=True)
    with open("sprint-memory/velocity.json", "w", encoding="utf-8") as f:
        json.dump(velocities, f, indent=2, ensure_ascii=False)


def main():
    print("📊  Velocity & Retro Agent")
    archives = load_archives()
    if not archives:
        print("No hay sprints archivados. Nada que calcular.")
        return

    velocities = calculate_velocity(archives)
    last = archives[-1]
    sprint_name = last.get("sprint", "Sprint ?")

    print(f"📈  {len(velocities)} sprints con datos de velocity")
    retro = generate_retro(sprint_name, velocities, last)

    html = build_html(sprint_name, velocities, retro)
    send_email(f"[Retrospectiva] {sprint_name} · Velocity & Mejoras", html)
    save_velocity(velocities)
    print("✅  Velocity y retrospectiva completados")


if __name__ == "__main__":
    main()
