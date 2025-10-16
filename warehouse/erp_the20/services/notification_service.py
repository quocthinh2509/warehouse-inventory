# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Iterable, Optional, Dict, Any, List
import logging

from django.conf import settings

from erp_the20.models import Notification
from erp_the20.repositories import notification_repository as repo
from erp_the20.utils.notify import send_email_notification, send_lark_notification

# Optional user info resolvers
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None

log = logging.getLogger(__name__)


def _coalesce(*vals):
    for v in vals:
        if v:
            return v
    return None


def _emails_from_user_ids(user_ids: Iterable[int]) -> List[str]:
    out: List[str] = []
    for uid in user_ids or []:
        mail = get_employee_email(uid)
        if mail:
            out.append(mail)
    return list(dict.fromkeys(out))


def _lark_open_ids_from_user_ids(user_ids: Iterable[int]) -> List[str]:
    mapping = getattr(settings, "LARK_AT_EMPLOYEE_IDS", {}) or {}
    out: List[str] = []
    for uid in user_ids or []:
        key = str(uid)
        if key in mapping and mapping[key]:
            out.append(mapping[key])
    return list(dict.fromkeys(out))


def send_broadcast_inapp_email_lark(
    *,
    title: str,
    recipients: Optional[Iterable[int]] = None,
    to_user: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    object_type: str = "",
    object_id: str = "",
    # toggles
    send_email: bool = False,
    send_lark: bool = False,
    # optional contents
    email_subject: Optional[str] = None,
    email_text: Optional[str] = None,
    email_html: Optional[str] = None,
    lark_text: Optional[str] = None,
) -> Notification:
    """
    Luôn tạo IN-APP notification.
    - Nếu send_email=True và có email hợp lệ -> gửi email.
    - Nếu send_lark=True và có open_id mapping -> gửi Lark.
    """
    all_user_ids: List[int] = []
    if recipients:
        all_user_ids.extend(list(recipients))
    if to_user:
        all_user_ids.append(int(to_user))
    all_user_ids = list(dict.fromkeys(all_user_ids))

    # 1) IN-APP
    inapp_obj = repo.create_notification(
        title=title,
        recipients=recipients,
        to_user=to_user,
        payload=payload,
        object_type=object_type,
        object_id=object_id,
        channel=Notification.Channel.INAPP,
        delivered=True,
    )

    # 2) Email (tuỳ chọn)
    if send_email:
        tos = _emails_from_user_ids(all_user_ids)
        subj = _coalesce(email_subject, title)
        text = _coalesce(email_text, (payload or {}).get("body"), title)
        html = email_html
        if tos and subj and text:
            try:
                send_email_notification(
                    subject=subj,
                    text_body=text,
                    to_emails=tos,
                    html_body=html,
                    object_type=object_type or "",
                    object_id=str(object_id or ""),
                    to_user=to_user,
                )
            except Exception as ex:
                log.exception("Send email failed: %s", ex)

    # 3) Lark (tuỳ chọn)
    if send_lark:
        at_ids = _lark_open_ids_from_user_ids(all_user_ids)
        txt = _coalesce(lark_text, email_text, (payload or {}).get("body"), title)
        if txt:
            try:
                send_lark_notification(
                    text=txt,
                    at_user_ids=at_ids or None,
                )
            except Exception as ex:
                log.exception("Send lark failed: %s", ex)

    return inapp_obj


def send_inapp(
    *,
    title: str,
    recipients: Optional[Iterable[int]] = None,
    to_user: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    object_type: str = "",
    object_id: str = "",
) -> Notification:
    return repo.create_notification(
        title=title,
        recipients=recipients,
        to_user=to_user,
        payload=payload,
        object_type=object_type,
        object_id=object_id,
        channel=Notification.Channel.INAPP,
        delivered=True,
    )
