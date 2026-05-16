#!/usr/bin/env python3
"""
Teams Notification Agent
========================
Envía notificaciones como Adaptive Cards a Microsoft Teams via Incoming Webhook.
Puede usarse standalone o importarse desde otros scripts.
"""

import os
import json
from urllib.request import Request, urlopen

TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")


def send_teams_card(title, body_text, color="0078d4", facts=None):
    """Send an Adaptive Card to Teams via webhook.
    
    Args:
        title: Card title
        body_text: Main message body
        color: Accent color hex (without #)
        facts: Optional list of {"name": ..., "value": ...} pairs
    """
    if not TEAMS_WEBHOOK_URL:
        print("⚠️  TEAMS_WEBHOOK_URL no configurado. Skipping Teams notification.")
        return False

    # Build adaptive card body
    body_elements = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "color": "Accent"},
        {"type": "TextBlock", "text": body_text, "wrap": True},
    ]

    if facts:
        fact_set = {"type": "FactSet", "facts": [{"title": f["name"], "value": f["value"]} for f in facts]}
        body_elements.append(fact_set)

    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": body_elements,
            }
        }]
    }

    data = json.dumps(card).encode("utf-8")
    req = Request(TEAMS_WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=15) as r:
            pass
        print(f"✅  Teams notification sent: {title}")
        return True
    except Exception as e:
        print(f"❌  Teams notification failed: {e}")
        return False


def main():
    """Standalone: send a test notification or use env vars for message."""
    title = os.environ.get("TEAMS_TITLE", "🔔 Notificación del Sprint")
    message = os.environ.get("TEAMS_MESSAGE", "Notificación de prueba desde GitHub Actions.")
    send_teams_card(title, message)


if __name__ == "__main__":
    main()
