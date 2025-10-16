# -*- coding: utf-8 -*-
from __future__ import annotations
from erp_the20.models import Proposal
from erp_the20.repositories import proposal_repository as repo
from erp_the20.services.notification_service import (
    send_broadcast_inapp_email_lark as notify,
    send_inapp,
)

# Optional helpers
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None

def submit(
    employee_id: int,
    type: int,
    title: str,
    content: str,
    manager_id: int | None = None,
    *,
    send_email: bool = True,
    send_lark: bool = False
) -> Proposal:
    """Nhân viên gửi đề xuất, gửi notify cho quản lý."""
    p = repo.create_proposal(
        employee_id=employee_id, type=type, title=title, content=content, manager_id=manager_id
    )

    if manager_id:
        emp_name = get_employee_fullname(employee_id) or f"Emp#{employee_id}"
        subject = f"[Proposal] {emp_name} — {title}"
        text = (
            f"Nhân viên: {emp_name} (#{employee_id})\n"
            f"Loại: {p.get_type_display()} \n"
            f"Tiêu đề: {title}\n\n"
            f"Nội dung:\n{content}\n"
        )

        notify(
            title=f"Đề xuất mới từ NV {employee_id}",
            recipients=[manager_id],
            to_user=manager_id,
            payload={"proposal_id": p.id},
            object_type="proposal",
            object_id=str(p.id),
            send_email=send_email,
            send_lark=send_lark,
            email_subject=subject,
            email_text=text,
            lark_text=text,
        )
    return p

def approve(proposal_id: int, note: str = "") -> Proposal:
    p = repo.set_status(proposal_id, Proposal.Status.APPROVED, note=note)
    send_inapp(
        f"Đề xuất #{p.id} đã được duyệt",
        recipients=[p.employee_id],
        payload={"proposal_id": p.id},
        object_type="proposal",
        object_id=str(p.id),
    )
    return p

def reject(proposal_id: int, note: str = "") -> Proposal:
    p = repo.set_status(proposal_id, Proposal.Status.REJECTED, note=note)
    send_inapp(
        f"Đề xuất #{p.id} bị từ chối",
        recipients=[p.employee_id],
        payload={"proposal_id": p.id},
        object_type="proposal",
        object_id=str(p.id),
    )
    return p

def set_decision_note(proposal_id: int, note: str) -> Proposal:
    return repo.update_decision_note(proposal_id, note)
