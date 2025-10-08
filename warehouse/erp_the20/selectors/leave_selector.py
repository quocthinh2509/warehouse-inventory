# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict, Any, List
from django.db.models import QuerySet
from erp_the20.models import LeaveRequest


def get_leave_by_id(leave_id: int) -> LeaveRequest:
    return LeaveRequest.objects.get(id=leave_id)


def get_or_none(leave_id: int) -> Optional[LeaveRequest]:
    return LeaveRequest.objects.filter(id=leave_id).first()


def list_my_leaves(employee_id: int, statuses: Optional[List[int]] = None) -> QuerySet[LeaveRequest]:
    qs = LeaveRequest.objects.filter(employee_id=employee_id)
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by("-created_at")


def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[LeaveRequest]:
    qs = LeaveRequest.objects.filter(status=LeaveRequest.Status.SUBMITTED)
    if date_from:
        qs = qs.filter(start_date__gte=date_from)
    if date_to:
        qs = qs.filter(end_date__lte=date_to)
    return qs.order_by("start_date", "employee_id")


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
    """
    Hỗ trợ:
      employee_id : 204 hoặc "204,205"
      status      : 0,1,2,3 (hoặc "0,1")
      leave_type  : 0..8   (hoặc "0,3,4")
      decided_by  : 1001 hoặc "1001,1002"
      start_from / start_to / end_from / end_to (YYYY-MM-DD)
      q           : tìm theo reason (icontains)
    """
    qs = LeaveRequest.objects.all()

    emp_ids = _as_int_list(filters.get("employee_id"))
    if emp_ids:
        qs = qs.filter(employee_id__in=emp_ids)

    statuses = _as_int_list(filters.get("status"))
    if statuses:
        qs = qs.filter(status__in=statuses)

    leave_types = _as_int_list(filters.get("leave_type"))
    if leave_types:
        qs = qs.filter(leave_type__in=leave_types)

    decided_bys = _as_int_list(filters.get("decided_by"))
    if decided_bys:
        qs = qs.filter(decided_by__in=decided_bys)

    s_from = filters.get("start_from")
    if s_from:
        qs = qs.filter(start_date__gte=s_from)

    s_to = filters.get("start_to")
    if s_to:
        qs = qs.filter(start_date__lte=s_to)

    e_from = filters.get("end_from")
    if e_from:
        qs = qs.filter(end_date__gte=e_from)

    e_to = filters.get("end_to")
    if e_to:
        qs = qs.filter(end_date__lte=e_to)

    qtext = (filters.get("q") or "").strip()
    if qtext:
        qs = qs.filter(reason__icontains=qtext)

    if order_by:
        qs = qs.order_by(*order_by)
    else:
        qs = qs.order_by("-created_at")

    return qs
