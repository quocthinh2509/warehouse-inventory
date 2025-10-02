from django.core.exceptions import ValidationError
from erp_the20.models import (
    ShiftTemplate,
    ShiftInstance,
)
from django.utils import timezone


# ============================================================
#  SHIFT TEMPLATE (Mẫu ca làm việc)
# ============================================================

def create_shift_template(data: dict) -> ShiftTemplate:
    """
    Tạo ShiftTemplate (mẫu ca làm việc).
    Args:
        data: {"code", "name", "start_time", "end_time", "break_minutes", "overnight"}
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

    for field in ["name", "start_time", "end_time", "break_minutes", "overnight"]:
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

