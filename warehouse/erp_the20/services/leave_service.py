# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Any, List
from django.db import transaction, router
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
import logging
from erp_the20.utils.notify import send_email_notification, send_lark_notification
from django.conf import settings

from erp_the20.models import LeaveRequest, Attendance

# Optional: map thông tin user
try:
    from erp_the20.selectors.user_selector import get_employee_email, get_employee_fullname, is_employee_manager
except Exception:
    def get_employee_email(_): return None
    def get_employee_fullname(_): return None
    def is_employee_manager(_): return False

logger = logging.getLogger(__name__)


# ===== DB utils =====
def _db_alias() -> str:
    return router.db_for_write(LeaveRequest)

def _atomic():
    return transaction.atomic(using=_db_alias())


# ===== Email utils (tối giản) =====
def _send_email(subject: str, text_body: str, to_emails: List[str], html_body: Optional[str] = None) -> None:
    tos = [e for e in (to_emails or []) if e]
    if not tos:
        return
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
    try:
        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=from_email, to=tos)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=True)
    except Exception as ex:
        logger.warning("[leave_service] email failed: %s", ex)

def _notify_manager_new_leave(leave: LeaveRequest, manager_id: int) -> None:
    email = get_employee_email(manager_id)
    name_emp = get_employee_fullname(leave.employee_id) or f"Emp#{leave.employee_id}"
    subject = f"[Leave] New request from {name_emp}"

    period = f"{leave.start_date} → {leave.end_date}"
    text = (
        f"Employee: {name_emp} (ID {leave.employee_id})\n"
        f"Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"Period: {period}; Hours: {leave.hours or '-'}\n"
        f"Reason: {leave.reason or '-'}\n"
    )

    # Email -> manager (log tự tạo trong notify)
    if email:
        send_email_notification(
            subject=subject,
            text_body=text,
            to_emails=[email],
            object_type="leave_request",
            object_id=str(leave.id),
            to_user=manager_id,
        )

    # Lark -> group webhook (mention manager nếu có map)
    at_uid = None
    try:
        at_uid = settings.LARK_AT_MANAGER_IDS.get(int(manager_id))
    except Exception:
        at_uid = None

    lark_text = (
        f"📝 NEW LEAVE\n"
        f"• Emp: {name_emp} (#{leave.employee_id})\n"
        f"• Type: {leave.get_leave_type_display()} | Paid: {'Yes' if leave.paid else 'No'}\n"
        f"• Period: {period}\n"
        f"• Hours: {leave.hours or '-'}\n"
        f"• Reason: {leave.reason or '-'}"
    )
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



# ===== Domain helpers =====
_APPROVABLE_OFF_TYPES = {
    LeaveRequest.LeaveType.ANNUAL,
    LeaveRequest.LeaveType.UNPAID,
    LeaveRequest.LeaveType.SICK,
    LeaveRequest.LeaveType.PAID_SPECIAL,
}

def _ensure_editable(obj: LeaveRequest, actor_employee_id: int, as_manager: bool = False) -> None:
    if as_manager:
        return
    if obj.employee_id != actor_employee_id:
        raise PermissionError("Không có quyền thao tác trên đơn này.")
    if obj.status != LeaveRequest.Status.SUBMITTED or obj.decision_ts is not None:
        raise ValueError("Chỉ thao tác khi đơn đang ở trạng thái SUBMITTED (chưa có quyết định).")


def _link_leave_to_attendance_on_approve(leave: LeaveRequest, db_alias: str) -> None:
    """
    Khi duyệt các loại nghỉ 'off', gắn FK on_leave vào các Attendance trong khoảng ngày
    và huỷ các Attendance đang PENDING/APPROVED (tuỳ policy).
    """
    if leave.leave_type not in _APPROVABLE_OFF_TYPES:
        # Với OVERTIME/ONLINE/SHIFT_CHANGE/LATE_IN/EARLY_OUT — không can thiệp Attendance ở đây.
        return

    qs = (
        Attendance.objects.using(db_alias)
        .select_for_update()
        .filter(employee_id=leave.employee_id, date__gte=leave.start_date, date__lte=leave.end_date)
    )
    # Link đơn nghỉ
    qs.update(on_leave=leave)

    # Huỷ (optional policy): nếu đã tạo Attendance cho ngày nghỉ thì chuyển CANCELED + is_valid=False
    for att in qs:
        if att.status in (Attendance.Status.PENDING, Attendance.Status.APPROVED):
            att.status = Attendance.Status.CANCELED
            att.is_valid = False
            att.approved_by = None
            att.approved_at = None
            att.save(using=db_alias, update_fields=["status", "is_valid", "approved_by", "approved_at", "updated_at"])


