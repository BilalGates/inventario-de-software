"""Envío de correo con Microsoft Graph desde un buzón compartido (Mail.Send.Shared).

La cuenta conectada necesita «Enviar como» sobre el buzón remitente (se concede en Exchange).
"""
from __future__ import annotations

from app.connectors.graph import GraphClient


def send_mail(client: GraphClient, sender: str, to: str, subject: str, body: str, cc: str | None = None) -> None:
    message = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": to}}],
    }
    if cc:
        message["ccRecipients"] = [{"emailAddress": {"address": a.strip()}} for a in cc.split(",") if a.strip()]
    client.post(f"/v1.0/users/{sender}/sendMail", json={"message": message, "saveToSentItems": True})
