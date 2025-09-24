from datetime import datetime, timedelta
from typing import Optional, Iterable
from django.utils import timezone
from django.db.models import QuerySet
from erp_the20.models import (
    ShiftTemplate, ShiftInstance, ShiftAssignment, ShiftRegistration, Employee
)

# ---- Employee ----
def get_active_employee(emp_id: int) -> Optional[Employee]:
    return Employee.objects.filter(id=emp_id, is_active=True).first()

# ---- ShiftTemplate ----
def list_shift_templates() -> QuerySet[ShiftTemplate]:
    return (
        ShiftTemplate.objects
        .select_related("default_worksite")
        .order_by("name")
    )

def reload_shift_template(pk: int) -> ShiftTemplate:
    return (
        ShiftTemplate.objects
        .select_related("default_worksite")
        .get(pk=pk)
    )

# ---- ShiftInstance ----
def list_open_shift_instances(date_from=None, date_to=None, worksite_id: Optional[int]=None) -> QuerySet[ShiftInstance]:
    qs = ShiftInstance.objects.filter(status="open")
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if worksite_id:
        qs = qs.filter(worksite_id=worksite_id)
    # LƯU Ý: field thật là `template`, không phải `shift_template`
    return qs.select_related("template__default_worksite", "worksite").order_by("date", "id")

def reload_shift_instance(pk: int) -> ShiftInstance:
    return (
        ShiftInstance.objects
        .select_related("template__default_worksite", "worksite")
        .get(pk=pk)
    )

# ---- Đếm / lấy theo id (đang dùng trong services) ----
def count_assignments(shift_instance_id: int) -> int:
    return ShiftAssignment.objects.filter(shift_instance_id=shift_instance_id).count()

def get_shift_instance(pk: int) -> Optional[ShiftInstance]:
    return (
        ShiftInstance.objects
        .select_related("template", "worksite")
        .filter(id=pk)
        .first()
    )

# ---- Read lại để serialize đủ quan hệ ----
def get_registration_with_related(pk: int) -> ShiftRegistration:
    return (
        ShiftRegistration.objects
        .select_related(
            "employee",
            "shift_instance__template__default_worksite",
            "shift_instance__worksite",
            "created_by",
        )
        .get(pk=pk)
    )

def get_assignment_with_related(pk: int) -> ShiftAssignment:
    return (
        ShiftAssignment.objects
        .select_related(
            "employee",
            "assigned_by",
            "shift_instance__template__default_worksite",
            "shift_instance__worksite",
        )
        .get(pk=pk)
    )

# ---- Helpers sẵn có của bạn, giữ nguyên (tuỳ nhu cầu) ----
def instances_for_employee_on_date(employee_id: int, d) -> list[ShiftInstance]:
    assigned_ids = list(
        ShiftAssignment.objects.filter(shift_instance__date=d, employee_id=employee_id)
        .values_list("shift_instance_id", flat=True)
    )
    reg_ids = list(
        ShiftRegistration.objects.filter(shift_instance__date=d, employee_id=employee_id, status="approved")
        .values_list("shift_instance_id", flat=True)
    )
    ids = set(assigned_ids + reg_ids)
    return list(
        ShiftInstance.objects.filter(id__in=ids).select_related("template", "worksite")
    )

def instances_around(ts) -> list[ShiftInstance]:
    d = ts.date()
    return list(
        ShiftInstance.objects.filter(date__in=[d - timedelta(days=1), d, d + timedelta(days=1)])
        .select_related("template", "worksite")
    )

def instance_window_with_grace(inst: ShiftInstance, *, checkin_open_grace_min: int, checkout_grace_min: int):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(inst.date, inst.template.start_time), tz)
    end   = timezone.make_aware(datetime.combine(inst.date, inst.template.end_time),   tz)
    if inst.template.overnight and end <= start:
        end += timedelta(days=1)
    start_grace = start - timedelta(minutes=checkin_open_grace_min)
    end_grace   = end + timedelta(minutes=checkout_grace_min)
    return start, end, start_grace, end_grace


# tính toán số phút làm việc theo kế hoạch của ca làm việc dựa trên mẫu ca và thời gian nghỉ
def planned_minutes(inst: ShiftInstance) -> int:
    """Planned minutes for this instance according to template and break."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(inst.date, inst.template.start_time), tz)
    end   = timezone.make_aware(datetime.combine(inst.date, inst.template.end_time), tz)
    if inst.template.overnight and end <= start:
        end += timedelta(days=1)
    total = int((end - start).total_seconds() // 60)
    return max(0, total - int(inst.template.break_minutes or 0))