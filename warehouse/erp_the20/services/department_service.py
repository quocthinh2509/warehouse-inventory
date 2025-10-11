# -*- coding: utf-8 -*-
"""
Service layer cho Department.
- Chứa validate UNIQUE code (theo lựa chọn A của bạn).
- Repo chỉ thuần DB.
"""
from __future__ import annotations
from typing import Dict, Any

from django.core.exceptions import ValidationError
from erp_the20.models import Department
from erp_the20.repositories import department_repository as repo

def create_department(data: Dict[str, Any]) -> Department:
    # Validate nghiệp vụ: code phải unique
    if Department.objects.filter(code=data["code"]).exists():
        raise ValidationError("Department code must be unique")
    return repo.create(data)

def update_department(dept: Department, data: Dict[str, Any]) -> Department:
    # Validate nghiệp vụ khi đổi code
    if "code" in data and data["code"] != dept.code:
        if Department.objects.filter(code=data["code"]).exists():
            raise ValidationError("Department code must be unique")
    allowed = {"code","name"}
    return repo.save_fields(dept, data, allowed=allowed)

def delete_department(dept: Department) -> None:
    repo.delete(dept)
