# -*- coding: utf-8 -*-
"""
Repository layer cho Department (thuần DB).
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.db.models import QuerySet

from erp_the20.models import Department


# ============== Queries ==============
def get_by_id(dept_id: int) -> Optional[Department]:
    return Department.objects.filter(id=dept_id).first()

def get_by_code(code: str) -> Optional[Department]:
    return Department.objects.filter(code=code).first()

def list_all() -> QuerySet[Department]:
    return Department.objects.all().order_by("name")


# ============== Mutations ==============
@transaction.atomic
def create(data: Dict[str, Any]) -> Department:
    return Department.objects.create(**data)

@transaction.atomic
def save_fields(obj: Department, patch: Dict[str, Any], allowed: Optional[set] = None) -> Department:
    fields: List[str] = []
    for k, v in patch.items():
        if (allowed is None) or (k in allowed):
            setattr(obj, k, v); fields.append(k)
    if fields:
        obj.save(update_fields=fields + ["updated_at"] if "updated_at" in [f.name for f in obj._meta.fields] else fields)
    return obj

@transaction.atomic
def delete(obj: Department) -> None:
    obj.delete()
