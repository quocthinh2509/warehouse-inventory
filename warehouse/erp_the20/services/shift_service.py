# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any

from erp_the20.models import ShiftTemplate
from erp_the20.repositories import shift_repository as repo

# ============================
# Service (business rules, if any)
# ============================
def create_shift_template(data: Dict[str, Any]) -> ShiftTemplate:
    """
    Nghiệp vụ tạo mới (nếu cần quy tắc riêng thì kiểm tra ở đây).
    Mặc định: ủy quyền repo.create (thuần DB).
    """
    # Ví dụ rule: code/giờ hợp lệ... (nếu cần)
    return repo.create(data)

def update_shift_template_versioned(instance: ShiftTemplate, data: Dict[str, Any]) -> ShiftTemplate:
    """
    Nghiệp vụ update có versioning (giữ nguyên flow cũ).
    Ủy quyền repo.update_versioned để đảm bảo tính nguyên tử.
    """
    return repo.update_versioned(instance, data)

def soft_delete_shift_template(instance: ShiftTemplate) -> None:
    """
    Nghiệp vụ xóa mềm. Ủy quyền repo.soft_delete (thuần DB).
    """
    repo.soft_delete(instance)
