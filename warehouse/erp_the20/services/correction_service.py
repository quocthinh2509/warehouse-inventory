from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from erp_the20.models import AttendanceCorrection, AttendanceEvent
from erp_the20.services.attendance_service import _rollup_summary

@transaction.atomic
def request_correction(*, employee, date, type: str, requested_by, changeset: dict) -> AttendanceCorrection:
    return AttendanceCorrection.objects.create(
        employee=employee, date=date, type=type, requested_by=requested_by, status="pending", changeset=changeset
    )


@transaction.atomic
def approve_correction(*, correction_id: int, approver):
    corr = AttendanceCorrection.objects.select_for_update().filter(id=correction_id).first()
    if not corr or corr.status != "pending":
        raise ValidationError("Correction not found or not pending")

    # Very MVP: apply simple changes
    cs = corr.changeset or {}
    if "check_in" in cs:
        AttendanceEvent.objects.create(
            employee=corr.employee, event_type="check_in", ts=cs["check_in"], source="correction"
        )
    if "check_out" in cs:
        AttendanceEvent.objects.create(
            employee=corr.employee, event_type="check_out", ts=cs["check_out"], source="correction"
        )

    corr.status = "approved"
    corr.approver = approver
    corr.save(update_fields=["status", "approver"])

    _rollup_summary(corr.employee_id, corr.date)
    return corr