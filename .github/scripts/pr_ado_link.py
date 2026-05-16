#!/usr/bin/env python3
"""
PR ↔ ADO Link Agent
====================
Se ejecuta en eventos de PR. Busca referencias a work items (AB#123 o #123)
en el título/body del PR y actualiza el estado en Azure DevOps.
"""

import os
import re
import json
import base64
from urllib.request import Request, urlopen

ADO_ORG     = "https://algoritmia8.visualstudio.com"
ADO_PROJECT = "Algoritmia IA"
ADO_PAT     = os.environ["ADO_PAT"]

# PR info from GitHub event
EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH", "")


def _ado_headers(content_type="application/json"):
    token = base64.b64encode(f":{ADO_PAT}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": content_type}


def _get(url):
    req = Request(url, headers=_ado_headers())
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _patch(url, body):
    data = json.dumps(body).encode()
    headers = _ado_headers("application/json-patch+json")
    req = Request(url, data=data, headers=headers, method="PATCH")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def extract_work_item_ids(text):
    """Extract work item IDs from text (AB#123 or #123 patterns)."""
    if not text:
        return []
    # AB#123 pattern (Azure DevOps standard)
    ids = re.findall(r'AB#(\d+)', text, re.IGNORECASE)
    # Also match standalone #123 that looks like a work item ref (not GitHub issue)
    ids += re.findall(r'(?<!\w)#(\d+)(?!\w)', text)
    return list(set(int(i) for i in ids))


def load_event():
    if not EVENT_PATH or not os.path.isfile(EVENT_PATH):
        return None
    with open(EVENT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def update_work_item_state(item_id, state, pr_url):
    """Update work item state and add PR link as comment."""
    proj = ADO_PROJECT.replace(" ", "%20")
    # Update state
    patch = [
        {"op": "replace", "path": "/fields/System.State", "value": state},
    ]
    try:
        _patch(f"{ADO_ORG}/_apis/wit/workitems/{item_id}?api-version=7.0", patch)
        print(f"  ✔ #{item_id} → {state}")
    except Exception as e:
        print(f"  ❌ #{item_id} state update: {e}")

    # Add comment with PR link
    comment_url = f"{ADO_ORG}/{proj}/_apis/wit/workitems/{item_id}/comments?api-version=7.0-preview.4"
    comment_body = {"text": f'<a href="{pr_url}">GitHub PR</a> vinculado automáticamente.'}
    try:
        data = json.dumps(comment_body).encode()
        headers = _ado_headers()
        req = Request(comment_url, data=data, headers=headers, method="POST")
        with urlopen(req, timeout=30) as r:
            pass
    except Exception:
        pass  # Comment is best-effort


def main():
    print("🔗  PR ↔ ADO Link Agent")
    event = load_event()
    if not event:
        print("No event data found.")
        return

    pr = event.get("pull_request", {})
    action = event.get("action", "")
    pr_title = pr.get("title", "")
    pr_body = pr.get("body", "") or ""
    pr_url = pr.get("html_url", "")
    merged = pr.get("merged", False)

    # Extract work item IDs from title and body
    ids = extract_work_item_ids(pr_title + " " + pr_body)
    if not ids:
        print("No work item references found in PR.")
        return

    print(f"📋  Found work item refs: {ids}")
    print(f"    Action: {action}, Merged: {merged}")

    # Determine target state
    if action == "closed" and merged:
        state = "Resolved"
    elif action == "opened" or action == "reopened":
        state = "Active"
    else:
        print(f"    Action '{action}' — no state change needed.")
        return

    for item_id in ids:
        update_work_item_state(item_id, state, pr_url)

    print("✅  PR ↔ ADO linking completado")


if __name__ == "__main__":
    main()
