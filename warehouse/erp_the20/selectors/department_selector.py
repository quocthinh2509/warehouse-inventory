# -*- coding: utf-8 -*-
"""
Selector layer cho Department: chỉ ủy quyền sang repo.
"""
from __future__ import annotations
from typing import Optional
from django.db.models import QuerySet

from erp_the20.models import Department
from erp_the20.repositories import department_repository as repo

def get_department_by_id(dept_id: int) -> Optional[Department]:
    return repo.get_by_id(dept_id)

def get_department_by_code(code: str) -> Optional[Department]:
    return repo.get_by_code(code)

def list_all_departments() -> QuerySet[Department]:
    return repo.list_all()
