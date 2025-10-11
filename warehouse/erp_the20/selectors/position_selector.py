# -*- coding: utf-8 -*-
"""
Selector layer cho Position: chỉ ủy quyền sang repo.
"""
from __future__ import annotations
from typing import Optional
from django.db.models import QuerySet

from erp_the20.models import Position
from erp_the20.repositories import position_repository as repo

def get_position_by_id(pos_id: int) -> Optional[Position]:
    return repo.get_by_id(pos_id)

def get_position_by_code(code: str) -> Optional[Position]:
    return repo.get_by_code(code)

def list_all_positions() -> QuerySet[Position]:
    return repo.list_all()
