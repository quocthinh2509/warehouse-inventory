from django.db.models import Prefetch, Q, F
from erp_the20.models import (
    ShiftTemplate,
    ShiftInstance,
    ShiftAssignment,
    ShiftRegistration,
    Employee,
)
from datetime import date
from datetime import datetime, timedelta


# ============================================================
#  SHIFT TEMPLATE
# ============================================================

def get_shift_template(template_id: int) -> ShiftTemplate | None:
    """Lấy 1 ShiftTemplate theo id."""
    return ShiftTemplate.objects.filter(id=template_id).first()


def list_shift_templates() -> list[ShiftTemplate]:
    """Lấy toàn bộ ShiftTemplate."""
    return ShiftTemplate.objects.all()


# ============================================================
#  SHIFT INSTANCE
# ============================================================

def get_shift_instance(instance_id: int) -> ShiftInstance | None:
    """Lấy 1 ShiftInstance theo id."""
    return ShiftInstance.objects.filter(id=instance_id).first()


def list_shift_instances(
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> list[ShiftInstance]:
    """
    Lấy danh sách ShiftInstance, có filter theo ngày và status.
    """
    qs = ShiftInstance.objects.select_related("template").all()

    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if status:
        qs = qs.filter(status=status)

    return qs


# ============================================================
#  SHIFT ASSIGNMENT
# ============================================================

def get_shift_assignment(assignment_id: int) -> ShiftAssignment | None:
    """Lấy 1 ShiftAssignment theo id."""
    return (
        ShiftAssignment.objects.select_related("employee", "shift_instance")
        .filter(id=assignment_id)
        .first()
    )


def list_shift_assignments(employee_id: int | None = None, shift_instance_id: int | None = None) -> list[ShiftAssignment]:
    """
    Lấy danh sách ShiftAssignment, có filter theo employee hoặc shift_instance.
    """
    qs = ShiftAssignment.objects.select_related("employee", "shift_instance")

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if shift_instance_id:
        qs = qs.filter(shift_instance_id=shift_instance_id)

    return qs


# ============================================================
#  SHIFT REGISTRATION
# ============================================================

def get_shift_registration(reg_id: int) -> ShiftRegistration | None:
    """Lấy 1 ShiftRegistration theo id."""
    return (
        ShiftRegistration.objects.select_related("employee", "shift_instance")
        .filter(id=reg_id)
        .first()
    )


def list_shift_registrations(employee_id: int | None = None, shift_instance_id: int | None = None, status: str | None = None) -> list[ShiftRegistration]:
    """
    Lấy danh sách ShiftRegistration (có filter).
    """
    qs = ShiftRegistration.objects.select_related("employee", "shift_instance")

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if shift_instance_id:
        qs = qs.filter(shift_instance_id=shift_instance_id)
    if status:
        qs = qs.filter(status=status)

    return qs


# ============================================================
#  EXTRA HELPERS
# ============================================================

def get_active_employee(emp_id: int) -> Employee | None:
    """Trả về Employee nếu đang active, ngược lại None."""
    return Employee.objects.filter(id=emp_id, is_active=True).first()


def get_registration_with_related(reg_id: int) -> ShiftRegistration | None:
    """Lấy 1 ShiftRegistration cùng thông tin liên quan (employee, shift_instance, template)."""
    return (
        ShiftRegistration.objects.select_related("employee", "shift_instance__template")
        .filter(id=reg_id)
        .first()
    )


def get_assignment_with_related(assignment_id: int) -> ShiftAssignment | None:
    """Lấy 1 ShiftAssignment cùng thông tin liên quan (employee, shift_instance, template)."""
    return (
        ShiftAssignment.objects.select_related("employee", "shift_instance__template")
        .filter(id=assignment_id)
        .first()
    )


def instances_around(ts) -> list[ShiftInstance]:
    """Lấy các ShiftInstance có thể bao quanh timestamp `ts`."""
    return ShiftInstance.objects.filter(
        Q(date=ts.date())
        | Q(date=ts.date() - timedelta(days=1), template__end_time__gt=F("template__start_time"))
        | Q(date=ts.date() + timedelta(days=1), template__end_time__lt=F("template__start_time"))
    ).select_related("template").all()


def planned_minutes(inst: ShiftInstance) -> int:
    """Tính tổng phút làm việc thực tế trong ca (đã trừ break)."""
    start_dt = datetime.combine(date.min, inst.template.start_time)
    end_dt = datetime.combine(date.min, inst.template.end_time)
    if inst.template.overnight and end_dt <= start_dt:
        end_dt += timedelta(days=1)
    total_minutes = int((end_dt - start_dt).total_seconds() // 60) - inst.template.break_minutes
    return max(total_minutes, 0)



