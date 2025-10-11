# -*- coding: utf-8 -*-
"""
Selector cho LeaveRequest:
- Chuẩn hoá input (string → list/date)
- Uỷ quyền sang repository
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from django.utils.dateparse import parse_date

from erp_the20.repositories import leave_repository as repo
from erp_the20.models import LeaveRequest
from django.db.models import QuerySet

def _as_int_list(v: Any) -> List[int]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        raw = []
        for x in v:
            if x is None:
                continue
            raw.extend(str(x).split(","))
    else:
        raw = str(v).split(",")
    out = []
    for s in raw:
        s = s.strip()
        if s.isdigit():
            out.append(int(s))
    return out

def filter_leaves(filters: Dict[str, Any], order_by: Optional[List[str]] = None) -> QuerySet[LeaveRequest]:
    norm = {
        "employee_id": _as_int_list(filters.get("employee_id")),
        "status": _as_int_list(filters.get("status")),
        "leave_type": _as_int_list(filters.get("leave_type")),
        "handover_to_employee_id": _as_int_list(filters.get("handover_to") or filters.get("handover_to_employee_id")),
        "decided_by": _as_int_list(filters.get("decided_by")),
        "start_from": parse_date(filters.get("start_from")) if filters.get("start_from") else None,
        "start_to": parse_date(filters.get("start_to")) if filters.get("start_to") else None,
        "end_from": parse_date(filters.get("end_from")) if filters.get("end_from") else None,
        "end_to": parse_date(filters.get("end_to")) if filters.get("end_to") else None,
        "q": (filters.get("q") or "").strip(),
    }
    return repo.filter_leaves(norm, order_by=order_by)

# Quick delegates (API quen thuộc)
get_leave_by_id = repo.get_by_id
get_or_none = repo.get_or_none
list_my_leaves = repo.list_my
list_pending_for_manager = repo.list_pending_for_manager
