#!/usr/bin/env python3
"""
Sprint Close Agent — Cierre automático de sprint
==================================================
Detecta si el sprint actual ha terminado (fecha fin <= hoy).
Mueve ítems incompletos al siguiente sprint y envía resumen.
"""

import os
import json
import base64
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from urllib.request import Request, urlopen
from urllib.error import HTTPError

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
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json-patch+json"}


def _get(url):
    headers = dict(_ado_headers())
    headers["Content-Type"] = "application/json"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _post(url, body):
    headers = dict(_ado_headers())
    headers["Content-Type"] = "application/json"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=headers, method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _patch(url, body):
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_ado_headers(), method="PATCH")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_iterations():
    proj = ADO_PROJECT.replace(" ", "%20")
    url = f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations?api-version=7.0"
    return _get(url).get("value", [])


def get_sprint_items(iteration_path):
    proj = ADO_PROJECT.replace(" ", "%20")
    escaped = iteration_path.replace("'", "''")
    wiql = {"query": (
        f"SELECT [System.Id] FROM WorkItems "
        f"WHERE [System.TeamProject] = '{ADO_PROJECT}' "
        f"AND [System.IterationPath] = '{escaped}'"
    )}
    result = _post(f"{ADO_ORG}/{proj}/_apis/wit/wiql?api-version=7.0", wiql)
    ids = [w["id"] for w in result.get("workItems", [])]
    if not ids:
        return []
    fields = "System.Id,System.Title,System.State,System.WorkItemType"
    items = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        url = f"{ADO_ORG}/_apis/wit/workitems?ids={','.join(map(str, batch))}&fields={fields}&api-version=7.0"
        items.extend(_get(url).get("value", []))
    return items


def move_item_to_iteration(item_id, iteration_path):
    url = f"{ADO_ORG}/_apis/wit/workitems/{item_id}?api-version=7.0"
    patch = [{"op": "replace", "path": "/fields/System.IterationPath", "value": iteration_path}]
    _patch(url, patch)


def main():
    now = datetime.now(timezone.utc)
    print(f"🔒  Sprint Close Agent — {now.isoformat()}")

    iterations = get_iterations()
    if not iterations:
        print("No hay iteraciones configuradas.")
        return

    # Find past sprint (ended today or before, most recent first)
    past_sprints = []
    future_sprints = []
    for it in iterations:
        attrs = it.get("attributes", {})
        end_date = attrs.get("finishDate", "")
        start_date = attrs.get("startDate", "")
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt.date() < now.date():
                past_sprints.append((end_dt, it))
            elif start_date:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if start_dt.date() > now.date():
                    future_sprints.append((start_dt, it))

    if not past_sprints:
        print("No hay sprints finalizados.")
        return

    # Most recently ended sprint
    past_sprints.sort(key=lambda x: x[0], reverse=True)
    ended_sprint = past_sprints[0][1]

    # Next sprint (future, earliest start)
    future_sprints.sort(key=lambda x: x[0])
    if not future_sprints:
        # Try current
        for it in iterations:
            tf = it.get("attributes", {}).get("timeFrame")
            if tf == "current":
                future_sprints = [(None, it)]
                break

    if not future_sprints:
        print("No hay sprint destino para mover ítems.")
        return

    next_sprint = future_sprints[0][1]
    ended_path = ended_sprint["path"]
    next_path = next_sprint["path"]

    print(f"Sprint terminado: {ended_sprint['name']}")
    print(f"Sprint destino:   {next_sprint['name']}")

    items = get_sprint_items(ended_path)
    incomplete = [i for i in items if i["fields"]["System.State"] not in DONE_STATES]

    if not incomplete:
        print("✅  Todos los ítems completados. Nada que mover.")
        return

    moved = []
    for item in incomplete:
        try:
            move_item_to_iteration(item["id"], next_path)
            moved.append(item)
        except Exception as e:
            print(f"  ❌ Error moviendo #{item['id']}: {e}")

    print(f"📦  {len(moved)} ítems movidos a {next_sprint['name']}")

    # Send summary email
    items_html = "".join(
        f"<li><b>#{i['id']}</b> {i['fields'].get('System.Title', '')[:60]} "
        f"({i['fields'].get('System.State', '')})</li>"
        for i in moved
    )
    html = (
        f"<h2>🔒 Sprint cerrado: {ended_sprint['name']}</h2>"
        f"<p><b>{len(moved)}</b> ítem(s) incompletos movidos a <b>{next_sprint['name']}</b>:</p>"
        f"<ul>{items_html}</ul>"
    )
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = f"🔒 [Sprint Close] {len(moved)} ítems movidos → {next_sprint['name']}"
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"✉️  Resumen enviado a {EMAIL_TO}")


if __name__ == "__main__":
    main()
