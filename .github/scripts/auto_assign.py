#!/usr/bin/env python3
"""
Auto-Assign Agent — Asigna ítems sin dueño
============================================
Busca ítems del sprint actual sin asignar y los asigna al miembro
con menos carga. Se ejecuta con el daily check.
"""

import os
import json
import base64
from urllib.request import Request, urlopen

ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
TEAM_GUID   = "98ffadb1-c96a-4fdd-b2cb-c10d310d968f"
ADO_PAT     = os.environ["ADO_PAT"]

DONE_STATES = {"Done", "Closed", "Resolved"}


def _ado_headers(content_type="application/json"):
    token = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": content_type}


def _get(url):
    req = Request(url, headers=_ado_headers())
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _post(url, body):
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_ado_headers(), method="POST")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _patch(url, body):
    data = json.dumps(body).encode()
    headers = _ado_headers("application/json-patch+json")
    req = Request(url, data=data, headers=headers, method="PATCH")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get_current_sprint():
    proj = ADO_PROJECT.replace(" ", "%20")
    url = f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations?$timeframe=current&api-version=7.0"
    data = _get(url)
    iters = data.get("value", [])
    return iters[0] if iters else None


def get_team_members():
    proj = ADO_PROJECT.replace(" ", "%20")
    url = f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations?$timeframe=current&api-version=7.0"
    data = _get(url)
    if not data.get("value"):
        return []
    iter_id = data["value"][0]["id"]
    cap_url = f"{ADO_ORG}/{proj}/{TEAM_GUID}/_apis/work/teamsettings/iterations/{iter_id}/capacities?api-version=7.0"
    caps = _get(cap_url)
    members = []
    for m in caps.get("value", []):
        tm = m.get("teamMember", {})
        if tm.get("uniqueName"):
            members.append(tm["uniqueName"])
    return members


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
    fields = "System.Id,System.Title,System.State,System.AssignedTo,System.WorkItemType"
    items = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        url = f"{ADO_ORG}/_apis/wit/workitems?ids={','.join(map(str, batch))}&fields={fields}&api-version=7.0"
        items.extend(_get(url).get("value", []))
    return items


def main():
    print("👤  Auto-Assign Agent")
    sprint = get_current_sprint()
    if not sprint:
        print("No hay sprint activo.")
        return

    items = get_sprint_items(sprint["path"])
    members = get_team_members()
    if not members:
        print("No hay miembros con capacidad configurada.")
        return

    # Count current assignments
    load = {m: 0 for m in members}
    unassigned = []
    for item in items:
        f = item["fields"]
        if f["System.State"] in DONE_STATES:
            continue
        assigned = f.get("System.AssignedTo")
        if assigned:
            email = assigned.get("uniqueName", "") if isinstance(assigned, dict) else ""
            if email in load:
                load[email] += 1
        else:
            unassigned.append(item)

    if not unassigned:
        print("✅  Todos los ítems tienen asignado.")
        return

    print(f"📋  {len(unassigned)} ítems sin asignar")
    for item in unassigned:
        # Assign to member with least load
        target = min(load, key=load.get)
        patch = [{"op": "replace", "path": "/fields/System.AssignedTo", "value": target}]
        try:
            _patch(f"{ADO_ORG}/_apis/wit/workitems/{item['id']}?api-version=7.0", patch)
            load[target] += 1
            print(f"  ✔ #{item['id']} → {target}")
        except Exception as e:
            print(f"  ❌ #{item['id']}: {e}")

    print(f"✅  Auto-asignación completada")


if __name__ == "__main__":
    main()
