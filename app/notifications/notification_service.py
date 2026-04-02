"""Job completion notification service. Non-fatal by design — never re-raises."""
from __future__ import annotations

import logging
import os
import pathlib
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import jinja2

from app.logging.structured import log_structured
from app.notifications.email_client import send_email

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = {"en", "ru", "sr", "de", "fr", "es", "it", "pt", "zh", "ja", "ko", "tr", "nl", "pl"}

TEMPLATES_DIR = pathlib.Path(__file__).parents[2] / "templates" / "email" / "job_completed"


def send_job_completion_notification(
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    user_email: str,
    display_name: str,
    book_title: str,
    ui_locale: Optional[str],
    base_url: str,
) -> None:
    """Send a job completion email. Never raises — any failure is logged and swallowed."""
    start = time.monotonic()
    resolved_locale = "en"
    locale_source = "fallback"
    success = False
    failure_reason: Optional[str] = None

    try:
        if not user_email or "@" not in user_email:
            failure_reason = "invalid_email"
            return

        if ui_locale in SUPPORTED_LOCALES:
            resolved_locale = ui_locale
            locale_source = "stored"

        jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=jinja2.select_autoescape([]),
        )
        try:
            template = jinja_env.get_template(f"{resolved_locale}.txt.j2")
        except jinja2.TemplateNotFound:
            failure_reason = "template_error"
            raise

        jobs_url = f"{base_url.rstrip('/')}/jobs"

        rendered = template.render(
            display_name=display_name,
            book_title=book_title,
            jobs_url=jobs_url,
        )

        lines = rendered.splitlines()
        subject_line = lines[0] if lines else ""
        subject = subject_line.removeprefix("Subject:").strip()
        body = "\n".join(lines[1:]).lstrip("\n")

        sent = send_email(to=user_email, subject=subject, text_body=body)
        success = sent
        if not sent:
            failure_reason = "api_key_missing" if not os.environ.get("RESEND_API_KEY", "") else "http_error"

    except Exception:
        if failure_reason is None:
            failure_reason = "unknown"
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        log_structured(
            logger,
            logging.INFO if success else logging.WARNING,
            "notification_dispatched",
            {
                "job_id": str(job_id),
                "user_id": str(user_id),
                "ui_locale": resolved_locale,
                "locale_source": locale_source,
                "success": success,
                "failure_reason": failure_reason,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
