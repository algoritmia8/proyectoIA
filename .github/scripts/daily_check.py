#!/usr/bin/env python3
"""
Daily Check Agent — Detección temprana de problemas
====================================================
Se ejecuta de lunes a viernes. Detecta:
  - Ítems sin asignar
  - Ítems en "New" más de 3 días
  - Ítems sin movimiento más de 5 días hábiles
Envía email solo si hay alertas.
"""

import os
import json
import base64
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from urllib.request import Request, urlopen

# ─── Config ──────────────────────────────────────────────────────────────────
ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
TEAM_GUID   = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"

ADO_PAT       = os.environ["ADO_PAT"]
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.office365.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
EMAIL_TO      = os.environ.get("EMAIL_TO", "ifont@algoritmia8.com")

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


def get_current_sprint():
    proj = ADO_PROJECT.replace(" ", "%20")
    url = f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations?$timeframe=current&api-version=7.0"
    try:
        data = _get(url)
        iters = data.get("value", [])
        if iters:
            return iters[0]
    except Exception:
        pass
    return None


def get_sprint_items(iteration_path):
    proj = ADO_PROJECT.replace(" ", "%20")
    escaped = iteration_path.replace("'", "''")
    wiql = {"query": (
        f"SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.TeamProject] = '{ADO_PROJECT}' "
        f"AND [System.IterationPath] = '{escaped}' "
        f"ORDER BY [System.ChangedDate] ASC"
    )}
    result = _post(f"{ADO_ORG}/{proj}/_apis/wit/wiql?api-version=7.0", wiql)
    ids = [w["id"] for w in result.get("workItems", [])]
    if not ids:
        return []
    fields = "System.Id,System.Title,System.State,System.AssignedTo,System.WorkItemType,System.ChangedDate"
    items = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        url = f"{ADO_ORG}/_apis/wit/workitems?ids={','.join(map(str, batch))}&fields={fields}&api-version=7.0"
        items.extend(_get(url).get("value", []))
    return items


def main():
    now = datetime.now(timezone.utc)
    print(f"🔍  Daily Check — {now.isoformat()}")

    sprint = get_current_sprint()
    if not sprint:
        print("No hay sprint activo.")
        return

    items = get_sprint_items(sprint["path"])
    pending = [i for i in items if i["fields"]["System.State"] not in DONE_STATES]

    alerts = []
    for item in pending:
        f = item["fields"]
        title = f.get("System.Title", "")[:70]
        iid = item["id"]
        state = f.get("System.State", "")
        assigned = f.get("System.AssignedTo")
        name = (assigned.get("displayName", "") if isinstance(assigned, dict) else "") if assigned else ""
        changed = f.get("System.ChangedDate", "")
        days_stale = 0
        if changed:
            changed_dt = datetime.fromisoformat(changed.replace("Z", "+00:00"))
            days_stale = (now - changed_dt).days

        reasons = []
        if not name:
            reasons.append("sin asignar")
        if state == "New" and days_stale >= 3:
            reasons.append(f"en New hace {days_stale} días")
        elif state != "New" and days_stale >= 5:
            reasons.append(f"sin movimiento hace {days_stale} días")

        if reasons:
            alerts.append(f"<li><b>#{iid}</b> {title} — {', '.join(reasons)}</li>")

    if not alerts:
        print("✅  Sin alertas.")
        return

    print(f"⚠️  {len(alerts)} alertas detectadas")
    html = (
        f"<h2>⚠️ Alerta diaria — {sprint['name']}</h2>"
        f"<p>{len(alerts)} ítem(s) requieren atención:</p>"
        f"<ul>{''.join(alerts)}</ul>"
        f'<p><a href="https://algoritmia8.visualstudio.com/Algoritmia%20IA/_sprints/taskboard/'
        f'Grupo%20IA/{sprint["name"].replace(chr(92), "/")}">Ver tablero</a></p>'
    )

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"⚠️ [Daily Check] {len(alerts)} alertas — {sprint['name']}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"✉️  Alerta enviada a {EMAIL_TO}")


if __name__ == "__main__":
    main()
