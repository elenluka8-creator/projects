"""Thin httpx wrapper around the Resend email API. Non-fatal by design."""
import logging
import os

import httpx

from app.logging.structured import log_structured

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, text_body: str) -> bool:
    """Send an email via Resend. Returns True on success, False on any failure. Never raises."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        log_structured(
            logger,
            logging.WARNING,
            "email_send_skipped",
            {"reason": "api_key_missing"},
        )
        return False
    from_address = os.environ.get("RESEND_FROM_ADDRESS", "Unfolda <noreply@unfolda.app>")
    try:
        response = httpx.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": from_address, "to": [to], "subject": subject, "text": text_body},
            timeout=10.0,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        log_structured(
            logger,
            logging.WARNING,
            "email_send_failed",
            {"error": type(exc).__name__},
        )
        return False
