# -*- coding: utf-8 -*-
"""
Service cho LeaveRequest:
- Giữ đầy đủ "phần quan trọng" từ implementation cũ: notify email/Lark, thao tác với Attendance khi approve/cancel
- Tất cả nghiệp vụ (quyền, điều kiện status, chọn loại nghỉ được link attendance) ở đây
- Truy cập DB qua repository (thuần DB)
"""
from __future__ import annotations
from typing import Optional, Any, List, Dict, Iterable
import logging
from django.utils import timezone

from erp_the20.models import LeaveRequest, Attendance
from erp_the20.repositories import leave_repository as repo
from erp_the20.utils.notify import send_email_notification, send_lark_notification
from django.conf import settings

# Optional: map thông tin user
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname, is_employee_manager
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None
    def is_employee_manager(_): return False

logger = logging.getLogger(__name__)

# ====== Policy: loại nghỉ được xem là "off" để link vào Attendance khi approve ======
APPROVABLE_OFF_TYPES = {
    LeaveRequest.LeaveType.ANNUAL,
    LeaveRequest.LeaveType.UNPAID,
    LeaveRequest.LeaveType.SICK,
    LeaveRequest.LeaveType.PAID_SPECIAL,
}

# ====== Notify helpers (giữ từ bản cũ, rút gọn nội dung) ======
def _notify_manager_new_leave(leave: LeaveRequest, manager_id: int) -> None:
    email = get_employee_email(manager_id)
    name_emp = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    subject = f"[Leave] New request from {name_emp}"
    period = f"{leave.start_date} → {leave.end_date}"

    extra_lines = []
    if leave.handover_to_employee_id:
        extra_lines.append(f"Handover to: {leave.handover_to_employee_id}")
    if leave.handover_content:
        extra_lines.append(f"Note: {leave.handover_content}")
    extra = ("\n" + "\n".join(extra_lines)) if extra_lines else ""

    text = (
        f"Employee: {name_emp} (ID {leave.employee_id})\n"
        f"Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"Period: {period}; Hours: {leave.hours or '-'}\n"
        f"Reason: {leave.reason or '-'}{extra}\n"
    )

    if email:
        send_email_notification(
            subject=subject,
            text_body=text,
            to_emails=[email],
            object_type="leave_request",
            object_id=str(leave.id),
            to_user=manager_id,
        )

    at_uid = None
    try:
        at_uid = settings.LARK_AT_MANAGER_IDS.get(int(manager_id))
    except Exception:
        at_uid = None

    lark_text = (
        "📝 NEW LEAVE\n"
        f"• Emp: {name_emp} (#{leave.employee_id})\n"
        f"• Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"• Period: {period}\n"
        f"• Hours: {leave.hours or '-'}\n"
        f"• Reason: {leave.reason or '-'}"
    )
    if extra_lines:
        lark_text += "\n• " + " / ".join(extra_lines)

    send_lark_notification(
        text=lark_text,
        at_user_ids=[at_uid] if at_uid else None,
        object_type="leave_request",
        object_id=str(leave.id),
        to_user=manager_id,
        to_lark_user_id=at_uid or "",
    )

def _notify_employee_decision(leave: LeaveRequest, manager_id: int) -> None:
    email = get_employee_email(leave.employee_id)
    name_emp = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    subject = f"[Leave] {leave.get_status_display()} — {leave.start_date} → {leave.end_date}"
    text = (
        f"Hello {name_emp},\n\n"
        f"Your leave request has been {leave.get_status_display().upper()} by Manager#{manager_id}.\n"
        f"Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"Period: {leave.start_date} → {leave.end_date}; Hours: {leave.hours or '-'}\n"
        f"Reason: {leave.reason or '-'}\n"
    )
    if email:
        send_email_notification(
            subject=subject,
            text_body=text,
            to_emails=[email],
            object_type="leave_request",
            object_id=str(leave.id),
            to_user=leave.employee_id,
        )

    at_uid = None
    try:
        at_uid = settings.LARK_AT_EMPLOYEE_IDS.get(int(leave.employee_id))
    except Exception:
        at_uid = None

    lark_text = (
        f"✅ LEAVE {leave.get_status_display().upper()}\n"
        f"• Emp: {name_emp} (#{leave.employee_id})\n"
        f"• Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"• Period: {leave.start_date} → {leave.end_date}\n"
        f"• Hours: {leave.hours or '-'}"
    )
    send_lark_notification(
        text=lark_text,
        at_user_ids=[at_uid] if at_uid else None,
        object_type="leave_request",
        object_id=str(leave.id),
        to_user=leave.employee_id,
        to_lark_user_id=at_uid or "",
    )