# ===== Employee APIs =====
def create_leave(
    *,
    employee_id: int,
    manager_id: int,
    leave_type: int,
    start_date,
    end_date,
    paid: bool = False,
    hours: Optional[float] = None,
    reason: str = "",
) -> LeaveRequest:
    if end_date < start_date:
        raise ValueError("end_date phải >= start_date.")

    db = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db).create(
            employee_id=employee_id,
            paid=paid,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            hours=hours,
            reason=reason or "",
            status=LeaveRequest.Status.SUBMITTED,
            decision_ts=None,
            decided_by=None,
        )
    # notify ngoài transaction
    try:
        _notify_manager_new_leave(obj, manager_id)
    except Exception as ex:
        logger.warning("[leave] notify manager failed: %s", ex)
    return obj


def update_leave(
    *,
    leave_id: int,
    employee_id: int,
    **changes: Any,
) -> LeaveRequest:
    for k in ("employee_id", "status", "decision_ts", "decided_by", "id", "pk", "created_at", "updated_at"):
        changes.pop(k, None)

    db = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db).select_for_update().get(id=leave_id)
        _ensure_editable(obj, actor_employee_id=employee_id, as_manager=False)

        for field in ("paid", "leave_type", "start_date", "end_date", "hours", "reason"):
            if field in changes and changes[field] is not None:
                setattr(obj, field, changes[field])

        if obj.end_date < obj.start_date:
            raise ValueError("end_date phải >= start_date.")

        obj.save(using=db)
        return obj


def delete_leave(*, leave_id: int, employee_id: int) -> None:
    db = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db).select_for_update().get(id=leave_id)
        _ensure_editable(obj, actor_employee_id=employee_id, as_manager=False)
        obj.delete(using=db)


def cancel_leave(*, leave_id: int, actor_employee_id: int, as_manager: bool = False) -> LeaveRequest:
    db = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db).select_for_update().get(id=leave_id)
        if not as_manager:
            _ensure_editable(obj, actor_employee_id=actor_employee_id, as_manager=False)

        if obj.status == LeaveRequest.Status.CANCELLED:
            return obj

        obj.status = LeaveRequest.Status.CANCELLED
        obj.decision_ts = timezone.now()
        obj.decided_by = actor_employee_id
        obj.save(using=db, update_fields=["status", "decision_ts", "decided_by", "updated_at"])

    try:
        _notify_employee_decision(obj, manager_id=actor_employee_id)
    except Exception as ex:
        logger.warning("[leave] notify employee cancel failed: %s", ex)
    return obj


# ===== Manager Decision =====
def manager_decide(*, leave_id: int, manager_id: int, approve: bool) -> LeaveRequest:
    db = _db_alias()
    with _atomic():
        obj = LeaveRequest.objects.using(db).select_for_update().get(id=leave_id)

        if obj.status != LeaveRequest.Status.SUBMITTED:
            raise ValueError("Chỉ quyết định đơn ở trạng thái SUBMITTED.")

        obj.decision_ts = timezone.now()
        obj.decided_by = manager_id

        if approve:
            obj.status = LeaveRequest.Status.APPROVED
            obj.save(using=db, update_fields=["status", "decision_ts", "decided_by", "updated_at"])
            _link_leave_to_attendance_on_approve(obj, db_alias=db)
        else:
            obj.status = LeaveRequest.Status.REJECTED
            obj.save(using=db, update_fields=["status", "decision_ts", "decided_by", "updated_at"])

    try:
        _notify_employee_decision(obj, manager_id=manager_id)
    except Exception as ex:
        logger.warning("[leave] notify employee decision failed: %s", ex)

    return obj
