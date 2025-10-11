# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict, Any, List
from django.db import transaction, IntegrityError
from django.db.models import QuerySet, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from erp_the20.models import ShiftTemplate

# ============================
# Base queries (general-purpose)
# ============================
def base_qs(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    qs = ShiftTemplate.objects.all()
    if not include_deleted:
        qs = qs.filter(deleted_at__isnull=True)
    return qs

def get_by_id(pk: int, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return base_qs(include_deleted).filter(pk=pk).first()

def get_by_code(code: str, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return base_qs(include_deleted).filter(code=code).first()

def list_shift_templates(
    q: Optional[str] = None,
    overnight: Optional[bool] = None,
    ordering: Optional[str] = None,
    include_deleted: bool = False,
) -> QuerySet[ShiftTemplate]:
    qs = base_qs(include_deleted)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    if overnight is not None:
        qs = qs.filter(overnight=overnight)
    if ordering:
        qs = qs.order_by(ordering)
    return qs

def list_all_ordered_by_start_time(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    return base_qs(include_deleted).order_by("start_time")


# ============================
# Mutations (general-purpose)
# ============================
ACTIVE_FIELDS = ["code", "name", "start_time", "end_time", "break_minutes", "overnight", "pay_factor"]

def _snapshot(instance: ShiftTemplate) -> Dict[str, Any]:
    return {f: getattr(instance, f) for f in ACTIVE_FIELDS}

@transaction.atomic
def create(data: Dict[str, Any]) -> ShiftTemplate:
    """
    Tạo mới ShiftTemplate (không gắn rule nghiệp vụ).
    Ném ValidationError nếu vi phạm unique 'code' ở bản active (tùy DB constraints).
    """
    return ShiftTemplate.objects.create(**data)

@transaction.atomic
def update_versioned(instance: ShiftTemplate, data: Dict[str, Any]) -> ShiftTemplate:
    """
    Versioning update (thuần DB):
    1) archive bản cũ (set deleted_at)
    2) tạo bản mới (ID mới) với payload = snapshot cũ + data mới
    """
    if instance.deleted_at is None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])

    payload = _snapshot(instance)
    payload.update(data)

    try:
        return ShiftTemplate.objects.create(**payload)
    except IntegrityError:
        # Vi phạm uniq_active_shifttemplate_code (nếu bạn có constraint này)
        raise ValidationError({"code": "Code đã tồn tại ở bản active."})

@transaction.atomic
def soft_delete(instance: ShiftTemplate) -> None:
    """Soft delete: set deleted_at, không xóa hẳn (thuần DB)."""
    if instance.deleted_at is None:
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])

@transaction.atomic
def save_fields(obj: ShiftTemplate, patch: Dict[str, Any], allowed: Optional[set] = None) -> ShiftTemplate:
    """
    Cập nhật “miếng vá” field vào object rồi save(update_fields=...). Thuần DB.
    Dùng khi service muốn update vài trường mà không cần thêm hàm repo riêng.
    """
    fields: List[str] = []
    for k, v in patch.items():
        if (allowed is None) or (k in allowed):
            setattr(obj, k, v)
            fields.append(k)
    if fields:
        fields.append("updated_at")
        obj.save(update_fields=fields)
    return obj
