# -*- coding: utf-8 -*-
from __future__ import annotations
from erp_the20.models import Proposal
from erp_the20.repositories import proposal_repository as repo
from erp_the20.services.notification_service import send_inapp
from erp_the20.utils.notify import send_email_notification

# Optional helpers
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None

def submit(employee_id: int, type: int, title: str, content: str, manager_id: int | None = None) -> Proposal:
    p = repo.create_proposal(
        employee_id=employee_id, type=type, title=title, content=content, manager_id=manager_id
    )

    # In-app cho manager (nếu có)
    if manager_id:
        send_inapp(
            f"Đề xuất mới từ NV {employee_id}",
            recipients=[manager_id],
            payload={"proposal_id": p.id},
            object_type="proposal",
            object_id=str(p.id),
        )

        # EMAIL cho manager
        email = get_employee_email(manager_id)
        emp_name = get_employee_fullname(employee_id) or f"Emp#{employee_id}"
        if email:
            subject = f"[Proposal] {emp_name} — {title}"
            text = (
                f"Nhân viên: {emp_name} (#{employee_id})\n"
                f"Loại: {p.get_type_display()} \n"
                f"Tiêu đề: {title}\n\n"
                f"Nội dung:\n{content}\n"
            )
            send_email_notification(
                subject=subject,
                text_body=text,
                to_emails=[email],
                object_type="proposal",
                object_id=str(p.id),
                to_user=manager_id,
            )
    return p

def approve(proposal_id: int, note: str = "") -> Proposal:
    p = repo.set_status(proposal_id, Proposal.Status.APPROVED, note=note)
    # In-app cho employee
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
