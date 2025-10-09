# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import logging
from typing import Iterable, Optional, Tuple, Dict, Any, List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from erp_the20.models import Notification

logger = logging.getLogger(__name__)

# -----------------------------
# Helpers
# -----------------------------
def _mask_webhook(url: Optional[str]) -> str:
    """Mask webhook để tránh lộ full URL trong payload log."""
    if not url:
        return ""
    if len(url) <= 14:
        return "***"
    return f"{url[:10]}...{url[-4:]}"

def _mk_subject(subject: str) -> str:
    prefix = getattr(settings, "EMAIL_SUBJECT_PREFIX", "")
    return f"{prefix}{subject}" if prefix else subject

def _create_log(
    *,
    channel: int,
    title: str,
    payload: Optional[Dict[str, Any]] = None,
    object_type: str = "",
    object_id: str = "",
    to_user: Optional[int] = None,
    to_email: str = "",
    to_lark_user_id: str = "",
    delivered: bool,
    provider_message_id: str = "",
    provider_status_code: str = "",
    provider_response: Optional[Dict[str, Any]] = None,
    last_error: str = "",
) -> Notification:
    return Notification.objects.create(
        channel=channel,
        title=title,
        payload=payload or None,
        object_type=object_type or "",
        object_id=str(object_id or ""),
        to_user=to_user,
        to_email=to_email or "",
        to_lark_user_id=to_lark_user_id or "",
        delivered=delivered,
        delivered_at=timezone.now() if delivered else None,
        attempt_count=1,
        provider_message_id=provider_message_id or "",
        provider_status_code=str(provider_status_code or ""),
        provider_response=provider_response or None,
        last_error=last_error or "",
    )


# -----------------------------
# Email
# -----------------------------
def send_email_notification(
    *,
    subject: str,
    text_body: str,
    to_emails: Iterable[str],
    html_body: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    # logging context
    object_type: str = "",
    object_id: str = "",
    to_user: Optional[int] = None,
) -> bool:
    """
    Gửi email theo settings.* và GHI LOG vào Notification (channel=EMAIL).
    Trả về True/False.
    """
    tos = [e for e in (to_emails or []) if e]
    if not tos:
        logger.warning("[notify.email] No recipients; skip.")
        _create_log(
            channel=Notification.Channel.EMAIL,
            title=_mk_subject(subject),
            payload={
            "kind": "email",
            "text": text_body,
            "has_html": bool(html_body),
            "cc": list(cc or []),
            "bcc": list(bcc or []),
            },
            object_type=object_type,
            object_id=str(object_id or ""),
            to_user=to_user,
            to_email="",
            delivered=False,
            last_error="No recipients",
        )
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None)
    if not from_email:
        logger.warning("[notify.email] DEFAULT_FROM_EMAIL / SERVER_EMAIL not set; skip.")
        _create_log(
            channel=Notification.Channel.EMAIL,
            title=_mk_subject(subject),
            payload={"html": bool(html_body), "tos": tos},
            object_type=object_type,
            object_id=str(object_id or ""),
            to_user=to_user,
            to_email=",".join(tos),
            delivered=False,
            last_error="From email not configured",
        )
        return False

    ok = False
    error_msg = ""
    try:
        msg = EmailMultiAlternatives(
            subject=_mk_subject(subject),
            body=text_body,
            from_email=from_email,
            to=tos,
            cc=list(cc or []),
            bcc=list(bcc or []),
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        ok = True
    except Exception as ex:
        error_msg = str(ex)
        logger.warning("[notify.email] send failed: %s", ex)

    _create_log(
        channel=Notification.Channel.EMAIL,
        title=_mk_subject(subject),
        payload={
        "kind": "email",
        "text": text_body,
        "has_html": bool(html_body),
        "tos": tos,
        "cc": list(cc or []),
        "bcc": list(bcc or []),
        },
        object_type=object_type,
        object_id=str(object_id or ""),
        to_user=to_user,
        to_email=",".join(tos),
        delivered=ok,
        provider_status_code="OK" if ok else "ERROR",
        provider_response=None,
        last_error="" if ok else error_msg,
    )
    return ok


# -----------------------------
# Lark Webhook
# -----------------------------
def _post_lark(url: str, payload: Dict[str, Any], timeout: Optional[float] = None) -> Tuple[bool, str, str, Optional[Dict[str, Any]]]:
    """
    POST JSON tới Lark webhook.
    Trả về (ok, status_code_str, resp_text, resp_json or None)
    """
    timeout = timeout or getattr(settings, "LARK_TIMEOUT", 8)
    try:
        import requests  # type: ignore
        r = requests.post(url, json=payload, timeout=timeout)
        text = r.text or ""
        try:
            rjson = r.json()
        except Exception:
            rjson = None
        ok = r.status_code < 300
        return ok, str(r.status_code), text[:2000], rjson
    except Exception as ex:
        return False, "EXC", str(ex), None


def send_lark_notification(
    *,
    text: str,
    at_user_ids: Optional[Iterable[str]] = None,
    webhook_url: Optional[str] = None,
    timeout: Optional[float] = None,
    # logging context
    object_type: str = "",
    object_id: str = "",
    to_user: Optional[int] = None,
    to_lark_user_id: Optional[str] = None,
) -> bool:
    """
    Gửi text vào Lark/Feishu qua webhook (v2) và GHI LOG vào Notification (channel=LARK).
    Có thể @mention: truyền open_id vào at_user_ids.
    """
    url = webhook_url or getattr(settings, "LARK_LEAVE_WEBHOOK_URL", None)
    if not url:
        logger.warning("[notify.lark] LARK_LEAVE_WEBHOOK_URL not set; skip.")
        _create_log(
            channel=Notification.Channel.LARK,
            title="Lark message",
            payload={
                "kind": "lark",
                "text": text,
                "webhook_mask": _mask_webhook(None),
                "at_user_ids": list(at_user_ids or []),
            },
            object_type=object_type,
            object_id=str(object_id or ""),
            to_user=to_user,
            to_lark_user_id=to_lark_user_id or "",
            delivered=False,
            last_error="Webhook URL not configured",
        )
        return False

    at_markup = ""
    if at_user_ids:
        at_markup = " " + " ".join(f'<at user_id="{uid}"></at>' for uid in at_user_ids if uid)

    payload = {
        "msg_type": "text",
        "content": { "text": f"{text}{at_markup}".strip() },
    }

    ok, code, resp_text, resp_json = _post_lark(url, payload, timeout=timeout)

    _create_log(
        channel=Notification.Channel.LARK,
        title="Lark message",
        payload={
        "kind": "lark",
        "text": text,
        "webhook_mask": _mask_webhook(None),
        "at_user_ids": list(at_user_ids or []),
        },
        
        object_type=object_type,
        object_id=str(object_id or ""),
        to_user=to_user,
        to_lark_user_id=to_lark_user_id or "",
        delivered=ok,
        provider_status_code=code,
        provider_response=resp_json or {"text": (resp_text[:500] if resp_text else "")},
        last_error="" if ok else (resp_text[:500] if resp_text else "Unknown error"),
    )
    return ok
