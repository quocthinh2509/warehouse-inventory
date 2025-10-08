# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from decimal import Decimal

from django.db.models import Q, QuerySet
from django.utils import timezone

from erp_the20.models import Attendance

# ==== helpers ====
def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        out: List[str] = []
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

def _to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1","true","t","yes","y"):
        return True
    if s in ("0","false","f","no","n"):
        return False
    return None

def _to_date(v: Any) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except Exception:
        return None

def _to_datetime(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if timezone.is_aware(v) else timezone.make_aware(v, timezone.get_current_timezone())
    try:
        dt = datetime.fromisoformat(str(v))
        return dt if timezone.is_aware(dt) else timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        pass
    d = _to_date(v)
    if d:
        return timezone.make_aware(datetime(d.year, d.month, d.day, 0, 0, 0), timezone.get_current_timezone())
    return None

def _to_decimal(v: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(v))
    except Exception:
        return None

# ==== quick lists ====
def list_my_pending(employee_id: int) -> QuerySet[Attendance]:
    return (
        Attendance.objects
        .filter(deleted_at__isnull=True, employee_id=employee_id, status=Attendance.Status.PENDING)
        .select_related("shift_template")
        .order_by("date", "shift_template_id")
    )

def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[Attendance]:
    qs = Attendance.objects.filter(deleted_at__isnull=True, status=Attendance.Status.PENDING)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs.select_related("shift_template").order_by("date", "employee_id")

def get_by_id(attendance_id: int) -> Attendance:
    return Attendance.objects.select_related("shift_template").get(id=attendance_id)

def get_or_none(attendance_id: int) -> Optional[Attendance]:
    return Attendance.objects.filter(id=attendance_id).select_related("shift_template").first()

# ==== powerful filter ====
def filter_attendances(filters: Dict[str, Any], include_deleted: bool = False,
                       order_by: Optional[List[str]] = None) -> QuerySet[Attendance]:
    """
    Hỗ trợ:
      - employee_id, status, work_mode, source (IN / equals)
      - khoảng ngày/giờ: date/ts_in/ts_out
      - template_code, template_name_icontains
      - bonus_min/max
      - q: tìm trên code/name template & reject_reason
    """
    base = Attendance.objects.select_related("shift_template")
    if not include_deleted:
        base = base.filter(deleted_at__isnull=True)

    # equals / IN
    employee_ids = _as_list(filters.get("employee_id"))
    if employee_ids:
        base = base.filter(employee_id__in=[int(x) for x in employee_ids if str(x).isdigit()])

    statuses = _as_list(filters.get("status"))
    if statuses:
        # nhận CSV "0,1" hoặc label "pending,approved"
        ints: List[int] = []
        for s in statuses:
            if str(s).isdigit():
                ints.append(int(s))
            else:
                mapping = {lbl: val for val, lbl in Attendance.Status.choices}
                rev = {lbl.lower(): val for val, lbl in mapping.items()}
                if s.lower() in rev:
                    ints.append(rev[s.lower()])
        if ints:
            base = base.filter(status__in=ints)

    work_modes = _as_list(filters.get("work_mode"))
    if work_modes:
        ints = [int(x) for x in work_modes if str(x).isdigit()]
        base = base.filter(work_mode__in=ints)

    sources = _as_list(filters.get("source"))
    if sources:
        ints = [int(x) for x in sources if str(x).isdigit()]
        base = base.filter(source__in=ints)

    template_codes = _as_list(filters.get("template_code"))
    if template_codes:
        base = base.filter(shift_template__code__in=template_codes)

    approved_bys = _as_list(filters.get("approved_by"))
    if approved_bys:
        base = base.filter(approved_by__in=[int(x) for x in approved_bys if str(x).isdigit()])

    requested_bys = _as_list(filters.get("requested_by"))
    if requested_bys:
        base = base.filter(requested_by__in=[int(x) for x in requested_bys if str(x).isdigit()])

    # booleans
    is_valid = _to_bool(filters.get("is_valid"))
    if is_valid is not None:
        base = base.filter(is_valid=is_valid)

    # dates / datetimes
    d_from = _to_date(filters.get("date_from") or filters.get("shift_date_from"))
    if d_from:
        base = base.filter(date__gte=d_from)
    d_to = _to_date(filters.get("date_to") or filters.get("shift_date_to"))
    if d_to:
        base = base.filter(date__lte=d_to)

    ti_from = _to_datetime(filters.get("ts_in_from"))
    if ti_from:
        base = base.filter(ts_in__gte=ti_from)
    ti_to = _to_datetime(filters.get("ts_in_to"))
    if ti_to:
        base = base.filter(ts_in__lte=ti_to)

    to_from = _to_datetime(filters.get("ts_out_from"))
    if to_from:
        base = base.filter(ts_out__gte=to_from)
    to_to = _to_datetime(filters.get("ts_out_to"))
    if to_to:
        base = base.filter(ts_out__lte=to_to)

    # numeric range
    bmin = _to_decimal(filters.get("bonus_min"))
    if bmin is not None:
        base = base.filter(bonus__gte=bmin)
    bmax = _to_decimal(filters.get("bonus_max"))
    if bmax is not None:
        base = base.filter(bonus__lte=bmax)

    # text search
    name_icontains = filters.get("template_name_icontains") or filters.get("template_name")
    if name_icontains:
        base = base.filter(shift_template__name__icontains=str(name_icontains).strip())

    q_text = (filters.get("q") or "").strip()
    if q_text:
        base = base.filter(
            Q(shift_template__name__icontains=q_text) |
            Q(shift_template__code__icontains=q_text) |
            Q(reject_reason__icontains=q_text)
        )

    # order
    if order_by:
        base = base.order_by(*order_by)
    else:
        base = base.order_by("-date", "employee_id")
    return base
