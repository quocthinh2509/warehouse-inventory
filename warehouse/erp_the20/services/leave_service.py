from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from erp_the20.models import LeaveRequest, LeaveBalance, AttendanceSummary

# ----------------------
# Leave Service
# ----------------------

@transaction.atomic
def request_leave(*, employee, leave_type, start_date, end_date, hours=None, reason="", attachment=None) -> LeaveRequest:
    """
    Nhân viên gửi yêu cầu nghỉ
    """
    if end_date < start_date:
        raise ValidationError("end_date must be >= start_date")
    return LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        hours=hours,
        reason=reason,
        attachment=attachment,
        status="pending"
    )


@transaction.atomic
def approve_leave(*, request_id: int, approver):
    """
    Quản lý duyệt yêu cầu nghỉ
    """
    req = LeaveRequest.objects.select_for_update().filter(id=request_id, status="pending").first()
    if not req:
        raise ValidationError("Request not found or not pending")

    req.status = "approved"
    req.approver = approver
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "approver", "decision_ts"])

    _apply_leave_to_summaries(req)
    _apply_to_balance(req)
    return req


def reject_leave(*, request_id: int, approver):
    """
    Quản lý từ chối yêu cầu nghỉ
    """
    req = LeaveRequest.objects.filter(id=request_id, status="pending").first()
    if not req:
        raise ValidationError("Request not found or not pending")
    req.status = "rejected"
    req.approver = approver
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "approver", "decision_ts"])
    return req


def cancel_leave(*, request_id: int, actor):
    """
    Hủy yêu cầu nghỉ đã được duyệt
    """
    req = LeaveRequest.objects.filter(id=request_id, status="approved").first()
    if not req:
        raise ValidationError("Only approved leave can be canceled")
    req.status = "canceled"
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "decision_ts"])
    return req


# ---- Internals ----

def _apply_leave_to_summaries(req: LeaveRequest):
    """
    Áp dụng leave vào AttendanceSummary: status="leave"
    """
    cur = req.start_date
    while cur <= req.end_date:
        summ, _ = AttendanceSummary.objects.get_or_create(employee=req.employee, date=cur)
        summ.status = "leave"
        summ.worked_minutes = 0
        summ.save(update_fields=["status", "worked_minutes"])
        cur += timedelta(days=1)


def _apply_to_balance(req: LeaveRequest):
    """
    Cập nhật LeaveBalance
    """
    period = str(req.start_date.year)
    bal, _ = LeaveBalance.objects.get_or_create(employee=req.employee, leave_type=req.leave_type, period=period)
    days = (req.end_date - req.start_date).days + 1
    bal.used = (bal.used or 0) + days
    bal.closing = (bal.opening + bal.accrued + bal.carry_in) - (bal.used + bal.carry_out)
    bal.save(update_fields=["used", "closing"])
