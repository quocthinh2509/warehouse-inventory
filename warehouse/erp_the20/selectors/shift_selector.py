# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional
from django.db.models import QuerySet

from erp_the20.models import ShiftTemplate
from erp_the20.repositories import shift_repository as repo

# ============================
# Selector (input normalization + delegate to repo)
# ============================
def base_qs(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    """Giữ tương thích với code cũ: trả về QuerySet cơ bản (ủy quyền repo)."""
    return repo.base_qs(include_deleted)

def get_by_id(pk: int, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return repo.get_by_id(pk, include_deleted)

def get_by_code(code: str, include_deleted: bool = False) -> Optional[ShiftTemplate]:
    return repo.get_by_code(code, include_deleted)

def list_shift_templates(
    q: Optional[str] = None,
    overnight: Optional[bool] = None,
    ordering: Optional[str] = None,
    include_deleted: bool = False,
) -> QuerySet[ShiftTemplate]:
    return repo.list_shift_templates(q=q, overnight=overnight, ordering=ordering, include_deleted=include_deleted)

def list_all_ordered_by_start_time(include_deleted: bool = False) -> QuerySet[ShiftTemplate]:
    return repo.list_all_ordered_by_start_time(include_deleted)
