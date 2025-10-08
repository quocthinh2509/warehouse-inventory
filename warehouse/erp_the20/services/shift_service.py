from typing import Dict, Any
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from erp_the20.models import ShiftTemplate

ACTIVE_FIELDS = ["code", "name", "start_time", "end_time",
                 "break_minutes", "overnight", "pay_factor"]

def _snapshot(instance: ShiftTemplate) -> Dict[str, Any]:
    return {f: getattr(instance, f) for f in ACTIVE_FIELDS}

@transaction.atomic
def create_shift_template(data: Dict[str, Any]) -> ShiftTemplate:
    return ShiftTemplate.objects.create(**data)

@transaction.atomic
def update_shift_template_versioned(instance: ShiftTemplate, data: Dict[str, Any]) -> ShiftTemplate:
    """
    Versioning update:
    1) archive bản cũ (set deleted_at)
    2) tạo bản mới (ID mới) với payload = snapshot cũ + data mới
    """
    if instance.deleted_at is None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])

    payload = _snapshot(instance)
    payload.update(data)

    try:
        new_obj = ShiftTemplate.objects.create(**payload)
    except IntegrityError as e:
        # vi phạm uniq_active_shifttemplate_code (có bản active cùng code)
        raise ValidationError({"code": "Code đã tồn tại ở bản active."})
    return new_obj

@transaction.atomic
def soft_delete_shift_template(instance: ShiftTemplate) -> None:
    """Soft delete: chỉ set deleted_at, không xóa hẳn."""
    if instance.deleted_at is None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])

# @transaction.atomic
# def restore_shift_template(instance: ShiftTemplate) -> None:
#     """
#     Khôi phục bản đã xóa mềm. Sẽ lỗi nếu đã có bản active cùng code.
#     """
#     if instance.deleted_at is None:
#         return
#     existed = ShiftTemplate.objects.filter(
#         code=instance.code, deleted_at__isnull=True
#     ).exclude(pk=instance.pk).exists()
#     if existed:
#         raise ValidationError({"code": "Đã có bản active cùng code, không thể restore."})
#     instance.deleted_at = None
#     instance.save(update_fields=["deleted_at"])
