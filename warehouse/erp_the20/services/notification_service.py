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

logger = logging.getLogger(__name__)

def _emails_from_user_ids(user_ids: Iterable[int]) -> List[str]:
    emails: List[str] = []
    for uid in user_ids or []:
        e = get_employee_email(uid)
        if e:
            emails.append(e)
    # unique & keep order
    seen = set()
    res = []
    for e in emails:
        if e not in seen:
            seen.add(e); res.append(e)
    return res

def _lark_open_ids_from_user_ids(user_ids: Iterable[int]) -> List[str]:
    # LARK_AT_EMPLOYEE_IDS: { employee_id -> open_id }
    mapping = getattr(settings, "LARK_AT_EMPLOYEE_IDS", {}) or {}
    result = []
    for uid in user_ids or []:
        try:
            oid = mapping.get(int(uid))
            if oid:
                result.append(oid)
        except Exception:
            continue
    # unique
    seen = set(); out = []
    for oid in result:
        if oid not in seen:
            seen.add(oid); out.append(oid)
    return out

def send_broadcast_inapp_email_lark(
    title: str,
    *,
    recipients: Optional[Iterable[int]] = None,
    to_user: Optional[int] = None,
    payload: Optional[Dict[str, Any]] = None,
    object_type: str = "",
    object_id: str = "",
    # email options
    email_subject: Optional[str] = None,
    email_text: Optional[str] = None,
    email_html: Optional[str] = None,
    # lark options
    lark_text: Optional[str] = None,
) -> Notification:
    """
    Gửi 3 kênh:
    - In-app: luôn ghi log Notification (repo.create_notification)
    - Email: nếu tìm được email của recipients/to_user
    - Lark : nếu có webhook + map open_id trong settings
    """
    recips = list(recipients or [])
    # in-app record (lưu là delivered=True để hiển thị ngay)
    inapp = repo.create_notification(
        title=title,
        recipients=recips if recips else None,
        to_user=to_user,
        payload=payload or {},
        object_type=object_type,
        object_id=object_id,
        channel=Notification.Channel.INAPP,
        delivered=True,
    )

    # EMAIL
    all_user_ids = recips[:]  # copy
    if to_user and to_user not in all_user_ids:
        all_user_ids.append(to_user)
    tos = _emails_from_user_ids(all_user_ids)
    if tos:
        subj = email_subject or title
        body = email_text or (payload.get("body") if payload else title)
        send_email_notification(
            subject=subj,
            text_body=str(body or title),
            html_body=email_html,
            to_emails=tos,
            object_type=object_type,
            object_id=str(object_id or ""),
        )

    # LARK
    at_ids = _lark_open_ids_from_user_ids(all_user_ids)
    txt = lark_text or email_text or (payload.get("body") if payload else title)
    if txt:
        send_lark_notification(
            text=str(txt),
            at_user_ids=at_ids or None,
            object_type=object_type,
            object_id=str(object_id or ""),
        )

    return inapp

# Giữ API cũ (compat) – gửi In-app only
def send_inapp(
    title: str,
    *,
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
