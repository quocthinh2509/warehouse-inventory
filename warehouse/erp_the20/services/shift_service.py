from django.core.exceptions import ValidationError
from erp_the20.models import (
    ShiftTemplate,
    ShiftInstance,
    ShiftAssignment,
    ShiftRegistration,
)
from django.utils import timezone


# ============================================================
#  SHIFT TEMPLATE (Mẫu ca làm việc)
# ============================================================

def create_shift_template(data: dict) -> ShiftTemplate:
    """
    Tạo ShiftTemplate (mẫu ca làm việc).
    Args:
        data: {"code", "name", "start_time", "end_time", "break_minutes", "overnight", "weekly_days"}
    Raises:
        ValidationError: nếu code đã tồn tại
    """
    if ShiftTemplate.objects.filter(code=data["code"]).exists():
        raise ValidationError("ShiftTemplate code must be unique")
    return ShiftTemplate.objects.create(**data)


def update_shift_template(template: ShiftTemplate, data: dict) -> ShiftTemplate:
    """
    Cập nhật ShiftTemplate.
    Args:
        template: object cần update
        data: dict các field
    """
    if "code" in data and data["code"] != template.code:
        if ShiftTemplate.objects.filter(code=data["code"]).exclude(id=template.id).exists():
            raise ValidationError("ShiftTemplate code must be unique")
        template.code = data["code"]

    for field in ["name", "start_time", "end_time", "break_minutes", "overnight", "weekly_days"]:
        if field in data:
            setattr(template, field, data[field])

    template.save()
    return template


def delete_shift_template(template: ShiftTemplate) -> None:
    """Xóa ShiftTemplate."""
    template.delete()


# ============================================================
#  SHIFT INSTANCE (Ca làm việc cụ thể)
# ============================================================

def create_shift_instance(data: dict) -> ShiftInstance:
    """
    Tạo ShiftInstance (ca cụ thể từ template).
    Args:
        data: {"template": ShiftTemplate, "date": date, "status": str}
    Raises:
        ValidationError: nếu (template, date) đã tồn tại
    """
    if ShiftInstance.objects.filter(template=data["template"], date=data["date"]).exists():
        raise ValidationError("ShiftInstance for this template and date already exists")
    return ShiftInstance.objects.create(**data)


def update_shift_instance(instance: ShiftInstance, data: dict) -> ShiftInstance:
    """
    Cập nhật ShiftInstance.
    """
    for field in ["template", "date", "status"]:
        if field in data:
            setattr(instance, field, data[field])

    instance.save()
    return instance


def delete_shift_instance(instance: ShiftInstance) -> None:
    """Xóa ShiftInstance."""
    instance.delete()


# ============================================================
#  SHIFT ASSIGNMENT (Gán ca cho nhân viên)
# ============================================================

def assign_employee_to_shift(data: dict) -> ShiftAssignment:
    """
    Gán nhân viên vào ca cụ thể.
    Args:
        data: {"employee": Employee, "shift_instance": ShiftInstance, "assigned_by": User, "status": str}
    Raises:
        ValidationError: nếu nhân viên đã được gán ca này
    """
    if ShiftAssignment.objects.filter(employee=data["employee"], shift_instance=data["shift_instance"]).exists():
        raise ValidationError("Employee already assigned to this shift")
    return ShiftAssignment.objects.create(**data)


def update_shift_assignment(assignment: ShiftAssignment, data: dict) -> ShiftAssignment:
    """
    Cập nhật thông tin gán ca.
    """
    for field in ["employee", "shift_instance", "assigned_by", "status"]:
        if field in data:
            setattr(assignment, field, data[field])

    assignment.save()
    return assignment


def delete_shift_assignment(assignment: ShiftAssignment) -> None:
    """Xóa ShiftAssignment."""
    assignment.delete()


# ============================================================
#  SHIFT REGISTRATION (Đăng ký ca)
# ============================================================

def register_shift(data: dict) -> ShiftRegistration:
    """
    Nhân viên đăng ký ca làm việc.
    Args:
        data: {"employee": Employee, "shift_instance": ShiftInstance, "created_by": User, "status": str, "reason": str}
    Raises:
        ValidationError: nếu nhân viên đã đăng ký ca này
    """
    if ShiftRegistration.objects.filter(employee=data["employee"], shift_instance=data["shift_instance"]).exists():
        raise ValidationError("Employee already registered for this shift")
    return ShiftRegistration.objects.create(**data)


def update_shift_registration(registration: ShiftRegistration, data: dict) -> ShiftRegistration:
    """
    Cập nhật thông tin đăng ký ca.
    """
    for field in ["employee", "shift_instance", "created_by", "status", "reason"]:
        if field in data:
            setattr(registration, field, data[field])

    registration.save()
    return registration


def delete_shift_registration(registration: ShiftRegistration) -> None:
    """Xóa ShiftRegistration."""
    registration.delete()
