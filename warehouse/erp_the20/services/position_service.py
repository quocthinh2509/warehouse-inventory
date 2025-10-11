# -*- coding: utf-8 -*-
"""
Service layer cho Position.
- Chứa validate UNIQUE code (theo lựa chọn A của bạn).
- Repo chỉ thuần DB.
"""
from __future__ import annotations
from typing import Dict, Any

from django.core.exceptions import ValidationError
from erp_the20.models import Position
from erp_the20.repositories import position_repository as repo

def create_position(data: Dict[str, Any]) -> Position:
    # Validate nghiệp vụ: code phải unique
    if Position.objects.filter(code=data["code"]).exists():
        raise ValidationError("Position code must be unique")
    return repo.create(data)

def update_position(pos: Position, data: Dict[str, Any]) -> Position:
    # Validate nghiệp vụ khi đổi code
    if "code" in data and data["code"] != pos.code:
        if Position.objects.filter(code=data["code"]).exclude(id=pos.id).exists():
            raise ValidationError("Position code must be unique")
    allowed = {"code","name","default_department","department"}
    return repo.save_fields(pos, data, allowed=allowed)

def delete_position(pos: Position) -> None:
    repo.delete(pos)
