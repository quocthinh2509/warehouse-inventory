from datetime import timedelta, date
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from erp_the20.models import LeaveRequest, LeaveBalance, AttendanceSummary

@transaction.atomic
def request_leave(*, employee, leave_type, start_date, end_date, hours=None, reason="", attachment=None) -> LeaveRequest:
    if end_date < start_date:
        raise ValidationError("end_date must be >= start_date")
    req = LeaveRequest.objects.create(
        employee=employee, leave_type=leave_type, start_date=start_date, end_date=end_date,
        hours=hours, reason=reason, attachment=attachment, status="pending"
    )
    return req


@transaction.atomic
def approve_leave(*, request_id: int, approver):
    req = LeaveRequest.objects.select_for_update().filter(id=request_id).first()
    if not req or req.status != "pending":
        raise ValidationError("Request not found or not pending")

    req.status = "approved"
    req.approver = approver
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "approver", "decision_ts"])

    _apply_leave_to_summaries(req)
    _apply_to_balance(req)
    return req


def reject_leave(*, request_id: int, approver):
    req = LeaveRequest.objects.filter(id=request_id).first()
    if not req or req.status != "pending":
        raise ValidationError("Request not found or not pending")
    req.status = "rejected"
    req.approver = approver
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "approver", "decision_ts"])
    return req


def cancel_leave(*, request_id: int, actor):
    req = LeaveRequest.objects.filter(id=request_id).first()
    if not req or req.status != "approved":
        raise ValidationError("Only approved leave can be canceled")
    req.status = "canceled"
    req.decision_ts = timezone.now()
    req.save(update_fields=["status", "decision_ts"])
    # Optionally revert summaries/balances
    return req


# ---- internals ----

def _apply_leave_to_summaries(req: LeaveRequest):
    cur = req.start_date
    while cur <= req.end_date:
        summ, _ = AttendanceSummary.objects.get_or_create(employee=req.employee, date=cur)
        summ.status = "leave"
        summ.worked_minutes = 0
        summ.save(update_fields=["status", "worked_minutes"])
        cur += timedelta(days=1)


def _apply_to_balance(req: LeaveRequest):
    period = str(req.start_date.year)
    bal, _ = LeaveBalance.objects.get_or_create(employee=req.employee, leave_type=req.leave_type, period=period)
    # very simple: each day = 1.00; if hours present, you can convert to day fraction
    days = (req.end_date - req.start_date).days + 1
    bal.used = (bal.used or 0) + days
    bal.closing = (bal.opening + bal.accrued + bal.carry_in) - (bal.used + bal.carry_out)
    bal.save(update_fields=["used", "closing"])