# ====== Business services ======
def create_leave(
    *, employee_id: int, manager_id: int, leave_type: int, start_date, end_date,
    paid: bool = False, hours: Optional[float] = None, reason: str = "",
    handover_to_employee_id: Optional[int] = None, handover_content: Optional[str] = None
) -> LeaveRequest:
    if end_date < start_date:
        raise ValueError("end_date phải >= start_date.")
    if hours is not None and float(hours) < 0:
        raise ValueError("hours phải >= 0")

    obj = repo.create({
        "employee_id": employee_id,
        "paid": bool(paid),
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "hours": hours,
        "reason": reason or "",
        "status": LeaveRequest.Status.SUBMITTED,
        "decision_ts": None,
        "decided_by": None,
        "handover_to_employee_id": handover_to_employee_id,
        "handover_content": handover_content or None,
    })

    # notify (ngoài transaction)
    try:
        _notify_manager_new_leave(obj, manager_id)
    except Exception as ex:
        logger.warning("[leave] notify manager failed: %s", ex)
    return obj

def update_leave(*, leave_id: int, employee_id: int, **changes: Any) -> LeaveRequest:
    # không cho sửa các field quản trị / khoá
    for k in ("employee_id","status","decision_ts","decided_by","id","pk","created_at","updated_at"):
        changes.pop(k, None)

    obj = repo.get_by_id(leave_id)
    # Rule: chỉ chủ đơn (hoặc manager ở API khác) được sửa khi SUBMITTED
    if obj.employee_id != employee_id or obj.status != LeaveRequest.Status.SUBMITTED or obj.decision_ts is not None:
        raise ValueError("Chỉ thao tác khi đơn SUBMITTED của chính bạn (chưa có quyết định).")

    # áp thay đổi
    allowed = {"paid","leave_type","start_date","end_date","hours","reason","handover_to_employee_id","handover_content"}
    obj = repo.save_fields(obj, changes, allowed=allowed)

    # kiểm tra lại date range
    if obj.end_date < obj.start_date:
        raise ValueError("end_date phải >= start_date.")

    return obj

def delete_leave(*, leave_id: int, employee_id: int) -> None:
    obj = repo.get_by_id(leave_id)
    if obj.employee_id != employee_id or obj.status != LeaveRequest.Status.SUBMITTED or obj.decision_ts is not None:
        raise ValueError("Chỉ xoá được đơn SUBMITTED của chính bạn.")
    repo.delete_leave(obj)

def cancel_leave(*, leave_id: int, actor_employee_id: int, as_manager: bool = False) -> LeaveRequest:
    obj = repo.get_by_id(leave_id)
    if not as_manager and obj.employee_id != actor_employee_id:
        raise PermissionError("Bạn không có quyền huỷ đơn nghỉ này.")
    if obj.status == LeaveRequest.Status.CANCELLED:
        return obj
    if obj.status in (LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED) and not as_manager:
        raise PermissionError("Đơn đã được quyết định. Vui lòng liên hệ quản lý.")
    obj = repo.cancel(leave_id=leave_id, actor_employee_id=actor_employee_id)

    try:
        _notify_employee_decision(obj, manager_id=actor_employee_id)
    except Exception as ex:
        logger.warning("[leave] notify employee cancel failed: %s", ex)
    return obj

def manager_decide(*, leave_id: int, manager_id: int, approve: bool) -> LeaveRequest:
    obj = repo.get_by_id(leave_id)
    if obj.status != LeaveRequest.Status.SUBMITTED:
        raise ValueError("Chỉ quyết định đơn ở trạng thái SUBMITTED.")

    # Nếu approve và loại nghỉ là OFF-type thì link vào Attendance
    do_link = obj.leave_type in APPROVABLE_OFF_TYPES

    if approve:
        obj = repo.approve_and_link(leave_id=leave_id, manager_id=manager_id, do_link_attendance=do_link)
    else:
        obj = repo.reject(leave_id=leave_id, manager_id=manager_id)

    try:
        _notify_employee_decision(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave] notify employee decision failed: %s", ex)

    return obj
