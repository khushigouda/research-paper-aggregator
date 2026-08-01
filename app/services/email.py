"""
Backward-compatibility alias for app.services.email_service.
"""
from app.services.email_service import (
    send_email,
    markdown_to_html,
    digest_to_html,
    send_email_to_self,
)

__all__ = [
    "send_email",
    "markdown_to_html",
    "digest_to_html",
    "send_email_to_self",
]
