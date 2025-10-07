# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional, Iterable, Dict, Any, List
from datetime import datetime, date
from django.utils import timezone
from django.db.models import QuerySet, Q
from erp_the20.models import AttendanceSummaryV2

# ===== Helper parsers =====

def _as_list(v: Any) -> List[str]:
    """
    Chuẩn hoá giá trị filter thành list.
    - None -> []
    - "a,b,c" -> ["a","b","c"]
    - ["a","b"] -> ["a","b"]
    - 1 -> ["1"]
    """
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
        # hỗ trợ "YYYY-MM-DD"
        return datetime.fromisoformat(str(v)[:10]).date()
    except Exception:
        return None

def _to_datetime(v: Any) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        # nếu client đã gửi aware thì giữ nguyên, nếu naive thì make_aware
        return v if timezone.is_aware(v) else timezone.make_aware(v, timezone.get_current_timezone())

    # Ưu tiên ISO 8601
    try:
        dt = datetime.fromisoformat(str(v))
        return dt if timezone.is_aware(dt) else timezone.make_aware(dt, timezone.get_current_timezone())
    except Exception:
        pass

    # Fallback: chỉ có date -> 00:00 local
    d = _to_date(v)
    if d:
        return timezone.make_aware(datetime(d.year, d.month, d.day, 0, 0, 0), timezone.get_current_timezone())
    return None

def _to_decimal(v: Any):
    try:
        from decimal import Decimal
        return Decimal(str(v))
    except Exception:
        return None

# ======= Quick lists =======

def list_my_pending(employee_id: int) -> QuerySet[AttendanceSummaryV2]:
    return (
        AttendanceSummaryV2.objects
        .filter(employee_id=employee_id, status=AttendanceSummaryV2.Status.PENDING)
        .select_related("shift_instance", "shift_instance__template")
        .order_by("shift_instance__date", "shift_instance_id")
    )

def list_pending_for_manager(date_from: Optional[str] = None, date_to: Optional[str] = None) -> QuerySet[AttendanceSummaryV2]:
    qs = AttendanceSummaryV2.objects.filter(status=AttendanceSummaryV2.Status.PENDING)
    if date_from:
        qs = qs.filter(shift_instance__date__gte=date_from)
    if date_to:
        qs = qs.filter(shift_instance__date__lte=date_to)
    return qs.select_related("shift_instance", "shift_instance__template").order_by("shift_instance__date", "employee_id")

def get_summary_by_id(summary_id: int) -> AttendanceSummaryV2:
    return AttendanceSummaryV2.objects.select_related("shift_instance", "shift_instance__template").get(id=summary_id)

def get_or_none(summary_id: int) -> Optional[AttendanceSummaryV2]:
    return AttendanceSummaryV2.objects.filter(id=summary_id).select_related("shift_instance", "shift_instance__template").first()

# ======= Powerful filter =======

def filter_summaries(
    filters: Dict[str, Any],
    order_by: Optional[List[str]] = None
) -> QuerySet[AttendanceSummaryV2]:
    """
    Lọc đa trường cho AttendanceSummaryV2.
    Hỗ trợ:
      - Bằng / IN cho các trường enum hoặc id
      - Khoảng ngày/giờ cho date, ts_in, ts_out
      - Tìm kiếm tự do (q) trên template code/name & reject_reason
      - Nhiều giá trị trong 1 trường: "a,b" hoặc ["a","b"]

    Các key filters được hỗ trợ (tuỳ chọn):
      employee_id           : int | "1,2,3"
      status                : one or many of ["pending","approved","rejected","canceled"]
      is_valid              : bool ("true/false/1/0")
      work_mode             : "onsite,remote"
      source                : "web,mobile,lark,googleforms"
      shift_date_from       : "YYYY-MM-DD"
      shift_date_to         : "YYYY-MM-DD"
      ts_in_from            : ISO datetime | date
      ts_in_to              : ISO datetime | date
      ts_out_from           : ISO datetime | date
      ts_out_to             : ISO datetime | date
      template_code         : exact hoặc nhiều giá trị
      template_name_icontains : chuỗi tìm kiếm (case-insensitive)
      approved_by           : user id or list
      requested_by          : employee id or list
      bonus_min             : decimal
      bonus_max             : decimal
      q                     : free text search (template code/name, reject_reason)

    order_by: ví dụ ["-shift_instance__date", "employee_id"]
    """
    qs = AttendanceSummaryV2.objects.select_related("shift_instance", "shift_instance__template")

    # === equals / in ===
    employee_ids = _as_list(filters.get("employee_id"))
    if employee_ids:
        qs = qs.filter(employee_id__in=[int(x) for x in employee_ids if x.isdigit()])

    statuses = _as_list(filters.get("status"))
    if statuses:
        qs = qs.filter(status__in=statuses)

    work_modes = _as_list(filters.get("work_mode"))
    if work_modes:
        qs = qs.filter(work_mode__in=work_modes)

    sources = _as_list(filters.get("source"))
    if sources:
        qs = qs.filter(source__in=sources)

    approved_bys = _as_list(filters.get("approved_by"))
    if approved_bys:
        qs = qs.filter(approved_by__in=[int(x) for x in approved_bys if x.isdigit()])

    requested_bys = _as_list(filters.get("requested_by"))
    if requested_bys:
        qs = qs.filter(requested_by__in=[int(x) for x in requested_bys if x.isdigit()])

    template_codes = _as_list(filters.get("template_code"))
    if template_codes:
        qs = qs.filter(shift_instance__template__code__in=template_codes)

    # === booleans ===
    is_valid = _to_bool(filters.get("is_valid"))
    if is_valid is not None:
        qs = qs.filter(is_valid=is_valid)

    # === dates / datetimes ===
    d_from = _to_date(filters.get("shift_date_from"))
    if d_from:
        qs = qs.filter(shift_instance__date__gte=d_from)

    d_to = _to_date(filters.get("shift_date_to"))
    if d_to:
        qs = qs.filter(shift_instance__date__lte=d_to)

    ti_from = _to_datetime(filters.get("ts_in_from"))
    if ti_from:
        qs = qs.filter(ts_in__gte=ti_from)
    ti_to = _to_datetime(filters.get("ts_in_to"))
    if ti_to:
        qs = qs.filter(ts_in__lte=ti_to)

    to_from = _to_datetime(filters.get("ts_out_from"))
    if to_from:
        qs = qs.filter(ts_out__gte=to_from)
    to_to = _to_datetime(filters.get("ts_out_to"))
    if to_to:
        qs = qs.filter(ts_out__lte=to_to)

    # === numeric range (bonus) ===
    bmin = _to_decimal(filters.get("bonus_min"))
    if bmin is not None:
        qs = qs.filter(bonus__gte=bmin)
    bmax = _to_decimal(filters.get("bonus_max"))
    if bmax is not None:
        qs = qs.filter(bonus__lte=bmax)

    # === text search ===
    name_icontains = filters.get("template_name_icontains")
    if name_icontains:
        qs = qs.filter(shift_instance__template__name__icontains=str(name_icontains).strip())

    q_text = (filters.get("q") or "").strip()
    if q_text:
        qs = qs.filter(
            Q(shift_instance__template__name__icontains=q_text) |
            Q(shift_instance__template__code__icontains=q_text) |
            Q(reject_reason__icontains=q_text)
        )

    # === order ===
    if order_by:
        qs = qs.order_by(*order_by)
    else:
        qs = qs.order_by("shift_instance__date", "employee_id")

    return qs
