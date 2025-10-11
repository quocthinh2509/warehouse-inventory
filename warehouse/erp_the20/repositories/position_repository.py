# -*- coding: utf-8 -*-
"""
Repository layer cho Position (thuần DB).
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.db.models import QuerySet

from erp_the20.models import Position

# ============== Queries ==============
def get_by_id(pos_id: int) -> Optional[Position]:
    return Position.objects.filter(id=pos_id).first()

def get_by_code(code: str) -> Optional[Position]:
    return Position.objects.filter(code=code).first()

def list_all() -> QuerySet[Position]:
    return Position.objects.all().select_related("department").order_by("name")

# ============== Mutations ==============
@transaction.atomic
def create(data: Dict[str, Any]) -> Position:
    return Position.objects.create(**data)

@transaction.atomic
def save_fields(obj: Position, patch: Dict[str, Any], allowed: Optional[set] = None) -> Position:
    fields: List[str] = []
    for k, v in patch.items():
        if (allowed is None) or (k in allowed):
            setattr(obj, k, v); fields.append(k)
    if fields:
        obj.save(update_fields=fields + ["updated_at"] if "updated_at" in [f.name for f in obj._meta.fields] else fields)
    return obj

@transaction.atomic
def delete(obj: Position) -> None:
    obj.delete()
