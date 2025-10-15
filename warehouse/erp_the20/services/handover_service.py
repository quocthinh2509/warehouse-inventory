# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional

from erp_the20.repositories import handover_repository as repo
from erp_the20.models import Handover, HandoverItem

# Dùng broadcast cho In-app + Email + Lark
try:
    from erp_the20.services.notification_service import send_broadcast_inapp_email_lark as notify
except Exception:
    def notify(*args, **kwargs):  # fallback no-op
        return None

# Helper lấy tên/email (nếu có)
try:
    from erp_the20.selectors.user_selector import get_employee_fullname
except Exception:
    def get_employee_fullname(_): return None


# ====================== Helpers ======================

def _name(uid: Optional[int]) -> str:
    if not uid:
        return ""
    return get_employee_fullname(uid) or f"Emp#{uid}"

def _status_txt_item(st: int) -> str:
    return {0: "PENDING", 1: "DONE"}.get(int(st), str(st))

def _status_txt_ho(st: int) -> str:
    return {0: "OPEN", 1: "IN_PROGRESS", 2: "DONE", 3: "CANCELLED"}.get(int(st), str(st))

def _join_ids(*uids: Optional[int]) -> list[int]:
    seen = set(); out = []
    for u in uids:
        if u and u not in seen:
            seen.add(u); out.append(u)
    return out


# ====================== SERVICES ======================

def open_handover(
    employee_id: int,
    manager_id: Optional[int] = None,
    receiver_employee_id: Optional[int] = None,
    due_date=None,
    note: str = "",
) -> Handover:
    h = repo.create_handover(
        employee_id=employee_id,
        manager_id=manager_id,
        receiver_employee_id=receiver_employee_id,
        due_date=due_date,
        note=note,
    )

    title = f"📦 Mở bàn giao #{h.id} cho {_name(employee_id)}"
    subject = f"[Handover] Mở bàn giao #{h.id} cho {_name(employee_id)}"
    body = (
        f"Employee : {_name(employee_id)} (#{employee_id})\n"
        f"Manager  : {_name(manager_id) or '-'}\n"
        f"Receiver : {_name(receiver_employee_id) or '-'}\n"
        f"Due date : {due_date or '-'}\n"
        f"Note     : {note or '-'}"
    )
    recipients = _join_ids(manager_id, receiver_employee_id)

    # Quan trọng: truyền cả recipients và to_user (manager) để chắc chắn có email
    notify(
        title,
        recipients=recipients,
        to_user=manager_id,
        payload={"handover_id": h.id, "body": body},
        object_type="handover",
        object_id=str(h.id),
        email_subject=subject,
        email_text=body,
        lark_text=body,
    )
    return h


def add_item(
    handover_id: int,
    title: str,
    detail: str = "",
    assignee_id: Optional[int] = None
) -> HandoverItem:
    it = repo.add_item(handover_id, title=title, detail=detail, assignee_id=assignee_id)
    ho = repo.get_handover(handover_id)

    n_title = f"🆕 Handover item #{it.id} — {title}"
    n_subject = f"[Handover] Item mới #{it.id} — {title}"
    n_body = (
        f"Handover : #{ho.id}\n"
        f"Employee : {_name(ho.employee_id)} (#{ho.employee_id})\n"
        f"Manager  : {_name(ho.manager_id) or '-'}\n"
        f"Title    : {title}\n"
        f"Detail   : {detail or '-'}\n"
        f"Assignee : {_name(assignee_id) or '-'}"
    )
    recipients = _join_ids(assignee_id, ho.manager_id)

    # Thêm to_user = manager để đảm bảo luôn có ít nhất 1 email target hợp lệ
    notify(
        n_title,
        recipients=recipients,
        to_user=ho.manager_id,
        payload={"handover_id": ho.id, "item_id": it.id, "body": n_body},
        object_type="handover",
        object_id=str(ho.id),
        email_subject=n_subject,
        email_text=n_body,
        lark_text=n_body,
    )
    return it


def set_item_status(item_id: int, status: int) -> HandoverItem:
    it = repo.set_item_status(item_id, status)
    ho = it.handover  # select_related ở repo

    st_item = _status_txt_item(it.status)
    st_ho = _status_txt_ho(ho.status)

    n_title = f"♻️ Item #{it.id} → {st_item}"
    n_subject = f"[Handover] Item #{it.id} trạng thái: {st_item}"
    n_body = (
        f"Handover : #{ho.id} (trạng thái: {st_ho})\n"
        f"Title    : {it.title}\n"
        f"Item     : #{it.id}\n"
        f"Status   : {st_item}"
    )
    recipients = _join_ids(ho.manager_id, it.assignee_id)

    # CHÌA KHÓA: thêm to_user=manager_id để email chắc chắn bắn ra
    notify(
        n_title,
        recipients=recipients,
        to_user=ho.manager_id,
        payload={"handover_id": ho.id, "item_id": it.id, "body": n_body},
        object_type="handover",
        object_id=str(ho.id),
        email_subject=n_subject,
        email_text=n_body,
        lark_text=n_body,
    )
    return it
