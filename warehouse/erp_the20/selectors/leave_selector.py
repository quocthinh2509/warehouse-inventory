# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Dict, Any, List
from datetime import date, datetime

from django.db.models import Q, QuerySet
from django.utils import timezone

from erp_the20.models import LeaveRequest


def get_leave_by_id(leave_id: int) -> LeaveRequest:
    return LeaveRequest.objects.get(id=leave_id)


def get_or_none(leave_id: int) -> Optional[LeaveRequest]:
    return LeaveRequest.objects.filter(id=leave_id).first()


def list_my_leaves(employee_id: int, statuses: Optional[List[str]] = None) -> QuerySet[LeaveRequest]:
    qs = LeaveRequest.objects.filter(employee_id=employee_id)
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by("-created_at")


def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[LeaveRequest]:
    qs = LeaveRequest.objects.filter(status="submitted")
    if date_from:
        qs = qs.filter(start_date__gte=date_from)
    if date_to:
        qs = qs.filter(end_date__lte=date_to)
    return qs.order_by("start_date", "employee_id")


# ----------- helpers for filter ----------
def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        out = []
        for x in v:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.extend([t for t in s.split(",") if t != ""])
        return out
    s = str(v).strip()
    if not s:
        return []
    return [t for t in s.split(",") if t != ""]


def filter_leaves(filters: Dict[str, Any], order_by: Optional[List[str]] = None) -> QuerySet[LeaveRequest]:
    """
    Hỗ trợ các key filters (tuỳ chọn):
      employee_id          : 1 hoặc "1,2"
      status               : "draft,submitted,approved,rejected,cancelled"
      start_from           : "YYYY-MM-DD"
      start_to             : "YYYY-MM-DD"
      end_from             : "YYYY-MM-DD"
      end_to               : "YYYY-MM-DD"
      decided_by           : 1001 hoặc "1001,1002"
      q                    : tìm trong reason (icontains)
    """
    qs = LeaveRequest.objects.all()

    emp_ids = _as_list(filters.get("employee_id"))
    if emp_ids:
        qs = qs.filter(employee_id__in=[int(x) for x in emp_ids if x.isdigit()])

    statuses = _as_list(filters.get("status"))
    if statuses:
        qs = qs.filter(status__in=statuses)

    decided_bys = _as_list(filters.get("decided_by"))
    if decided_bys:
        qs = qs.filter(decided_by__in=[int(x) for x in decided_bys if x.isdigit()])

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
