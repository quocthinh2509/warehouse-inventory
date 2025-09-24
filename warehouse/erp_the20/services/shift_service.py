from datetime import datetime, timedelta
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from erp_the20.models import ShiftTemplate, ShiftInstance, ShiftAssignment, ShiftRegistration, Worksite
from erp_the20.selectors.shift_selector import (
    count_assignments, get_shift_instance, instances_for_employee_on_date,
)

# ---------- Registration & Assignment ----------
# Nhân viên có thể đăng ký ca đang mở
@transaction.atomic
def register_shift(*, employee, shift_instance_id: int, created_by=None, reason="") -> ShiftRegistration:
    shift = get_shift_instance(shift_instance_id)
    if not shift or shift.status != "open":
        raise ValidationError("Shift is not open or not found")

    if ShiftRegistration.objects.filter(employee=employee, shift_instance=shift).exists():
        raise ValidationError("Already registered for this shift")

    # Optional capacity guard if model has it
    if hasattr(shift, "capacity") and shift.capacity is not None:
        if count_assignments(shift.id) >= shift.capacity:
            raise ValidationError("Shift capacity has been reached")

    return ShiftRegistration.objects.create(
        employee=employee, shift_instance=shift, created_by=created_by, reason=reason, status="pending"
    )

# Người quản lý có thể duyệt đăng ký
@transaction.atomic
def approve_registration(*, registration_id: int, approver):
    reg = ShiftRegistration.objects.select_for_update().filter(id=registration_id).first()
    if not reg or reg.status != "pending":
        raise ValidationError("Registration not found or not pending")

    shift = reg.shift_instance
    if shift.status != "open":
        raise ValidationError("Shift is not open")

    if hasattr(shift, "capacity") and shift.capacity is not None:
        if count_assignments(shift.id) >= shift.capacity:
            raise ValidationError("Shift capacity has been reached")

    ShiftAssignment.objects.create(
        employee=reg.employee, shift_instance=shift, assigned_by=approver, status="assigned"
    )
    reg.status = "approved"
    reg.save(update_fields=["status"])
    return reg

# Người quản lý có thể phân công trực tiếp nhân viên vào ca
@transaction.atomic
def assign_shift(*, employee, shift_instance_id: int, assigned_by=None) -> ShiftAssignment:
    shift = get_shift_instance(shift_instance_id)
    if not shift:
        raise ValidationError("Shift not found")

    if ShiftAssignment.objects.filter(employee=employee, shift_instance=shift).exists():
        raise ValidationError("Already assigned to this shift")

    if hasattr(shift, "capacity") and shift.capacity is not None:
        if count_assignments(shift.id) >= shift.capacity:
            raise ValidationError("Shift capacity has been reached")

    return ShiftAssignment.objects.create(
        employee=employee, shift_instance=shift, assigned_by=assigned_by, status="assigned"
    )


# ---------- Generation from templates ----------

WEEKDAY_MAP = {  # ISO weekday numbers: Monday=1, Sunday=7
    "1", "2", "3", "4", "5", "6", "7"
}

# parse a string like "1,3,5" into a set of valid weekday strings
def _parse_weekly_days(s: str) -> set[str]:
    if not s:
        return set()
    items = {x.strip() for x in s.split(",") if x.strip()}
    # keep only valid tokens 1..7
    return {x for x in items if x in WEEKDAY_MAP}

# Tạo ca làm việc từ mẫu trong khoảng thời gian nhất định
@transaction.atomic
def generate_instances_from_template(*, template_id: int, date_from, date_to, worksite_id: int | None = None) -> int:
    """Create ShiftInstance(s) from a template for the range [date_from, date_to]. Returns number created."""
    tpl = ShiftTemplate.objects.select_related("default_worksite").get(id=template_id)
    weekdays = _parse_weekly_days(tpl.weekly_days)
    ws_id = worksite_id or (tpl.default_worksite_id if tpl.default_worksite_id else None)

    created = 0
    cur = date_from
    while cur <= date_to:
        iso = cur.isoweekday()  # 1..7
        if not weekdays or str(iso) in weekdays:
            inst, is_created = ShiftInstance.objects.get_or_create(
                template=tpl, date=cur, worksite_id=ws_id,
                defaults={"status": "open"}
            )
            if is_created:
                created += 1
        cur += timedelta(days=1)
    return created

# Quản lý có thể đống ca làm việc
@transaction.atomic
def close_instance(*, shift_instance_id: int):
    inst = ShiftInstance.objects.filter(id=shift_instance_id).first()
    if not inst:
        raise ValidationError("Shift instance not found")
    inst.status = "closed"
    inst.save(update_fields=["status"])
    return inst

# Quản lý có thể hủy ca làm việc
@transaction.atomic
def cancel_instance(*, shift_instance_id: int):
    inst = ShiftInstance.objects.filter(id=shift_instance_id).first()
    if not inst:
        raise ValidationError("Shift instance not found")
    inst.status = "canceled"
    inst.save(update_fields=["status"])
    return inst